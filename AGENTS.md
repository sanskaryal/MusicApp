# Working on Cadence

Read PROJECT_SPEC.md, docs/ARCHITECTURE.md, docs/PROGRESS.md and the existing code before changing behavior. Keep changes scoped to the requested task. Never leave placeholder implementations.

## Stack and boundaries
- React + Vite in apps/music-web; Python standard library + SQLite in backend.
- No external database, account service, or Docker required for local use.
- Invoke yt-dlp as an argument array, never a shell string. Accept validated YouTube video IDs, never arbitrary download URLs or filenames.
- Keep music, database files and secrets out of Git. Do not erase user data during tests.
- Bind to loopback by default. LAN mode is for a trusted private network only.
- Keep docs/api/openapi.yaml synchronized with API changes and update docs/PROGRESS.md.

## Verification
Run `python3 -m unittest discover -s backend/tests -v` and, from apps/music-web, `npm install`, `npm run lint`, `npm run test`, and `npm run build`. For browser integration run `npm run test:e2e` after installing Chromium with `npx playwright install chromium`. Report commands and actual outcomes, including blocked checks. Review `git status` and list changed files. Use mocked downloader tests; live network checks must be reported separately.

The original supplied checklist also names Docker, Gradle, pos-web, and ecommerce-web. This new project has none of those components; do not introduce unrelated applications solely to satisfy that checklist.
