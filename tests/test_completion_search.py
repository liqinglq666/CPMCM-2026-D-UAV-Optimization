"""Counterexamples for completion preference and relay relocation windows."""
from types import SimpleNamespace

import pytest

from src.q3.search import target_score
from src.q3.window_search import service_windows, start_windows
from src.q2.columns import SortieColumn


def test_completion_preference_can_choose_more_flights():
    efficient = dict(jobs=[{}] * 19, relays=[{}] * 3,
                     objective=(0, 0, 0, 7800, 68, 3, 1000))
    fast = dict(jobs=[{}] * 25, relays=[{}] * 4,
                objective=(0, 0, 0, 6000, 72, 4, 1000))
    params = dict(q3_selection_mode='completion')
    assert target_score(fast, params) < target_score(efficient, params)
    fast['objective'] = (0, 0, 1, 6000, 72, 4, 1000)
    assert target_score(efficient, params) < target_score(fast, params)


def test_four_windows_include_return_turnaround_and_new_outbound():
    relays = [dict(id=str(i), drone=str(i % 2), component=str(i)) for i in range(4)]
    preparer = SimpleNamespace(
        relay=lambda r: (None, dict(lead=100, inbound=80)),
        relay_inputs=SimpleNamespace(spec=SimpleNamespace(turnaround_s=30)),
    )
    windows = service_windows(relays, preparer, 1000, {'0': 300, '1': 400})
    assert windows == [(100, 300), (100, 400), (510, 920), (610, 920)]
    relays[3]['component'] = '0'
    with pytest.raises(ValueError, match='distinct'):
        service_windows(relays, preparer, 1000, {'0': 300, '1': 400})


def test_start_windows_reject_empty_and_keep_relay_assignment():
    columns = [SortieColumn('T', ((0, 1),), ('S',), 200, 1, 20, 700)]
    geometry = [(50, 150, (True, True, False, True))]
    relays = [dict(id=str(i)) for i in range(4)]
    windows = [(100, 180), (100, 400), (0, 900), (600, 900)]
    assert start_windows(columns, geometry, relays, windows, 1000) == [
        [(55, 245, '1'), (555, 700, '3')]
    ]
    assert start_windows(columns, [None], relays, windows, 100) == [[]]


def test_cumulative_neighborhood_keeps_full_battery_occupation(drone, monkeypatch):
    from src.core.models import Resource
    from src.q3 import resource_master

    jobs = [dict(id=f'j{i}', type='T', boxes=[f'b{i}'], route=[f'S{i}'],
                 drone='U', battery='B0', relay=None) for i in range(2)]
    preparer = SimpleNamespace(
        physics=SimpleNamespace(types={'T': drone}),
        boxes={f'b{i}': SimpleNamespace(expected=1000, hard_deadline=None) for i in range(2)},
        relay_inputs=SimpleNamespace(spec=SimpleNamespace()),
        profile=lambda j: SimpleNamespace(duration=2.1, energy=0.5,
                                         delivery={b: 1 for b in j['boxes']}),
        outages=lambda j: (2, []),
    )
    monkeypatch.setattr(resource_master, 'evaluate',
                        lambda *args: {'objective': (0, 0, 0, 4.2, 1, 0, 0)})
    plan = dict(jobs=jobs, relays=[])
    drones = [Resource('U', 'T')]
    batteries = [Resource('B0', 'T'), Resource('B1', 'T')]
    failed, _, audit = resource_master.reassign_resources(
        plan, preparer, drones, batteries[:1], 6, time_limit=2,
    )
    assert failed is None and audit['status'] == 'INFEASIBLE'
    selected, _, audit = resource_master.reassign_resources(
        plan, preparer, drones, batteries, 6, time_limit=2,
    )
    assert {j['battery'] for j in selected['jobs']} == {'B0', 'B1'}
    assert audit['integer_makespan_s'] == 6  # 2.1 s occupations round outwards
    failed, _, _ = resource_master.reassign_resources(
        plan, preparer, drones, batteries, 5, time_limit=2,
    )
    assert failed is None
    preparer.boxes['b0'].hard_deadline = 0
    failed, _, audit = resource_master.reassign_resources(
        plan, preparer, drones, batteries, 6, time_limit=2,
    )
    assert failed is None and audit['status'] == 'no_feasible_job_variant'


def test_energy_pricing_and_integer_filter_do_not_claim_global_bound(boxes):
    from src.core.models import Resource
    from src.q2.interval_master import IntervalMaster

    columns = [SortieColumn('T', ((0, 1),), ('S',), 1, energy, 0, 2)
               for energy in (1., 3.)]
    master = IntervalMaster(columns, [[boxes[0]]], [Resource('U', 'T')],
                            [Resource('B', 'T')], 3, 1, 1, trip_penalty=0)
    choices, audit = master.solve(iterations=8, time_limit=2, integer_reduced_cost_limit=0)
    assert choices[0][0] == 0
    assert audit['finite_catalogue_lp_lower_bound'] == pytest.approx(1)
    assert not audit['global_continuous_bound']
    assert audit['integer_reduced_cost_limit'] == 0
