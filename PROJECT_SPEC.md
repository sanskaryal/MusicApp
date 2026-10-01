# Cadence — personal music player

A lightweight music library running on the user's Mac, with a responsive browser interface for desktop and phones on the same trusted network.

## Required behavior
- Search YouTube using the locally installed yt-dlp and present clean song cards.
- Clicking a song starts an asynchronous MP3 download using yt-dlp and ffmpeg, then plays the local audio. Show progress states and actionable failures; allow retries.
- Persist song metadata, ordered playback queue, liked songs and named playlists in SQLite.
- Support queue add, remove, reorder and clear; playlist create, rename, delete, add and remove songs; like and unlike.
- Provide play/pause, previous/next, seeking, volume, shuffle and repeat, with a persistent bottom player.
- Keep downloaded songs available offline. Download only content the user is authorized to save.

## Scope
Single personal library, no accounts or cloud sync. Python's standard library avoids backend dependencies. React is the only UI framework. The Mac must stay awake and run the server for phone access. Mobile autoplay rules may require a second tap after a download finishes. No guarantee of uninterrupted background playback on mobile browsers.
