#!/usr/bin/env bash
# Render both cuts of the v6 guide variant (the mascot travels to whatever Ben is
# talking about; src/guide.tsx). Same narration and scenes as v6; the plain v6 cut
# is scripts/render-v6.sh. Stand-in narration names the files -v6-guide-standin-*.
#
#   bash scripts/render-v6-guide.sh              # GPU GL (angle)
#   bash scripts/render-v6-guide.sh --gl=swangle # no usable GPU GL: software, slower
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"
[[ -f public/media/mascot/run/055.png ]] || bash scripts/run-frames.sh
tag="v6-guide"
compgen -G "public/media/narration_v6/*.standin" > /dev/null && tag="v6-guide-standin"
gl="${1:---gl=angle}"
for c in 16x9 9x16; do
  npx remotion render "Explainer-$c-guide" "out/fmright-explainer-$tag-$c.mp4" "$gl" \
    --pixel-format=yuv420p --color-space=bt709
done
ls -la out/fmright-explainer-"$tag"-*.mp4
