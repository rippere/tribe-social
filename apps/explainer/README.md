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

# 2. mascot shots: Kling walk-in + watching scene, Seedance talking shots (skip existing)
cd apps/explainer && npm ci && npm run mascot:gen && npm run talk:gen

# 3. copy media in, key the mascot to alpha WebM + track, export cortex activity
npm run sync

# 4. narration timings + per-second result
uv run --no-project --with faster-whisper --with numpy python scripts/build_data.py \
  --preds ../../research/demo_mac_and_cheese_preds.npy

# 5. preview / render
npm run studio            # http://<host>:3200
npm run render:landing    # out/fmright-explainer-16x9.mp4
npm run render:vertical   # out/fmright-explainer-9x16.mp4
# no GPU GL (e.g. a driver/library mismatch)? append: -- --gl=swangle  (software, slower)
```

Media (`public/media/`, `public/cortex/`) and renders (`out/`) are git-ignored. The
source media lives in the git-ignored `business/explainer/` folder; point
`EXPLAINER_MEDIA` elsewhere to swap it. To use a filmed clip instead of the
AI-generated one, replace `stimulus/mac_and_cheese.mp4` there, re-score, and re-run
steps 2–4. The callouts and quotes are derived from the new result.

## The mascot

The brain narrates and teaches from inside the scorer. Two kinds of shot, all on chroma
green and keyed to alpha:

- **Talking shots (Seedance 2.0, `scripts/talk_shots.json`).** One per sentence or two,
  lip-synced to that slice of the narration: the mouth moves only while Isla speaks.
  Each prompt ties a gesture to a phrase ("while it says 'graphics card' it points
  straight up"). Shots play at natural speed with their own audio slice from the first
  frame, so gestures land on their words. `npm run talk:gen [-- <name>]` (720p, about
  4.5 credits/s; Higgsfield runs at most 6 at once).
- **Walk-in and watching (Kling 3.0, `scripts/mascot_shots.json`).** `intro_a` walks in;
  `play_a`–`play_e` sit and watch the scored clip. The watching shots are pinned to the
  result: the excited lean lands just after the peak, and the frown and walk-off land on
  the decline into the biggest drop.
- **Pointing at the UI.** The character stands at centre in every scorer scene, and the
  UI is laid out as three targets around it: up-left, straight up, up-right. A prompt
  names the direction on the word that names the element, and the accent ring is cued
  from the same word.
- **Anchors.** `business/explainer/v2/anchors/A_{empty,C,SIT}.png`: the same keyed
  character at a fixed size and ground line. Every shot starts and ends on one, so shots
  join without a jump. Seedance sometimes frames a shot tighter than its start image;
  `fitToAnchor` (src/mascot.tsx) scales those back about the feet.
- **Keying.** `scripts/key_mascot.py` keys to VP9 alpha WebM and writes
  `src/data/mascot_track.json` (per-frame bounding box). Clip lengths come from it.
- **Captions.** Lower third at bottom-left in 16:9 (clear of the character), centred
  above its head in 9:16. Words light up as they are spoken.
- **Changing a line.** Edit `business/explainer/v3/narration/<line>.txt` (and its row in
  `lines.tsv`), regenerate its TTS (Higgsfield `text2speech_v2`, ElevenLabs voice Isla),
  update the quoted phrases in that shot's prompt in `scripts/talk_shots.json` (and its
  `duration` if the audio moves past a whole second), then `npm run talk:gen -- <shot>`,
  `npm run sync`, and step 4 above. `.txt` is also the caption text, so never change it
  without the matching `.mp3` and shot, or captions drift off the voice. From a worktree,
  set `EXPLAINER_MEDIA` to the main checkout's `business/explainer`; `business/` is
  git-ignored, so a worktree has none.
- **Check every new talking shot before syncing it.** Seedance sometimes ignores "hands
  empty" and adds a prop. The 2026-10-05 `t_read1` retake held a pointer stick through the
  whole sweep and was rejected. A track box much taller than the anchor (`h` ~0.354) is the
  tell.

## Script status (v4)

The target script is `business/explainer/v4/lines.tsv`. As of 2026-10-05:

| Line | Shot | State |
|---|---|---|
| n6_read2 ("I predict an average viewer locks in… I predict they drift off") | t_read2 | **Live.** Audio, shot, prompt and captions all match |
| n1_intro ("I'll predict how an average viewer's brain responds") | t_intro | **Pending.** TTS done (`v4/narration/n1_intro.*`); shot not generated (63 credits at 14 s) |
| n5_read ("tracks the predicted response across my whole surface") | t_read1 | **Pending.** TTS done (`v4/narration/n5_read.*`); first retake rejected (`v4/rejected/`); regenerate at 13 s (58.5 credits) |
| n2, n3, n4, n7 | | Unchanged from v3 |

Pending lines still render with their v3 audio, shot and captions, so the cut stays in
sync. To land one: copy its `v4/narration/<line>.{mp3,json,txt}` into `v3/narration/`,
replace its row in `v3/narration/lines.tsv`, update the quoted phrases in its shot prompt
(for t_read1, also add "it never holds a stick, pointer or wand"), then run `talk:gen`,
`sync` and `build_data.py`.

## What's real and what isn't

- **Real model output:** the cortex activity (`activity.bin`, `source: "tribe"`) and
  the per-second curve (global field power, the RMS across all 20,484 fsaverage5
  points, scaled 0–1 within the clip). No region masks are used: the index-range
  masks in `run_and_save.py` / `roi_masks.py` are not anatomical regions.
- **Warm-up:** the first 5 s are shaded. The fMRI signal TRIBE predicts lags the
  stimulus by about 5 s, so every clip starts low. That is not a weak hook.
- **Generated media:** the stimulus clip (Veo 3.1), mascot shots (Kling 3.0 and Seedance 2.0, keyed from green screen), and
  narration (ElevenLabs voice "Isla") come from Higgsfield. The clip is labelled
  "AI-generated test clip" on screen.
- **No real data, nothing shown:** if `activity.*` or `result.json` is missing, the
  scenes show an amber "awaiting model output" tag. They never fall back to
  illustrative data.
- **Limits:** v3 drops the spoken limits scene. The play scene notes "model output,
  not measured brain data". From v4 the sign-off card carries the caveat on screen,
  because the video travels without the page around it (e.g. a social post): "not a
  forecast of views", plus the pilot result (weak, not significant: r = 0.25, p = 0.24,
  n = 24) and that a pre-registered test is next. TRIBE v2 is CC-BY-NC-4.0; check
  `NOTICE` before this goes anywhere commercial-facing.
