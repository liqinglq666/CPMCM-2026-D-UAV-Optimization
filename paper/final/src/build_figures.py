"""Rebuild the 27 figures from existing records and the original official DEM."""
import json
import os
from pathlib import Path
import subprocess
import sys

from paths import FINAL, RAW, OUT, WORK
from verify_bundle import verify


def normalize(value):
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize(v) for v in value]
    if isinstance(value, str):
        return value.replace('\\', '/').replace('work/raw_input/', 'raw-input/').replace('work/team_repo/', '')
    return value


def main():
    result = verify(RAW)
    if result['failed']:
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    here = Path(__file__).resolve().parent
    for script in ('figures_01_09.py', 'figures_10_16.py', 'figures_17_27.py'):
        subprocess.run([sys.executable, str(here / script)], check=True, env=os.environ.copy())
    from PIL import Image, ImageChops
    checks = []
    for n in range(1, 28):
        stem = f'fig_{n:02d}'
        expected = json.loads((FINAL / 'figures' / (stem + '_data.json')).read_text(encoding='utf-8'))
        actual = json.loads((OUT / (stem + '_data.json')).read_text(encoding='utf-8'))
        data_equal = normalize(expected) == normalize(actual)
        with Image.open(FINAL / 'figures' / (stem + '.png')) as a, Image.open(OUT / (stem + '.png')) as b:
            png_equal = a.size == b.size and ImageChops.difference(a.convert('RGB'), b.convert('RGB')).getbbox() is None
        checks.append({'figure': n, 'data_equal': data_equal, 'png_pixels_equal': png_equal})
    report = {'checks': checks, 'all_data_equal': all(c['data_equal'] for c in checks),
              'all_png_pixels_equal': all(c['png_pixels_equal'] for c in checks),
              'scope': 'Only provenance path prefixes are normalized for data comparison. Different library versions may change glyph rasterization; no automated claim of new visual approval.'}
    (WORK / 'rebuild_comparison.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report['all_data_equal']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
