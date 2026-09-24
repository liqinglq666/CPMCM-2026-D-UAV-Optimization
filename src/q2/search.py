"""Seeded variable-neighborhood search over the freshly rebuilt merge frontier.

Exact conditional transport timing, heuristic discrete search. The incumbent
and every archive entry are hard-feasible. Occasional feasible perturbations
explore beyond local minima without ever replacing the protected incumbent
with a worse objective. No historical result is read here.
"""

import random
from time import perf_counter

from src.core.discrete import (
    TransportEvaluator,
    TRANSPORT_MOVES,
    fingerprint,
    q2_objective,
    improves,
    dominates,
    transport_neighbor,
)
from src.core.io import write_csv, write_json
from .tradeoff import Profile, solution_rows


def discrete_plan(result):
    return [
        dict(
            id=f"job-{i}",
            type=j["profile"].type_code,
            drone=j["drone"],
            battery=j["battery"],
            boxes=sorted(j["ids"]),
            route=list(j["profile"].order),
        )
        for i, j in enumerate(
            sorted(result["jobs"], key=lambda j: (j["start"], j["drone"]))
        )
    ]


def exportable(result, box_map):
    output = dict(result)
    rows = []
    for j in result["jobs"]:
        job, p = j["job"], j["profile"]
        latest = min(
            (
                box_map[b].hard_deadline - p.delivery[b]
                for b in job["boxes"]
                if box_map[b].hard_deadline is not None
            ),
            default=1e18,
        )
        profile = Profile(
            job["type"], job["route"], p.duration, p.energy, p.delivery, latest
        )
        rows.append(
            dict(
                group=j["group"],
                ids=set(job["boxes"]),
                profile=profile,
                drone=job["drone"],
                battery=job["battery"],
                start=j["start"],
                end=j["end"],
                delivery=j["delivery"],
                soc=j["soc"],
            )
        )
    output["jobs"] = rows
    return output


def improve_frontier(
    solutions, box_map, physics, drones, batteries, params, out_dir, target_trips=None
):
    rng = random.Random(params["seed"])
    evaluator = TransportEvaluator(physics, box_map, drones, batteries)
    started = perf_counter()
    seeds, by_count, archive = [], dict(solutions), []
    trace = []

    def retain(plan, result):
        objective = q2_objective(result)
        count = result["trips"]
        if count not in by_count or improves(
            objective, q2_objective(by_count[count][1])
        ):
            by_count[count] = (
                [set(j["boxes"]) for j in plan],
                exportable(result, box_map),
            )
        if any(dominates(o, objective) or o == objective for o, _p, _r in archive):
            return
        archive[:] = [(o, p, r) for o, p, r in archive if not dominates(objective, o)]
        archive.append((objective, plan, result))

    for count, (_groups, result) in sorted(solutions.items()):
        plan = discrete_plan(result)
        recomputed = evaluator.schedule(plan)
        seeds.append((plan, recomputed))
        retain(plan, recomputed)
    allowed = [s for s in seeds if target_trips is None or len(s[0]) == target_trips]
    if not allowed:
        raise ValueError("Requested trip count has no feasible seed")
    best_plan, best = min(allowed, key=lambda item: q2_objective(item[1]))
    current_plan, current = best_plan, best
    visited = {fingerprint(plan) for plan, _result in seeds}
    for iteration in range(1, params["q2_iterations"] + 1):
        if iteration % params["q2_restart_interval"] == 0:
            # Alternate archived tradeoffs and original seeds, not result-file replay.
            choices = seeds + [(p, r) for _o, p, r in archive]
            current_plan, current = rng.choice(choices)
        operator = TRANSPORT_MOVES[(iteration - 1) % len(TRANSPORT_MOVES)]
        status, accepted, signature = "infeasible", False, ""
        objective = None
        try:
            proposal = transport_neighbor(
                current_plan, operator, rng, evaluator, iteration
            )
            signature = fingerprint(proposal)
            if signature in visited:
                status = "duplicate"
            else:
                visited.add(signature)
                result = evaluator.schedule(proposal)
                objective = q2_objective(result)
                retain(proposal, result)
                if improves(objective, q2_objective(current)) or iteration % 79 == 0:
                    current_plan, current, accepted = proposal, result, True
                if (
                    target_trips is None or result["trips"] == target_trips
                ) and improves(objective, q2_objective(best)):
                    best_plan, best = proposal, result
                    status = "improved"
                else:
                    status = "feasible"
        except ValueError as error:
            status = str(error)
        trace.append(
            dict(
                iteration=iteration,
                operator=operator,
                status=status,
                accepted=accepted,
                candidate_objective=objective,
                best_so_far=q2_objective(best),
                plan_sha256=signature,
                elapsed_s=perf_counter() - started,
            )
        )
    elapsed = perf_counter() - started
    result = exportable(best, box_map)
    # Keep the selected plan byte-for-byte representable in the by-count output.
    by_count[result["trips"]] = ([set(j["boxes"]) for j in best_plan], result)
    frontier = [
        {
            k: sol[k]
            for k in (
                "trips",
                "makespan",
                "energy",
                "weighted_tardiness",
                "hard_violations",
            )
        }
        for _n, (_g, sol) in sorted(by_count.items(), reverse=True)
    ]
    pareto, plans = [], {}
    for i, (objective, plan, item) in enumerate(
        sorted(archive, key=lambda item: item[0])
    ):
        key = f"P{i:04d}"
        trips, deliveries = solution_rows(exportable(item, box_map), box_map)
        plans[key] = dict(trips=trips, deliveries=deliveries)
        pareto.append(
            dict(
                plan_id=key,
                weighted_tardiness=objective[0],
                trips=objective[1],
                makespan=objective[2],
                energy=objective[3],
                hard_violations=0,
            )
        )
    write_csv(out_dir / "Q2_pareto_frontier.csv", pareto)
    write_json(out_dir / "Q2_pareto_plans.json", plans)
    write_json(out_dir / "Q2_search_trace.json", trace)
    write_json(
        out_dir / "Q2_search_summary.json",
        dict(
            seed=params["seed"],
            iterations=params["q2_iterations"],
            stop_reason="iteration_budget",
            search_runtime_s=elapsed,
            pareto_points=len(pareto),
            unique_candidates=len(visited),
            baseline_objectives=[q2_objective(s[1]) for s in seeds],
            best_objective=q2_objective(best),
            target_trips=target_trips,
            exactness="heuristic discrete search; exact conditional earliest starts",
            parameters=params,
        ),
    )
    return [set(j["boxes"]) for j in best_plan], result, frontier, by_count
