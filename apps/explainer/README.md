# fMRIght explainer

Remotion source for the scoring explainer: Ben (who built fMRIght) narrates off-screen
in the first person while the brain mascot walks in, stands by the scorer UI through
upload → encode → extract → read, then watches a real clip play against its real
TRIBE v2 result. The mascot never talks. Two compositions from one source:

| Composition | Size | Use |
|---|---|---|
| `Explainer-16x9` | 1920×1080 | landing page "See it in action" slot |
| `Explainer-9x16` | 1080×1920 | vertical cut for socials |

## Rebuild

```bash
# 1. score the stimulus clip (rents one A100 pod, terminates it after)
cd research && uv run tribe-score score <clip.mp4> --label demo_mac_and_cheese

# 2. mascot shots: Kling walk-in + watching scene (skip existing)
cd apps/explainer && npm ci && npm run mascot:gen

# 3. copy media in: key the mascot to alpha WebM + track, key the idle still,
#    copy the v6 narration, export cortex activity
npm run sync

# 4. narration word timings (+ per-second result with --preds)
npm run data
uv run --no-project --with faster-whisper --with numpy python scripts/build_data.py \
  --preds ../../research/demo_mac_and_cheese_preds.npy

# 5. preview / render
npm run studio            # http://<host>:3200
npm run render:v6         # out/fmright-explainer-v6[-standin]-{16x9,9x16}.mp4
# no GPU GL (e.g. a driver/library mismatch)? bash scripts/render-v6.sh --gl=swangle
```

Scrub each render before shipping it: GPU GL occasionally drops the cortex canvas
mid-render and leaves a white box for the rest of a scene (seen once on the 16:9 play
scene, 2026-10-20). Re-rendering that cut fixed it.

Media (`public/media/`, `public/cortex/`) and renders (`out/`) are git-ignored. The
source media lives in the git-ignored `business/explainer/` folder; point
`EXPLAINER_MEDIA` elsewhere to swap it. From a worktree, set `EXPLAINER_MEDIA` to the
main checkout's `business/explainer`: `business/` is git-ignored, so a worktree has
none. To use a filmed clip instead of the AI-generated one, replace
`stimulus/mac_and_cheese.mp4` there, re-score, and re-run steps 3–4. The callouts and
quotes are derived from the new result.

## Narration (v6: Ben's voice)

The script is `business/explainer/v6/lines.tsv`, one row per line (`b1_intro` …
`b9_outro`); `v6/narration/<line>.txt` is that line's exact wording and also the
caption text. Each line's audio is `v6/narration/<line>.mp3`. A scene lasts as long as
its lines (0.25 s lead, 0.35 s between lines, 0.6 s tail), so a longer or shorter take
just moves the cut.

| Scene | Lines |
|---|---|
| intro | b1_intro |
| upload | b2_upload |
| encode | b3_encode, b4_scan |
| extract | b5_extract |
| read | b6_read, b7_lag, b8_read2 |
| play | none (the clip's own audio) |
| cta | b9_outro |

**Stand-ins.** Until Ben records, every line is a free offline TTS stand-in (piper,
voice `en_US-ryan-medium`, paced to ~2.6 words/s): `npm run vo:standin`. A stand-in
line carries a `v6/narration/<line>.standin` marker. While any marker is left, the
video shows an amber "Stand-in voice" tag and `render:v6` names the files
`-v6-standin-*`.

**Dropping in Ben's takes** (any subset of lines; the rest stay stand-ins):

```bash
# 1. save each take as business/explainer/v6/recordings/<line>.{wav,m4a,mp3}
# 2. trim, level, replace the stand-in, re-align the captions
npm run vo:ingest
# 3. render both cuts
npm run render:v6
```

`vo:ingest` trims leading/trailing silence to 0.15 s, levels the take to the v5
narration's loudness (measured from `public/media/narration/n1_intro.mp3`, -11.5 LUFS,
peaks under -1 dBTP), writes `v6/narration/<line>.mp3`, removes that line's marker,
copies the narration into `public/media/narration_v6/` and re-runs the Whisper word
alignment (`npm run data`). Read the takes against the `.txt` exactly: the captions
show the script, and Whisper only times it. If a line's wording has to change, edit
its `.txt` and its row in `lines.tsv` together.

## The mascot

The brain never speaks: Ben's voice is off-screen, and the mascot's mouth stays shut
whenever he talks. An intro chip ("Narrated by Ben, who built it") says whose voice
it is.

- **Walk-in (intro).** Kling `intro_a` walks in from the left. Its mouth starts moving
  (a "hi") at source frame 78, right after it reaches the centre, so it is cut at
  frame 76 and cross-faded over 6 frames into the idle still (`WALK_IN`, src/mascot.tsx).
- **Idle (upload, encode, extract, read, cta).** The centre anchor
  `business/explainer/v2/anchors/A_C.png`, keyed to `public/media/mascot/idle.png`
  (`key_mascot.py --still`), at the same size and ground line as the shots. Remotion
  animates it: breathing (~1.2 % vertical scale), a slow bob and sway on global time
  (so it carries across cuts), and a beat per cue word: it leans toward the UI
  element Ben names (the UI sits up-left, up and up-right of it), hops on the payoff
  words and droops on "dips" (`beatsFor`, src/Explainer.tsx).
- **Watching (play).** Kling `w_a`–`w_e` (`scripts/mascot_shots.json`), silent. They
  are pinned to the result: the excited lean lands just after the peak, and the frown
  and walk-off land on the decline into the biggest drop.
- **Rejected for v6.** Every talking shot (Seedance `t_*`, `scripts/talk_shots.json`,
  and the v2 `enc_`/`ext_`/`read_`/`lim_`/`intro_b`/`intro_c` clips) moves its mouth.
  The v2 `cta` wave opens into a grin from about frame 42, so the sign-off uses idle
  as well.
- **Anchors.** `business/explainer/v2/anchors/A_{empty,C,SIT}.png`: the same character
  at a fixed size and ground line. Every shot starts and ends on one, so shots and
  the idle still join without a jump.
- **Keying.** `scripts/key_mascot.py` keys to VP9 alpha WebM and writes
  `src/data/mascot_track.json` (per-frame bounding box). Clip lengths come from it.
- **Captions.** Lower third at bottom-left in 16:9 (clear of the character), centred
  above its head in 9:16. Words light up as they are spoken. Each UI highlight (accent
  ring) is cued from a word in the v6 script: "video", "brain", "second" (intro);
  "upload", "graphics card", "delete", "numbers" (upload); "frames", "audio", "words",
  "Meta", "trained", "MRI", "alone" (encode); "comes", "twenty thousand", "every",
  "lighting" (extract); "real", "line", "behind", "slide", "climbs", "dips" (read);
  "fMRIght", "forecast", "testing", "Try" (sign-off).
- **v3–v5 history.** Those cuts had the brain narrate (ElevenLabs "Isla") with lip-synced
  Seedance shots: `scripts/gen_talk.py`, `scripts/talk_shots.json`, `npm run talk:gen`.
  They are kept for reference; v6 uses none of them. The v5 source is commit `6edc00a`.

## The guide cut (experimental)

`Explainer-16x9-guide` / `Explainer-9x16-guide` (`npm run render:v6-guide` →
`out/fmright-explainer-v6-guide-{16x9,9x16}.mp4`) are the same v6 scenes and narration,
but the mascot is an attention guide: it travels to whatever Ben is talking about and
lands beside it just before the word. No new footage: the same idle still, and for long
level moves a run cycle looped from the walk-in itself (`intro_a` source frames 49–55,
a side-on step, mouth closed; `scripts/run-frames.sh` writes them to
`public/media/mascot/run/`).

- **Targets** are the Spots: each `Spot` takes the cue time(s) it lights up on (`cue`)
  and, inside the guide's `GuideStage`, reports its on-screen box (measured each frame,
  divided by the root's scale so Studio and render agree). Other UI the guide must not
  stand on registers with `useKeepClear()`. In the plain cut nothing is measured.
- **Where it stands** (`place`, src/guide.tsx): beside the element with its feet on the
  element's bottom edge, perched on its top edge, under it, on the floor below it, or on
  top of the caption block; never over the captions or the element it points at, inside
  the scorer window; covering other UI costs most. 16:9 mostly stands beside or under
  the cards; 9:16, where the captions sit between the UI and the floor, walks along the
  floor under the named column and looks up.
- **How it gets there**: short → shuffle, medium → hop, long and level → run, a big
  change in height → jump (crouch, arc, squash on landing). Cues closer than 0.6 s to the
  last one, or that would leave it less than 0.35 s at a target, are skipped.
- **Seams**: each scene starts and ends at the anchor's feet, small between narrated
  scenes and full size where the walk-in hands over and before the play scene's Kling
  shots, so cuts join without a jump. The cue-word hop, nod and droop beats are kept;
  the leans are replaced by its travel.
- **Knobs**: `GUIDE` in src/guide.tsx (size, lead, gaps, hop and jump heights, run speed).

## What's real and what isn't

- **Real model output:** the cortex activity (`activity.bin`, `source: "tribe"`) and
  the per-second curve (global field power, the RMS across all 20,484 fsaverage5
  points, scaled 0–1 within the clip). No region masks are used: the index-range
  masks in `run_and_save.py` / `roi_masks.py` are not anatomical regions.
- **Warm-up:** the first 5 s are shaded. The fMRI signal TRIBE predicts lags the
  stimulus by about 5 s, so every clip starts low. That is not a weak hook.
- **Generated media:** the stimulus clip (Veo 3.1) and mascot shots (Kling 3.0, keyed
  from green screen) come from Higgsfield. The clip is labelled "AI-generated test
  clip" on screen. The narration is Ben's own voice; until he records, it is a piper
  TTS stand-in, tagged on screen.
- **No real data, nothing shown:** if `activity.*` or `result.json` is missing, the
  scenes show an amber "awaiting model output" tag. They never fall back to
  illustrative data.
- **Limits:** v3 drops the spoken limits scene. The play scene notes "model output,
  not measured brain data". From v4 the sign-off card carries the caveat on screen,
  because the video travels without the page around it (e.g. a social post): "not a
  forecast of views", plus the pilot result (weak, not significant: r = 0.25, p = 0.24,
  n = 24) and that a pre-registered test is next. TRIBE v2 is CC-BY-NC-4.0; check
  `NOTICE` before this goes anywhere commercial-facing.
