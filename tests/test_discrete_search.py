"""Behavioral counterexamples for feasible-incumbent search and exact timing."""

from collections import Counter
from copy import deepcopy
from dataclasses import replace
import random

import pytest

from src.core.models import Resource
from src.core.discrete import (
    TransportEvaluator,
    TRANSPORT_MOVES,
    transport_neighbor,
    improves,
    dominates,
)
from src.core.energy import charge_time
from src.q2.tradeoff import schedule_groups
from src.q2.search import improve_frontier


def resources():
    return [Resource("U1", "T"), Resource("U2", "T")], [
        Resource("BAT1", "T"),
        Resource("BAT2", "T"),
    ]


def jobs(boxes):
    return [
        dict(
            id=f"J{i}",
            type="T",
            drone="U1",
            battery="BAT1",
            boxes=[box.id],
            route=[box.service],
        )
        for i, box in enumerate(boxes)
    ]


def test_fixed_resource_order_waits_for_full_recharge(physics, boxes):
    drones, batteries = resources()
    evaluator = TransportEvaluator(physics, {b.id: b for b in boxes}, drones, batteries)
    plan = jobs(boxes)
    plan[1]["drone"] = "U2"
    result = evaluator.schedule(plan)
    first, second = result["jobs"]
    expected = first["end"] + charge_time(physics.types["T"], first["soc"] / 100)
    assert second["start"] == pytest.approx(expected)
    plan[1]["battery"] = "BAT2"
    assert evaluator.schedule(plan)["jobs"][1]["start"] == 0


def test_coupled_rebuild_uses_parallel_inventory_without_changing_cargo(physics, boxes):
    from src.core.resource_rebuild import rebuild_resources

    drones, batteries = resources()
    evaluator = TransportEvaluator(physics, {b.id: b for b in boxes}, drones, batteries)
    plan = jobs(boxes)
    frozen = deepcopy(plan)
    rebuilt = rebuild_resources(plan, evaluator)
    result = evaluator.schedule(rebuilt)
    assert all(job["start"] == 0 for job in result["jobs"])
    assert result["makespan"] < evaluator.schedule(plan)["makespan"]
    assert [j["boxes"] for j in rebuilt] == [j["boxes"] for j in plan]
    assert plan == frozen


def test_coupled_rebuild_retains_battery_recharge_wait(physics, boxes):
    from src.core.resource_rebuild import rebuild_resources

    drones, batteries = resources()
    evaluator = TransportEvaluator(physics, {b.id: b for b in boxes}, drones, batteries[:1])
    rebuilt = rebuild_resources(jobs(boxes), evaluator)
    first, second = evaluator.schedule(rebuilt)["jobs"]
    assert second["start"] == pytest.approx(
        first["end"] + charge_time(physics.types["T"], first["soc"] / 100)
    )


@pytest.mark.parametrize(
    "change",
    ["duplicate", "missing", "mass", "volume", "deadline", "battery_type", "energy"],
)
def test_precheck_rejects_real_constraint_violations(physics, boxes, change):
    drones, batteries = resources()
    cargo = list(boxes)
    plan = jobs(cargo)
    if change == "duplicate":
        plan[1]["boxes"] = [cargo[0].id]
    elif change == "missing":
        plan.pop()
    elif change == "mass":
        cargo[0] = replace(cargo[0], mass=21)
    elif change == "volume":
        cargo[0] = replace(cargo[0], volume=1.1)
    elif change == "deadline":
        cargo[0] = replace(cargo[0], hard_deadline=1)
    elif change == "battery_type":
        plan[0]["battery"] = "unknown"
    else:
        physics.types["T"] = replace(physics.types["T"], rho=0.99999)
    evaluator = TransportEvaluator(physics, {b.id: b for b in cargo}, drones, batteries)
    with pytest.raises(ValueError):
        evaluator.schedule(plan)


def test_lexicographic_priorities_cannot_buy_deadline_or_communication_violations():
    from src.q3.search import Q3_TOLERANCES

    feasible = (0, 0, 100, 1000, 10, 2, 100)
    assert not improves((1, 0, 0, 0, 0, 0, 0), feasible, Q3_TOLERANCES)
    assert not improves((0, 1, 0, 0, 0, 0, 0), feasible, Q3_TOLERANCES)
    assert improves((0, 0, 99, 2000, 20, 3, 200), feasible, Q3_TOLERANCES)
    assert not dominates((99, 3, 2000, 20), (100, 2, 1000, 10))


def test_all_transport_moves_preserve_cargo_or_explicitly_reject(physics, boxes):
    drones, batteries = resources()
    physics.types["V"] = replace(physics.types["T"], code="V")
    drones.append(Resource("U3", "V"))
    batteries.append(Resource("BAT3", "V"))
    cargo = [replace(box, id=f"{box.id}-{i}") for i in range(3) for box in boxes]
    evaluator = TransportEvaluator(physics, {b.id: b for b in cargo}, drones, batteries)
    plan = jobs(cargo)
    frozen = deepcopy(plan)
    for index, operator in enumerate(TRANSPORT_MOVES):
        for seed in range(8):
            try:
                proposed = transport_neighbor(
                    plan, operator, random.Random(seed), evaluator, index
                )
            except ValueError:
                continue
            assert Counter(b for j in proposed for b in j["boxes"]) == Counter(
                b.id for b in cargo
            )
            for job in proposed:
                assert set(job["route"]) == {
                    evaluator.boxes[b].service for b in job["boxes"]
                }
    assert plan == frozen


def test_rejected_neighborhood_keeps_baseline_and_records_stop(
    physics, boxes, tmp_path, monkeypatch
):
    import src.q2.search as search
    import json

    drones, batteries = resources()
    box_map = {b.id: b for b in boxes}
    groups = [{b.id for b in boxes}]
    baseline = schedule_groups(
        groups, box_map, physics, physics.types, drones, batteries
    )

    def impossible(*_args):
        raise ValueError("deliberate infeasible neighborhood")

    monkeypatch.setattr(search, "transport_neighbor", impossible)
    parameters = dict(seed=7, q2_iterations=12, q2_restart_interval=5)
    _groups, selected, _frontier, _solutions = improve_frontier(
        {1: (groups, baseline)},
        box_map,
        physics,
        drones,
        batteries,
        parameters,
        tmp_path,
    )
    for key in ("trips", "energy", "makespan", "weighted_tardiness"):
        assert selected[key] == pytest.approx(baseline[key])
    trace = json.loads((tmp_path / "Q2_search_trace.json").read_text())
    assert len(trace) == 12
    assert all(not row["accepted"] for row in trace)
    assert (
        json.loads((tmp_path / "Q2_search_summary.json").read_text())["stop_reason"]
        == "iteration_budget"
    )


def test_pareto_validator_rejects_a_dominated_feasible_plan(physics, boxes, tmp_path):
    from src.q2.tradeoff import solution_rows
    from src.core.io import write_csv, write_json
    from src.validation import validate_pareto

    drones, batteries = resources()
    box_map = {b.id: b for b in boxes}
    result = schedule_groups(
        [{b.id for b in boxes}], box_map, physics, physics.types, drones, batteries
    )
    trips, deliveries = solution_rows(result, box_map)
    delayed_trips, delayed_deliveries = deepcopy(trips), deepcopy(deliveries)
    for row in delayed_trips:
        row["开始时刻（s）"] += 10
        row["返回O01时刻（s）"] += 10
    for row in delayed_deliveries:
        row["交付完成时刻（s）"] += 10
    rows = [
        dict(
            plan_id=key,
            trips=1,
            makespan=result["makespan"] + delay,
            weighted_tardiness=0,
            energy=result["energy"],
            hard_violations=0,
        )
        for key, delay in (("P0", 0), ("P1", 10))
    ]
    write_csv(tmp_path / "Q2_pareto_frontier.csv", rows)
    write_json(
        tmp_path / "Q2_pareto_plans.json",
        {
            "P0": dict(trips=trips, deliveries=deliveries),
            "P1": dict(trips=delayed_trips, deliveries=delayed_deliveries),
        },
    )
    with pytest.raises(ValueError, match="dominated"):
        validate_pareto(tmp_path, physics, boxes, drones, batteries)
