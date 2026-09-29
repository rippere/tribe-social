"""
export_cortex.py — cortex mesh + activity export for the web cortex view.

TRIBE v2 predicts on fsaverage5 (20484 vertices, LH 0-10241, RH 10242-20483).
fsaverage5 is too coarse to look like a brain at hero size, so the mesh is the
fsaverage6 pial surface (81924 vertices). The two are nested icosahedra: the
first 10242 vertices of each fsaverage6 hemisphere ARE the fsaverage5 vertices,
so every TRIBE value lands on its own vertex and the in-between vertices blend
their three nearest fsaverage5 neighbours on the sphere. No atlas resampling.

Outputs (default → ../apps/web/public/cortex/):
  cortex.glb      fsaverage6 pial, both hemispheres, Y-up, unit-scaled.
                  Custom vertex attributes: _SULC (sulcal depth, shading),
                  _FSA5_IDX (3 fsaverage5 indices), _FSA5_W (3 blend weights).
  activity.bin    uint8 [T, 20484], 128 = 0, one frame per TRIBE second.
  activity.json   {frames, vertices, hz, source, label, note}

Usage:
  # illustrative activity (region-scripted, NOT model output)
  uv run --no-project --with nilearn --with scipy python export_cortex.py

  # real TRIBE output from a scoring run
  uv run --no-project --with nilearn --with scipy python export_cortex.py \\
      --preds reels/batch/ali_005_preds.npy --skip-mesh
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.spatial import cKDTree

N5 = 10242    # fsaverage5 vertices per hemisphere
N_VERTS = 2 * N5
OUT_DIR = Path(__file__).resolve().parent.parent / "apps" / "web" / "public" / "cortex"


# ── mesh ──────────────────────────────────────────────────────────────────────

def _load_hemi(fs6, fs5, hemi: str):
    from nilearn import surface

    pial = surface.load_surf_mesh(getattr(fs6, f"pial_{hemi}"))
    sphere6 = surface.load_surf_mesh(getattr(fs6, f"sphere_{hemi}")).coordinates
    sphere5 = surface.load_surf_mesh(getattr(fs5, f"sphere_{hemi}")).coordinates
    sulc = surface.load_surf_data(getattr(fs6, f"sulc_{hemi}")).astype(np.float32)

    if not np.allclose(sphere6[:N5], sphere5):
        raise RuntimeError("fsaverage6 does not nest fsaverage5 — mesh mapping would be wrong")

    # 3 nearest fsaverage5 vertices on the sphere, inverse-distance weights.
    # Vertices 0..10241 hit themselves at distance 0 → weight 1 on their own value.
    dist, idx = cKDTree(sphere5).query(sphere6, k=3)
    exact = dist[:, 0] < 1e-6
    w = 1.0 / np.maximum(dist, 1e-6)
    w[exact] = [1.0, 0.0, 0.0]
    w /= w.sum(axis=1, keepdims=True)

    offset = 0 if hemi == "left" else N5
    return (
        pial.coordinates.astype(np.float32),
        pial.faces.astype(np.uint32),
        sulc,
        (idx + offset).astype(np.uint16),
        w.astype(np.float32),
    )


def build_mesh():
    from nilearn import datasets

    fs6 = datasets.fetch_surf_fsaverage("fsaverage6")
    fs5 = datasets.fetch_surf_fsaverage("fsaverage5")
    lh = _load_hemi(fs6, fs5, "left")
    rh = _load_hemi(fs6, fs5, "right")

    pos = np.vstack([lh[0], rh[0]])
    faces = np.vstack([lh[1], rh[1] + len(lh[0])])
    sulc = np.concatenate([lh[2], rh[2]])
    idx = np.vstack([lh[3], rh[3]])
    w = np.vstack([lh[4], rh[4]])

    # RAS (mm) → three.js Y-up: x = right, y = superior, z = posterior.
    pos = pos[:, [0, 2, 1]] * np.array([1, 1, -1], dtype=np.float32)
    pos -= (pos.max(axis=0) + pos.min(axis=0)) / 2
    pos /= np.abs(pos).max()

    # sulc: positive = deep (sulcus). Normalise to 0 (gyrus crown) .. 1 (fundus).
    lo, hi = np.percentile(sulc, [2, 98])
    sulc = np.clip((sulc - lo) / (hi - lo), 0, 1).astype(np.float32)
    return pos.astype(np.float32), faces, sulc, idx, w


def write_glb(path: Path, pos, faces, sulc, idx, w) -> None:
    """Minimal single-mesh glTF 2.0 binary with custom vertex attributes."""
    chunks: list[bytes] = []
    views, accessors = [], []

    def add(arr: np.ndarray, comp: int, typ: str, target: int | None, minmax=False):
        data = np.ascontiguousarray(arr).tobytes()
        offset = sum(len(c) for c in chunks)
        chunks.append(data + b"\0" * (-len(data) % 4))
        view = {"buffer": 0, "byteOffset": offset, "byteLength": len(data)}
        if target:
            view["target"] = target
        views.append(view)
        acc = {"bufferView": len(views) - 1, "componentType": comp,
               "count": len(arr), "type": typ}
        if minmax:
            acc["min"] = arr.min(axis=0).tolist()
            acc["max"] = arr.max(axis=0).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    FLOAT, USHORT, UINT = 5126, 5123, 5125
    ARRAY, ELEMENT = 34962, 34963
    attrs = {
        "POSITION": add(pos, FLOAT, "VEC3", ARRAY, minmax=True),
        "_SULC": add(sulc, FLOAT, "SCALAR", ARRAY),
        "_FSA5_IDX": add(idx, USHORT, "VEC3", ARRAY),
        "_FSA5_W": add(w, FLOAT, "VEC3", ARRAY),
    }
    indices = add(faces.reshape(-1), UINT, "SCALAR", ELEMENT)

    binary = b"".join(chunks)
    gltf = {
        "asset": {"version": "2.0", "generator": "tribe-social export_cortex.py"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "cortex"}],
        "meshes": [{"name": "fsaverage6_pial",
                    "primitives": [{"attributes": attrs, "indices": indices}]}],
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": views,
        "accessors": accessors,
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(binary)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(binary), 0x004E4942) + binary)


# ── activity ──────────────────────────────────────────────────────────────────

def _smooth_on_fs5(values: np.ndarray, iters: int = 6) -> np.ndarray:
    """Laplacian smoothing over fsaverage5 mesh adjacency (per hemisphere)."""
    from nilearn import datasets, surface

    faces = surface.load_surf_mesh(datasets.fetch_surf_fsaverage("fsaverage5").pial_left).faces
    e = np.vstack([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    a = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(N5, N5))
    a = ((a + a.T) > 0).astype(np.float32)
    a = sparse.diags(1.0 / np.asarray(a.sum(axis=1)).ravel()) @ a
    out = values.copy()
    for h in (slice(0, N5), slice(N5, N_VERTS)):
        v = out[:, h].T
        for _ in range(iters):
            v = 0.5 * v + 0.5 * (a @ v)
        out[:, h] = v.T
    return out


def illustrative_activity(seconds: int = 30, seed: int = 7) -> np.ndarray:
    """
    Region-scripted stand-in for a TRIBE prediction. Regions come from the
    Destrieux atlas on fsaverage5 (real anatomy), timelines are invented.
    It exists so the renderer can be built before real preds are available;
    the web view labels it as illustrative.
    """
    from nilearn import datasets

    d = datasets.fetch_atlas_surf_destrieux()
    names = [n.decode() if isinstance(n, bytes) else n for n in d.labels]
    lab = np.concatenate([d.map_left, d.map_right])
    left = np.arange(N_VERTS) < N5

    def region(*keys: str, lh_only: bool = False) -> np.ndarray:
        ids = [i for i, n in enumerate(names) if any(k in n for k in keys)]
        m = np.isin(lab, ids)
        return (m & left) if lh_only else m

    t = np.arange(seconds, dtype=np.float32)
    rng = np.random.default_rng(seed)

    def bumps(onsets, width=2.5):
        return sum(np.exp(-0.5 * ((t - o) / width) ** 2) for o in onsets)

    speech = ((t > 3) & (t < 13)) | ((t > 17) & (t < 27))
    speech_env = np.convolve(speech.astype(np.float32), np.ones(3) / 3, mode="same")
    cuts = [0, 6, 11, 15, 21, 26]
    tracks = [
        # visual cortex: always on, spikes at scene cuts
        (region("Pole_occipital", "S_calcarine", "G_cuneus", "G_occipital_sup",
                "G_and_S_occipital_inf", "G_oc-temp_lat-fusifor"),
         0.55 + 0.45 * bumps(cuts, 1.2)),
        # lateral occipito-temporal (MT+ neighbourhood): motion beats
        (region("G_occipital_middle", "S_occipital_middle", "G_temporal_inf"),
         0.25 + 0.6 * bumps([6, 7, 21, 22], 1.5)),
        # auditory: superior temporal, follows speech
        (region("G_temp_sup-G_T_transv", "S_temporal_transverse", "G_temp_sup-Plan_tempo",
                "G_temp_sup-Lateral", "S_temporal_sup"),
         0.15 + 0.85 * speech_env),
        # language: left IFG + middle temporal, lags speech
        (region("G_front_inf-Opercular", "G_front_inf-Triangul", "S_front_inf",
                "G_temporal_middle", lh_only=True),
         0.1 + 0.7 * np.roll(speech_env, 2)),
        # dorsal attention: orienting at onset and mid-clip reset
        (region("S_precentral-inf-part", "S_intrapariet_and_P_trans", "G_parietal_sup"),
         0.1 + 0.5 * bumps([1, 15], 2.0)),
    ]

    act = np.zeros((seconds, N_VERTS), dtype=np.float32)
    for mask, tl in tracks:
        act[:, mask] += tl[:, None].astype(np.float32)
    act += 0.08 * rng.standard_normal(act.shape).astype(np.float32)
    act = _smooth_on_fs5(act)
    # Hemodynamic lag: TRIBE predicts BOLD, which trails the stimulus by seconds.
    act = np.roll(act, 2, axis=0)
    act[:2] *= np.array([0.3, 0.8], dtype=np.float32)[:, None]
    return act


def quantize(act: np.ndarray) -> np.ndarray:
    """Signed → uint8 around 128, scaled by the robust max |value|."""
    scale = float(np.percentile(np.abs(act), 99.5)) or 1.0
    return np.clip(np.round(128 + 127 * act / scale), 0, 255).astype(np.uint8)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--preds", type=Path, help="TRIBE *_preds.npy [T, 20484]; omit for illustrative activity")
    p.add_argument("--label", help="Display label for the clip (defaults to the preds file stem)")
    p.add_argument("--out", type=Path, default=OUT_DIR)
    p.add_argument("--skip-mesh", action="store_true", help="Only rewrite activity.*")
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    if not args.skip_mesh:
        pos, faces, sulc, idx, w = build_mesh()
        write_glb(args.out / "cortex.glb", pos, faces, sulc, idx, w)
        print(f"cortex.glb  {len(pos)} verts  {len(faces)} faces  "
              f"{(args.out / 'cortex.glb').stat().st_size / 1e6:.1f} MB")

    if args.preds:
        act = np.load(args.preds).astype(np.float32)
        if act.ndim != 2 or act.shape[1] != N_VERTS:
            raise ValueError(f"expected [T, {N_VERTS}] preds, got {act.shape}")
        source, label = "tribe", args.label or args.preds.stem.replace("_preds", "")
        note = "TRIBE v2 predicted cortical response (fsaverage5), 1 frame per second."
    else:
        act = illustrative_activity()
        source, label = "illustrative", args.label or "Illustrative sequence"
        note = "Region-scripted placeholder on real anatomy. Not TRIBE output."

    q = quantize(act)
    q.tofile(args.out / "activity.bin")
    meta = {"frames": int(q.shape[0]), "vertices": N_VERTS, "hz": 1,
            "source": source, "label": label, "note": note}
    (args.out / "activity.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(f"activity.bin  {q.shape[0]} frames  source={source}")


if __name__ == "__main__":
    main()
