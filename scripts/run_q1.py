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

from src.q1.physics_engine import solve_q1


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CPMCM 2026 D Q1")
    parser.add_argument("root", type=Path, help="Root directory of unpacked official D-problem data")
    parser.add_argument("--rho", type=float, default=0.20, help="Return reserve, e.g. 0.20")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "results" / "q1")
    args = parser.parse_args()

    solve_q1(args.root, rho=args.rho, out_dir=args.out)


if __name__ == "__main__":
    main()
