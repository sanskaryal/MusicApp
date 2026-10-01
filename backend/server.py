"""Cadence's dependency-free local API and audio server."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from urllib.parse import parse_qs, unquote, urlsplit
import uuid

ROOT = Path(__file__).resolve().parent.parent
VIDEO_ID = re.compile(r'^[A-Za-z0-9_-]{11}$')


class APIError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def track_input(data):
    if not isinstance(data, dict) or not isinstance(data.get('id'), str) or not VIDEO_ID.fullmatch(data['id']):
        raise APIError('A valid YouTube video ID is required.')
    title = data.get('title', '')
    artist = data.get('artist', 'YouTube')
    duration = data.get('duration', 0) or 0
    if not isinstance(title, str) or not title.strip() or len(title) > 500:
        raise APIError('A song title is required (maximum 500 characters).')
    if not isinstance(artist, str) or len(artist) > 300:
        raise APIError('Invalid artist name.')
    if type(duration) not in (int, float) or not 0 <= duration <= 7200:
        raise APIError('Choose a song shorter than two hours.')
    return {'id': data['id'], 'title': title.strip(), 'artist': artist, 'duration': int(duration),
            'thumbnail': f"https://i.ytimg.com/vi/{data['id']}/hqdefault.jpg"}


class Library:
    def __init__(self, directory, runner=subprocess.run):
        self.directory = Path(directory)
        self.audio = self.directory / 'audio'
        self.audio.mkdir(parents=True, exist_ok=True)
        self.db = self.directory / 'library.sqlite3'
        self.runner = runner
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='download')
        self.lock = threading.RLock()
        self.search_slots = threading.BoundedSemaphore(2)
        self.cache = {}
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS tracks (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, artist TEXT NOT NULL,
                    duration INTEGER NOT NULL, thumbnail TEXT NOT NULL,
                    liked INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'idle',
                    error TEXT, created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS playlists (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS playlist_tracks (
                    playlist_id TEXT REFERENCES playlists(id) ON DELETE CASCADE,
                    track_id TEXT REFERENCES tracks(id), position INTEGER NOT NULL,
                    PRIMARY KEY (playlist_id, track_id));
                CREATE TABLE IF NOT EXISTS queue (
                    id TEXT PRIMARY KEY, track_id TEXT REFERENCES tracks(id), position INTEGER NOT NULL);
            ''')
            db.execute("UPDATE tracks SET status='error', error='Download interrupted. Click the song to retry.' WHERE status IN ('queued','downloading')")
            for row in db.execute("SELECT id FROM tracks WHERE status='ready'").fetchall():
                if not (self.audio / f"{row['id']}.mp3").is_file():
                    db.execute("UPDATE tracks SET status='error',error='Audio file is missing. Click to download again.' WHERE id=?", (row['id'],))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.db, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def close(self):
        self.executor.shutdown(wait=True)

    def save_track(self, data):
        song = track_input(data)
        with self.connect() as db:
            db.execute('''INSERT INTO tracks (id,title,artist,duration,thumbnail,created_at)
                VALUES (:id,:title,:artist,:duration,:thumbnail,:created_at)
                ON CONFLICT(id) DO UPDATE SET title=excluded.title, artist=excluded.artist,
                duration=excluded.duration, thumbnail=excluded.thumbnail''', {**song, 'created_at': time.time()})
        return song['id']

    def get_track(self, track_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM tracks WHERE id=?', (track_id,)).fetchone()
        if not row:
            raise APIError('Song not found.', 404)
        return dict(row)

    def state(self):
        with self.connect() as db:
            tracks = [dict(r) for r in db.execute('SELECT * FROM tracks ORDER BY created_at DESC')]
            queue = [dict(r) for r in db.execute('SELECT * FROM queue ORDER BY position')]
            playlists = []
            for row in db.execute('SELECT * FROM playlists ORDER BY created_at'):
                playlist = dict(row)
                playlist['track_ids'] = [r[0] for r in db.execute('SELECT track_id FROM playlist_tracks WHERE playlist_id=? ORDER BY position', (row['id'],))]
                playlists.append(playlist)
        return {'tracks': tracks, 'queue': queue, 'playlists': playlists}

    def search(self, query):
        query = query.strip()
        if not query or len(query) > 200:
            raise APIError('Enter a search between 1 and 200 characters.')
        with self.lock:
            cached = self.cache.get(query.casefold())
            if cached and time.monotonic() - cached[0] < 300:
                return cached[1]
        if not self.search_slots.acquire(blocking=False):
            raise APIError('Other searches are running. Try again shortly.', 429)
        try:
            result = self.runner(['yt-dlp', '--ignore-config', '--no-plugin-dirs', '--flat-playlist', '--dump-single-json',
                                  '--no-warnings', '--socket-timeout', '15', '--', f'ytsearch16:{query}'],
                                 capture_output=True, text=True, timeout=60)
            if result.returncode:
                raise APIError('YouTube search failed. Check your connection and yt-dlp installation.', 502)
            data = json.loads(result.stdout)
            songs = []
            for entry in data.get('entries', []):
                if not entry or entry.get('is_live'):
                    continue
                try:
                    songs.append(track_input({'id': entry.get('id'), 'title': entry.get('title'),
                                              'artist': entry.get('channel') or entry.get('uploader') or 'YouTube',
                                              'duration': entry.get('duration') or 0}))
                except APIError:
                    continue
            with self.lock:
                if len(self.cache) >= 50:
                    self.cache.pop(next(iter(self.cache)))
                self.cache[query.casefold()] = (time.monotonic(), songs)
            return songs
        except FileNotFoundError as exc:
            raise APIError('yt-dlp was not found on the server PATH.', 503) from exc
        except subprocess.TimeoutExpired as exc:
            raise APIError('YouTube search timed out. Please try again.', 504) from exc
        except (ValueError, TypeError) as exc:
            raise APIError('YouTube returned an unreadable response. Please retry.', 502) from exc
        finally:
            self.search_slots.release()

    def download(self, data):
        track_id = self.save_track(data)
        with self.lock:
            song = self.get_track(track_id)
            if song['status'] in ('queued', 'downloading'):
                return song
            if song['status'] == 'ready' and (self.audio / f'{track_id}.mp3').is_file():
                return song
            if not shutil.which('yt-dlp') or not shutil.which('ffmpeg'):
                raise APIError('Install yt-dlp and ffmpeg on the server before downloading.', 503)
            with self.connect() as db:
                count = db.execute("SELECT count(*) FROM tracks WHERE status IN ('queued','downloading')").fetchone()[0]
                if count >= 20:
                    raise APIError('The download queue is full. Wait for a download to finish.', 429)
                db.execute("UPDATE tracks SET status='queued',error=NULL WHERE id=?", (track_id,))
            self.executor.submit(self._download, track_id)
        return self.get_track(track_id)

    def _download(self, track_id):
        with self.connect() as db:
            db.execute("UPDATE tracks SET status='downloading' WHERE id=?", (track_id,))
        try:
            result = self.runner(['yt-dlp', '--ignore-config', '--no-plugin-dirs', '--no-playlist', '--no-warnings',
                                  '--socket-timeout', '20', '--retries', '2', '--max-filesize', '150M',
                                  '--match-filter', 'duration <= 7200 & !is_live', '-f', 'bestaudio/best',
                                  '--extract-audio', '--audio-format', 'mp3', '--audio-quality', '192K',
                                  '--no-progress', '-o', str(self.audio / f'{track_id}.%(ext)s'),
                                  '--', f'https://www.youtube.com/watch?v={track_id}'],
                                 capture_output=True, text=True, timeout=600)
            target = self.audio / f'{track_id}.mp3'
            if result.returncode or not target.is_file() or target.stat().st_size == 0:
                detail = (result.stderr or 'No audio was produced. The video may exceed the download limits.').strip()[-700:]
                raise APIError(detail)
            with self.connect() as db:
                db.execute("UPDATE tracks SET status='ready',error=NULL WHERE id=?", (track_id,))
        except Exception as exc:
            message = 'Download timed out. Click the song to retry.' if isinstance(exc, subprocess.TimeoutExpired) else str(exc)
            with self.connect() as db:
                db.execute("UPDATE tracks SET status='error',error=? WHERE id=?", (message[:700], track_id))

    def mutate(self, method, path, body):
        if path == '/api/downloads' and method == 'POST':
            return self.download(body)
        if path == '/api/likes' and method == 'POST':
            if type(body.get('liked')) is not bool:
                raise APIError('liked must be a boolean.')
            track_id = self.save_track(body.get('track'))
            with self.connect() as db:
                db.execute('UPDATE tracks SET liked=? WHERE id=?', (body['liked'], track_id))
            return self.state()
        if path == '/api/queue' and method == 'POST':
            track_id = self.save_track(body.get('track'))
            with self.connect() as db:
                db.execute('INSERT INTO queue VALUES (?,?,(SELECT COALESCE(MAX(position),-1)+1 FROM queue))', (uuid.uuid4().hex, track_id))
            return self.state()
        if path == '/api/queue' and method == 'DELETE':
            with self.connect() as db:
                db.execute('DELETE FROM queue')
            return self.state()
        if path == '/api/queue' and method == 'PUT':
            ids = body.get('ids')
            if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids) or len(ids) != len(set(ids)):
                raise APIError('Provide the ordered queue entry IDs without duplicates.')
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                current = {r[0] for r in db.execute('SELECT id FROM queue')}
                if set(ids) != current:
                    raise APIError('The queue changed. Refresh and try again.', 409)
                db.executemany('UPDATE queue SET position=? WHERE id=?', enumerate(ids))
            return self.state()
        match = re.fullmatch(r'/api/queue/([a-f0-9]{32})', path)
        if match and method == 'DELETE':
            with self.connect() as db:
                if not db.execute('DELETE FROM queue WHERE id=?', (match[1],)).rowcount:
                    raise APIError('Queue entry not found.', 404)
            return self.state()
        if path == '/api/playlists' and method == 'POST':
            name = self._name(body)
            with self.connect() as db:
                db.execute('INSERT INTO playlists VALUES (?,?,?)', (uuid.uuid4().hex, name, time.time()))
            return self.state()
        match = re.fullmatch(r'/api/playlists/([a-f0-9]{32})(?:/tracks(?:/([A-Za-z0-9_-]{11}))?)?', path)
        if match:
            playlist_id, track_id = match.groups()
            with self.connect() as db:
                if not db.execute('SELECT 1 FROM playlists WHERE id=?', (playlist_id,)).fetchone():
                    raise APIError('Playlist not found.', 404)
            if path.endswith('/tracks') and method == 'POST':
                track_id = self.save_track(body.get('track'))
                with self.connect() as db:
                    db.execute('INSERT OR IGNORE INTO playlist_tracks VALUES (?,?,(SELECT COALESCE(MAX(position),-1)+1 FROM playlist_tracks WHERE playlist_id=?))', (playlist_id, track_id, playlist_id))
            elif track_id and method == 'DELETE':
                with self.connect() as db:
                    db.execute('DELETE FROM playlist_tracks WHERE playlist_id=? AND track_id=?', (playlist_id, track_id))
            elif path == f'/api/playlists/{playlist_id}' and method == 'PATCH':
                with self.connect() as db:
                    db.execute('UPDATE playlists SET name=? WHERE id=?', (self._name(body), playlist_id))
            elif path == f'/api/playlists/{playlist_id}' and method == 'DELETE':
                with self.connect() as db:
                    db.execute('DELETE FROM playlists WHERE id=?', (playlist_id,))
            else:
                raise APIError('Endpoint not found.', 404)
            return self.state()
        raise APIError('Endpoint not found.', 404)

    @staticmethod
    def _name(body):
        name = body.get('name')
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
            raise APIError('Playlist names must be between 1 and 80 characters.')
        return name.strip()


def byte_range(header, size):
    if not header:
        return 0, size - 1
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', header)
    if not match or not any(match.groups()):
        raise APIError('Invalid byte range.', 416)
    a, b = match.groups()
    if not a:
        length = int(b)
        if length <= 0:
            raise APIError('Invalid byte range.', 416)
        start, end = max(0, size - length), size - 1
    else:
        start, end = int(a), min(int(b) if b else size - 1, size - 1)
    if start >= size or start > end:
        raise APIError('Range outside audio file.', 416)
    return start, end


class Handler(BaseHTTPRequestHandler):
    server_version = 'Cadence/1.0'

    def log_message(self, format, *args):
        if os.environ.get('MUSIC_QUIET') != '1':
            super().log_message(format, *args)

    def do_GET(self):
        self.dispatch()

    def do_HEAD(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()

    do_PUT = do_PATCH = do_DELETE = do_POST

    def json(self, value, status=200):
        data = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def dispatch(self):
        try:
            path = unquote(urlsplit(self.path).path)
            library = self.server.library
            if self.command not in ('GET', 'HEAD'):
                origin = self.headers.get('Origin')
                if origin and origin not in (f"http://{self.headers.get('Host')}", f"https://{self.headers.get('Host')}"):
                    raise APIError('Cross-origin requests are not allowed.', 403)
                if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                    raise APIError('Cross-site requests are not allowed.', 403)
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 <= length <= 16384:
                    raise APIError('Request body is too large.', 413)
                if length and self.headers.get_content_type() != 'application/json':
                    raise APIError('Use application/json.', 415)
                body = json.loads(self.rfile.read(length)) if length else {}
                if not isinstance(body, dict):
                    raise APIError('Expected a JSON object.')
                self.json(library.mutate(self.command, path, body))
            elif path == '/api/health':
                self.json({'status': 'ok', 'yt_dlp': bool(shutil.which('yt-dlp')), 'ffmpeg': bool(shutil.which('ffmpeg'))})
            elif path == '/api/state':
                self.json(library.state())
            elif path == '/api/search':
                query = parse_qs(urlsplit(self.path).query).get('q', [''])[0]
                self.json({'tracks': library.search(query)})
            elif re.fullmatch(r'/api/audio/[A-Za-z0-9_-]{11}', path):
                track_id = path.rsplit('/', 1)[1]
                if library.get_track(track_id)['status'] != 'ready':
                    raise APIError('This song is not downloaded yet.', 409)
                self.file(library.audio / f'{track_id}.mp3', audio=True)
            elif path.startswith('/api/'):
                raise APIError('Endpoint not found.', 404)
            else:
                target = (self.server.webroot / path.lstrip('/')).resolve()
                if not target.is_relative_to(self.server.webroot):
                    raise APIError('Not found.', 404)
                if not target.is_file():
                    if '.' in Path(path).name:
                        raise APIError('Not found.', 404)
                    target = self.server.webroot / 'index.html'
                self.file(target)
        except APIError as exc:
            self.json({'error': str(exc)}, exc.status)
        except (ValueError, TypeError, OverflowError):
            self.json({'error': 'Invalid request.'}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            self.log_error('Unexpected error: %s', exc)
            self.json({'error': 'Unexpected server error. Please retry.'}, 500)

    def file(self, target, audio=False):
        if not target.is_file():
            raise APIError('File not found. Build the frontend or re-download the song.', 404)
        size = target.stat().st_size
        header = self.headers.get('Range') if audio else None
        try:
            start, end = byte_range(header, size)
        except APIError:
            self.send_response(416)
            self.send_header('Content-Range', f'bytes */{size}')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        self.send_response(206 if header else 200)
        self.send_header('Content-Type', 'audio/mpeg' if audio else mimetypes.guess_type(target)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        if audio:
            self.send_header('Accept-Ranges', 'bytes')
            self.send_header('Cache-Control', 'private, max-age=3600')
            if header:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        else:
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' https://i.ytimg.com data:; style-src 'self' 'unsafe-inline'; script-src 'self'; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'")
        self.end_headers()
        if self.command == 'HEAD':
            return
        with target.open('rb') as source:
            source.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = source.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)


def make_server(library, host='127.0.0.1', port=8765, webroot=None):
    server = ThreadingHTTPServer((host, port), Handler)
    server.library = library
    server.webroot = Path(webroot or ROOT / 'apps/music-web/dist').resolve()
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default=os.environ.get('MUSIC_HOST', '127.0.0.1'))
    parser.add_argument('--port', type=int, default=int(os.environ.get('MUSIC_PORT', '8765')))
    args = parser.parse_args()
    library = Library(os.environ.get('MUSIC_DATA_DIR', ROOT / 'data'))
    server = make_server(library, args.host, args.port)
    print(f'Cadence is ready at http://{args.host}:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        library.close()


if __name__ == '__main__':
    main()
