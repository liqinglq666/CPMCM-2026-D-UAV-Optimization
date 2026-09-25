"""Cargo column scheduling under three relay service-window choices.

A coarse geometric screen proposes columns. Every accepted complete plan is
then independently checked on the mandatory 1 s/0.5 s union and timed by the
physical LP. Screening infeasibility is never called physical infeasibility.
Relocation uses a return to O01, turnaround and a fresh outbound flight.
"""

import json
import math
from pathlib import Path

from src.config import PROJECT_ROOT, RELAY_GUARD_S
from src.core.io import write_json
from src.core.routes import evaluate_route
from src.q2.columns import cargo_classes, enumerate_columns, reconstruct
from src.q2.interval_master import IntervalMaster
from .search import build_plan, evaluate, target_score


def screen_windows(columns, classes, preparer, relays, horizon):
    if len(relays) != 3:
        raise ValueError("Three-window seed requires exactly three relay sorties")
    spec = preparer.relay_inputs.spec
    points, travel = zip(*(preparer.relay(r) for r in relays))
    # One persistent relay; the second returns to O01 before redeployment.
    early_end = 3200.0
    service_windows = [
        (travel[0]["lead"], horizon - travel[0]["inbound"]),
        (travel[1]["lead"], early_end),
        (early_end + travel[1]["inbound"] + spec.turnaround_s + travel[2]["lead"],
         horizon - travel[2]["inbound"]),
    ]
    phase_cache = {}

    def phase_info(code, phase):
        name, start, end, source, target, z0, z1, _distance = phase
        duration = end - start
        key = (code, name, source, target)
        if key not in phase_cache:
            a, b = preparer.physics.nodes[source], preparer.physics.nodes[target]
            outage_fractions, coverage = [], [True] * 3
            count = max(1, math.ceil(duration / 5.0))
            for index in range(count + 1):
                fraction = index / count
                if name == "cruise":
                    point = (a.lon + (b.lon - a.lon) * fraction,
                             a.lat + (b.lat - a.lat) * fraction,
                             z0 + (z1 - z0) * fraction)
                else:
                    node = b if name == "descent" else a
                    point = (node.lon, node.lat, z0 + (z1 - z0) * fraction)
                if not preparer.link(point, preparer.comm.gateway,
                                     preparer.comm.parameters.direct_budget_db)[0]:
                    outage_fractions.append(fraction)
                    for relay_index, relay_point in enumerate(points):
                        if coverage[relay_index] and not preparer.link(
                            point, relay_point, preparer.comm.parameters.access_budget_db,
                        )[0]:
                            coverage[relay_index] = False
            phase_cache[key] = (
                (min(outage_fractions), max(outage_fractions), coverage)
                if outage_fractions else None
            )
        cached = phase_cache[key]
        if cached is None:
            return None
        first, last, coverage = cached
        return (start + max(0, first * duration - 5),
                start + min(duration, last * duration + 5), coverage)

    modes = []
    for column in columns:
        ids = [b.id for i, number in column.counts for b in classes[i][:number]]
        profile = evaluate_route(preparer.physics, column.type,
                                 [preparer.boxes[bid] for bid in ids], column.route)
        info = [value for phase in profile.phases
                if (value := phase_info(column.type, phase)) is not None]
        latest = min(column.latest, horizon - column.duration)
        choices = []
        if not info:
            choices = [(0.0, latest, None)]
        else:
            first, last = min(v[0] for v in info), max(v[1] for v in info)
            for index, (begin, end) in enumerate(service_windows):
                if all(v[2][index] for v in info):
                    lower = max(0.0, begin - first + RELAY_GUARD_S)
                    upper = min(latest, end - last - RELAY_GUARD_S)
                    if lower <= upper:
                        choices.append((lower, upper, relays[index]["id"]))
        modes.append(choices)
    return modes, service_windows


def improve_with_columns(baseline_plan, baseline, preparer, drones, batteries, params, out_dir):
    audit = dict(screen_step_s=5.0, acceptance_steps_s=list(preparer.audit_steps),
                 relocation="return to O01, turnaround, new outbound and link setup",
                 global_continuous_bound=False)
    candidates = [(baseline_plan, baseline)]
    seed_path = PROJECT_ROOT / "config/q3_column_seed.json"
    if not seed_path.is_file():
        return baseline_plan, baseline
    seed = build_plan(json.loads(seed_path.read_text(encoding="utf-8")))
    try:
        recomputed = evaluate(seed, preparer, drones, batteries)
        candidates.append((seed, recomputed))
        audit["seed_recomputed_objective"] = recomputed["objective"]
    except (ValueError, RuntimeError) as error:
        audit["seed_rejection"] = str(error)
    classes = cargo_classes(preparer.boxes.values())
    columns = enumerate_columns(preparer.physics, classes)
    try:
        modes, windows = screen_windows(
            columns, classes, preparer, seed["relays"], params["q3_column_horizon_s"],
        )
        master = IntervalMaster(
            columns, classes, drones, batteries, params["q3_column_horizon_s"],
            params["column_grid_s"], params["q3_target_transport_trips"],
            windows=[[(lo, hi) for lo, hi, _rid in choices] for choices in modes],
        )
        choices, certificate = master.solve(
            iterations=params["column_iterations"], time_limit=params["column_mip_seconds"],
            mip_gap=0.02,
        )
        audit.update(master=certificate, proposed_relay_service_windows=windows)
        if choices:
            jobs = reconstruct(columns, choices, classes, drones, batteries)
            expanded = [(c, start) for c, start, copies in
                        sorted(choices, key=lambda x: (x[1], x[0])) for _ in range(copies)]
            for job, (column, start) in zip(jobs, expanded):
                job["relay"] = next(rid for lo, hi, rid in modes[column] if lo <= start <= hi)
                job.pop("start", None)
            plan = build_plan(dict(jobs=jobs, relays=seed["relays"]))
            candidate = evaluate(plan, preparer, drones, batteries)
            candidates.append((plan, candidate))
            audit["integer_candidate_recomputed_objective"] = candidate["objective"]
    except (ValueError, RuntimeError) as error:
        audit["candidate_rejection"] = str(error)
    selected_plan, selected = min(candidates, key=lambda pair: target_score(pair[1], params))
    audit["selected_recomputed_objective"] = selected["objective"]
    write_json(Path(out_dir) / "Q3_column_audit.json", audit)
    return selected_plan, selected
