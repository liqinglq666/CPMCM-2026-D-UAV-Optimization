"""Parametric figure evidence checked against independent Q1 solves."""

from dataclasses import replace

import pytest

from scripts.paper_sensitivity import partition_reserve_limits
from src.q1.physics_engine import compute_segments, optimize_service_q1


def test_parametric_limits_match_q1_on_both_sides_of_each_transition(physics, boxes):
    cargo = [
        replace(boxes[0], id=f"P{i}", mass=m, volume=0.2)
        for i, m in enumerate((3, 5, 7, 9))
    ]
    types = {
        "T": replace(physics.types["T"], max_payload=13),
        "U": replace(physics.types["T"], code="U", max_payload=18, energy_use=5),
    }
    segment = compute_segments(physics.nodes, physics.dem_file)["S001"]
    limits = partition_reserve_limits(cargo, types, segment)
    for cap in limits.values():
        for reserve in (cap - 1e-7, cap + 1e-7):
            if not 0 <= reserve <= 1:
                continue
            expected = min(
                (k for k, maximum in limits.items() if maximum >= reserve), default=None
            )
            if expected is None:
                with pytest.raises(RuntimeError, match="不存在可行组批"):
                    optimize_service_q1("S001", cargo, types, segment, reserve)
            else:
                assert (
                    optimize_service_q1("S001", cargo, types, segment, reserve)[0]
                    == expected
                )


def test_parametric_limits_never_invent_capacity_for_oversized_box(physics, boxes):
    cargo = [replace(boxes[0], mass=1e6)]
    segment = compute_segments(physics.nodes, physics.dem_file)["S001"]
    assert partition_reserve_limits(cargo, physics.types, segment) == {}
