"""Paths for reproducible manuscript figures; original inputs stay read-only."""
from pathlib import Path
import os

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO
FINAL = REPO / 'paper/final'
DATA = REPO / 'paper/figure_data_v2'
FONT_DIR = FINAL / 'fonts'
RAW = Path(os.environ.get('UAV_DATA_ROOT', REPO / 'data/raw')).resolve()
OUT = Path(os.environ.get('UAV_FIGURE_OUT', REPO / 'outputs/figures_v2')).resolve()
WORK = Path(os.environ.get('UAV_FIGURE_QA', REPO / 'outputs/figure_qa_v2')).resolve()
for p in (DATA, OUT, WORK):
    p.mkdir(parents=True, exist_ok=True)

def source_path(path):
    p = Path(path).resolve()
    if p.is_relative_to(RAW):
        return 'raw-input/' + p.relative_to(RAW).as_posix()
    return p.relative_to(REPO).as_posix()
