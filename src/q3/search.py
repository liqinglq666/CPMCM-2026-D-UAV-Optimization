"""Discrete transport/relay neighborhoods with exact conditional HiGHS timing.

The initial JSON is an incumbent, not an answer. Every candidate is rebuilt
from official physics, audited on the union of 1 s and 0.5 s grids, and
hard-feasible before scoring.
"""

from copy import deepcopy
from collections import Counter
import logging
import random
from time import perf_counter

import numpy as np
from pyproj import Geod

from src.config import RELAY_GUARD_S
from src.core.discrete import (
    clean_jobs,
    fingerprint,
    improves,
    transport_neighbor,
    TRANSPORT_MOVES,
    service_components,
)
from src.core.constraints import validate_transport, validate_relays, RESULT_TOLERANCE
from src.core.io import write_json
from .preparation import PlanPreparer
from .solver import optimize_timing, solution_rows

RELAY_KEYS = (
    "id",
    "drone",
    "component",
    "candidate",
    "lon",
    "lat",
    "agl_m",
    "charge_regime",
)
RELAY_MOVES = (
    "relay_point",
    "relay_match",
    "relay_order",
    "relay_drone",
    "relay_component",
    "relay_merge",
    "relay_split",
    "relay_charge_branch",
)
Q3_TOLERANCES = (0, 0, 1e-5, 1e-5, 1e-9, 0, 1e-6)
TARGET_TOLERANCES = (0, 0, 1e-5, 1e-5, 1e-9, 1e-6)


def build_plan(plan):
    return dict(
        jobs=clean_jobs(plan["jobs"]),
        relays=[
            {key: deepcopy(r[key]) for key in RELAY_KEYS if key in r}
            for r in plan["relays"]
        ],
    )


def objective(rows):
    transport, boxes, _communication, relays = rows
    return (
        0,
        0,
        sum(r["加权延误"] for r in boxes),
        max(r["返回O01时刻_s"] for r in transport + relays),
        sum(r["架次能耗_kWh"] for r in transport + relays),
        len(relays),
        sum(r["服务结束时刻_s"] - r["建链完成时刻_s"] for r in relays),
    )


def evaluate(plan, preparer, drones, batteries):
    if len(service_components(job["route"] for job in plan["jobs"])) < 3:
        raise ValueError("Q3 plan cannot support the required Q4 three-way partition")
    jobs, relays = preparer.prepare(plan)
    times = optimize_timing(
        jobs,
        relays,
        preparer.boxes,
        preparer.physics.types,
        preparer.relay_inputs.spec,
        preparer.relay_inputs.full_charge_s,
    )
    rows = solution_rows(
        jobs,
        relays,
        times,
        preparer.boxes,
        preparer.physics.types,
        preparer.relay_inputs,
    )
    validate_transport(
        rows[0],
        rows[1],
        "q3",
        preparer.physics,
        list(preparer.boxes.values()),
        drones,
        batteries,
    )
    validate_relays(rows[3], preparer.physics, preparer.relay_inputs, preparer.comm)
    # prepare() audited every sampled point spatially. A fixed relay location
    # with one service interval covers all those offsets iff these extrema fit.
    for job in jobs:
        if job["outage"] is None:
            continue
        first, last = job["outage"]
        start = times["job", job["id"]]
        if (
            times["begin", job["relay"]]
            > start + first - RELAY_GUARD_S + RESULT_TOLERANCE
            or times["end", job["relay"]]
            < start + last + RELAY_GUARD_S - RESULT_TOLERANCE
        ):
            raise ValueError("Relay unavailable in the union-grid communication audit")
    return dict(jobs=jobs, relays=relays, times=times, objective=objective(rows))


def target_score(candidate, params):
    """Condition the heuristic search on declared Pareto aspiration counts."""
    value = candidate["objective"]
    return (
        abs(len(candidate["jobs"]) - params["q3_target_transport_trips"]),
        abs(len(candidate["relays"]) - params["q3_target_relay_sorties"]),
        value[2],
        value[3],
        value[4],
        value[6],
    )


def candidate_points(initial, physics, params):
    """Finite spatial neighborhood, derived from input nodes and the initial seed."""
    nodes = list(physics.nodes.values())
    points = {(r["lon"], r["lat"]) for r in initial["relays"]}
    points.update((n.lon, n.lat) for n in nodes)
    for lon in np.linspace(
        min(n.lon for n in nodes),
        max(n.lon for n in nodes),
        params["relay_grid_columns"],
    ):
        for lat in np.linspace(
            min(n.lat for n in nodes),
            max(n.lat for n in nodes),
            params["relay_grid_rows"],
        ):
            points.add((float(lon), float(lat)))
    return sorted(points)


def repair_matching(plan, preparer, rng):
    """Preserve valid assignments; repair changed routes using covering sorties."""
    preparer.precheck(plan["jobs"])
    by_id = {r["id"]: r for r in plan["relays"]}
    for job in plan["jobs"]:
        _n, outages = preparer.outages(job)
        if not outages:
            job["relay"] = None
            continue
        old = by_id.get(job.get("relay"))
        if old is not None and preparer.covers(job, old):
            continue
        alternatives = list(plan["relays"])
        rng.shuffle(alternatives)
        found = next((r for r in alternatives if preparer.covers(job, r)), None)
        if found is None:
            raise ValueError("No covering relay for repaired transport route")
        job["relay"] = found["id"]
    used = {j["relay"] for j in plan["jobs"] if j.get("relay")}
    plan["relays"] = [r for r in plan["relays"] if r["id"] in used]
    return plan


def relay_neighbor(plan, operator, rng, preparer, points, params, iteration):
    plan = build_plan(plan)
    relays = plan["relays"]
    if not relays:
        raise ValueError("No relay neighborhood in a direct-only incumbent")
    index = rng.randrange(len(relays))
    relay = relays[index]
    if operator == "relay_point":
        if rng.random() < 0.5:
            lon, lat, _az = Geod(ellps="WGS84").fwd(
                relay["lon"],
                relay["lat"],
                rng.choice((0, 90, 180, 270)),
                params["relay_local_step_m"],
            )
        else:
            lon, lat = rng.choice(points)
        relay.update(lon=lon, lat=lat, candidate="generated")
        if iteration % 5 == 0:
            relay["agl_m"] = preparer.relay_inputs.spec.max_hover_agl_m * rng.choice(
                (0.75, 1.0)
            )
        preparer.relay(relay)
    elif operator == "relay_match":
        job = rng.choice(plan["jobs"])
        alternatives = [
            r for r in relays if r["id"] != job.get("relay") and preparer.covers(job, r)
        ]
        if not alternatives:
            raise ValueError("No alternate covering relay")
        job["relay"] = rng.choice(alternatives)["id"]
    elif operator == "relay_order":
        relays.pop(index)
        relays.insert(rng.randrange(len(relays) + 1), relay)
    elif operator in ("relay_drone", "relay_component"):
        key = "drone" if operator == "relay_drone" else "component"
        resources = (
            preparer.relay_inputs.drone_ids
            if key == "drone"
            else preparer.relay_inputs.component_ids
        )
        choices = [r for r in resources if r != relay[key]]
        if not choices:
            raise ValueError("No alternate relay resource")
        relay[key] = rng.choice(choices)
    elif operator == "relay_charge_branch":
        relay["charge_regime"] = (
            "above_knee_soc"
            if relay.get("charge_regime", "below_knee_soc") == "below_knee_soc"
            else "below_knee_soc"
        )
    elif operator == "relay_merge":
        choices = [r for r in relays if r is not relay]
        if not choices:
            raise ValueError("No second relay sortie to merge")
        other = rng.choice(choices)
        for job in plan["jobs"]:
            if job.get("relay") == other["id"]:
                job["relay"] = relay["id"]
        relays.remove(other)
    elif operator == "relay_split":
        served = [j for j in plan["jobs"] if j.get("relay") == relay["id"]]
        if len(served) < 2:
            raise ValueError("No relay service group to split")
        new = deepcopy(relay)
        new["id"] = f"relay-split-{iteration}"
        new["drone"] = rng.choice(preparer.relay_inputs.drone_ids)
        used = {r["component"] for r in relays}
        components = [c for c in preparer.relay_inputs.component_ids if c not in used]
        new["component"] = rng.choice(components or preparer.relay_inputs.component_ids)
        rng.shuffle(served)
        for job in served[: rng.randrange(1, len(served))]:
            job["relay"] = new["id"]
        relays.insert(index + 1, new)
    else:
        raise ValueError("Unknown relay move")
    return plan


def search_plan(
    initial,
    physics,
    boxes,
    drones,
    batteries,
    relay_inputs,
    communication,
    step_s,
    params,
    out_dir,
):
    if step_s > 1.0:
        raise ValueError("Q3 final communication audit must use a step <= 1 s")
    started = perf_counter()
    rng = random.Random(params["seed"])
    preparer = PlanPreparer(
        physics, boxes, drones, batteries, relay_inputs, communication, step_s
    )
    initial = build_plan(initial)
    from .seed_repair import repair_seed

    initial, baseline = repair_seed(
        initial, preparer, drones, batteries, params, out_dir
    )
    if params.get("column_iterations", 0):
        from .column_schedule import improve_with_columns

        initial, baseline = improve_with_columns(
            initial, baseline, preparer, drones, batteries, params, out_dir,
        )
    best_plan, best = initial, baseline
    current_plan, current = best_plan, best
    points = candidate_points(initial, physics, params)
    moves = TRANSPORT_MOVES + RELAY_MOVES
    visited = {fingerprint(initial)}
    trace, incumbents = (
        [],
        [dict(iteration=0, plan=initial, objective=baseline["objective"])],
    )
    status_counts, operator_attempts = Counter(), Counter()
    for iteration in range(1, params["q3_iterations"] + 1):
        if iteration % params["q3_restart_interval"] == 0:
            current_plan, current = best_plan, best
        operator = moves[(iteration - 1) % len(moves)]
        operator_attempts[operator] += 1
        status, signature, accepted, value = "infeasible", "", False, None
        try:
            if operator in TRANSPORT_MOVES:
                proposal = build_plan(current_plan)
                proposal["jobs"] = transport_neighbor(
                    proposal["jobs"], operator, rng, preparer, iteration
                )
            else:
                proposal = relay_neighbor(
                    current_plan, operator, rng, preparer, points, params, iteration
                )
            proposal = repair_matching(proposal, preparer, rng)
            signature = fingerprint(proposal)
            if signature in visited:
                status = "duplicate"
            else:
                visited.add(signature)
                candidate = evaluate(proposal, preparer, drones, batteries)
                value = candidate["objective"]
                if (
                    improves(
                        target_score(candidate, params),
                        target_score(current, params),
                        TARGET_TOLERANCES,
                    )
                    or iteration % 97 == 0
                ):
                    current_plan, current, accepted = proposal, candidate, True
                status = "feasible"
                if improves(
                    target_score(candidate, params),
                    target_score(best, params),
                    TARGET_TOLERANCES,
                ):
                    best_plan, best = proposal, candidate
                    status = "improved"
                    incumbents.append(
                        dict(iteration=iteration, plan=best_plan, objective=value)
                    )
        except (ValueError, RuntimeError) as error:
            status = str(error)
        status_counts[status] += 1
        if status == "improved" or iteration % 100 == 0:
            trace.append(
                dict(
                    iteration=iteration,
                    operator=operator,
                    status=status,
                    accepted=accepted,
                    objective=value,
                    best_so_far=best["objective"],
                    best_target_score=target_score(best, params),
                    plan_sha256=signature,
                    elapsed_s=perf_counter() - started,
                )
            )
        if iteration % 100 == 0:
            logging.getLogger(__name__).info(
                "Q3 search %d/%d target=%s objective=%s",
                iteration,
                params["q3_iterations"],
                target_score(best, params),
                best["objective"],
            )
    write_json(out_dir / "Q3_search_trace.json", trace)
    write_json(out_dir / "Q3_incumbents.json", incumbents)
    write_json(out_dir / "Q3_selected_plan.json", best_plan)
    write_json(
        out_dir / "Q3_search_summary.json",
        dict(
            seed=params["seed"],
            parameters=params,
            iterations=params["q3_iterations"],
            stop_reason="iteration_budget",
            runtime_s=perf_counter() - started,
            unique_candidates=len(visited),
            initial_objective=baseline["objective"],
            best_objective=best["objective"],
            initial_target_score=target_score(baseline, params),
            best_target_score=target_score(best, params),
            status_counts=dict(status_counts),
            operator_attempts=dict(operator_attempts),
            communication_step_s=step_s,
            communication_sampling_steps_s=list(preparer.audit_steps),
            continuous_time_proof=False,
            exactness="HiGHS timing conditional on discrete decisions and charging branches; outer search heuristic",
            spatial_candidate_count=len(points),
        ),
    )
    return best_plan, best
