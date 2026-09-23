"""Compatibility entry for Q2."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cli import run_question

if __name__ == "__main__":
    run_question("q2")
