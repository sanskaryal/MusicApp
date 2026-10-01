"""Isolated browser-test server: real API/storage, deterministic search and audio."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import json

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.server import Library, make_server


def main():
    with tempfile.TemporaryDirectory(prefix='cadence-browser-') as directory:
        sample = Path(directory) / 'sample.mp3'
        subprocess.run(['ffmpeg', '-y', '-f', 'lavfi', '-i', 'sine=frequency=220:duration=12', '-q:a', '9', str(sample)], capture_output=True, check=True)
        library = Library(Path(directory) / 'library')
        def runner(command, **kwargs):
            if '--dump-single-json' in command:
                result = {'entries': [
                    {'id': 'abcdefghijk', 'title': 'Ocean lights', 'channel': 'Cadence sessions', 'duration': 12},
                    {'id': 'lmnopqrstuv', 'title': 'Sunday slow', 'channel': 'Cadence sessions', 'duration': 12}]}
                return subprocess.CompletedProcess(command, 0, json.dumps(result), '')
            track_id = command[-1].split('v=')[-1]
            shutil.copyfile(sample, library.audio / f'{track_id}.mp3')
            return subprocess.CompletedProcess(command, 0, '', '')
        library.runner = runner
        server = make_server(library, port=8766)
        print('Browser fixture ready on 8766', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            library.close()


if __name__ == '__main__':
    main()
