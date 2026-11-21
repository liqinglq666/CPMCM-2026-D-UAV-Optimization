"""Adversarial coverage cases independent of the optimization search."""
from types import SimpleNamespace
import math

import numpy as np
import pytest
from rasterio.transform import from_origin

from src.core.communication import Communication
from src.core.continuous_radio import obstruction_intervals, distance_upper, certify_profile
from src.core.models import Node
from src.core.terrain import Terrain, horizontal_distance


def scene():
    terrain = Terrain(np.zeros((30, 30)), from_origin(109, 24, .0001, .0001))
    def point(col, row, z=10):
        return (* (terrain.transform * (col, row)), z)
    terrain.dem[15, 14] = 20
    anchor, first, last = point(2.5, 15.5), point(25.5, 4.5), point(25.5, 26.5)
    nodes = {k: Node(k, *p) for k, p in zip(('O01', 'A', 'B'), (anchor, first, last))}
    physics = SimpleNamespace(terrain=terrain, nodes=nodes)
    radio = SimpleNamespace(gateway_agl_m=0, frequency_mhz=2400, direct_budget_db=96,
                            access_budget_db=200, backhaul_budget_db=200, obstruction_loss_db=20)
    return physics, Communication(physics, radio), anchor, first, last


def test_thin_ridge_between_clear_phase_endpoints_is_rejected():
    physics, comm, anchor, first, last = scene()
    assert not physics.terrain.obstructed(anchor, first)
    assert not physics.terrain.obstructed(anchor, last)
    profile = SimpleNamespace(phases=[('cruise', 0, 1, 'A', 'B', 10, 10, 1)])
    result = certify_profile(profile, 0, physics, comm)
    assert result['status'] == 'FAIL'
    assert any(0 < w['time_s'] < 1 for w in result['witnesses'])
    assert result['geometric_intervals'] >= 3


def test_swept_prism_contains_all_blocked_random_rays_and_vertical_contacts():
    physics, _, anchor, first, last = scene()
    rng = np.random.default_rng(314)
    pairs = [(first, last), (first, (*first[:2], -10)), (last, last)]
    for _ in range(8):
        points = [(* (physics.terrain.transform * tuple(rng.uniform(1, 29, 2))),
                   float(rng.uniform(0, 30))) for _ in range(2)]
        pairs.append(tuple(points))
    for first, last in pairs:
        intervals = obstruction_intervals(physics.terrain, anchor, first, last)
        for t in np.linspace(0, 1, 251):
            point = tuple(a + (b-a)*t for a, b in zip(first, last))
            if physics.terrain.obstructed(anchor, point):
                assert any(a <= t <= b for a, b in intervals)
    # Exactly on a pixel corner, terrain equality is blocked, also when stationary.
    corner = (* (physics.terrain.transform * (14, 15)), 20)
    assert physics.terrain.obstructed(corner, corner)
    assert obstruction_intervals(physics.terrain, corner, corner, corner) == [(0., 1.)]


def test_service_window_interior_gap_fails_even_when_backhaul_is_valid():
    physics, comm, _, first, _ = scene()
    comm.parameters.direct_budget_db = 20
    relay = (*first[:2], 30)
    profile = SimpleNamespace(phases=[('handover', 0, 100, 'A', 'A', 10, 10, 0)])
    assert certify_profile(profile, 0, physics, comm, (relay, 0, 100))['status'] == 'PASS'
    report = certify_profile(profile, 0, physics, comm, (relay, 0, 99.999))
    assert report['status'] == 'FAIL'
    assert any(w['time_s'] > 99.999 for w in report['witnesses'])
    with pytest.raises(ValueError):
        certify_profile(profile, 0, physics, comm, min_interval_s=0)


def test_ellipsoid_distance_bound_encloses_interiors_near_pole_and_dateline():
    for anchor, first, last in [((179.8, 89.5, 1), (179.9, 89.8, 500), (-179.9, 89.8, 10)),
                                ((109, 24, 0), (109.1, 24.1, 50), (109.2, 24.2, 300))]:
        bound = distance_upper(anchor, first, last)
        for t in np.linspace(0, 1, 101):
            point = tuple(a+(b-a)*t for a,b in zip(first,last))
            assert math.hypot(horizontal_distance(anchor, point), anchor[2]-point[2]) <= bound


def test_loose_numeric_enclosure_remains_unresolved_instead_of_sampling_pass(monkeypatch):
    physics, comm, _, _, _ = scene()
    comm.parameters.direct_budget_db = 200
    monkeypatch.setattr('src.core.continuous_radio.distance_upper', lambda *args: 1e12)
    profile = SimpleNamespace(phases=[('handover', 0, .001, 'A', 'A', 10, 10, 0)])
    result = certify_profile(profile, 0, physics, comm, min_interval_s=.001)
    assert result['status'] == 'UNRESOLVED'
    assert not result['witnesses'] and result['unresolved_intervals']
