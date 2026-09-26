"""Export frozen Q3 phase, radio and ray evidence without any optimization."""
import csv
import hashlib
import json
import sys
import numpy as np
from paths import REPO, RAW, DATA, source_path

sys.path.insert(0, str(REPO))
from src.core.communication import Communication, sample_states
from src.core.constraints import validate_relays, validate_transport, RESULT_TOLERANCE
from src.core.inputs import load_inputs, load_relay_inputs, load_communication_inputs
from src.core.io import read_csv
from src.core.physics import Physics
from src.core.terrain import horizontal_distance


def dump(name, value):
    (DATA / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def csvout(name, rows):
    with (DATA / name).open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def hashes():
    return {p.relative_to(REPO).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((REPO / 'results').rglob('*')) if p.is_file()}


def main():
    before = hashes()
    nodes, types, drones, batteries, boxes, dem = load_inputs(RAW)
    physics = Physics(nodes, types, dem)
    radio = load_communication_inputs(RAW)
    comm = Communication(physics, radio)
    directory = REPO / 'results/q3'
    trips = read_csv(directory / 'Q3_transport_trips.csv')
    tripmap = {r['架次编号']: r for r in trips}
    profiles, _ = validate_transport(trips, read_csv(directory / 'Q3_box_delivery.csv'),
                                     'q3', physics, boxes, drones, batteries)
    relays = validate_relays(read_csv(directory / 'Q3_relay_sorties.csv'), physics, load_relay_inputs(RAW), comm)
    assigned = {r['运输架次编号']: r['中继架次编号'] for r in read_csv(directory / 'Q3_communication.csv')}
    backhauls = {rid: radio.backhaul_budget_db - comm.link(p, comm.gateway, radio.backhaul_budget_db)[1]
                 for rid, (p, _, _) in relays.items()}
    boxmap = {b.id: b for b in boxes}
    phases = []
    for tid, (profile, start) in profiles.items():
        ids = tripmap[tid]['货箱编号列表'].split(',')
        payload = sum(boxmap[b].mass for b in ids)
        raw_phases = [('prep', 0, profile.phases[0][1], 'O01', 'O01',
                       physics.operation_altitude('O01'), physics.operation_altitude('O01'), 0), *profile.phases]
        for i, (kind, a, b, source, target, z0, z1, distance) in enumerate(raw_phases):
            display = 'prep' if kind == 'prep' else 'handover' if kind == 'handover' else 'return' if target == 'O01' else 'flight'
            phases.append({'question': 'Q3', 'trip_id': tid, 'phase_id': i, 'phase_kind': kind,
                           'display_stage': display, 't_begin_s': start+a, 't_end_s': start+b,
                           'source': source, 'target': target, 'z0_m': z0, 'z1_m': z1,
                           'distance_m': distance, 'payload_kg': payload,
                           'source_lon': nodes[source].lon, 'source_lat': nodes[source].lat,
                           'target_lon': nodes[target].lon, 'target_lat': nodes[target].lat})
            if kind == 'handover':
                payload -= sum(boxmap[x].mass for x in ids if boxmap[x].service == target)
        assert abs(payload) <= 1e-10
        assert abs(phases[-1]['t_end_s'] - float(tripmap[tid]['返回O01时刻_s'])) <= RESULT_TOLERANCE
    csvout('q3_task_phases.csv', phases)

    critical = json.loads((REPO / 'paper/data/communication_critical_state.json').read_text(encoding='utf-8'))
    state = critical['state']
    point = tuple(state[k] for k in ('longitude', 'latitude', 'altitude_m'))
    relay = relays[critical['assigned_relay']][0]
    ray_rows = []
    ray_meta = []
    for name, a, b, budget in [('direct', point, comm.gateway, radio.direct_budget_db),
                              ('access', point, relay, radio.access_budget_db),
                              ('backhaul', relay, comm.gateway, radio.backhaul_budget_db)]:
        rows, cols, begin, end = physics.terrain.cell_intervals(a, b)
        elevation = physics.terrain.values(rows, cols)
        available, loss, blocked = comm.link(a, b, budget)
        margin = budget-loss
        assert abs(margin-critical[name+'_margin_db']) <= RESULT_TOLERANCE
        dist = horizontal_distance(a, b)
        for rr, cc, lo, hi, h in zip(rows, cols, begin, end, elevation):
            zl = a[2]+(b[2]-a[2])*lo
            zh = a[2]+(b[2]-a[2])*hi
            ray_rows.append({'link': name, 'frac_start': float(lo), 'frac_end': float(hi),
                             'terrain_m': float(h), 'line_start_m': float(zl), 'line_end_m': float(zh),
                             'distance_m': dist, 'dem_row': int(rr), 'dem_col': int(cc),
                             'blocked_cell': bool(h >= min(zl, zh))})
        ray_meta.append({'link': name, 'from': a, 'to': b, 'distance_m': dist,
                         'margin_db': margin, 'obstructed': bool(blocked), 'available': bool(available)})
    csvout('q3_link_profiles.csv', ray_rows)
    dump('q3_link_profiles.json', ray_meta)
    print('Exported Q3 phases and three critical radio rays', flush=True)

    # Reproduce only the missing native map cache from analyze_paper.py.
    terrain = physics.terrain
    west = min(n.lon for n in nodes.values())-.007
    east = max(n.lon for n in nodes.values())+.007
    south = min(n.lat for n in nodes.values())-.007
    north = max(n.lat for n in nodes.values())+.007
    c0, r0 = terrain.pixel(west, north); c1, r1 = terrain.pixel(east, south)
    cols = np.arange(int(c0), int(c1)+1); rows = np.arange(int(r0), int(r1)+1)
    dump('terrain_map.json', {'longitude': [float((terrain.transform*(c+.5,0))[0]) for c in cols],
         'latitude': [float((terrain.transform*(0,r+.5))[1]) for r in rows],
         'elevation_m': terrain.values(rows[:,None], cols[None,:]).tolist(),
         'purpose':'Native original DEM centres; independently exported only for figure evidence.',
         'crs':'EPSG:4326','resampled':False,'grid_step_degrees':[terrain.transform.a,terrain.transform.e]})

    summaries = []
    old = json.loads((REPO / 'results/communication_replay.json').read_text(encoding='utf-8'))['sampling']
    for step, filename in [(1.0, 'communication_states_1s.csv'), (.5, 'communication_states_05s.csv')]:
        states = []
        for tid, (profile, start) in profiles.items():
            rid = assigned[tid]
            for offset, point in sample_states(profile, physics, step):
                time = start+offset
                direct = comm.link(point, comm.gateway, radio.direct_budget_db)
                dm = radio.direct_budget_db-direct[1]
                margin, mode, access, backhaul = dm, 'direct', None, None
                active = False
                if rid:
                    relaypoint, lo, hi = relays[rid]
                    active = lo <= time <= hi
                    if active:
                        access = radio.access_budget_db-comm.link(point, relaypoint, radio.access_budget_db)[1]
                        backhaul = backhauls[rid]
                        if min(access, backhaul) > margin:
                            margin, mode = min(access, backhaul), 'relay'
                states.append({'trip':tid,'time_s':time,'longitude':point[0],'latitude':point[1],
                               'altitude_m':point[2],'direct_margin_db':dm,'available_margin_db':margin,
                               'best_mode':mode,'direct_obstructed':bool(direct[2]),'assigned_relay':rid,
                               'assigned_relay_active':active,'access_margin_db':access,'backhaul_margin_db':backhaul})
        csvout(filename, states)
        summary = {'step_s':step,'checked_states':len(states),'violations':sum(r['available_margin_db']<0 for r in states),
                   'minimum_margin_db':min(r['available_margin_db'] for r in states)}
        expected = next(s for s in old if s['step_s']==step)
        assert summary['checked_states']==expected['checked_states']
        assert summary['violations']==expected['violations']==0
        assert abs(summary['minimum_margin_db']-expected['minimum_margin_db'])<=RESULT_TOLERANCE
        summaries.append(summary)
        print(summary, flush=True)
    assert before == hashes()
    dump('q3_replay_verification.json', {'sampling':summaries,'phase_rows':len(phases),'ray_interval_rows':len(ray_rows),
         'transport_validation':'Repository validate_transport passed, including energy, return, deliveries and resource allocation.',
         'relay_validation':'Repository validate_relays passed.', 'results_unchanged':True,'result_hashes':before,
         'scope':'Deterministic replay of the frozen schedule; no optimization, no claimed switching log, no new continuous proof.',
         'raw_dem':{'path':source_path(dem),'sha256':hashlib.sha256(dem.read_bytes()).hexdigest()}})


if __name__ == '__main__':
    main()
