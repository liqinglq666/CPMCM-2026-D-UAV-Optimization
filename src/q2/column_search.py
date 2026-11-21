"""Globally regroup cargo within a finite catalogue, preserving verified seeds."""

import json
from pathlib import Path

from src.config import PROJECT_ROOT
from src.core.discrete import TransportEvaluator
from src.core.io import write_json
from .columns import cargo_classes, enumerate_columns, reconstruct
from .interval_master import IntervalMaster
from .search import discrete_plan, exportable


def improve_with_columns(result, physics, box_map, drones, batteries, params, out_dir):
    evaluator = TransportEvaluator(physics, box_map, drones, batteries)
    plans = [discrete_plan(result)]
    audit = {"seed_recomputed": False, "all_on_time_subproblem": True}
    completion = params.get("q2_selection_mode") == "completion"
    fast_seed = PROJECT_ROOT / "config/q2_completion_seed.json"
    if completion and fast_seed.is_file():
        candidate = json.loads(fast_seed.read_text(encoding="utf-8"))
        try:
            checked = evaluator.schedule(candidate)
            if len(candidate) <= params["q2_trip_cap"]:
                plans.append(candidate)
                audit["completion_seed_recomputed"] = True
        except ValueError as error:
            audit["completion_seed_rejection"] = str(error)
    seed = PROJECT_ROOT / "config/q2_column_seed.json"
    if seed.is_file():
        # A disclosed discrete warm start, not reported times or energies. It is
        # recomputed against the current official inputs and rejected on failure.
        candidate = json.loads(seed.read_text(encoding="utf-8"))
        if len(candidate) == result["trips"]:
            try:
                evaluator.schedule(candidate)
                plans.append(candidate)
                audit["seed_recomputed"] = True
            except ValueError as error:
                audit["seed_rejection"] = str(error)
    classes = cargo_classes(box_map.values())
    columns = enumerate_columns(physics, classes)
    master = IntervalMaster(
        columns, classes, drones, batteries, params["q2_column_horizon_s"],
        params["column_grid_s"], params["q2_trip_cap"] if completion else result["trips"],
        trip_penalty=params.get("column_trip_penalty", 100.0),
    )
    choices, master_audit = master.solve(
        iterations=params["column_iterations"], time_limit=params["column_mip_seconds"],
        integer_reduced_cost_limit=params.get("column_integer_reduced_cost_limit"),
    )
    audit["master"] = master_audit
    if choices:
        candidate = reconstruct(columns, choices, classes, drones, batteries)
        checked = evaluator.schedule(candidate)
        if checked["weighted_tardiness"] > 1e-5:
            raise ValueError("Column incumbent is not all on time after reconstruction")
        if completion or len(candidate) == result["trips"]:
            plans.append(candidate)
    candidates = [(plan, evaluator.schedule(plan)) for plan in plans]
    plan, best = min(candidates, key=lambda item: (
        item[1]["weighted_tardiness"], item[1]["makespan"], item[1]["energy"],
    ))
    audit.update(selected_objective={k: best[k] for k in (
        "trips", "makespan", "energy", "weighted_tardiness",
    )}, selected_plan_recomputed=True,
        selection_scope="verified discrete warm start, baseline and generated integer incumbent")
    write_json(Path(out_dir) / "Q2_column_audit.json", audit)
    return [set(job["boxes"]) for job in plan], exportable(best, box_map)
