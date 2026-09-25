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
from src.core.resource_rebuild import rebuild_resources, reorder_and_rebuild


FIXED_COUNT_MOVES = tuple(
    move for move in TRANSPORT_MOVES if move not in ("merge", "split")
)


def target_score(result):
    """Search score inside a fixed trip-count Pareto slice.

    Hard deadlines are enforced by ``TransportEvaluator``.  At an explicitly
    selected trip count, weighted tardiness is optimized first, followed by makespan and
    energy.  The global archive still uses the full nondominance
    relation and therefore does not turn this search preference into a claim
    of global optimality.
    """
    return (
        result["weighted_tardiness"],
        result["makespan"],
        result["energy"],
    )


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
    selection_score = target_score if target_trips is not None else q2_objective
    best_plan, best = min(allowed, key=lambda item: selection_score(item[1]))
    current_plan, current = best_plan, best
    visited = {fingerprint(plan) for plan, _result in seeds}
    total_iterations = params["q2_iterations"] + params.get("q2_resource_iterations", 0)
    for iteration in range(1, total_iterations + 1):
        polishing = iteration > params["q2_iterations"]
        if iteration == params["q2_iterations"] + 1:
            current_plan, current = best_plan, best
        if iteration % params["q2_restart_interval"] == 0:
            # Fixed-count intensification returns to the protected incumbent;
            # the unrestricted mode alternates freshly generated tradeoffs.
            if target_trips is not None:
                current_plan, current = best_plan, best
            else:
                choices = seeds + [(p, r) for _o, p, r in archive]
                current_plan, current = rng.choice(choices)
        moves = FIXED_COUNT_MOVES if target_trips is not None else TRANSPORT_MOVES
        operator = moves[(iteration - 1) % len(moves)]
        if polishing and iteration % 2 == 0:
            operator = "resource_rebuild"
        status, accepted, signature = "infeasible", False, ""
        objective = None
        try:
            if operator == "resource_rebuild":
                proposal = reorder_and_rebuild(current_plan, evaluator, rng)
            else:
                proposal = transport_neighbor(
                    current_plan, operator, rng, evaluator, iteration
                )
                if polishing:
                    proposal = rebuild_resources(proposal, evaluator)
            if target_trips is not None and len(proposal) != target_trips:
                raise ValueError("Fixed-count neighborhood changed trip count")
            signature = fingerprint(proposal)
            if signature in visited:
                status = "duplicate"
            else:
                visited.add(signature)
                result = evaluator.schedule(proposal)
                objective = q2_objective(result)
                retain(proposal, result)
                if (
                    selection_score(result) < selection_score(current)
                    or iteration % 97 == 0
                ):
                    current_plan, current, accepted = proposal, result, True
                if (
                    target_trips is None or result["trips"] == target_trips
                ) and selection_score(result) < selection_score(best):
                    best_plan, best = proposal, result
                    status = "improved"
                else:
                    status = "feasible"
        except ValueError as error:
            status = str(error)
        # Small test runs retain every step; production runs retain all
        # improvements plus periodic checkpoints to keep the audit compact.
        if (
            params["q2_iterations"] <= 10_000
            or status == "improved"
            or iteration % 1000 == 0
        ):
            trace.append(
                dict(
                    iteration=iteration,
                    operator=operator,
                    status=status,
                    accepted=accepted,
                    candidate_objective=objective,
                    best_so_far=q2_objective(best),
                    best_selection_score=selection_score(best),
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
            iterations=total_iterations,
            resource_polish_iterations=params.get("q2_resource_iterations", 0),
            stop_reason="iteration_budget",
            search_runtime_s=elapsed,
            pareto_points=len(pareto),
            unique_candidates=len(visited),
            baseline_objectives=[q2_objective(s[1]) for s in seeds],
            best_objective=q2_objective(best),
            best_selection_score=selection_score(best),
            target_trips=target_trips,
            exactness="heuristic discrete search; exact conditional earliest starts",
            parameters=params,
        ),
    )
    return [set(j["boxes"]) for j in best_plan], result, frontier, by_count
