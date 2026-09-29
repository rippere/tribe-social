# Cortex view — state of play (2026-09-29)

Handoff for anyone picking up the web experience. Read this before touching the
landing page, the processing page, or anything under `components/brain/`.

## The direction (decided with Ben, 2026-09-29)

- **Dark theme, x.ai/bot layout.** `business/lanes/design-ref/DESIGN-SPEC.md`
  (git-ignored) maps the x.ai/bot page part by part. Keep its structure, spacing,
  type scale and pill/window language, but on a dark background, not the white
  tokens in that spec. The palette will be refined as the page is built.
- **Scorer is the hero.** The landing hero is the real scorer app window (sidebar of
  scored clips, main pane with video + per-second timeline), not a 3D centerpiece.
- **Brain is the mascot.** It walks the visitor through the process (upload, encode,
  extract, read) in the sections below the hero.
- **Full cortex demonstration on the processing page.** The 3D model with the
  cortex lighting up lives on the processing/results flow, not the landing page.
  That's what `/cortex` prototypes.
- **No orb.** No glowing blob, no painted-on glow over a photo-scanned brain,
  no white-matter tracts, deep structures or cut sections. TRIBE v2's released
  model predicts only the cortical surface (fsaverage5, 20,484 vertices), so
  that's all we render. See `business/canon/DEFENSIBILITY.md` for why the orb
  story does not survive contact with the evidence.

## What exists now

| Piece | Path | What it does |
|---|---|---|
| Exporter | `research/export_cortex.py` | Builds `cortex.glb` (fsaverage6 pial, both hemispheres) + `activity.bin/json`. `--preds X_preds.npy` swaps in real TRIBE output. |
| Assets | `apps/web/public/cortex/` | `cortex.glb` 4.8 MB, `activity.bin` (uint8 `[T, 20484]`, 128 = 0), `activity.json` (frames, hz, source, label, note). |
| Mesh + shader | `apps/web/components/brain/CortexBrain.tsx` | Loads the GLB, uploads one TRIBE frame per render tick into a 144×144 float texture, shades gyri/sulci + a cyan activation ramp. Exports `useActivity`, `CortexClock`. |
| Scene | `apps/web/components/brain/CortexScene.tsx` | Canvas, orbit controls, named camera views (left/right/top/front/back). |
| Viewer UI | `apps/web/components/brain/CortexViewer.tsx` | Play/pause, time scrubber, threshold slider, view pills, source badge. |
| Route | `apps/web/app/cortex/page.tsx` | `/cortex` preview. The processing page will embed `CortexViewer` (or a slimmer variant). |
| Old placeholder | `components/brain/BrainHero.tsx`, `BrainScene.tsx` | Still on `/`. Retire it when the scorer-as-hero landing lands. |

Rendered output (SwiftShader, 1400×860):

![left](cortex/cortex-left.png)
![right](cortex/cortex-right.png)
![top](cortex/cortex-top.png)

## Why it's accurate

- **Real mesh.** fsaverage6 pial surface from nilearn, the same template family
  TRIBE predicts on. It is not a photo-scanned brain, so the folds match TRIBE's
  vertices.
- **No resampling guesswork.** fsaverage meshes are nested icosahedra: the first
  10,242 vertices of each fsaverage6 hemisphere are exactly the fsaverage5
  vertices. The exporter asserts this and it holds to 0.0 difference. Each of
  those vertices shows its own TRIBE value. The in-between vertices blend their
  3 nearest fsaverage5 neighbours on the sphere, weighted by inverse distance.
- **Time is real.** TRIBE outputs one frame per second. The viewer interpolates
  linearly between seconds and plays at 1×.
- **Honest labelling.** `activity.json.source` is `illustrative` or `tribe`.
  The viewer shows an amber "Illustrative — not model output" badge until real
  preds are exported.

## What's illustrative right now

The current `activity.bin` is a **region-scripted placeholder**:
- The regions are real (Destrieux atlas on fsaverage5): visual, MT+ neighbourhood,
  auditory, left-lateralised language, dorsal attention.
- The timelines are invented: cuts, speech on/off, a 2 s haemodynamic lag.
- Its only job is to let the renderer be built before real preds exist. Do not
  screenshot it for marketing.

## Open items / gates

1. **Real preds (Ben, in progress).** No `*_preds.npy` exists locally; they were
   left on RunPod. Once one clip is scored:
   `cd research && uv run --no-project --with nilearn --with scipy python export_cortex.py --preds <file> --skip-mesh`
2. **Licensing.** TRIBE v2 is CC-BY-NC-4.0. Showing its output on a
   commercial-facing page needs a check against `NOTICE` and
   `business/canon/MODEL-LICENSE-DECISION.md`. fsaverage is a FreeSurfer template:
   add its attribution to `NOTICE` before this ships.
3. **Asset weight.** The GLB is 4.8 MB uncompressed (float32 positions, no
   quantisation). Run `gltf-transform meshopt` or quantise to around 1.5 MB before
   production. Custom `_SULC/_FSA5_*` attributes must survive the pass.
4. **Landing page rebuild.** Dark x.ai/bot layout, scorer-as-hero, brain mascot
   walkthrough. Not started.
5. **Processing page integration.** Embed the viewer in `components/scorer/JobProgress.tsx`.
   It needs per-job preds from the API, which don't exist yet (the API returns ROI
   scores, not vertex arrays).
6. **Stale copy.** `app/scorer/page.tsx` still says "6 brain regions that predict
   viral engagement". That breaks the public-repo contract in `CLAUDE.md`.

## Dev gotcha: don't run `next dev` from /mnt/external

`/mnt/external` is an **sshfs mount over Tailscale**. `next dev` there took 8.4
minutes to boot, and the first route compile timed out. Run from a local mirror:

```bash
rsync -a --delete --exclude node_modules --exclude .next \
  /mnt/external/Projects/tribe-social/apps/web/ ~/dev/tribe-web/
cd ~/dev/tribe-web && npm ci && npx next dev -p 3100   # → http://localhost:3100/cortex
```

Edit in the repo, then rsync `components/`, `app/` and `public/` into the mirror.
Headless Chrome under WSL has no WebGL. For screenshots, launch Chrome with
`--use-angle=swiftshader --enable-unsafe-swiftshader`.
