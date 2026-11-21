"""Counterexamples for aggregate transport resources and finite pricing bounds."""

from dataclasses import replace
import numpy as np
import pytest

from src.core.models import Resource
from src.q2.columns import SortieColumn, cargo_classes, color_intervals, reconstruct
from src.q2.interval_master import IntervalMaster


def test_interval_coloring_reuses_touching_intervals_but_rejects_overlap():
    resources = [Resource("U1", "T"), Resource("U2", "T")]
    coloring = color_intervals([(0, 0, 4), (1, 0, 2), (2, 2, 6)], resources)
    assert coloring[1] == coloring[2]
    with pytest.raises(ValueError, match="peak"):
        color_intervals([(0, 0, 4), (1, 0, 2), (2, 1, 6)], resources)


def test_cargo_symmetry_keeps_different_effective_deadlines_separate(boxes):
    first = replace(boxes[0], expected=100, hard_deadline=30)
    second = replace(first, id="duplicate-physical-box", hard_deadline=None)
    assert len(cargo_classes([first, second])) == 2
    assert len(cargo_classes([first, replace(first, id="interchangeable")])) == 1


def test_reconstruction_counts_battery_charging_not_just_flight(boxes):
    column = SortieColumn("T", ((0, 1),), (boxes[0].service,), 2, 1, 4, 20)
    classes = [[boxes[0], replace(boxes[0], id="second")]]
    drones = [Resource("U1", "T")]
    with pytest.raises(ValueError, match="peak"):
        reconstruct([column], [(0, 0, 1), (0, 2, 1)], classes,
                    drones, [Resource("B1", "T")])
    plan = reconstruct([column], [(0, 0, 1), (0, 2, 1)], classes,
                       drones, [Resource("B1", "T"), Resource("B2", "T")])
    assert plan[0]["drone"] == plan[1]["drone"]
    assert plan[0]["battery"] != plan[1]["battery"]
    assert len({b for j in plan for b in j["boxes"]}) == 2


def test_integer_master_retains_exact_delivery_and_interval_capacity(boxes):
    classes = [[boxes[0]], [boxes[1]]]
    columns = [SortieColumn("T", ((i, 1),), (box.service,), 2.1, 1, 2, 4)
               for i, box in enumerate(boxes)]
    master = IntervalMaster(columns, classes, [Resource("U", "T")],
                            [Resource("B1", "T"), Resource("B2", "T")], 6, 1, 2)
    choices, audit = master.solve(iterations=10, time_limit=10)
    assert len(choices) == 2
    starts = sorted(start for _, start, _ in choices)
    assert starts[1] - starts[0] >= 3  # outward grid occupancy, no 0.1 s overlap
    assert audit["finite_catalogue_lp_lower_bound"] <= 202 + 1e-7
    assert not audit["global_continuous_bound"]


def test_pricing_sees_unadded_columns_and_respects_relay_windows(boxes):
    columns = [SortieColumn("T", ((0, 1),), (boxes[0].service,), 1, 1, 0, 10)]
    master = IntervalMaster(columns, [[boxes[0]]], [Resource("U", "T")],
                            [Resource("B", "T")], 5, 1, 1, windows=[[(3, 4)]])
    minimum, offers = master.pricing(np.array([102.0]),
                                    np.zeros(master.resource_rows), 100)
    assert minimum == -1
    assert {slot for _, _, slot in offers} == {3, 4}
    with pytest.raises(ValueError, match="window"):
        master.add(0, 2)


def test_unpriced_cheaper_column_corrects_bound_even_when_integer_pool_is_optimal(boxes):
    columns = [SortieColumn("T", ((0, 1),), (boxes[0].service,), 1, e, 0, 0)
               for e in (5, 1)]
    master = IntervalMaster(columns, [[boxes[0]]], [Resource("U", "T")],
                            [Resource("B", "T")], 1, 1, 1)
    master.add(0, 0)  # Deliberately leave the cheaper feasible sortie ungenerated.
    choices, audit = master.solve(iterations=1, time_limit=10)
    assert choices == [(0, 0, 1)]
    assert audit["restricted_mip_dual_bound"] == pytest.approx(105)
    assert audit["finite_catalogue_lp_lower_bound"] == pytest.approx(101)
