"""Rebuild the figure release from frozen decisions, without any optimization."""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', type=Path, help='Directory containing the complete official D attachment')
    parser.add_argument('--out', type=Path, help='Independent output directory')
    parser.add_argument('--qa', type=Path, help='PDF inspection output directory')
    parser.add_argument('--replay', action='store_true', help='First replay the frozen Q2/Q3 plans; never optimize')
    args = parser.parse_args()
    env = dict(os.environ, PYTHONUTF8='1')
    for key, value in [('UAV_DATA_ROOT', args.raw), ('UAV_FIGURE_OUT', args.out), ('UAV_FIGURE_QA', args.qa)]:
        if value:
            env[key] = str(value.resolve())
    folder = Path(__file__).resolve().parent
    steps = (['replay_q2.py', 'replay_q3.py'] if args.replay else []) + [
        'figures_01_09.py', 'figures_10_16.py', 'figures_17_27.py',
        'finalize_evidence.py', 'qa_figures.py',
    ]
    for step in steps:
        subprocess.run([sys.executable, str(folder / step)], env=env, check=True)
    print('All 27 figures exported. PDF/PNG previews require visual review after any change.')


if __name__ == '__main__':
    main()
