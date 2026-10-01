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
for k in m1_hello m2_point m3_think m4_count m5_shrug; do
  cp "$SRC/mascot/shots/$k.mp4" "$OUT/mascot/$k.mp4"
done
for k in n1_intro n2_upload n3_encode n4_extract n5_read n6_limits; do
  cp "$SRC/narration/$k.mp3" "$SRC/narration/$k.txt" "$OUT/narration/"
done

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
