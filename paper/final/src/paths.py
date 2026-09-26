"""Repository-relative paths for the frozen manuscript's plotting programs."""
import os
from pathlib import Path

FINAL = Path(__file__).resolve().parents[1]
REPO = FINAL.parents[1]
ROOT = REPO
FONT_DIR = FINAL / 'fonts'
RAW = Path(os.environ.get('UAV_DATA_ROOT', REPO / 'data/raw')).resolve()
BUILD = Path(os.environ.get('UAV_PAPER_BUILD', REPO / 'outputs/final-paper')).resolve()
OUT = BUILD / 'figures'
WORK = BUILD / 'review'
for folder in (OUT, WORK):
    folder.mkdir(parents=True, exist_ok=True)


def source_path(path):
    """Retain external raw-input identity without embedding machine-local paths."""
    path = Path(path).resolve()
    if path.is_relative_to(RAW):
        return 'raw-input/' + path.relative_to(RAW).as_posix()
    return path.relative_to(REPO).as_posix()
