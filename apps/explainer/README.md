# fMRIght explainer

Remotion source for the scoring explainer: a brain-mascot narrator walks through
upload → encode → extract → read, then a real clip plays against its real TRIBE v2
result. Two compositions from one source:

| Composition | Size | Use |
|---|---|---|
| `Explainer-16x9` | 1920×1080 | landing page "See it in action" slot |
| `Explainer-9x16` | 1080×1920 | vertical cut for socials |

## Rebuild

```bash
# 1. score the stimulus clip (rents one A100 pod, terminates it after)
cd research && uv run tribe-score score <clip.mp4> --label demo_mac_and_cheese

# 2. copy media in + export cortex activity from the preds
cd apps/explainer && npm ci && npm run sync

# 3. narration timings + per-second result
uv run --no-project --with faster-whisper --with numpy python scripts/build_data.py \
  --preds ../../research/demo_mac_and_cheese_preds.npy

# 4. preview / render
npm run studio            # http://<host>:3200
npm run render:landing    # out/fmright-explainer-16x9.mp4
npm run render:vertical   # out/fmright-explainer-9x16.mp4
```

Media (`public/media/`, `public/cortex/`) and renders (`out/`) are git-ignored. The
source media lives in the git-ignored `business/explainer/` folder; point
`EXPLAINER_MEDIA` elsewhere to swap it. To use a filmed clip instead of the
AI-generated one, replace `stimulus/mac_and_cheese.mp4` there, re-score, and re-run
steps 2–4. The callouts and quotes are derived from the new result.

## What's real and what isn't

- **Real model output:** the cortex activity (`activity.bin`, `source: "tribe"`) and
  the per-second curve (global field power, the RMS across all 20,484 fsaverage5
  points, scaled 0–1 within the clip). No region masks are used: the index-range
  masks in `run_and_save.py` / `roi_masks.py` are not anatomical regions.
- **Warm-up:** the first 5 s are shaded. The fMRI signal TRIBE predicts lags the
  stimulus by about 5 s, so every clip starts low. That is not a weak hook.
- **Generated media:** the stimulus clip (Veo 3.1), mascot shots (Kling 3.0), and
  narration (ElevenLabs voice "Isla") come from Higgsfield. The clip is labelled
  "AI-generated test clip" on screen.
- **No real data, nothing shown:** if `activity.*` or `result.json` is missing, the
  scenes show an amber "awaiting model output" tag. They never fall back to
  illustrative data.
- **Limits card:** pilot r = 0.25, p = 0.24, n = 24. TRIBE v2 is CC-BY-NC-4.0. Check
  `NOTICE` before this goes anywhere commercial-facing.
