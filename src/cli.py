"""Portable entry points with common data/output defaults."""

import argparse
import logging
import shutil
import tempfile
from pathlib import Path
from src.config import (
    DEFAULT_DATA_ROOT,
    PROJECT_ROOT,
    BALANCED_TRIPS,
    FRONTIER_MIN_TRIPS,
    Q3_PLAN,
)


def run_question(question, argv=None):
    parser = argparse.ArgumentParser(
        description=f"Run UAV optimization {question.upper()}"
    )
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=DEFAULT_DATA_ROOT,
        help="Unpacked official D-problem data (default: data/raw)",
    )
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "results" / question)
    if question == "q1":
        parser.add_argument(
            "--rho",
            type=float,
            default=None,
            help="Override all type reserves; default: official per-type values",
        )
    elif question == "q2":
        parser.add_argument("--target-trips", type=int, default=BALANCED_TRIPS)
        parser.add_argument("--frontier-min", type=int, default=FRONTIER_MIN_TRIPS)
    elif question == "q3":
        parser.add_argument("--plan", type=Path, default=Q3_PLAN)
    elif question == "q4":
        parser.add_argument(
            "--q3-dir", type=Path, default=PROJECT_ROOT / "results" / "q3"
        )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    (args.out.parent / "validation.json").unlink(missing_ok=True)
    if question == "q1":
        from src.q1.physics_engine import solve_q1

        return solve_q1(args.root, args.rho, args.out)
    if question == "q2":
        from src.q2.tradeoff import solve_q2

        return solve_q2(args.root, args.out, args.target_trips, args.frontier_min)
    if question == "q3":
        from src.q3.solver import solve_q3

        return solve_q3(args.root, args.out, args.plan)
    from src.q4.partition import solve_partitions

    return solve_partitions(args.q3_dir, args.out, args.root)


def run_all(argv=None):
    from src.q1.physics_engine import solve_q1
    from src.q2.tradeoff import solve_q2
    from src.q3.solver import solve_q3
    from src.q4.partition import solve_partitions
    from src.validation import validate_results

    parser = argparse.ArgumentParser(
        description="Run Q1-Q4 and recompute validation from official inputs"
    )
    parser.add_argument("root", nargs="?", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "results")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.resolve() == args.root.resolve():
        raise ValueError("Output root must differ from official data root")
    # Build a complete validated generation before replacing existing outputs.
    with tempfile.TemporaryDirectory(
        prefix=".uav-run-", dir=args.out.parent
    ) as directory:
        stage = Path(directory) / "results"
        if args.out.exists():
            shutil.copytree(args.out, stage)
        else:
            stage.mkdir()
        (stage / "validation.json").unlink(missing_ok=True)
        solve_q1(args.root, out_dir=stage / "q1")
        solve_q2(args.root, stage / "q2")
        solve_q3(args.root, stage / "q3")
        solve_partitions(stage / "q3", stage / "q4", args.root)
        summary = validate_results(args.root, stage)
        backup = Path(directory) / "previous"
        if args.out.exists():
            args.out.rename(backup)
        try:
            stage.rename(args.out)
        except OSError:
            if backup.exists():
                backup.rename(args.out)
            raise
    logging.info("Full validation passed: %s", summary)
    return summary
