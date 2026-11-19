#!/usr/bin/env bash
# Render both v6 cuts. While any narration line is still a stand-in (a *.standin
# marker in public/media/narration_v6), the files are named -v6-standin-* so a
# placeholder render can't be mistaken for the real one.
#
#   bash scripts/render-v6.sh              # GPU GL (angle)
#   bash scripts/render-v6.sh --gl=swangle # no usable GPU GL: software, slower
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"
tag="v6"
compgen -G "public/media/narration_v6/*.standin" > /dev/null && tag="v6-standin"
gl="${1:---gl=angle}"
for c in 16x9 9x16; do
  npx remotion render "Explainer-$c" "out/fmright-explainer-$tag-$c.mp4" "$gl" \
    --pixel-format=yuv420p --color-space=bt709
done
ls -la out/fmright-explainer-"$tag"-*.mp4
