"""Portable entry points with common data/output defaults."""

import argparse
import logging
import shutil
import tempfile
from pathlib import Path
from src.config import (
    DEFAULT_DATA_ROOT,
    PROJECT_ROOT,
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
        parser.add_argument(
            "--target-trips",
            type=int,
            default=None,
            help="Optional fixed trip count; default uses the configured Pareto target",
        )
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
    if question == "q3":
        for name in ("continuous_communication.json", "communication_replay.json"):
            (args.out.parent / name).unlink(missing_ok=True)
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
        from time import perf_counter
        from src.core.io import write_json
        import platform
        import hashlib
        import scipy
        import numpy

        runtimes = {}
        for question, solve in (
            ("Q1", lambda: solve_q1(args.root, out_dir=stage / "q1")),
            ("Q2", lambda: solve_q2(args.root, stage / "q2")),
            ("Q3", lambda: solve_q3(args.root, stage / "q3")),
            ("Q4", lambda: solve_partitions(stage / "q3", stage / "q4", args.root)),
        ):
            started = perf_counter()
            solve()
            runtimes[question] = perf_counter() - started
        started = perf_counter()
        summary = validate_results(args.root, stage)
        write_json(
            stage / "run_metadata.json",
            dict(
                solver_runtime_s=runtimes,
                validation_runtime_s=perf_counter() - started,
                python=platform.python_version(),
                platform=platform.platform(),
                numpy=numpy.__version__,
                scipy=scipy.__version__,
                algorithm_sha256={
                    str(p.relative_to(PROJECT_ROOT)): hashlib.sha256(
                        p.read_bytes()
                    ).hexdigest()
                    for folder in ("src", "config")
                    for p in sorted((PROJECT_ROOT / folder).rglob("*"))
                    if p.is_file() and p.suffix in (".py", ".json")
                },
            ),
        )
        # Reporting consumes the validated generations; solvers never consume
        # historical result tables. Do not retain a stale comparison after reruns.
        (stage / "algorithm_comparison.csv").unlink(missing_ok=True)
        baseline = PROJECT_ROOT / "archive/baseline-bf2e053/recomputed"
        if (baseline / "validation.json").is_file():
            from scripts.compare_algorithms import main as compare_algorithms

            compare_algorithms(["--baseline", str(baseline), "--results", str(stage)])
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
