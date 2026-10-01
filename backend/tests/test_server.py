import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from backend.server import APIError, Library, byte_range, make_server, track_input

SONG = {'id': 'abcdefghijk', 'title': 'First song', 'artist': 'Test artist', 'duration': 125}
OTHER = {**SONG, 'id': 'lmnopqrstuv', 'title': 'Second song'}


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.library = Library(self.directory.name)

    def tearDown(self):
        self.library.close()
        self.directory.cleanup()

    def test_validation_rejects_urls_traversal_and_invalid_metadata(self):
        for value in ['../file.mp3', 'https://youtube.com/watch?v=abcdefghijk', ';echo bad', None, 3]:
            with self.assertRaises(APIError):
                track_input({**SONG, 'id': value})
        for value in [-1, float('nan'), float('inf'), 7201, '5', True]:
            with self.assertRaises(APIError):
                track_input({**SONG, 'duration': value})
        self.assertEqual(track_input(SONG)['thumbnail'], 'https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg')

    def test_likes_and_collections_persist_after_restart(self):
        self.library.mutate('POST', '/api/likes', {'track': SONG, 'liked': True})
        state = self.library.mutate('POST', '/api/playlists', {'name': 'Evenings'})
        playlist = state['playlists'][0]['id']
        for _ in range(2):
            self.library.mutate('POST', f'/api/playlists/{playlist}/tracks', {'track': SONG})
        self.library.mutate('PATCH', f'/api/playlists/{playlist}', {'name': 'Night drive'})
        self.library.mutate('POST', '/api/queue', {'track': SONG})
        self.library.close()
        self.library = Library(self.directory.name)
        state = self.library.state()
        self.assertEqual(state['tracks'][0]['liked'], 1)
        self.assertEqual(state['playlists'][0]['name'], 'Night drive')
        self.assertEqual(state['playlists'][0]['track_ids'], [SONG['id']])
        self.assertEqual(len(state['queue']), 1)
        self.library.mutate('DELETE', f'/api/playlists/{playlist}/tracks/{SONG["id"]}', {})
        self.assertEqual(self.library.state()['playlists'][0]['track_ids'], [])
        self.library.mutate('DELETE', f'/api/playlists/{playlist}', {})
        self.assertEqual(len(self.library.state()['tracks']), 1)
        self.assertEqual(self.library.state()['playlists'], [])
        self.library.mutate('POST', '/api/likes', {'track': SONG, 'liked': False})
        self.assertEqual(self.library.get_track(SONG['id'])['liked'], 0)

    def test_queue_duplicate_tracks_reorder_and_conflict(self):
        for song in [SONG, OTHER, SONG]:
            self.library.mutate('POST', '/api/queue', {'track': song})
        ids = [entry['id'] for entry in self.library.state()['queue']]
        self.assertEqual(len(set(ids)), 3)
        state = self.library.mutate('PUT', '/api/queue', {'ids': ids[::-1]})
        self.assertEqual([e['id'] for e in state['queue']], ids[::-1])
        with self.assertRaises(APIError) as error:
            self.library.mutate('PUT', '/api/queue', {'ids': ids[:-1]})
        self.assertEqual(error.exception.status, 409)
        self.library.mutate('DELETE', f'/api/queue/{ids[0]}', {})
        self.assertEqual(len(self.library.state()['queue']), 2)
        self.library.mutate('DELETE', '/api/queue', {})
        self.assertEqual(self.library.state()['queue'], [])

    def test_search_filters_bad_results_and_caches(self):
        calls = []
        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, json.dumps({'entries': [
                {'id': SONG['id'], 'title': SONG['title'], 'channel': SONG['artist'], 'duration': 125},
                {'id': OTHER['id'], 'title': 'Live', 'is_live': True}, {'id': '../bad'}, None]}), '')
        self.library.runner = runner
        self.assertEqual(len(self.library.search('indie')), 1)
        self.assertEqual(len(self.library.search('INDIE')), 1)
        self.assertEqual(len(calls), 1)
        self.assertIn('--ignore-config', calls[0])
        self.assertEqual(calls[0][-1], 'ytsearch16:indie')

    def test_search_error_and_timeout(self):
        self.library.runner = lambda *a, **kw: subprocess.CompletedProcess(a, 1, '', 'network failed')
        with self.assertRaises(APIError) as error:
            self.library.search('test')
        self.assertEqual(error.exception.status, 502)
        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired('yt-dlp', 60)
        self.library.runner = timeout
        with self.assertRaises(APIError) as error:
            self.library.search('test')
        self.assertEqual(error.exception.status, 504)

    @patch('backend.server.shutil.which', return_value='/usr/bin/fake')
    def test_download_is_deduplicated_and_ready_file_reused(self, _which):
        calls = []
        gate = threading.Event()
        def runner(command, **kwargs):
            calls.append(command)
            gate.wait(3)
            (self.library.audio / f'{SONG["id"]}.mp3').write_bytes(b'fake mp3 data')
            return subprocess.CompletedProcess(command, 0, '', '')
        self.library.runner = runner
        self.library.download(SONG)
        self.library.download(SONG)
        gate.set()
        self.wait_status('ready')
        self.library.download(SONG)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][-1], f'https://www.youtube.com/watch?v={SONG["id"]}')
        self.assertIn('--no-plugin-dirs', calls[0])

    @patch('backend.server.shutil.which', return_value='/usr/bin/fake')
    def test_failed_download_can_retry(self, _which):
        self.library.runner = lambda *a, **kw: subprocess.CompletedProcess(a, 1, '', 'Video unavailable')
        self.library.download(SONG)
        self.wait_status('error')
        self.assertIn('Video unavailable', self.library.get_track(SONG['id'])['error'])
        def runner(command, **kwargs):
            (self.library.audio / f'{SONG["id"]}.mp3').write_bytes(b'mp3')
            return subprocess.CompletedProcess(command, 0, '', '')
        self.library.runner = runner
        self.library.download(SONG)
        self.wait_status('ready')
        self.assertIsNone(self.library.get_track(SONG['id'])['error'])

    def test_restart_recovers_interrupted_and_missing_files(self):
        self.library.save_track(SONG)
        self.library.save_track(OTHER)
        with self.library.connect() as db:
            db.execute("UPDATE tracks SET status='downloading' WHERE id=?", (SONG['id'],))
            db.execute("UPDATE tracks SET status='ready' WHERE id=?", (OTHER['id'],))
        self.library.close()
        self.library = Library(self.directory.name)
        self.assertTrue(all(t['status'] == 'error' for t in self.library.state()['tracks']))

    def wait_status(self, status):
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            if self.library.get_track(SONG['id'])['status'] == status:
                return
            time.sleep(.01)
        self.fail(f'Download did not reach {status}')


class HTTPTests(unittest.TestCase):
    def setUp(self):
        os.environ['MUSIC_QUIET'] = '1'
        self.directory = tempfile.TemporaryDirectory()
        self.library = Library(self.directory.name)
        self.library.save_track(SONG)
        (self.library.audio / f'{SONG["id"]}.mp3').write_bytes(b'0123456789')
        with self.library.connect() as db:
            db.execute("UPDATE tracks SET status='ready'")
        self.server = make_server(self.library, port=0, webroot=self.directory.name)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.library.close()
        self.directory.cleanup()

    def get(self, path, method='GET', data=None, headers=None):
        return urlopen(Request(self.url + path, method=method, data=data, headers=headers or {}), timeout=5)

    def test_audio_range_suffix_head_and_unsatisfiable_range(self):
        with self.get('/api/audio/abcdefghijk', headers={'Range': 'bytes=2-5'}) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.headers['Content-Range'], 'bytes 2-5/10')
            self.assertEqual(response.read(), b'2345')
        with self.get('/api/audio/abcdefghijk', headers={'Range': 'bytes=-3'}) as response:
            self.assertEqual(response.read(), b'789')
        with self.get('/api/audio/abcdefghijk', method='HEAD') as response:
            self.assertEqual(response.headers['Content-Length'], '10')
            self.assertEqual(response.read(), b'')
        with self.assertRaises(HTTPError) as error:
            self.get('/api/audio/abcdefghijk', headers={'Range': 'bytes=100-'})
        self.assertEqual(error.exception.code, 416)
        self.assertEqual(error.exception.headers['Content-Range'], 'bytes */10')
        error.exception.close()

    def test_mutation_validation_origin_and_traversal(self):
        cases = [('/api/likes', 'POST', b'{}', {'Content-Type': 'text/plain'}, 415),
                 ('/api/likes', 'POST', b'{}', {'Content-Type': 'application/json', 'Origin': 'https://evil.test'}, 403),
                 ('/api/likes', 'POST', b'[]', {'Content-Type': 'application/json'}, 400),
                 ('/api/likes', 'POST', b'{', {'Content-Type': 'application/json'}, 400),
                 ('/api/playlists', 'POST', b'{"name":""}', {'Content-Type': 'application/json'}, 400),
                 ('/api/does-not-exist', 'GET', None, {}, 404),
                 ('/%2e%2e/server.py', 'GET', None, {}, 404)]
        for path, method, data, headers, status in cases:
            with self.subTest(path=path, headers=headers):
                with self.assertRaises(HTTPError) as error:
                    self.get(path, method, data, headers)
                self.assertEqual(error.exception.code, status)
                error.exception.close()
        with self.get('/api/playlists', 'POST', b'{"name":"Sunday"}', {'Content-Type': 'application/json', 'Origin': self.url}) as response:
            self.assertEqual(json.load(response)['playlists'][0]['name'], 'Sunday')

    def test_state_and_health(self):
        with self.get('/api/state') as response:
            self.assertEqual(json.load(response)['tracks'][0]['id'], SONG['id'])
        with self.get('/api/health') as response:
            self.assertEqual(json.load(response)['status'], 'ok')


class RangeTests(unittest.TestCase):
    def test_range_bounds(self):
        self.assertEqual(byte_range('bytes=3-', 10), (3, 9))
        self.assertEqual(byte_range('bytes=0-999', 10), (0, 9))
        self.assertEqual(byte_range('bytes=-999', 10), (0, 9))
        for value in ['bytes=-0', 'bytes=5-2', 'bytes=0-1,4-6', 'bytes=-', 'items=0-1']:
            with self.assertRaises(APIError):
                byte_range(value, 10)


if __name__ == '__main__':
    unittest.main()
