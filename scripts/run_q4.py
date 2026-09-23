from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.q4.partition import solve_partitions


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run CPMCM 2026 D Q4"
    )
    parser.add_argument(
        "--q3-dir",
        type=Path,
        default=PROJECT_ROOT / "results" / "q3",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "results" / "q4",
    )
    args = parser.parse_args()

    result = solve_partitions(
        args.q3_dir,
        args.out,
    )

    print("Atomic service groups:")
    for atom in result["atoms"]:
        print("  ", atom)


if __name__ == "__main__":
    main()
