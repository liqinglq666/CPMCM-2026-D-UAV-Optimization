"""Reproduced cap bypasses, stale certificates, and preference ID collisions."""

import importlib
import json
import sys
from types import SimpleNamespace

import pytest

from src.core.discrete import TransportEvaluator
from src.core.models import Resource


def transport_seeds(physics, boxes):
    drones = [Resource(f'U{i}', 'T') for i in range(2)]
    batteries = [Resource(f'B{i}', 'T') for i in range(2)]
    box_map = {b.id: b for b in boxes}
    evaluator = TransportEvaluator(physics, box_map, drones, batteries)
    together = [dict(id='one', type='T', drone='U0', battery='B0',
                     boxes=[b.id for b in boxes], route=[b.service for b in boxes])]
    apart = [dict(id=f'j{i}', type='T', drone=f'U{i}', battery=f'B{i}',
                  boxes=[b.id], route=[b.service]) for i, b in enumerate(boxes)]
    return evaluator, together, apart, box_map, drones, batteries


@pytest.mark.parametrize('only_over_cap', [False, True])
def test_q2_initial_incumbent_obeys_completion_cap(physics, boxes, tmp_path, only_over_cap):
    from src.q2.search import exportable, improve_frontier

    evaluator, one, two, box_map, drones, batteries = transport_seeds(physics, boxes)
    assert evaluator.schedule(two)['makespan'] < evaluator.schedule(one)['makespan']
    seeds = {len(p): ([set(j['boxes']) for j in p], exportable(evaluator.schedule(p), box_map))
             for p in ([two] if only_over_cap else [one, two])}
    params = dict(seed=1, q2_selection_mode='completion', q2_trip_cap=1, q2_iterations=0)
    if only_over_cap:
        with pytest.raises(ValueError, match='cap'):
            improve_frontier(seeds, box_map, physics, drones, batteries, params, tmp_path)
    else:
        _, selected, _, _ = improve_frontier(
            seeds, box_map, physics, drones, batteries, params, tmp_path)
        assert selected['trips'] == 1


def test_q2_completion_restarts_stay_within_cap(physics, boxes, tmp_path, monkeypatch):
    from src.q2 import search

    evaluator, one, two, box_map, drones, batteries = transport_seeds(physics, boxes)
    seeds = {len(p): ([set(j['boxes']) for j in p], search.exportable(evaluator.schedule(p), box_map))
             for p in (one, two)}
    observed = []

    def inspect_pool(self, choices):
        observed.append([len(plan) for plan, _result in choices])
        return choices[0]

    monkeypatch.setattr(search.random.Random, 'choice', inspect_pool)
    monkeypatch.setattr(search, 'transport_neighbor', lambda plan, *a: plan)
    params = dict(seed=1, q2_selection_mode='completion', q2_trip_cap=1,
                  q2_iterations=1, q2_restart_interval=1)
    search.improve_frontier(seeds, box_map, physics, drones, batteries, params, tmp_path)
    assert observed and all(n == 1 for pool in observed for n in pool)


def relay_plan(njobs, nrelays):
    return dict(jobs=[dict(id=f'j{i}', type='T', drone='U', battery='B',
                           boxes=[f'b{i}'], route=[f'S{i}'], relay=None)
                      for i in range(njobs)],
                relays=[dict(id=f'r{i}', drone=f'R{i}', component=f'C{i}')
                        for i in range(nrelays)])


def relay_result(plan):
    fast = len(plan['jobs']) > 1 or len(plan['relays']) > 1
    return dict(**plan, times={('end', r['id']): 90 for r in plan['relays']},
                objective=(0, 0, 0, 100 if fast else 200, 1, len(plan['relays']), 10))


@pytest.mark.parametrize('njobs,nrelays', [(2, 1), (1, 2)])
def test_q3_initial_incumbent_obeys_completion_caps(tmp_path, monkeypatch, njobs, nrelays):
    from src.q3 import search, seed_repair

    plan = relay_plan(njobs, nrelays)
    monkeypatch.setattr(search, 'PlanPreparer', lambda *a: SimpleNamespace(audit_steps=(1, .5)))
    monkeypatch.setattr(search, 'candidate_points', lambda *a: [])
    monkeypatch.setattr(seed_repair, 'repair_seed', lambda *a: (plan, relay_result(plan)))
    params = dict(seed=1, q3_selection_mode='completion', q3_trip_cap=1,
                  q3_relay_cap=1, q3_iterations=0)
    with pytest.raises(ValueError, match='cap'):
        search.search_plan(plan, None, None, None, None, None, None, 1, params, tmp_path)


@pytest.mark.parametrize('njobs,nrelays,invalid_baseline',
                         [(2, 1, False), (1, 2, False), (2, 1, True), (1, 2, True)])
def test_q3_column_seed_cannot_bypass_caps(tmp_path, monkeypatch, njobs, nrelays, invalid_baseline):
    from src.q3 import column_schedule, window_search

    valid, invalid = relay_plan(1, 1), relay_plan(njobs, nrelays)
    baseline, seed = (invalid, valid) if invalid_baseline else (valid, invalid)
    config = tmp_path / 'config'
    config.mkdir()
    (config / 'q3_completion_seed.json').write_text(json.dumps(seed))
    monkeypatch.setattr(column_schedule, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(column_schedule, 'evaluate', lambda plan, *a: relay_result(plan))
    monkeypatch.setattr(column_schedule, 'enumerate_columns', lambda *a: [])

    def no_column_solution(*args):
        raise ValueError('No feasible column window')

    monkeypatch.setattr(window_search, 'service_windows', no_column_solution)
    preparer = SimpleNamespace(audit_steps=(1, .5), boxes={}, physics=None)
    params = dict(q3_selection_mode='completion', q3_trip_cap=1, q3_relay_cap=1,
                  q3_column_horizon_s=300)
    selected, _ = column_schedule.improve_with_columns(
        baseline, relay_result(baseline), preparer, [], [], params, tmp_path)
    assert len(selected['jobs']) == len(selected['relays']) == 1


def fail_recomputation(*args, **kwargs):
    raise ValueError('Changed input is invalid')


def test_failed_q3_rerun_invalidates_all_q3_certificates(tmp_path, monkeypatch):
    from src.cli import run_question
    from src.q3 import solver

    certificates = ['validation.json', 'continuous_communication.json', 'communication_replay.json']
    for filename in certificates:
        (tmp_path / filename).write_text('{"status":"PASS"}')
    monkeypatch.setattr(solver, 'solve_q3', fail_recomputation)
    with pytest.raises(ValueError, match='Changed input'):
        run_question('q3', ['--out', str(tmp_path / 'q3')])
    assert not any((tmp_path / name).exists() for name in certificates)


@pytest.mark.parametrize('module,entry', [('certify_communication', 'certify'),
                                        ('replay_communication', 'replay')])
def test_failed_standalone_recheck_removes_old_certificate(tmp_path, monkeypatch, module, entry):
    script = importlib.import_module(f'scripts.{module}')
    out = tmp_path / 'certificate.json'
    out.write_text('{"status":"PASS"}')
    monkeypatch.setattr(sys, 'argv', [module, '--out', str(out)])
    monkeypatch.setattr(script, entry, fail_recomputation)
    with pytest.raises(ValueError, match='Changed input'):
        script.main()
    assert not out.exists()


def test_preference_rerun_invalidates_global_validation(tmp_path, monkeypatch):
    from scripts import optimize_preferences

    certificate = tmp_path / 'validation.json'
    certificate.write_text('{"status":"PASS"}')
    monkeypatch.setattr(sys, 'argv', ['preferences', '--out', str(tmp_path / 'q2')])
    monkeypatch.setattr(optimize_preferences, 'load_inputs', fail_recomputation)
    with pytest.raises(ValueError, match='Changed input'):
        optimize_preferences.main()
    assert not certificate.exists()


@pytest.mark.parametrize('epsilons', [(0.05, 0.05), (0.05000001, 0.05000002)])
def test_preference_ids_cannot_silently_overwrite_plans(physics, boxes, tmp_path, monkeypatch, epsilons):
    from src.q2 import preferences

    _, jobs, _, box_map, drones, batteries = transport_seeds(physics, boxes)
    monkeypatch.setattr(preferences, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(preferences, 'optimize_resources', lambda *a: (None, None, {}))
    with pytest.raises(ValueError, match='unique'):
        preferences.export_preferences(jobs, physics, box_map, drones, batteries, tmp_path,
                                       epsilons=epsilons)
    assert not (tmp_path / 'Q2_preference_plans.json').exists()
