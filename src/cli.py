"""Portable entry points with common data/output defaults."""
import argparse
import logging
from pathlib import Path
from src.config import DEFAULT_DATA_ROOT, PROJECT_ROOT, DEFAULT_RESERVE, BALANCED_TRIPS, FRONTIER_MIN_TRIPS, Q3_PLAN


def run_question(question, argv=None):
    parser = argparse.ArgumentParser(description=f"Run UAV optimization {question.upper()}")
    parser.add_argument("root", nargs="?", type=Path, default=DEFAULT_DATA_ROOT,
                        help="Unpacked official D-problem data (default: data/raw)")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT/"results"/question)
    if question == "q1":
        parser.add_argument("--rho", type=float, default=DEFAULT_RESERVE)
    elif question == "q2":
        parser.add_argument("--target-trips", type=int, default=BALANCED_TRIPS)
        parser.add_argument("--frontier-min", type=int, default=FRONTIER_MIN_TRIPS)
    elif question == "q3":
        parser.add_argument("--plan", type=Path, default=Q3_PLAN)
    elif question == "q4":
        parser.add_argument("--q3-dir", type=Path, default=PROJECT_ROOT/"results"/"q3")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
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
    parser = argparse.ArgumentParser(description="Run Q1-Q4 and recompute validation from official inputs")
    parser.add_argument("root", nargs="?", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT/"results")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    solve_q1(args.root, out_dir=args.out/"q1")
    solve_q2(args.root, args.out/"q2")
    solve_q3(args.root, args.out/"q3")
    solve_partitions(args.out/"q3", args.out/"q4", args.root)
    summary = validate_results(args.root, args.out)
    logging.info("Full validation passed: %s", summary)
    return summary
