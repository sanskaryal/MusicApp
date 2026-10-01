# Cadence

Your own music corner: a responsive React player, YouTube search, local MP3 downloads, persistent queues, playlists and likes. Python + SQLite power the backend with **no Python dependencies**. Your installed `yt-dlp` and `ffmpeg` do the downloading.

## Start on your Mac

Requires Python 3.11+, Node 20.19+ or 22.12+, yt-dlp, and ffmpeg on PATH.

```sh
cd apps/music-web
npm install
npm run build
cd ../..
python3 backend/server.py
```

Open **http://localhost:8765**. Next time, just run `python3 backend/server.py`.

Or use `./scripts/start.sh` to install missing frontend dependencies, build, and launch in one step.

## Listen on your phone

Start with `MUSIC_HOST=0.0.0.0 ./scripts/start.sh`, then open `http://<your-Mac-LAN-IP>:8765` on a phone on the same Wi-Fi. Find the Mac's IP in System Settings → Wi-Fi → Details → TCP/IP. The Mac needs to remain awake. This is a single personal library with no login: use a trusted private network, not public internet exposure. The phone may require a play tap after downloading because of browser autoplay rules.

## Using it

- Search by title, artist or mood. A result click downloads the audio and plays it when ready.
- Heart a song to save it to **Liked songs**. Use **+** to add it to a playlist.
- Use the queue icon to append songs. **Play queue** provides move up/down, remove and clear. Click an entry to start there; next/previous follow its order.
- **Your library** holds downloaded music. Likes and playlist additions save metadata without starting a download.
- Downloads show queued/downloading/ready/error states. Failed downloads offer retry, including errors returned by yt-dlp.
- Seek, volume, shuffle and repeat are available in the desktop player. Mobile uses compact playback controls; device volume controls audio.
- Download only music you own or have permission to save.

## Data and limits

`data/library.sqlite3` holds the library; `data/audio/<video-id>.mp3` holds downloaded music. Back up the entire data directory with the server stopped. Nothing is uploaded to a cloud database. Set `MUSIC_DATA_DIR` to move storage; `MUSIC_PORT` changes the default 8765 port. Search and first downloads require internet. Saved audio plays offline while the server runs. Covers still load from YouTube.

Downloads are limited to two concurrent workers, twenty pending requests, two hours per track and a 150 MB source file. A download can take up to ten minutes. Restarted/interrupted downloads become retryable errors. YouTube changes can break extraction; update yt-dlp through the method you used to install it. The app never reads browser cookies or authentication credentials.

The downloader flags follow the [official yt-dlp documentation](https://github.com/yt-dlp/yt-dlp/blob/master/README.md).

## Development

Run `python3 backend/server.py` in one terminal. In another, run `cd apps/music-web && npm run dev`. Open the Vite URL; `/api` is proxied to port 8765. Production uses only the Python server and the built static frontend.

## Verification

```sh
python3 -m unittest discover -s backend/tests -v
cd apps/music-web
npm install
npm run lint
npm run test
npm run build
npx playwright install chromium
npm run test:e2e
cd ../..
git status
```

Browser tests launch a temporary server and use generated audio, so they do not require a YouTube download. See [docs/VERIFICATION.md](docs/VERIFICATION.md) for actual results, including the supplied Docker/Gradle/commerce checklist. See [AGENTS.md](AGENTS.md), [project spec](PROJECT_SPEC.md), [architecture](docs/ARCHITECTURE.md), [API contract](docs/api/openapi.yaml) and [progress](docs/PROGRESS.md) before changing code.
