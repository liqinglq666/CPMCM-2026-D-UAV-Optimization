"""Read-only deterministic Q2 replay; exports figure evidence, never optimizes."""
from pathlib import Path
import os, sys, csv, json, hashlib
from dataclasses import replace
from paths import source_path

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO))
from src.core.inputs import load_inputs
from src.core.physics import Physics
from src.core.constraints import validate_transport, close, RESULT_TOLERANCE
from src.core.communication import sample_states
from src.core.energy import leg_energy

OUT=REPO/'paper/figure_data_v2'
RAW=Path(os.environ.get('UAV_DATA_ROOT',REPO/'data/raw'))

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read_csv(p):
    with Path(p).open(encoding='utf-8-sig',newline='')as f:return list(csv.DictReader(f))
def write_csv(p,rows):
    with Path(p).open('w',encoding='utf-8-sig',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def results_hashes():return {str(p.relative_to(REPO)):sha(p)for p in sorted((REPO/'results').rglob('*'))if p.is_file()}

def main():
    OUT.mkdir(exist_ok=True,parents=True)
    before=results_hashes()
    nodes,types,drones,batteries,boxes,dem=load_inputs(RAW)
    physics=Physics(nodes,types,dem);bm={b.id:b for b in boxes}
    trips=read_csv(REPO/'results/q2/Q2_transport_trips_balanced.csv')
    deliveries=read_csv(REPO/'results/q2/Q2_box_delivery_balanced.csv')
    resource=read_csv(REPO/'results/q2/Q2_resource_check.csv')
    profiles,replayed_resource=validate_transport(trips,deliveries,'q2',physics,boxes,drones,batteries)
    phase_rows=[];trajectory=[];summary=[];events=[];terrain_rows=[];audit=[]
    for tr in trips:
        tid=tr['架次编号'];typ=tr['机型编号'];drone=types[typ]
        profile,start=profiles[tid];remaining={i:bm[i]for i in tr['货箱编号列表'].split(',')}
        identity=dict(question='q2',trip_id=tid,type_code=typ,uav_id=tr['无人机编号'],battery_id=tr['电池编号'])
        origin=nodes['O01'];prep=drone.prep_time+drone.load_time_per_box*len(remaining)
        phases=(('prep_load',0.,prep,'O01','O01',origin.elev,origin.elev,0.),)+profile.phases
        distance=0.;energy=0.
        for pi,p in enumerate(phases):
            kind,begin,end,source,target,z0,z1,legdist=p
            mass=sum(b.mass for b in remaining.values())
            a,b=nodes[source],nodes[target]
            if kind=='cruise':p0=(a.lon,a.lat,z0);p1=(b.lon,b.lat,z1)
            else:
                node=b if kind=='descent'else a
                p0=(node.lon,node.lat,z0);p1=(node.lon,node.lat,z1)
            duration=end-begin
            if kind in ['climb','cruise']:
                segment=physics.segment(source,target)
                total,horizontal,climb=leg_energy(drone,segment.distance,segment.climb,mass)
                e=climb if kind=='climb'else horizontal
            else:e=0.
            dist_end=distance+(legdist if kind=='cruise'else 0.)
            display=('prep_load'if kind=='prep_load'else 'handover'if kind=='handover'else 'return'if target=='O01'else 'flight')
            row={**identity,'phase_id':pi,'phase_kind':kind,'display_phase':display,
                 't_begin_s':start+begin,'t_end_s':start+end,'t_begin_relative_s':begin,'t_end_relative_s':end,
                 'source':source,'target':target,'lon_begin':p0[0],'lat_begin':p0[1],'altitude_begin_m':p0[2],
                 'lon_end':p1[0],'lat_end':p1[1],'altitude_end_m':p1[2],
                 'payload_kg':mass,'phase_energy_kwh':e,'cumulative_energy_begin_kwh':energy,'cumulative_energy_end_kwh':energy+e,
                 'cumulative_distance_begin_m':distance,'cumulative_distance_end_m':dist_end}
            phase_rows.append(row)
            # Use the unmodified phase sampler, preserving its phase endpoints.
            states=[(begin,p0),(end,p1)]if kind=='prep_load'else list(sample_states(replace(profile,phases=(p,)),physics,1.0))
            for index,(time,point)in enumerate(states):
                fraction=(time-begin)/duration if duration else 0.
                trajectory.append({**identity,'phase_id':pi,'phase_kind':kind,'display_phase':display,'sample_index':index,
                   'time_s':start+time,'relative_time_s':time,'lon':point[0],'lat':point[1],'altitude_m':point[2],
                   'payload_kg':mass,'cumulative_distance_m':distance+fraction*(dist_end-distance),
                   'cumulative_energy_kwh':energy+fraction*e})
            distance=dist_end;energy+=e
            if kind=='handover':
                delivered=[b for b in remaining.values()if b.service==source]
                for box in delivered:
                    events.append({**identity,'box_id':box.id,'service':source,'mass_kg':box.mass,
                                   'delivery_s':start+profile.delivery[box.id],'expected_s':box.expected,
                                   'hard_deadline_s':box.hard_deadline if box.hard_deadline is not None else '',
                                   'first_batch':box.first})
                    del remaining[box.id]
        assert not remaining
        close(energy,profile.energy,tid+' phase energy sum')
        assert abs(energy-profile.energy)<1e-8
        summary.append({**identity,'route':tr['访问服务区顺序'],'box_ids':tr['货箱编号列表'],
          'box_count':len(tr['货箱编号列表'].split(',')),'initial_payload_kg':profile.mass,'initial_volume_m3':profile.volume,
          'start_s':start,'return_s':start+profile.duration,'duration_s':profile.duration,'energy_kwh':profile.energy,
          'soc_pct':100*(1-profile.energy/drone.energy_use),'last_delivery_s':start+max(profile.delivery.values()),
          'horizontal_distance_m':distance})
        audit.append({'trip_id':tid,'return_difference_s':start+profile.duration-float(tr['返回O01时刻（s）']),
           'energy_difference_kwh':profile.energy-float(tr['架次能耗（kWh）']),
           'soc_difference_pp':100*(1-profile.energy/drone.energy_use)-float(tr['返航SOC（%）']),
           'phase_energy_difference_kwh':energy-profile.energy,
           'delivery_max_difference_s':max(abs(start+profile.delivery[r['货箱编号']]-float(r['交付完成时刻（s）']))for r in deliveries if r['架次编号']==tid)})
        if tid=='Q2-020':
            cumulative=0.
            order=['O01']+tr['访问服务区顺序'].split('->')+['O01']
            for li,(a_id,b_id)in enumerate(zip(order[:-1],order[1:])):
                a,b=nodes[a_id],nodes[b_id];seg=physics.segment(a_id,b_id)
                rr,cc,bb,ee=physics.terrain.cell_intervals((a.lon,a.lat),(b.lon,b.lat))
                for ri,ci,ab,ae,z in zip(rr,cc,bb,ee,physics.terrain.values(rr,cc)):
                    terrain_rows.append({'trip_id':tid,'leg_id':li,'source':a_id,'target':b_id,'row':int(ri),'col':int(ci),
                      'begin_m':cumulative+float(ab)*seg.distance,'end_m':cumulative+float(ae)*seg.distance,
                      'elevation_m':float(z),'cruise_altitude_m':seg.cruise_alt})
                cumulative+=seg.distance
    original_resources={(r['架次编号'],r['资源类型']):r for r in resource}
    assert len(resource)==len(replayed_resource)==48
    for rr in replayed_resource:
        original=original_resources[(rr['架次编号'],rr['资源类型'])]
        for key,value in rr.items():
            if isinstance(value,(int,float)):close(original[key],value,f'{rr["架次编号"]} {key}')
            else:assert original[key]==value
    assert len(trips)==24 and len(events)==80 and sum(r['hard_deadline_s']!=''for r in events)==31
    assert before==results_hashes(),'The frozen results tree changed during replay'
    write_csv(OUT/'q2_task_phases.csv',phase_rows)
    write_csv(OUT/'q2_trajectory.csv',trajectory)
    write_csv(OUT/'q2_018_trajectory.csv',[r for r in trajectory if r['trip_id']=='Q2-018'])
    write_csv(OUT/'q2_020_profile.csv',sorted(terrain_rows,key=lambda r:(r['leg_id'],r['begin_m'],r['end_m'])))
    write_csv(OUT/'q2_trip_summary.csv',summary)
    write_csv(OUT/'q2_delivery_events.csv',events)
    sources=[REPO/f'results/q2/{n}'for n in ['Q2_transport_trips_balanced.csv','Q2_box_delivery_balanced.csv','Q2_resource_check.csv']]
    sources += [REPO/'src/core'/n for n in ['routes.py','physics.py','communication.py','sampling.py','energy.py','constraints.py','terrain.py','inputs.py']]
    sources += [REPO/'src/config.py',dem]+list(RAW.rglob('*调度中心与服务区*.xlsx'))+list(RAW.rglob('*运输无人机数据*.xlsx'))+list(RAW.rglob('*物资需求与配送时限*.xlsx'))
    report={'operation':'Deterministic replay of the frozen 24 Q2 routes; no route selection, timing optimization or parameter changes.',
       'result_tolerance':RESULT_TOLERANCE,'trajectory_sampling_step_s':1.0,'phase_count':len(phase_rows),'trajectory_rows':len(trajectory),
       'trip_count':len(trips),'box_count':len(events),'hard_deadline_boxes':31,'resource_rows':48,
       'sources':[{'path':source_path(p),'sha256':sha(p)}for p in sources],
       'checks':audit,'results_before_sha256':before,'results_after_identical':True,
       'definitions':{'phase_intervals':'Half-open except shared plotting endpoints; load decreases only after handover completion.',
         'prep_load':'Prep+per-box load time from official type; displayed payload is the assigned payload ready for departure, not a measured intra-loading mass curve.',
         'energy':'Climb and cruise components are original leg_energy; other phases have zero modeled energy. Within-phase cumulative energy scales with constant prescribed speed.',
         'altitude':'Absolute model altitude in metres. Service operation altitude is node elevation+30m; cruise is closed-cell terrain maximum+50m. Node elevation is not replaced by DSM.',
         'distance':'WGS84 geodesic segment length as original Physics.segment; linear lon/lat sampler retained; only cruise increases cumulative horizontal distance.'},
       'output_sha256':{p.name:sha(p)for p in OUT.glob('q2*.csv')}}
    (OUT/'q2_replay_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k]for k in ['trip_count','box_count','hard_deadline_boxes','phase_count','trajectory_rows','results_after_identical']},ensure_ascii=False))

if __name__=='__main__':main()
