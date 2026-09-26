"""Read-only integrity check for the v2 manuscript, figures, and frozen inputs."""
import hashlib
import json
import os
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
RELEASE = REPO / 'paper/final_v2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def matches(path, expected):
    if not path.is_file():
        return False
    if sha(path) == expected:
        return True
    # Permit only a Windows newline conversion of the actual working file.
    # Never substitute HEAD, which could conceal a modified working copy.
    data = path.read_bytes()
    if b'\x00' not in data and b'\r\n' in data:
        return hashlib.sha256(data.replace(b'\r\n', b'\n')).hexdigest() == expected
    return False


def main():
    manifest = json.loads((RELEASE / 'manifest.json').read_text(encoding='utf-8'))
    checked = []
    skipped = []
    for name, expected in manifest['files'].items():
        checked.append((name, matches(REPO / name, expected)))
    raw = Path(os.environ.get('UAV_DATA_ROOT', REPO / 'data/raw')).resolve()
    for name, expected in manifest['raw_sources'].items():
        path = raw / name.removeprefix('raw-input/')
        if path.is_file():
            checked.append((name, sha(path) == expected))
        else:
            skipped.append(name)
    for n in range(1, 28):
        stem = f'fig_{n:02d}'
        spec = json.loads((RELEASE / 'figures' / (stem + '_spec.json')).read_text(encoding='utf-8'))
        for ext, expected in spec['output_sha256'].items():
            checked.append((stem + '.' + ext + ' matches provenance', sha(RELEASE / 'figures' / (stem + '.' + ext)) == expected))
        checked.append((stem + ' data matches provenance', sha(RELEASE / 'figures' / (stem + '_data.json')) == spec['data_sha256']))
    failed = [name for name, ok in checked if not ok]
    print(json.dumps({'passed': len(checked) - len(failed), 'failed': failed, 'raw_inputs_unavailable': skipped,
                      'scope': 'File/source integrity only; does not replace scientific validation or visual review.'}, ensure_ascii=False, indent=2))
    return bool(failed)


if __name__ == '__main__':
    sys.exit(main())
