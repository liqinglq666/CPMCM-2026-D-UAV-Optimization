"""An independent exhaustive partition enumerator checks Q1's exact DP."""

from dataclasses import replace
import pytest
from src.q1.physics_engine import (
    compute_segments,
    feasible_batch,
    roundtrip_energy,
    roundtrip_time,
    optimize_service_q1,
)


def test_q1_dp_matches_independent_set_partition_enumeration(physics, boxes):
    cargo = [
        replace(boxes[0], id=f"B{i}", mass=m, volume=0.2)
        for i, m in enumerate((3, 5, 7, 9))
    ]
    types = {
        "T": replace(physics.types["T"], max_payload=13),
        "U": replace(physics.types["T"], code="U", max_payload=18, energy_use=5),
    }
    seg = compute_segments(physics.nodes, physics.dem_file)["S001"]

    def partitions(items):
        if not items:
            yield []
            return
        first, *rest = items
        for tail in partitions(rest):
            yield [[first]] + tail
            for index in range(len(tail)):
                yield [
                    group + [first] if i == index else group
                    for i, group in enumerate(tail)
                ]

    candidates = []
    for partition in partitions(cargo):
        choices = [[]]
        for group in partition:
            options = [
                (
                    roundtrip_energy(t, seg, sum(b.mass for b in group)),
                    roundtrip_time(t, seg, len(group)),
                )
                for t in types.values()
                if feasible_batch(t, seg, group)
            ]
            choices = [chosen + [option] for chosen in choices for option in options]
        candidates.extend(
            (len(partition), sum(e for e, _t in c), sum(t for _e, t in c))
            for c in choices
        )
    reference = min(candidates)
    result = optimize_service_q1("S001", cargo, types, seg)
    assert result[:3] == pytest.approx(reference)
