#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
for executable in python3 node npm yt-dlp ffmpeg; do
  if ! command -v "$executable" >/dev/null 2>&1; then
    echo "Missing dependency: $executable. Install it before starting Cadence." >&2
    exit 1
  fi
done
if [ ! -d apps/music-web/node_modules ]; then
  (cd apps/music-web && npm ci)
fi
(cd apps/music-web && npm run build)
exec python3 backend/server.py "$@"
