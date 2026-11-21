"""Joint cumulative resource reassignment for fixed cargo groups/relay points.

Integer-second durations round outwards. This is a restricted neighborhood,
not a continuous-time global optimizer. The final physical LP and communication
audit recompute every accepted plan independently of the CP schedule.
"""

from collections import Counter, defaultdict
from copy import deepcopy
import math
import random
from time import perf_counter

from ortools.sat.python import cp_model

from src.config import RELAY_GUARD_S
from src.core.energy import charge_time
from src.core.discrete import fingerprint, transport_neighbor
from src.q2.columns import color_intervals
from .search import build_plan, evaluate


def improve_resources(plan, result, preparer, drones, batteries, params):
    """Regroup cargo and jointly reassign all intervals at each neighborhood."""
    rng = random.Random(params["seed"])
    best_plan, best = plan, result
    seen, trace = set(), []
    moves = ("merge", "relocate", "swap", "destroy_repair")
    for iteration in range(params.get("q3_resource_iterations", 0) + 1):
        try:
            jobs = (best_plan["jobs"] if iteration == 0 else transport_neighbor(
                best_plan["jobs"], moves[(iteration - 1) % len(moves)], rng,
                preparer, iteration,
            ))
            if len(jobs) > params["q3_trip_cap"]:
                continue
            proposal = build_plan(dict(jobs=jobs, relays=best_plan["relays"]))
            signature = fingerprint([(j["route"], j["boxes"]) for j in jobs])
            if signature in seen:
                continue
            seen.add(signature)
            candidate, checked, audit = reassign_resources(
                proposal, preparer, drones, batteries, math.ceil(best["objective"][3]) + 10,
                params.get("q3_resource_seconds", 2), params["seed"],
            )
            accepted = checked is not None and checked["objective"][2:5] < best["objective"][2:5]
            if accepted:
                best_plan, best = candidate, checked
            trace.append(dict(iteration=iteration, accepted=accepted, **audit))
        except (ValueError, RuntimeError) as error:
            trace.append(dict(iteration=iteration, status="rejected", reason=str(error)))
    return best_plan, best, dict(
        iterations=params.get("q3_resource_iterations", 0),
        initial_objective=result["objective"], selected_objective=best["objective"],
        trials=trace, exactness="heuristic regrouping; conditional integer-second resource optimization",
    )


def reassign_resources(plan, preparer, drones, batteries, horizon, time_limit=60,
                       seed=20260925):
    started = perf_counter()
    if len({r["component"] for r in plan["relays"]}) != len(plan["relays"]):
        raise ValueError("Cumulative neighborhood requires distinct relay components")
    model = cp_model.CpModel()
    horizon = math.floor(horizon)
    if horizon < 1 or time_limit <= 0:
        raise ValueError("Invalid cumulative scheduling budget")
    finish = model.new_int_var(0, horizon, "makespan")
    begin, end, travel, previous = {}, {}, {}, {}
    spec = preparer.relay_inputs.spec
    for relay in plan["relays"]:
        rid = relay["id"]
        travel[rid] = preparer.relay(relay)[1]
        begin[rid] = model.new_int_var(math.ceil(travel[rid]["lead"]), horizon, f"begin_{rid}")
        end[rid] = model.new_int_var(0, horizon, f"end_{rid}")
        model.add(end[rid] >= begin[rid])
        max_service = ((1 - spec.reserve_fraction) * spec.usable_energy_kwh
                       - travel[rid]["fixed_energy"]) * 3600 / (
                           spec.hover_power_kw + spec.communication_power_kw)
        model.add(end[rid] - begin[rid] <= math.floor(max_service))
        model.add(end[rid] + math.ceil(travel[rid]["inbound"]) <= finish)
        if relay["drone"] in previous:
            left = previous[relay["drone"]]
            gap = math.ceil(travel[left]["inbound"] + spec.turnaround_s + travel[rid]["lead"])
            model.add(begin[rid] >= end[left] + gap)
        previous[relay["drone"]] = rid
    flights, charging, choices = defaultdict(list), defaultdict(list), []
    for index, job in enumerate(plan["jobs"]):
        alternatives = []
        for code, typ in preparer.physics.types.items():
            proposal = dict(job, type=code)
            try:
                profile = preparer.profile(proposal)
            except ValueError:
                continue
            latest = min(min(preparer.boxes[b].expected,
                             math.inf if preparer.boxes[b].hard_deadline is None
                             else preparer.boxes[b].hard_deadline) - offset
                         for b, offset in profile.delivery.items())
            latest = min(math.floor(latest), horizon - math.ceil(profile.duration))
            if latest < 0:
                continue
            _count, outages = preparer.outages(proposal)
            relays = [None] if not outages else [r["id"] for r in plan["relays"]
                                                 if preparer.covers(proposal, r)]
            for rid in relays:
                active = model.new_bool_var(f"use_{index}_{code}_{rid}")
                start = model.new_int_var(0, latest, f"start_{index}_{code}_{rid}")
                flight = model.new_optional_fixed_size_interval_var(
                    start, math.ceil(profile.duration), active, f"flight_{index}_{code}_{rid}")
                charge = charge_time(typ, 1 - profile.energy / typ.energy_use)
                battery = model.new_optional_fixed_size_interval_var(
                    start, math.ceil(profile.duration + charge), active,
                    f"battery_{index}_{code}_{rid}")
                flights[code].append(flight); charging[code].append(battery)
                model.add(start + math.ceil(profile.duration) <= finish).only_enforce_if(active)
                if rid is not None:
                    model.add(begin[rid] <= start + math.floor(outages[0][0] - RELAY_GUARD_S)).only_enforce_if(active)
                    model.add(end[rid] >= start + math.ceil(outages[-1][0] + RELAY_GUARD_S)).only_enforce_if(active)
                alternatives.append(active)
                choices.append((index, code, rid, profile, charge, active, start))
        if not alternatives:
            return None, None, dict(status="no_feasible_job_variant", job=job["id"])
        model.add_exactly_one(alternatives)
    for resources, intervals in ((drones, flights), (batteries, charging)):
        inventory = Counter(r.type for r in resources)
        for code, values in intervals.items():
            model.add_cumulative(values, [1] * len(values), inventory[code])
    model.minimize(finish)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 4
    solver.parameters.random_seed = seed
    status = solver.solve(model)
    audit = dict(status=solver.status_name(status), variants=len(choices),
                 horizon_s=horizon, integer_time_unit_s=1, workers=4, seed=seed,
                 runtime_s=perf_counter() - started, global_continuous_bound=False,
                 scope="fixed cargo groups, routes, relay locations/order; outward integer seconds",
                 restricted_integer_makespan_bound_s=solver.best_objective_bound)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, None, audit
    selected = sorted([(solver.value(start), i, code, rid, profile, charge)
                       for i, code, rid, profile, charge, active, start in choices
                       if solver.value(active)], key=lambda row: (row[0], row[1]))
    jobs, flight_intervals, battery_intervals = [], defaultdict(list), defaultdict(list)
    for index, (start, old, code, rid, profile, charge) in enumerate(selected):
        job = deepcopy(plan["jobs"][old]); job.update(type=code, relay=rid)
        jobs.append(job)
        flight_intervals[code].append((index, start, start + profile.duration))
        battery_intervals[code].append((index, start, start + profile.duration + charge))
    for key, resources, intervals in (("drone", drones, flight_intervals),
                                      ("battery", batteries, battery_intervals)):
        for code, values in intervals.items():
            for index, resource in color_intervals(values, [r for r in resources if r.type == code]).items():
                jobs[index][key] = resource
    proposal = build_plan(dict(jobs=jobs, relays=plan["relays"]))
    checked = evaluate(proposal, preparer, drones, batteries)
    audit.update(integer_makespan_s=solver.objective_value,
                 recomputed_objective=checked["objective"])
    return proposal, checked, audit
