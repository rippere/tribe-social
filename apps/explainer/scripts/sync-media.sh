#!/usr/bin/env bash
# Copy the generated media into public/ (git-ignored) under the names the
# compositions expect. Source defaults to the git-ignored business/explainer
# folder the Higgsfield + scoring runs write to; override with EXPLAINER_MEDIA.
#
#   bash scripts/sync-media.sh
#   EXPLAINER_MEDIA=/path/to/explainer PREDS=/path/to/x_preds.npy bash scripts/sync-media.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
SRC="${EXPLAINER_MEDIA:-$ROOT/business/explainer}"
PREDS="${PREDS:-$ROOT/research/demo_mac_and_cheese_preds.npy}"
OUT="$HERE/public/media"

mkdir -p "$OUT/mascot" "$OUT/narration" "$HERE/public/cortex"

cp "$SRC/stimulus/mac_and_cheese.mp4" "$OUT/stimulus.mp4"
# Mascot shots are green-screen clips: Kling for the walk-in and the watching scene
# (scripts/gen_mascot.py), Seedance for the talking shots (scripts/gen_talk.py). Key
# them to alpha WebM and refresh the per-frame track the composition times against.
uv run --no-project --with numpy python "$HERE/scripts/key_mascot.py" \
  --src "$SRC/v2/clips" --out "$OUT/mascot" --track "$HERE/src/data/mascot_track.json" \
  --only intro_a play_a play_b play_c play_d play_e
talk=$(python3 -c 'import json,sys; print(" ".join(json.load(open(sys.argv[1]))["shots"]))' "$HERE/scripts/talk_shots.json")
[[ -n "$talk" ]] || { echo "no talking shots in scripts/talk_shots.json" >&2; exit 1; }
# shellcheck disable=SC2086  # $talk is a space-separated list of shot names
uv run --no-project --with numpy python "$HERE/scripts/key_mascot.py" \
  --src "$SRC/v3/clips" --out "$OUT/mascot" --track "$HERE/src/data/mascot_track.json" --only $talk
# Full lines (for alignment) and each talking shot's audio slice (what plays).
cp "$SRC"/v3/narration/n*.mp3 "$SRC"/v3/narration/n*.txt "$OUT/narration/"
cp "$SRC"/v3/clips/t_*.mp3 "$OUT/narration/"

# Cortex mesh + exporter live on feat/cortex-render until it merges.
git -C "$ROOT" show feat/cortex-render:apps/web/public/cortex/cortex.glb > "$HERE/public/cortex/cortex.glb"

if [[ -f "$PREDS" ]]; then
  tmp="$(mktemp -d)"
  git -C "$ROOT" show feat/cortex-render:research/export_cortex.py > "$tmp/export_cortex.py"
  uv run --no-project --with nilearn --with scipy python "$tmp/export_cortex.py" \
    --preds "$PREDS" --label "Sample creator clip (AI-generated)" --skip-mesh --out "$HERE/public/cortex"
  rm -rf "$tmp"
  echo "cortex activity: TRIBE output from $PREDS"
else
  echo "no preds at $PREDS: cortex activity not exported" >&2
fi
echo "synced media → $OUT"
