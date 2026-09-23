"""Recompute constraints from official inputs, including Q3 communication."""

from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import DEFAULT_DATA_ROOT, PROJECT_ROOT
from src.validation import validate_results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--results", type=Path, default=PROJECT_ROOT / "results")
    args = parser.parse_args()
    print(validate_results(args.root, args.results))


if __name__ == "__main__":
    main()
