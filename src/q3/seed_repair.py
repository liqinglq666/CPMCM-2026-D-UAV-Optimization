"""Bounded deterministic relay relocation for a spatially invalid warm start.

Cargo, transport routes and resource order are preserved. Candidate offsets
are algorithm parameters, not changes to the radio budget or DEM. Every leaf
is rebuilt by the normal union-grid precheck, HiGHS LP and resource validators.
Failure to find a feasible leaf is explicit; an invalid seed is never retained.
"""

from copy import deepcopy
from itertools import product
from time import perf_counter

from pyproj import Geod

from src.core.discrete import improves
from src.core.io import write_json


def repair_seed(plan, preparer, drones, batteries, params, out_dir):
    from .search import build_plan, evaluate, Q3_TOLERANCES

    started = perf_counter()
    try:
        result = evaluate(plan, preparer, drones, batteries)
    except (ValueError, RuntimeError) as error:
        original_error = str(error)
    else:
        write_json(
            out_dir / "Q3_seed_repair.json",
            {
                "required": False,
                "candidate_count": 0,
                "runtime_s": perf_counter() - started,
            },
        )
        return plan, result

    preparer.precheck(plan["jobs"])
    alternatives, failed = [], []
    geod = Geod(ellps="WGS84")
    for relay in plan["relays"]:
        served = [j for j in plan["jobs"] if j.get("relay") == relay["id"]]
        if all(preparer.covers(j, relay) for j in served):
            continue
        failed.append(relay["id"])
        candidates = []
        for scale in params["q3_repair_radius_factors"]:
            for azimuth in range(0, 360, 45):
                candidate = deepcopy(relay)
                lon, lat, _ = geod.fwd(
                    relay["lon"],
                    relay["lat"],
                    azimuth,
                    params["relay_local_step_m"] * scale,
                )
                candidate.update(lon=lon, lat=lat, candidate="generated-seed-repair")
                try:
                    if all(preparer.covers(j, candidate) for j in served):
                        candidates.append(candidate)
                except ValueError:
                    # E.g. outside DEM or unavailable backhaul: reject, don't clip.
                    continue
        alternatives.append(candidates)
    if not failed or any(not group for group in alternatives):
        raise ValueError(f"No spatial seed repair found: {original_error}")

    best, trace = None, []
    budget = params["q3_repair_combination_limit"]
    combinations = 1
    for group in alternatives:
        combinations *= len(group)
    for iteration, choices in enumerate(product(*alternatives), 1):
        if iteration > budget:
            break
        candidate = build_plan(plan)
        replacements = {r["id"]: r for r in choices}
        candidate["relays"] = [
            replacements.get(r["id"], r) for r in candidate["relays"]
        ]
        value, status = None, "feasible"
        try:
            result = evaluate(candidate, preparer, drones, batteries)
            value = result["objective"]
            if best is None or improves(value, best[1]["objective"], Q3_TOLERANCES):
                best = candidate, result
                status = "improved"
        except (ValueError, RuntimeError) as error:
            status = str(error)
        trace.append(dict(iteration=iteration, status=status, objective=value))
    write_json(
        out_dir / "Q3_seed_repair.json",
        dict(
            required=True,
            original_error=original_error,
            failed_relay_groups=failed,
            spatial_candidates=[len(group) for group in alternatives],
            candidate_count=len(trace),
            combination_count=combinations,
            stop_reason="enumeration_complete"
            if combinations <= budget
            else "combination_budget",
            trace=trace,
            best_objective=best[1]["objective"] if best else None,
            runtime_s=perf_counter() - started,
        ),
    )
    if best is None:
        raise ValueError(f"No jointly feasible seed repair found: {original_error}")
    return best
