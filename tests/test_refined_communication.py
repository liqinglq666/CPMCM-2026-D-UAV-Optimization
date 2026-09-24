"""Regressions for the 0.5 s counterexample and non-nested phase grids."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.core.communication import sample_states, Communication
from src.core.sampling import sample_audit_states, audit_steps
from src.core.inputs import load_inputs, load_relay_inputs, load_communication_inputs
from src.core.physics import Physics
from src.q3.preparation import PlanPreparer
from src.validation import validate_communication


def short_profile():
    return SimpleNamespace(
        phases=[("cruise", 0.0, 1.2, "O01", "S001", 50.0, 50.0, 1.0)],
        duration=1.2,
    )


def test_refinement_preserves_both_non_nested_grids(physics):
    profile = short_profile()
    coarse = set(sample_states(profile, physics, 1.0))
    fine = set(sample_states(profile, physics, 0.5))
    assert coarse - fine and fine - coarse
    union = list(sample_audit_states(profile, physics))
    assert set(union) == coarse | fine
    assert union == sorted(set(union))
    assert set(sample_audit_states(profile, physics, 0.25)) >= set(union)
    assert audit_steps(0.25) == (1.0, 0.5, 0.25)


@pytest.mark.parametrize("grid", [1.0, 0.5])
def test_search_and_independent_audit_reject_gap_unique_to_either_grid(physics, grid):
    profile = short_profile()
    states = set(sample_states(profile, physics, grid))
    other = set(sample_states(profile, physics, 0.5 if grid == 1.0 else 1.0))
    gap = min(states - other)[1]
    comm = SimpleNamespace(
        gateway=(0, 0, 0),
        parameters=SimpleNamespace(direct_budget_db=100),
        link=lambda point, *_args: (point != gap, 0, False),
    )
    preparer = PlanPreparer(physics, {}, [], [], None, comm, 1.0)
    preparer.profile = lambda _job: profile
    job = dict(type="T", boxes=[], route=["S001"])
    _checked, outages = preparer.outages(job)
    assert any(point == gap for _t, point in outages)
    rows = [
        {
            "运输架次编号": "J",
            "通信阶段": "全程",
            "保障方式": "直连",
            "中继架次编号": "",
            "开始时刻_s": 0,
            "结束时刻_s": 1.2,
        }
    ]
    with pytest.raises(ValueError, match="False direct-link claim"):
        validate_communication({"J": (profile, 0)}, rows, {}, physics, comm, 1.0)


def test_historical_dem_counterexample_is_reproduced_and_rejected(official_root):
    root = Path(__file__).resolve().parents[1]
    baseline = root / "archive/baseline-2a98f09"
    nodes, types, drones, batteries, boxes, dem = load_inputs(official_root)
    physics = Physics(nodes, types, dem)
    comm = Communication(physics, load_communication_inputs(official_root))
    evidence = json.loads(
        (baseline / "paper/data/communication_critical_state.json").read_text()
    )
    state = evidence["state"]
    point = tuple(state[key] for key in ("longitude", "latitude", "altitude_m"))
    available, loss, obstructed = comm.link(
        point, comm.gateway, comm.parameters.direct_budget_db
    )
    assert not available and obstructed
    assert comm.parameters.direct_budget_db - loss == pytest.approx(
        -0.15425101859619872
    )
    plan = json.loads((baseline / "results/q3/Q3_selected_plan.json").read_text())
    preparer = PlanPreparer(
        physics,
        {b.id: b for b in boxes},
        drones,
        batteries,
        load_relay_inputs(official_root),
        comm,
        1.0,
    )
    job = next(j for j in plan["jobs"] if j["id"] == state["trip"])
    relay = next(r for r in plan["relays"] if r["id"] == job["relay"])
    profile = preparer.profile(job)
    coarse_outages = [
        p
        for _t, p in sample_states(profile, physics, 1.0)
        if not comm.link(p, comm.gateway, comm.parameters.direct_budget_db)[0]
    ]
    relay_point, _travel = preparer.relay(relay)
    assert all(
        comm.link(p, relay_point, comm.parameters.access_budget_db)[0]
        for p in coarse_outages
    )
    assert not preparer.covers(job, relay)
    with pytest.raises(ValueError, match="Uncovered union-grid"):
        preparer.prepare(plan)


def test_unrepairable_seed_cannot_be_returned_as_incumbent(monkeypatch, tmp_path):
    from src.q3.seed_repair import repair_seed
    import src.q3.search as search

    def impossible(*_args):
        raise ValueError("uncovered")

    monkeypatch.setattr(search, "evaluate", impossible)
    preparer = SimpleNamespace(precheck=lambda _jobs: None, covers=lambda *_args: False)
    plan = {
        "jobs": [{"relay": "R"}],
        "relays": [{"id": "R", "lon": 109.0, "lat": 23.0}],
    }
    with pytest.raises(ValueError, match="No spatial seed repair"):
        repair_seed(
            plan,
            preparer,
            [],
            [],
            {"q3_repair_radius_factors": [0.1], "relay_local_step_m": 250.0},
            tmp_path,
        )
