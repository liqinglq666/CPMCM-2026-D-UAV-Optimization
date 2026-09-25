from dataclasses import replace
from types import SimpleNamespace

import pytest

from src.core.models import Resource
from src.q2.preferences import optimize_resources
from src.q4.partition import normalized_gini


def test_normalized_gini_and_invalid_negative_work():
    assert normalized_gini([1, 1, 1]) == 0
    assert normalized_gini([0, 0, 3]) == 1
    assert normalized_gini([3, 1]) == .5
    with pytest.raises(ValueError):
        normalized_gini([1, -1])


def test_energy_preference_enforces_time_cap_and_full_battery_cycle(drone):
    fast = replace(drone, code='F')
    slow = replace(drone, code='S')
    jobs = [dict(id=f'j{i}', type='F', boxes=[f'b{i}'], route=['X'],
                 drone='UF', battery='BF0') for i in range(2)]
    def profile(job):
        return SimpleNamespace(duration=2.1 if job['type']=='F' else 5.1,
                               energy=.5 if job['type']=='F' else .1,
                               delivery={b: 1 for b in job['boxes']})
    evaluator = SimpleNamespace(physics=SimpleNamespace(types={'F':fast, 'S':slow}),
        precheck=lambda jobs: None, profile=profile,
        boxes={f'b{i}': SimpleNamespace(expected=1000, hard_deadline=None) for i in range(2)},
        schedule=lambda jobs: dict(weighted_tardiness=0, makespan=max(sum(profile(j).duration for j in jobs if j["type"]==code) for code in ("F","S"))))
    drones=[Resource('UF','F'), Resource('US','S')]
    batteries=[Resource('BF0','F'), Resource('BF1','F'), Resource('BS0','S'), Resource('BS1','S')]
    selected, _, audit=optimize_resources(jobs,evaluator,drones,batteries,6,2)
    assert {j['type'] for j in selected} == {'S','F'}  # slow can run alongside fast
    selected, _, audit=optimize_resources(jobs,evaluator,drones,batteries,12,2)
    assert {j['type'] for j in selected} == {'S'}
    assert len({j['battery'] for j in selected}) == 2  # charging forbids reuse
    selected, _, audit=optimize_resources(jobs,evaluator,drones,batteries,2,2)
    assert selected is None
    assert not audit.get('global_continuous_bound',False)


def test_exported_energy_alternative_cannot_forge_metrics(official_root, tmp_path):
    from pathlib import Path
    import shutil
    from src.core.inputs import load_inputs
    from src.core.physics import Physics
    from src.core.io import read_csv, write_csv
    from src.validation import validate_preferences

    root = Path(__file__).resolve().parents[1]
    nodes, types, drones, batteries, boxes, dem = load_inputs(official_root)
    for name in ('Q2_preference_frontier.csv', 'Q2_preference_plans.json'):
        shutil.copyfile(root/'results/q2'/name, tmp_path/name)
    rows = read_csv(tmp_path/'Q2_preference_frontier.csv')
    fastest = float(rows[0]['makespan_s'])
    physics = Physics(nodes, types, dem)
    assert validate_preferences(tmp_path, physics, boxes, drones, batteries, fastest) == 4
    rows[-1]['energy_kwh'] = float(rows[-1]['energy_kwh']) - 1
    write_csv(tmp_path/'Q2_preference_frontier.csv', rows)
    with pytest.raises(ValueError):
        validate_preferences(tmp_path, physics, boxes, drones, batteries, fastest)


def test_low_count_soft_late_selection_does_not_keep_stale_ontime_preferences(monkeypatch, tmp_path):
    from src.q2.preferences import export_preferences

    monkeypatch.setattr('src.q2.preferences.TransportEvaluator', lambda *args:
                        SimpleNamespace(schedule=lambda jobs: dict(weighted_tardiness=1)))
    for name in ('Q2_preference_frontier.csv', 'Q2_preference_plans.json'):
        (tmp_path/name).write_text('stale earlier selection')
    assert export_preferences([], None, {}, [], [], tmp_path) == []
    assert not (tmp_path/'Q2_preference_frontier.csv').exists()
    assert not (tmp_path/'Q2_preference_plans.json').exists()
