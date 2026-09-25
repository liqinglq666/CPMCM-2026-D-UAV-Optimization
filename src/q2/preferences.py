"""Time-capped energy alternatives using joint type/resource CP-SAT scheduling.

The primary fastest solution is protected. Each epsilon cap is an explicit
preference, not a relaxed deadline. Routes/cargo remain fixed in each CP solve;
all durations round outwards and the original continuous evaluator recomputes
the proposed order. No global route-space bound is claimed.
"""

from collections import Counter, defaultdict
from copy import deepcopy
import json
import math
from pathlib import Path

from ortools.sat.python import cp_model

from src.config import PROJECT_ROOT
from src.core.discrete import TransportEvaluator
from src.core.energy import charge_time
from src.core.io import write_csv, write_json
from .columns import color_intervals


def optimize_resources(jobs, evaluator, drones, batteries, horizon, seconds=5, objective="energy"):
    from src.core.numeric import positive

    positive(horizon, "time cap")
    positive(seconds, "CP time budget")
    if objective not in ("energy", "completion"):
        raise ValueError("Unknown preference objective")
    evaluator.precheck(jobs)
    model = cp_model.CpModel()
    horizon = math.floor(horizon)
    finish = model.new_int_var(0, horizon, "finish")
    flights, charging, variants = defaultdict(list), defaultdict(list), []
    energy_terms = []
    for index, job in enumerate(jobs):
        choices = []
        for code, typ in evaluator.physics.types.items():
            try:
                profile = evaluator.profile(dict(job, type=code))
            except ValueError:
                continue
            latest = min(min(evaluator.boxes[b].expected,
                             math.inf if evaluator.boxes[b].hard_deadline is None
                             else evaluator.boxes[b].hard_deadline) - offset
                         for b, offset in profile.delivery.items())
            latest = min(math.floor(latest), horizon - math.ceil(profile.duration))
            if latest < 0:
                continue
            active = model.new_bool_var(f"use_{index}_{code}")
            start = model.new_int_var(0, latest, f"start_{index}_{code}")
            charge = charge_time(typ, 1 - profile.energy / typ.energy_use)
            flights[code].append(model.new_optional_fixed_size_interval_var(
                start, math.ceil(profile.duration), active, f"flight_{index}_{code}"))
            charging[code].append(model.new_optional_fixed_size_interval_var(
                start, math.ceil(profile.duration + charge), active, f"battery_{index}_{code}"))
            model.add(start + math.ceil(profile.duration) <= finish).only_enforce_if(active)
            energy_terms.append(math.ceil(profile.energy * 1e6) * active)
            choices.append(active)
            variants.append((index, code, profile, charge, active, start))
        if not choices:
            return None, None, dict(status="no_feasible_variant", job=job["id"])
        model.add_exactly_one(choices)
    for resources, intervals in ((drones, flights), (batteries, charging)):
        inventory = Counter(r.type for r in resources)
        for code, values in intervals.items():
            model.add_cumulative(values, [1] * len(values), inventory[code])
    model.minimize(finish if objective == "completion" else sum(energy_terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.num_search_workers = 4
    solver.parameters.random_seed = 20260925
    status = solver.solve(model)
    audit = dict(status=solver.status_name(status), horizon_s=horizon, objective=objective,
                 variants=len(variants), time_limit_s=seconds, workers=4,
                 restricted_integer_objective_bound=solver.best_objective_bound,
                 objective_units="s" if objective == "completion" else "ceil(energy * 1e6)",
                 scope="fixed cargo/routes; selectable types; integer outward-rounded resource intervals",
                 global_continuous_bound=False)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, None, audit
    selected = sorted((solver.value(start), i, code, profile, charge)
                      for i, code, profile, charge, active, start in variants if solver.value(active))
    proposal, flight_intervals, battery_intervals = [], defaultdict(list), defaultdict(list)
    for j, (start, old, code, profile, charge) in enumerate(selected):
        job = deepcopy(jobs[old]); job["type"] = code
        proposal.append(job)
        flight_intervals[code].append((j, start, start + profile.duration))
        battery_intervals[code].append((j, start, start + profile.duration + charge))
    for key, resources, intervals in (("drone", drones, flight_intervals),
                                      ("battery", batteries, battery_intervals)):
        for code, values in intervals.items():
            for index, resource in color_intervals(values, [r for r in resources if r.type == code]).items():
                proposal[index][key] = resource
    checked = evaluator.schedule(proposal)
    if checked["weighted_tardiness"] > 1e-5 or checked["makespan"] > horizon + 1e-6:
        raise ValueError("Recomputed CP proposal exceeds its time/deadline constraints")
    audit["integer_objective"] = solver.objective_value
    return proposal, checked, audit


def export_preferences(primary_jobs, physics, boxes, drones, batteries, out_dir,
                       epsilons=(0.05, 0.10, 0.20), seconds=5):
    from .search import exportable
    from .tradeoff import solution_rows

    if any(not math.isfinite(e) or e <= 0 for e in epsilons):
        raise ValueError("Preference epsilons must be finite and positive")
    evaluator = TransportEvaluator(physics, boxes, drones, batteries)
    primary = evaluator.schedule(primary_jobs)
    # An explicitly selected low-count slice may allow soft tardiness. The
    # optional all-on-time energy comparison is not defined for that baseline.
    if primary["weighted_tardiness"] > 1e-5:
        directory = Path(out_dir)
        for name in ("Q2_preference_frontier.csv", "Q2_preference_plans.json"):
            (directory / name).unlink(missing_ok=True)
        write_json(directory / "Q2_preference_audit.json", dict(
            status="not_applicable", reason="Primary selection has nonzero soft tardiness",
            primary_unchanged=True))
        return []
    seeds = [("current_fastest", primary_jobs, primary)]
    for label, filename in (("previous_low_sortie", "q2_column_seed.json"),
                            ("reference_paper_recomputed", "q2_reference_seed.json")):
        path = PROJECT_ROOT / "config" / filename
        if path.is_file():
            plan = json.loads(path.read_text(encoding="utf-8"))
            try:
                checked = evaluator.schedule(plan)
            except ValueError:
                continue
            if checked["weighted_tardiness"] <= 1e-5:
                seeds.append((label, plan, checked))
    rows, plans, traces = [], {}, []
    for epsilon in (0., *epsilons):
        cap = primary["makespan"] * (1 + epsilon)
        available = [(label, plan, result) for label, plan, result in seeds if result["makespan"] <= cap + 1e-6]
        if epsilon:
            for label, plan, _result in seeds:
                candidate, checked, audit = optimize_resources(plan, evaluator, drones, batteries, cap, seconds)
                traces.append(dict(epsilon=epsilon, source=label, **audit))
                if checked is not None:
                    available.append((label + "+joint_resources", candidate, checked))
        label, plan, checked = min(available, key=lambda x: (x[2]["energy"], x[2]["makespan"], x[2]["trips"]))
        key = f"epsilon_{epsilon:g}"
        trips, deliveries = solution_rows(exportable(checked, boxes), boxes)
        last_delivery = max(t for job in checked["jobs"] for t in job["delivery"].values())
        rows.append(dict(preference=key, epsilon=epsilon, horizon_s=cap, source=label,
                         trips=checked["trips"], makespan_s=checked["makespan"],
                         last_delivery_s=last_delivery, energy_kwh=checked["energy"],
                         weighted_tardiness=checked["weighted_tardiness"]))
        plans[key] = dict(discrete_plan=plan, trips=trips, deliveries=deliveries)
    out_dir = Path(out_dir)
    write_csv(out_dir / "Q2_preference_frontier.csv", rows)
    write_json(out_dir / "Q2_preference_plans.json", plans)
    write_json(out_dir / "Q2_preference_audit.json", dict(
        reference_fastest_s=primary["makespan"], primary_unchanged=True, trials=traces,
        scope="Energy choice among recomputed seeds and fixed-route CP neighborhoods; not global Pareto optimality"))
    return rows
