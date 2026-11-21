# 本程序及代码是在人工智能工具辅助下完成的。
# AI assistance declaration (this entry point and its imported src modules)
# Tool: ChatGPT/Codex.
# Model: GPT-6 Astra (gpt-6-astra).
# Developer: OpenAI.
# Public release date: 2026-09-03.
# Release source: https://developers.openai.com/api/docs/changelog
# Use: code drafting/review, data preparation, scientific plotting, paper editing,
# and consistency checks. Model identity was confirmed by the participants.
# This submission-stage change adds disclosure only; algorithm code is unchanged.
# Original method attribution and seed provenance remain in src and config.

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
