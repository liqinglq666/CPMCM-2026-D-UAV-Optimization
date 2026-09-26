"""Validate the committed paper and its frozen sources; never run an optimizer."""
from pathlib import Path
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
import zipfile

FINAL = Path(__file__).resolve().parents[1]
REPO = FINAL.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(raw_root=None):
    manifest = json.loads((FINAL / 'manifest.json').read_text(encoding='utf-8'))
    checks = []

    def check(item, passed):
        checks.append({'item': item, 'passed': bool(passed)})

    for scope in ('files', 'frozen_sources'):
        for entry in manifest[scope]:
            path = REPO / entry['path']
            expected = {entry['sha256'], entry.get('git_blob_sha256', entry['sha256'])}
            check(entry['path'], path.is_file() and sha(path) in expected)
    for ext in ('pdf', 'svg', 'png'):
        check(f'27 {ext} figures', len(list((FINAL / 'figures').glob(f'fig_[0-9][0-9].{ext}'))) == 27)
    with zipfile.ZipFile(FINAL / 'manuscript.docx') as archive:
        xml = ET.fromstring(archive.read('word/document.xml'))
        ns = {'m':'http://schemas.openxmlformats.org/officeDocument/2006/math',
              'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
              'a':'http://schemas.openxmlformats.org/drawingml/2006/main',
              'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
        check('170 editable math objects', len(xml.findall('.//m:oMath', ns)) == 170)
        check('automatic TOC field', any('TOC ' in (e.text or '') for e in xml.findall('.//w:instrText', ns)))
        images = xml.findall('.//a:blip', ns)
        check('27 embedded figures', len(images) == 27)
        rels = ET.fromstring(archive.read('word/_rels/document.xml.rels'))
        targets = {e.get('Id'): e.get('Target') for e in rels}
        for n, image in enumerate(images, 1):
            target = targets[image.get('{' + ns['r'] + '}embed')]
            check(f'embedded figure {n} matches PNG', archive.read('word/' + target) == (FINAL / f'figures/fig_{n:02d}.png').read_bytes())
    if raw_root is not None:
        raw_root = Path(raw_root).resolve()
        entries = json.loads((FINAL / 'reports/raw_manifest.json').read_text(encoding='utf-8'))
        for entry in entries:
            relative = entry['path'].replace('\\', '/').removeprefix('work/raw_input/')
            path = raw_root / relative
            check('raw-input/' + relative, path.is_file() and sha(path) == entry['sha256'])
    failures = [c['item'] for c in checks if not c['passed']]
    return {'checks': len(checks), 'passed': len(checks)-len(failures), 'failed': len(failures),
            'failures': failures, 'raw_inputs_checked': raw_root is not None,
            'scope': 'File integrity, unchanged frozen sources, and Word structure; does not rerun optimization or replace visual review.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-root')
    args = parser.parse_args()
    result = verify(args.raw_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(1 if result['failed'] else 0)
