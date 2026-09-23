"""Counterexamples found by the audit of the merged refactor."""

from dataclasses import replace
import json
import pytest


@pytest.mark.parametrize(
    "first,second,cell",
    [
        ((0.5, 11.0, 50), (2.5, 11.0, 50), (0, 1)),
        ((1.0, 11.5, 50), (1.0, 9.5, 50), (1, 0)),
        ((0.5, 11.5, 50), (2.5, 9.5, 50), (0, 1)),
    ],
)
def test_grid_edge_and_corner_ridges_are_conservative(terrain, first, second, cell):
    terrain.dem[cell] = 100
    for start, end in ((first, second), (second, first)):
        assert terrain.maximum(start, end) == 100
        assert terrain.obstructed(start, end)


def test_q1_default_uses_each_official_type_reserve(
    physics, boxes, tmp_path, monkeypatch
):
    import src.q1.physics_engine as q1

    conservative = replace(physics.types["T"], rho=0.999)
    types = {"T": conservative}
    monkeypatch.setattr(
        q1,
        "load_inputs",
        lambda root: (physics.nodes, types, [], [], boxes[:1], physics.dem_file),
    )
    monkeypatch.setattr(q1, "save_provenance", lambda *args: None)
    # No output/provenance is expected: even an empty round trip is infeasible.
    with pytest.raises(RuntimeError, match="不存在可行组批"):
        q1.solve_q1(tmp_path, out_dir=tmp_path / "q1")


def test_failed_validation_removes_stale_success(tmp_path, monkeypatch):
    import src.validation as validation

    verdict = tmp_path / "validation.json"
    verdict.write_text('{"old_success": true}')

    def fail(*args):
        raise ValueError("source mismatch")

    monkeypatch.setattr(validation, "check_provenance", fail)
    with pytest.raises(ValueError, match="source mismatch"):
        validation.validate_results(tmp_path, tmp_path)
    assert not verdict.exists()


def test_q2_skips_types_without_physical_resources(physics, boxes):
    from src.core.models import Resource
    from src.q2.tradeoff import schedule_groups

    physics.types["UNAVAILABLE"] = replace(physics.types["T"], code="UNAVAILABLE")
    result = schedule_groups(
        [{b.id for b in boxes}],
        {b.id: b for b in boxes},
        physics,
        physics.types,
        [Resource("U1", "T")],
        [Resource("BAT1", "T")],
    )
    assert result is not None
    assert result["jobs"][0]["profile"].type_code == "T"


def test_q4_rejects_mismatched_q3_inputs_before_loading(tmp_path, monkeypatch):
    import src.q4.partition as q4
    import src.core.provenance as provenance

    (tmp_path / "input_manifest.json").write_text(json.dumps({"source": "old"}))
    monkeypatch.setattr(
        provenance, "input_fingerprints", lambda root: {"source": "new"}
    )

    def forbidden(*args):
        pytest.fail("Q4 accepted stale Q3 provenance and started loading inputs")

    monkeypatch.setattr(q4, "load_inputs", forbidden)
    with pytest.raises(ValueError, match="Stale"):
        q4.solve_partitions(tmp_path, tmp_path / "out", tmp_path)


def test_q1_mixed_type_reserves_and_explicit_override(
    physics, boxes, tmp_path, monkeypatch
):
    import src.q1.physics_engine as q1
    from src.validation import validate_q1
    from src.core.io import read_csv, write_csv

    strict = replace(physics.types["T"], rho=0.999)
    usable = replace(physics.types["T"], code="U")
    types = {"T": strict, "U": usable}
    cargo = boxes[:1]
    monkeypatch.setattr(
        q1,
        "load_inputs",
        lambda root: (physics.nodes, types, [], [], cargo, physics.dem_file),
    )
    monkeypatch.setattr(q1, "save_provenance", lambda *args: None)
    out = tmp_path / "q1"
    q1.solve_q1(tmp_path, out_dir=out)
    assert read_csv(out / "Q1_batch_solution.csv")[0]["机型编号"] == "U"
    metrics = validate_q1(out, physics.nodes, types, cargo, physics.dem_file)
    assert metrics["reserve_by_type"] == {"T": 0.999, "U": 0.2}
    payloads = read_csv(out / "Q1_max_safe_payload.csv")
    payloads[0]["U型空载可达"] = "False"
    write_csv(out / "Q1_max_safe_payload.csv", payloads)
    with pytest.raises(ValueError, match="marked unreachable"):
        validate_q1(out, physics.nodes, types, cargo, physics.dem_file)
    q1.solve_q1(tmp_path, rho=0.2, out_dir=out)
    assert validate_q1(out, physics.nodes, types, cargo, physics.dem_file)[
        "reserve_by_type"
    ] == {"T": 0.2, "U": 0.2}


@pytest.mark.parametrize("bad_slack", [1e9, float("nan"), -1])
def test_q3_metrics_cannot_invent_hard_deadline_slack(boxes, bad_slack):
    from src.validation import validate_q3_metrics

    summary = dict(
        energy_kwh=1,
        relay_energy_kwh=2,
        makespan_s=3,
        joint_makespan_s=4,
        checked_states=5,
    )
    metrics = dict(
        transport_trips=1,
        relay_sorties=1,
        transport_energy_kwh=1,
        relay_energy_kwh=2,
        transport_makespan_s=3,
        joint_makespan_s=4,
        weighted_tardiness=0,
        checked_states=5,
        communication_step_s=1,
        minimum_hard_slack_s=100,
        continuous_time_proof=False,
    )
    deliveries = [{"货箱编号": "B1", "交付完成时刻_s": 900, "加权延误": 0}]
    validate_q3_metrics(metrics, summary, [{}], [{}], deliveries, boxes, 1)
    metrics["minimum_hard_slack_s"] = bad_slack
    with pytest.raises(ValueError, match="minimum_hard_slack"):
        validate_q3_metrics(metrics, summary, [{}], [{}], deliveries, boxes, 1)


def test_core_does_not_depend_on_question_solvers():
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "core"
    for path in root.glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(
                    ("src.q1", "src.q2", "src.q3", "src.q4")
                ), path


def test_grid_boundary_nodata_is_not_ignored(terrain):
    terrain.dem[0, 1] = float("nan")
    for method in (terrain.maximum, terrain.obstructed):
        with pytest.raises(ValueError, match="NoData"):
            method((0.5, 11, 50), (2.5, 11, 50))


def test_q4_resource_counts_use_the_same_time_tolerance_as_validation():
    from src.core.constraints import check_intervals, RESULT_TOLERANCE
    from src.q4.partition import max_overlap

    touching = [(0.0, 10.0), (10.0 - RESULT_TOLERANCE / 2, 20.0)]
    check_intervals(
        [("one-UAV", start, end, str(i)) for i, (start, end) in enumerate(touching)],
        "UAV",
    )
    assert max_overlap(touching) == 1
    assert max_overlap([(0, 10), (10 - 2 * RESULT_TOLERANCE, 20)]) == 2


def test_terrain_traversal_against_independent_rectangle_intersections(terrain):
    """Brute-force every cell using line/rectangle clipping, not raster traversal."""
    import numpy as np

    rng = np.random.default_rng(20260923)
    terrain.dem[:] = rng.uniform(0, 200, terrain.shape)
    for _ in range(20):
        first = rng.uniform(0.01, 11.99, 2)
        second = rng.uniform(0.01, 11.99, 2)
        heights = rng.uniform(50, 250, 2)
        touched = []
        blocked = False
        for row in range(terrain.height):
            for col in range(terrain.width):
                enter, leave = 0.0, 1.0
                for axis, low, high in ((0, col, col + 1), (1, row, row + 1)):
                    delta = second[axis] - first[axis]
                    crossings = sorted(
                        ((low - first[axis]) / delta, (high - first[axis]) / delta)
                    )
                    enter, leave = max(enter, crossings[0]), min(leave, crossings[1])
                if enter <= leave:
                    elevation = terrain.dem[row, col]
                    touched.append(elevation)
                    ray_min = min(
                        heights[0] + t * (heights[1] - heights[0])
                        for t in (enter, leave)
                    )
                    blocked |= elevation >= ray_min
        a = (*(terrain.transform * tuple(first)), heights[0])
        b = (*(terrain.transform * tuple(second)), heights[1])
        assert terrain.maximum(a, b) == max(touched)
        assert terrain.obstructed(a, b) == blocked


def test_selected_q2_plan_must_match_saved_frontier(physics, boxes, tmp_path):
    from src.core.models import Resource
    from src.core.io import read_csv, write_csv, write_json
    from src.q2.tradeoff import schedule_groups, solution_rows
    from src.validation import validate_frontier

    drones, batteries = [Resource("U1", "T")], [Resource("BAT1", "T")]
    result = schedule_groups(
        [{b.id for b in boxes}],
        {b.id: b for b in boxes},
        physics,
        physics.types,
        drones,
        batteries,
    )
    trips, deliveries = solution_rows(result, {b.id: b for b in boxes})
    write_json(
        tmp_path / "Q2_frontier_plans.json",
        {"1": dict(trips=trips, deliveries=deliveries)},
    )
    write_csv(
        tmp_path / "Q2_tradeoff_frontier.csv",
        [
            {
                k: result[k]
                for k in (
                    "trips",
                    "energy",
                    "makespan",
                    "weighted_tardiness",
                    "hard_violations",
                )
            }
        ],
    )
    write_csv(tmp_path / "selected_trips.csv", trips)
    write_csv(tmp_path / "selected_deliveries.csv", deliveries)
    selected_trips = read_csv(tmp_path / "selected_trips.csv")
    selected_deliveries = read_csv(tmp_path / "selected_deliveries.csv")
    validate_frontier(
        tmp_path, physics, boxes, drones, batteries, selected_trips, selected_deliveries
    )
    selected_trips[0]["电池编号"] = "BAT-other"
    with pytest.raises(ValueError, match="selected frontier"):
        validate_frontier(
            tmp_path,
            physics,
            boxes,
            drones,
            batteries,
            selected_trips,
            selected_deliveries,
        )
