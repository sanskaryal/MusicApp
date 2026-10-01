# Verification — 2026-10-01

Project root: `/Users/san/Library/Mobile Documents/com~apple~CloudDocs/proj/MusicApp`.
All source files were created in an initially empty folder. The music app checks pass. The unrelated supplied checklist has the explicit failures below.

## Music app commands and actual results

Commands use the project root unless a different directory is shown.

| Command | Result |
| --- | --- |
| `node --version` | Exit 0: v25.2.1 |
| `npm --version` | Exit 0: 11.6.2 |
| `python3 --version` | Exit 0: 3.14.7 |
| `yt-dlp --version` | Exit 0: 2026.08.19 |
| `ffmpeg -version` | Exit 0: 8.1 |
| `python3 -m unittest discover -s backend/tests -v` | Initial sandbox run: 9 passed, 3 HTTP tests blocked by local-port permissions. Rerun with permission: exit 0, all 12 passed. Final run after closing HTTP error responses: 12 passed in 1.627 s, no resource warnings. |
| `npm install --prefix apps/music-web` | Initial sandbox install stalled on network access. Stopped with Ctrl-C (exit 130) after the permitted install succeeded. |
| `cd apps/music-web && npm install` | Exit 0. Initial install had two moderate Vitest findings. Final install: 237 packages audited, zero vulnerabilities. |
| `cd apps/music-web && npm audit --json` | Initial exit 1: Vitest / @vitest/mocker GHSA-82fw-gwwq-j7x9. Fixed by upgrading Vitest. |
| `cd apps/music-web && npm install -D vitest@^4.1.11` | Exit 0; zero vulnerabilities. |
| `cd apps/music-web && npm audit` | Final exit 0; zero vulnerabilities. |
| `cd apps/music-web && npm run lint` | Initial exit 1: JSX component parameter treated as unused by core ESLint. Corrected JSX naming configuration. Final exit 0, no warnings. |
| `cd apps/music-web && npm run test` | Initial exit 1: Node 25 native localStorage conflicted with the test environment; dialog query was ambiguous in jsdom. Isolated unit-test storage and scoped the dialog query. Final exit 0: 7/7 tests passed. |
| `cd apps/music-web && npm run build` | Final exit 0: Vite 7.3.6; JavaScript 251.07 kB / 78.79 kB gzip; CSS 18.28 kB / 5.04 kB gzip. |
| `cd apps/music-web && npx playwright install chromium` | Exit 0; Chromium installed for browser testing. |
| `cd apps/music-web && npm run test:e2e` | First run: desktop passed, mobile failed because the sidebar stayed open after creating a playlist. Fixed that interaction. Final exit 0: desktop + mobile both passed, 7.4 s. |
| `yt-dlp --ignore-config --no-plugin-dirs --flat-playlist --dump-single-json --no-warnings --socket-timeout 15 -- 'ytsearch3:YouTube Audio Library Cheel Sunset Dream' > /tmp/cadence-live-search.json` | Exit 0; returned three results, including the artist's original track. |
| `python3 scripts/live_smoke.py` | Exit 0; real API search returned 16 songs; real download and conversion yielded 3,881,709-byte MP3. ffprobe: 161.680563 seconds. Temporary library removed automatically. |
| `node --input-type=module -` in apps/music-web, loading the OpenAPI file with js-yaml and resolving every `$ref` | Exit 0; 12 paths, 44 internal references verified. This was a syntax/reference check, not full schema conformance validation. |
| `git init` | Exit 0; initialized repository on main; no commit created. |
| `python3 backend/server.py` | Started successfully at http://127.0.0.1:8765; left running for preview. |
| `curl -fsS http://127.0.0.1:8765/api/health` | Exit 0: status ok, yt_dlp true, ffmpeg true. |
| `curl -fsS -o /dev/null -w '\nHomepage HTTP %{http_code}\n' http://127.0.0.1:8765/` | Exit 0: homepage HTTP 200. |
| `git status` | Final exit 0; no commits yet; all project files untracked. Runtime data, build artifacts, dependencies and test traces ignored. |

A first attempt to adjust ESLint used a root-relative path while already inside the frontend directory and failed with FileNotFoundError. It was rerun from the correct directory before the passing checks above. No application files were lost.

## Supplied checklist — commands that do not match this project

Each command below was attempted. Directory changes were guarded so npm never ran in the wrong project. Missing application directories mean npm itself could not start for those entries.

| Supplied command | Actual result |
| --- | --- |
| `docker compose up -d` | Exit 1: `no configuration file provided: not found`. This native Mac app has no Compose services. |
| `cd backend && ./gradlew clean test` | Exit 127: no such file `./gradlew`. Backend is Python, not Gradle. |
| `cd backend && ./gradlew build` | Retried with backend as explicit working directory; exit 127: no such file `./gradlew`. An earlier chained directory change also failed because it was already in backend. |
| `cd apps/pos-web && npm install` | Exit 1: apps/pos-web does not exist. |
| `cd apps/pos-web && npm run lint` | Exit 1: apps/pos-web does not exist. |
| `cd apps/pos-web && npm run test` | Exit 1: apps/pos-web does not exist. |
| `cd apps/pos-web && npm run build` | Exit 1: apps/pos-web does not exist. |
| `cd apps/ecommerce-web && npm install` | Exit 1: apps/ecommerce-web does not exist. |
| `cd apps/ecommerce-web && npm run lint` | Exit 1: apps/ecommerce-web does not exist. |
| `cd apps/ecommerce-web && npm run test` | Exit 1: apps/ecommerce-web does not exist. |
| `cd apps/ecommerce-web && npm run build` | Exit 1: apps/ecommerce-web does not exist. |
| `git status` | Initially exit 128 because the folder had no repository. After `git init`, exit 0. |

These failures remain visible. Introducing Gradle and two unrelated commerce applications would violate the music-app-only scope and lightweight-backend requirement.

## Test coverage and visual review

Backend tests cover invalid IDs/metadata, persisted likes/playlists/queue, playlist membership/deletion/rename, queue duplicates/order conflicts, cached search, upstream errors/timeouts, duplicate download suppression, failed-download retry, restart recovery, missing media recovery, actual HTTP audio ranges/suffixes/HEAD/416, JSON validation, same-origin writes, traversal rejection, and health/state responses.

Frontend tests cover formatting/queue selection, API failures, search, likes, enqueueing, download initiation, playlist creation, and search retry UI. Playwright uses the real Python server and SQLite with deterministic search/download subprocess results and an ffmpeg-generated MP3. It verifies actual playback, pause, seeking, likes, playlist creation/membership/rename/removal/deletion, reload persistence, queue order/removal/clear and next-song playback. Desktop uses 1440px; mobile emulates an iPhone 13 viewport using Chromium. Physical Safari playback was not tested.

Desktop and mobile screenshots were opened and visually inspected; no horizontal overflow was found. They show test-library content, not preloaded songs in the user's real library.

## Changed files (all new)

- `.gitignore`
- `AGENTS.md`
- `PROJECT_SPEC.md`
- `README.md`
- `backend/server.py`
- `backend/tests/test_server.py`
- `backend/tests/browser_fixture.py`
- `apps/music-web/package.json`
- `apps/music-web/package-lock.json`
- `apps/music-web/index.html`
- `apps/music-web/public/favicon.svg`
- `apps/music-web/vite.config.js`
- `apps/music-web/eslint.config.js`
- `apps/music-web/playwright.config.js`
- `apps/music-web/src/main.jsx`
- `apps/music-web/src/App.jsx`
- `apps/music-web/src/api.js`
- `apps/music-web/src/styles.css`
- `apps/music-web/src/test-setup.js`
- `apps/music-web/src/App.test.jsx`
- `apps/music-web/e2e/player.spec.js`
- `scripts/start.sh`
- `scripts/live_smoke.py`
- `docs/ARCHITECTURE.md`
- `docs/PROGRESS.md`
- `docs/VERIFICATION.md`
- `docs/api/openapi.yaml`
- `docs/screenshots/desktop.png`
- `docs/screenshots/mobile.png`
