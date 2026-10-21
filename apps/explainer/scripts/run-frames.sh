#!/usr/bin/env bash
# The guide cut's run cycle: source frames 49-55 of the keyed walk-in (intro_a), a
# clean side-on step with the whole character in frame and its mouth closed (the
# mouth only starts moving at frame 78). Written as alpha PNGs to
# public/media/mascot/run/049.png … 055.png, which src/guide.tsx loops.
#
#   bash scripts/run-frames.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$HERE/public/media/mascot/intro_a.webm"
OUT="$HERE/public/media/mascot/run"
[[ -f "$SRC" ]] || { echo "no $SRC: run npm run sync first" >&2; exit 1; }
mkdir -p "$OUT"
# libvpx-vp9 keeps the alpha plane (the native VP9 decoder drops it).
ffmpeg -v error -y -c:v libvpx-vp9 -i "$SRC" -vf "select='between(n,49,55)'" \
  -fps_mode passthrough -start_number 49 "$OUT/%03d.png"
ls "$OUT"
