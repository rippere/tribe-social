#!/usr/bin/env bash
# Render the ~30 s short (both orientations). Needs public/ synced (npm run sync) and
# the cut narration (scripts/short_vo.py, which writes public/media/narration_short).
#
#   bash scripts/render-short.sh              # GPU GL (angle)
#   bash scripts/render-short.sh --gl=swangle # no usable GPU GL: software, slower
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"
gl="${1:---gl=angle}"
uv run --no-project --with numpy python scripts/short_vo.py
for c in 9x16 16x9; do
  npx remotion render "Short-$c" "out/prepost-short-$c.mp4" "$gl" \
    --pixel-format=yuv420p --color-space=bt709
done
ls -la out/prepost-short-*.mp4
