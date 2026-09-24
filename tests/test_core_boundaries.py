from dataclasses import replace
import math
import numpy as np
import pytest
from src.core.energy import (
    equivalent_range,
    leg_energy,
    two_stage_charge_time,
    energy_feasible,
    flight_time,
)
from src.core.terrain import horizontal_distance
from src.core.routes import evaluate_route
from src.core.constraints import check_intervals
from src.core.discrete import service_components
from src.q1.physics_engine import SegmentPhysics, max_safe_payload, roundtrip_energy
from src.q3.communication import free_space_path_loss, link_available
from src.q3.solver import sample_states
from src.q4.partition import canonical_partitions, max_overlap


def test_distance_zero_and_known_degree():
    assert horizontal_distance((0.0, 0.0), (0.0, 0.0)) == 0
    assert horizontal_distance((0.0, 0.0), (1.0, 0.0)) == pytest.approx(
        111319.490793, abs=1e-6
    )


def test_time_and_height_units():
    assert flight_time(1000.0, 100.0, 50.0, 10.0, 2.0, 5.0) == 160.0


@pytest.mark.parametrize("payload", [-1.0, 20.01, math.nan, math.inf])
def test_invalid_payload_is_rejected(drone, payload):
    with pytest.raises(ValueError):
        equivalent_range(drone, payload)


def test_energy_zero_and_monotonic(drone):
    assert leg_energy(drone, 0.0, 0.0, 0.0) == (0.0, 0.0, 0.0)
    assert (
        leg_energy(drone, 1000.0, 0.0, 20.0)[0] > leg_energy(drone, 1000.0, 0.0, 0.0)[0]
    )
    assert (
        leg_energy(drone, 2000.0, 0.0, 10.0)[0]
        > leg_energy(drone, 1000.0, 0.0, 10.0)[0]
    )
    assert leg_energy(drone, 0.0, 10.0, 0.0)[0] > 0


@pytest.mark.parametrize(
    "distance,climb", [(-1, 0), (0, -1), (math.nan, 0), (0, math.inf)]
)
def test_invalid_energy_inputs(drone, distance, climb):
    with pytest.raises(ValueError):
        leg_energy(drone, distance, climb, 0)


def test_reserve_boundary():
    assert energy_feasible(3.2, 4.0, 0.2)
    assert not energy_feasible(3.2 + 1e-6, 4.0, 0.2)
    with pytest.raises(ValueError):
        energy_feasible(math.nan, 4.0, 0.2)


def test_payload_bisection_and_reserve_monotonic(drone):
    seg = SegmentPhysics("S001", 3500.0, 0.0, 50.0, 0.0, 0.0, 0.0, 0.0)
    payload = max_safe_payload(drone, seg)
    assert 0 < payload < drone.max_payload
    assert roundtrip_energy(drone, seg, payload - 1e-5) < 0.8 * drone.energy_use
    assert roundtrip_energy(drone, seg, payload + 1e-5) > 0.8 * drone.energy_use
    assert max_safe_payload(drone, seg, 0.3) < payload
    assert max_safe_payload(drone, replace(seg, distance=10000.0)) is None


@pytest.mark.parametrize(
    "soc,expected", [(0.0, 1800.0), (0.9, 630.0), (0.95, 315.0), (1.0, 0.0)]
)
def test_two_stage_charging(soc, expected):
    assert two_stage_charge_time(1800.0, soc) == pytest.approx(expected)


@pytest.mark.parametrize("soc", [-0.01, 1.01, math.nan, math.inf])
def test_invalid_soc_is_not_silently_clipped(soc):
    with pytest.raises(ValueError):
        two_stage_charge_time(1800.0, soc)


def test_charging_continuity():
    assert (
        abs(
            two_stage_charge_time(1800.0, 0.9 - 1e-9)
            - two_stage_charge_time(1800.0, 0.9 + 1e-9)
        )
        < 1e-4
    )


def test_terrain_boundaries_nodata(terrain):
    assert terrain.elevation(0.5, 11.5) == 0
    assert terrain.elevation(11.999, 0.001) == 0
    with pytest.raises(ValueError):
        terrain.elevation(12.0, 1.0)
    with pytest.raises(ValueError):
        terrain.maximum((0.5, 11.5), (20.0, 11.5))
    terrain.dem[0, 3] = np.nan
    with pytest.raises(ValueError):
        terrain.maximum((0.5, 11.5), (5.5, 11.5))
    with pytest.raises(ValueError):
        terrain.obstructed((0.5, 11.5, 100.0), (5.5, 11.5, 100.0))


def test_every_intersected_ridge_cell_is_checked(terrain):
    terrain.dem[1, 2] = 50
    # Short interval through row 1 / column 2 before entering row 2.
    a, b = (0.2, 11.8, 40), (4.8, 7.7, 40)
    assert terrain.maximum(a, b) == 50
    assert terrain.obstructed(a, b)
    assert not terrain.obstructed((a[0], a[1], 60), (b[0], b[1], 60))


def test_vertical_ray_within_same_pixel(terrain):
    terrain.dem[0, 0] = 20
    assert terrain.obstructed((0.5, 11.5, 10.0), (0.5, 11.5, 40.0))
    assert not terrain.obstructed((0.5, 11.5, 21.0), (0.5, 11.5, 40.0))


def test_radio_budget_boundary(terrain):
    a, b = (0.1, 11.9, 1000.0), (0.1001, 11.9, 1000.0)
    distance = horizontal_distance(a, b) / 1000
    loss = free_space_path_loss(2400.0, distance)
    assert link_available(a, b, 2400.0, loss, 10.0, terrain, terrain.dem)[0]
    assert link_available(a, b, 2400.0, loss + 1e-6, 10.0, terrain, terrain.dem)[0]
    assert not link_available(a, b, 2400.0, loss - 1e-6, 10.0, terrain, terrain.dem)[0]


def test_route_unloads_and_returns_empty(physics, boxes):
    profile = evaluate_route(physics, "T", boxes, ["S001", "S002"])
    expected = (
        physics.energy("T", "O01", "S001", 7.0)
        + physics.energy("T", "S001", "S002", 4.0)
        + physics.energy("T", "S002", "O01", 0.0)
    )
    assert profile.energy == pytest.approx(expected)
    assert profile.delivery["B1"] < profile.delivery["B2"] < profile.duration
    assert evaluate_route(physics, "T", boxes[::-1], ["S001", "S002"]) == profile
    assert physics.segment("O01", "O01").distance == 0
    assert physics.flight_time("T", "O01", "O01") == 0


@pytest.mark.parametrize("route", [[], ["S001"], ["S001", "S001", "S002"]])
def test_invalid_route_does_not_drop_boxes(physics, boxes, route):
    with pytest.raises(ValueError):
        evaluate_route(physics, "T", boxes, route)


def test_sampling_phase_endpoints_and_step(physics, boxes):
    profile = evaluate_route(physics, "T", boxes, ["S001", "S002"])
    states = list(sample_states(profile, physics, 0.7))
    times = [t for t, _ in states]
    assert max(np.diff(times)) <= 0.7 + 1e-10
    assert times[0] == profile.phases[0][1]
    assert times[-1] == profile.duration
    assert all(end in times for _ph, _start, end, *_ in profile.phases)


def test_resources_turnaround_and_nested_overlap():
    check_intervals([("A", 0.0, 10.0, "x"), ("A", 10.0, 20.0, "y")], "battery")
    with pytest.raises(ValueError, match="overlap"):
        check_intervals(
            [("A", 0.0, 20.0, "x"), ("A", 2.0, 3.0, "y"), ("A", 4.0, 5.0, "z")],
            "battery",
        )
    with pytest.raises(ValueError):
        check_intervals([("A", 2.0, 1.0, "x")], "battery")


def test_partitions_complete_and_zero_intervals():
    assert len(list(canonical_partitions(4, 2))) == 7
    assert len(list(canonical_partitions(4, 3))) == 6
    assert max_overlap([(0.0, 0.0), (0.0, 5.0)]) == 1
    for n, k in [(0, 0), (2, 3), (2, 0)]:
        with pytest.raises(ValueError):
            list(canonical_partitions(n, k))


def test_service_components_preserve_q4_partition_atoms():
    routes = (
        route
        for route in [
            ["S001", "S002"],
            ["S002", "S003"],
            ["S004"],
            ["S005", "S006"],
        ]
    )
    assert service_components(routes) == [
        ["S001", "S002", "S003"],
        ["S005", "S006"],
        ["S004"],
    ]
