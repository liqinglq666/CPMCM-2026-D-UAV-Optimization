"""Exact small timing cases including both official component charging pieces."""

from copy import deepcopy
from dataclasses import replace

import pytest

from src.core.models import Resource
from src.core.routes import evaluate_route
from src.core.communication import RelaySpec, Communication
from src.core.inputs import RelayInputs, CommunicationInputs
from src.core.energy import two_stage_charge_time
from src.q3.solver import optimize_timing
from src.q3.preparation import PlanPreparer


@pytest.fixture
def relay_inputs():
    spec = RelaySpec(
        takeoff_mass_kg=23.5,
        cruise_speed_mps=15,
        cruise_power_kw=1.15,
        usable_energy_kwh=3.2,
        reserve_fraction=0.2,
        prep_s=180,
        link_setup_s=30,
        turnaround_s=300,
        climb_speed_mps=4,
        descent_speed_mps=3,
        climb_efficiency=0.72,
        hover_power_kw=1.05,
        communication_power_kw=0.05,
        max_hover_agl_m=300,
    )
    return RelayInputs(spec, ("R1", "R2"), ("RB1", "RB2"), 1800)


@pytest.mark.parametrize(
    "fixed,regime", [(0.05, "above_knee_soc"), (0.5, "below_knee_soc")]
)
def test_lp_component_reuse_respects_literal_two_stage_charge(
    physics, boxes, relay_inputs, fixed, regime
):
    cargo = [replace(b, hard_deadline=None, expected=100000) for b in boxes]
    box_map = {b.id: b for b in cargo}
    jobs = [
        dict(
            id=f"J{i}",
            type="T",
            drone=f"U{i}",
            battery=f"B{i}",
            relay=f"R{i}",
            profile=evaluate_route(physics, "T", [b], [b.service]),
            outage=(100, 150),
        )
        for i, b in enumerate(cargo)
    ]
    relays = [
        dict(
            id=f"R{i}",
            drone=f"relay-{i}",
            component="shared",
            charge_regime=regime,
            travel=dict(lead=10, inbound=5, fixed_energy=fixed),
        )
        for i in range(2)
    ]
    times = optimize_timing(
        jobs,
        relays,
        box_map,
        physics.types,
        relay_inputs.spec,
        relay_inputs.full_charge_s,
    )
    first_service = times["end", "R0"] - times["begin", "R0"]
    energy = fixed + 1.1 * first_service / 3600
    charge = two_stage_charge_time(1800, 1 - energy / 3.2)
    first_return = times["end", "R0"] + 5
    next_start = times["begin", "R1"] - 10
    assert next_start >= first_return + charge - 1e-5
    assert first_service == pytest.approx(60, abs=1e-5)  # 50 s outage + two 5 s guards
    if regime == "above_knee_soc":
        assert 1 - energy / 3.2 >= 0.9 - 1e-8
    else:
        assert 1 - energy / 3.2 <= 0.9 + 1e-8


def test_lp_hard_deadline_is_a_constraint_not_a_penalty(physics, boxes, relay_inputs):
    box_map = {b.id: replace(b, hard_deadline=0) for b in boxes}
    jobs = [
        dict(
            id=f"J{i}",
            type="T",
            drone="U",
            battery="B",
            relay=None,
            profile=evaluate_route(physics, "T", [b], [b.service]),
            outage=None,
        )
        for i, b in enumerate(boxes)
    ]
    with pytest.raises(RuntimeError, match="infeasible"):
        optimize_timing(jobs, [], box_map, physics.types, relay_inputs.spec)


def test_plan_preparation_is_pure_and_audits_one_second(physics, boxes, relay_inputs):
    communication = Communication(
        physics, CommunicationInputs(2400, 10, 20, 200, 200, 200)
    )
    plan = dict(
        jobs=[
            dict(
                id="J",
                type="T",
                drone="U",
                battery="B",
                boxes=[b.id for b in boxes],
                route=[b.service for b in boxes],
                relay=None,
            )
        ],
        relays=[],
    )
    frozen = deepcopy(plan)
    preparer = PlanPreparer(
        physics,
        {b.id: b for b in boxes},
        [Resource("U", "T")],
        [Resource("B", "T")],
        relay_inputs,
        communication,
        1.0,
    )
    jobs, relays = preparer.prepare(plan)
    assert plan == frozen
    assert not relays
    assert jobs[0]["checked_states"] > 100
    assert jobs[0]["outage"] is None
    # Exact-coordinate memoization must not collapse neighboring locations.
    a = (109.001500001, 23.9985, 20.0)
    b = (109.001500002, 23.9985, 20.0)
    before = preparer.link.cache_info().misses
    preparer.link(a, communication.gateway, 200)
    preparer.link(b, communication.gateway, 200)
    assert preparer.link.cache_info().misses == before + 2


def test_coarse_communication_cannot_be_a_final_acceptance(
    physics, boxes, relay_inputs, tmp_path
):
    from src.q3.search import search_plan

    communication = Communication(
        physics, CommunicationInputs(2400, 10, 20, 200, 200, 200)
    )
    with pytest.raises(ValueError, match="step <= 1 s"):
        search_plan(
            {},
            physics,
            {b.id: b for b in boxes},
            [],
            [],
            relay_inputs,
            communication,
            2.0,
            {},
            tmp_path,
        )


@pytest.mark.parametrize("mutation", ["energy", "soc", "overlap", "backhaul"])
def test_independent_relay_validator_rejects_invalid_sorties(
    physics, relay_inputs, mutation
):
    from src.core.communication import relay_travel
    from src.core.constraints import validate_relays

    comm = Communication(physics, CommunicationInputs(2400, 10, 20, 200, 200, 200))
    node = physics.nodes["S001"]
    point = (node.lon, node.lat, physics.terrain.elevation(node.lon, node.lat) + 300)
    travel = relay_travel(physics, relay_inputs.spec, point)
    begin, end = travel["lead"], travel["lead"] + 100
    energy = travel["fixed_energy"] + 1.1 * 100 / 3600
    row = {
        "中继架次编号": "R",
        "中继无人机编号": "R1",
        "能源组件编号": "RB1",
        "开始时刻_s": 0,
        "悬停经度": point[0],
        "悬停纬度": point[1],
        "悬停海拔_m": point[2],
        "建链完成时刻_s": begin,
        "服务结束时刻_s": end,
        "返回O01时刻_s": end + travel["inbound"],
        "架次能耗_kWh": energy,
        "返航SOC_pct": 100 * (1 - energy / 3.2),
    }
    validate_relays([row], physics, relay_inputs, comm)
    rows = [dict(row)]
    if mutation == "energy":
        rows[0]["架次能耗_kWh"] = 0
    elif mutation == "soc":
        rows[0]["返航SOC_pct"] = 100
    elif mutation == "overlap":
        rows.append(dict(row, **{"中继架次编号": "second"}))
    else:
        comm = Communication(physics, CommunicationInputs(2400, 10, 20, 200, 200, 0))
    with pytest.raises(ValueError):
        validate_relays(rows, physics, relay_inputs, comm)
