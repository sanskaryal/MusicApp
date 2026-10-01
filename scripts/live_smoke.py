"""Optional real-network search/download check, using temporary library storage."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.server import Library

with tempfile.TemporaryDirectory(prefix='cadence-live-') as directory:
    library = Library(directory)
    try:
        songs = library.search('Cheel Sunset Dream YouTube Audio Library')
        print(f'Search returned {len(songs)} songs', flush=True)
        song = next(song for song in songs if song['id'] == 'ysAwdX7ntjU')
        print(f'Downloading: {song["title"]} ({song["id"]})', flush=True)
        library.download(song)
        deadline = time.monotonic() + 620
        while time.monotonic() < deadline:
            current = library.get_track(song['id'])
            if current['status'] in ('ready', 'error'):
                break
            time.sleep(1)
        if current['status'] != 'ready':
            raise RuntimeError(current.get('error') or 'Download did not finish')
        audio = library.audio / f'{song["id"]}.mp3'
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration,size', '-of', 'json', str(audio)], capture_output=True, text=True, check=True)
        print(f'Download ready: {audio.stat().st_size} bytes; audio probe: {json.loads(probe.stdout)["format"]}', flush=True)
    finally:
        library.close()
