"""End-to-end tests for hook_test_analysis.py, on generated feature and outcome tables.

Each study is 18 bases x 4 variants. A latent "hook quality" z is drawn per clip and
moves its logit hook rate. The scenario decides where z is visible: in a brain feature
(the analysis should say GO), in a content feature (NO-GO: the brain adds nothing),
or nowhere. Permutation and bootstrap counts are cut so the suite runs in minutes;
the registered counts are exercised by `make hook-test`, not here.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import hook_test_analysis as h
from validate_stimuli import VARIANTS


@pytest.fixture(autouse=True)
def fast(monkeypatch):
    monkeypatch.setattr(h, "N_PERM", 200)
    monkeypatch.setattr(h, "N_BOOT", 100)


SCALARS = ("a_lufs", "a_motion", "a_rms", "a_duration")


def make_study(d: Path, signal: str, n_bases: int = 18, p_a: int = 300, p_b: int = 27,
               seed: int = 0) -> tuple[Path, Path, pd.DataFrame]:
    """Write features.csv and outcomes.csv; return them plus the latent truth per clip."""
    rng = np.random.default_rng(seed)
    feats, outs, truth = [], [], []
    for b in range(1, n_bases + 1):
        body_a, body_b = rng.standard_normal(p_a + len(SCALARS)), rng.standard_normal(p_b)
        base_effect = rng.normal(-0.5, 0.5)
        for v in VARIANTS:
            name = f"base{b:02d}_{v}.mp4"
            a = body_a + 0.3 * rng.standard_normal(p_a + len(SCALARS))
            bb = body_b + 0.3 * rng.standard_normal(p_b)
            z = rng.standard_normal()
            if signal == "brain":
                bb[0] += z
            elif signal == "content":
                a[p_a + 1] += 3 * z  # motion energy carries the hook quality
            logit = base_effect + (0.6 * z if signal != "none" else 0.0)
            n = int(1000 * rng.uniform(0.95, 1.05))
            k = rng.binomial(n, 1 / (1 + np.exp(-logit)))
            feats.append({"filename": name, **{f"a_emb_{i:04d}": a[i] for i in range(p_a)},
                          **{c: a[p_a + j] for j, c in enumerate(SCALARS)},
                          **{f"b_{i:02d}": bb[i] for i in range(p_b)}})
            outs.append({"filename": name, "impressions": n, "plays_3s": k,
                         "plays_15s": rng.binomial(k, 0.4), "rejected": ""})
            truth.append({"base": b, "variant": v, "z": z})
    fp, op = d / "features.csv", d / "outcomes.csv"
    pd.DataFrame(feats).to_csv(fp, index=False)
    pd.DataFrame(outs).to_csv(op, index=False)
    return fp, op, pd.DataFrame(truth)


def run(fp: Path, op: Path, out: Path, *extra: str) -> tuple[int, dict]:
    code = h.main(["--features", str(fp), "--outcomes", str(op), "--out", str(out), *extra])
    return code, json.loads(out.read_text()) if out.exists() else {}


def test_planted_brain_signal_is_go(tmp_path):
    fp, op, truth = make_study(tmp_path, "brain")
    guesses = truth.assign(guesser="g1", role="team",
                           rank=truth.groupby("base").z.rank(ascending=False).astype(int))
    gp = tmp_path / "guesses.csv"
    guesses[["guesser", "role", "base", "variant", "rank"]].to_csv(gp, index=False)

    code, res = run(fp, op, tmp_path / "res.json", "--guesses", str(gp))
    assert code == 0
    assert res["h1"]["B"]["clears"] and res["h1"]["B"]["r"] > 0.5
    assert res["h2"]["clears"], res["h2"]
    assert not res["control"]["clears"], res["control"]
    assert res["verdict"] == "GO"
    assert res["guesses"]["team"]["r"] > 0.5  # guesses ranked by the true hook quality


def test_signal_only_in_content_is_no_go(tmp_path):
    fp, op, _ = make_study(tmp_path, "content", seed=1)
    code, res = run(fp, op, tmp_path / "res.json")
    assert code == 0
    assert res["r2"]["A"] > 0.3, res["r2"]  # the content model finds the signal in motion energy
    assert not res["h2"]["clears"], res["h2"]
    assert not res["control"]["clears"], res["control"]
    assert res["verdict"] == "NO-GO"


def test_no_signal_is_not_go(tmp_path):
    fp, op, _ = make_study(tmp_path, "none", seed=3)
    code, res = run(fp, op, tmp_path / "res.json")
    assert code == 0
    assert not res["h2"]["clears"], res["h2"]
    assert res["verdict"] != "GO"


def test_exclusions_and_blank_rejected(tmp_path):
    fp, op, _ = make_study(tmp_path, "none", seed=2)
    outs = pd.read_csv(op, keep_default_na=False)
    outs.loc[outs.filename == "base01_spoken.mp4", "impressions"] = 500  # under the floor
    outs.loc[outs.filename == "base02_cold.mp4", "impressions"] = 1300  # >20% imbalance
    outs.loc[outs.filename == "base03_text.mp4", "rejected"] = "1"  # ad review
    outs["plays_3s"] = outs[["plays_3s", "impressions"]].min(axis=1)
    outs["plays_15s"] = outs[["plays_15s", "plays_3s"]].min(axis=1)
    outs.to_csv(op, index=False)

    code, res = run(fp, op, tmp_path / "res.json")
    assert code == 0
    assert set(res["excluded"]) == {"01", "02", "03"}  # blank rejected cells are not rejections
    assert res["bases_analysed"] == 15


def test_too_few_bases_is_instrument_failure(tmp_path):
    fp, op, _ = make_study(tmp_path, "brain", n_bases=9)
    code, res = run(fp, op, tmp_path / "res.json")
    assert code == 0
    assert res["verdict"] == "INSTRUMENT FAILURE"
    assert "below the minimum of 10" in res["verdict_reason"]


@pytest.mark.parametrize("column,value", [("rejected", "yes"), ("plays_3s", 5000), ("impressions", 999.5)])
def test_bad_outcomes_stop_the_run(tmp_path, column, value):
    fp, op, _ = make_study(tmp_path, "none", n_bases=10)
    outs = pd.read_csv(op, keep_default_na=False)
    outs[column] = outs[column].astype(object)
    outs.loc[0, column] = value
    outs.to_csv(op, index=False)
    assert h.main(["--features", str(fp), "--outcomes", str(op)]) == 2


def test_missing_variant_stops_the_run(tmp_path):
    fp, op, _ = make_study(tmp_path, "none", n_bases=10)
    feats = pd.read_csv(fp)
    feats[feats.filename != "base04_visual.mp4"].to_csv(fp, index=False)
    assert h.main(["--features", str(fp), "--outcomes", str(op)]) == 2


def test_check_features_needs_no_outcomes(tmp_path, capsys):
    fp, _, _ = make_study(tmp_path, "brain")
    assert h.main(["--features", str(fp), "--check-features"]) == 0
    assert "leaves unexplained" in capsys.readouterr().out


def test_outcomes_required_without_check(tmp_path):
    fp, _, _ = make_study(tmp_path, "none", n_bases=10)
    with pytest.raises(SystemExit):
        h.main(["--features", str(fp)])
