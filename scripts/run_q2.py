# AI-assisted development disclosure
# Tool: ChatGPT
# Model: GPT-5.6 Sol
# Developer: OpenAI
# General-availability release date: 2026-07-09
# The participating team must independently verify all modeling assumptions,
# equations, code and numerical outputs before submission.

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.q2.tradeoff import solve_q2


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CPMCM 2026 D Q2")
    parser.add_argument("root", type=Path, help="Root directory of unpacked official D-problem data")
    parser.add_argument("--target-trips", type=int, default=22, help="Target trip count on the trade-off frontier")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "results" / "q2")
    args = parser.parse_args()
    solve_q2(args.root, out_dir=args.out, target_trips=args.target_trips)


if __name__ == "__main__":
    main()
