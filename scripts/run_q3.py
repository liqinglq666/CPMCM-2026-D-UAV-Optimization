from __future__ import annotations

"""
Q3 feasible joint transport-relay baseline for CPMCM 2026 Problem D.

This script keeps the Q2 physical model, checks DEM line-of-sight and FSPL link
budgets, performs a small transport regrouping to remove early relay conflicts,
and schedules two relay UAVs in regional waves. It is a verified feasible
baseline, not a proof of the global optimum.

AI-assisted development: ChatGPT / GPT-5.6 Sol / OpenAI.
All assumptions, formulas, code and outputs must be independently verified by
the participating team before submission.
"""
import csv, math, argparse
from pathlib import Path
from collections import defaultdict
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from shapely.geometry import LineString
from pyproj import Geod

parser=argparse.ArgumentParser(description='Run CPMCM 2026 D Q3 joint transport-relay baseline')
parser.add_argument('root', type=Path, help='Root directory containing the official 30 m DEM')
parser.add_argument('--q2-dir', type=Path, default=Path(__file__).resolve().parents[1]/'results'/'q2')
parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1]/'results'/'q3')
args=parser.parse_args()
ROOT=args.root; Q2_DIR=args.q2_dir; OUT_DIR=args.out; DEM=next(ROOT.rglob('*.tif')); GEOD=Geod(ellps='WGS84'); G=9.80665
NODES={'O01':(109.2308517,23.0085095,127.7),'S001':(109.2432319,23.0335927,154),'S002':(109.2585519,23.0703271,189.5),'S003':(109.1688578,23.0402714,308.5),'S004':(109.2381714,23.0778414,198.3),'S005':(109.2283003,23.0561338,165),'S006':(109.1997836,23.007714,284.8),'S007':(109.1928191,23.0294186,318.5),'S008':(109.2127472,23.0795113,240.9),'S009':(109.2541424,23.0552989,200),'S010':(109.2760168,23.0194009,321.6),'S011':(109.2203356,23.0319231,182.1),'S012':(109.2831357,23.054464,249.8),'S013':(109.2713839,23.0310882,321.7),'S014':(109.2835966,23.0052097,321),'S015':(109.1923786,23.0494548,444.5)}
TYPES={
'A':dict(empty=70,Q=25,V=.06,speed=12,L0=25000,LF=20000,E=4.5,rho=.2,prep=300,load=30,hand=150,handbox=30,climb=3,desc=2.5,eta=.72,charge=1800,nD=4,nB=6),
'B':dict(empty=65,Q=30,V=.073,speed=15,L0=28000,LF=16000,E=4,rho=.2,prep=300,load=30,hand=150,handbox=30,climb=3,desc=2.5,eta=.72,charge=2400,nD=2,nB=4),
'C':dict(empty=69.9,Q=80,V=.25,speed=15,L0=26000,LF=12000,E=8,rho=.2,prep=300,load=30,hand=180,handbox=36,climb=2.5,desc=2,eta=.72,charge=3000,nD=2,nB=4)}
RELAY=dict(mass=23.5,speed=15,cruiseP=1.15,E=3.2,rho=.2,prep=180,link=30,turn=300,climb=4,desc=3,eta=.72,hoverP=1.05,commP=.05,charge=1800)
FREQ=2400;LOBS=10;LMAX_TG=122;LMAX_TR=116;LMAX_RG=126;G01=(NODES['O01'][0],NODES['O01'][1],NODES['O01'][2]+20)

with open(Q2_DIR/'Q2_box_delivery_balanced.csv',encoding='utf-8-sig') as f:q2boxes=list(csv.DictReader(f))
BOX={}
for r in q2boxes:
 code=r['货箱编号'];kind=code.split('-')[1]; mv={'MED':(3,.012),'WAT':(14,.027),'FOD':(8,.028),'HYG':(6,.035)}[kind]
 BOX[code]=dict(service=r['服务区编号'],mass=mv[0],vol=mv[1],expected=float(r['期望送达时间（s）']),hard=(float(r['硬截止时间（s）']) if r['硬截止时间（s）'] else None),priority=float(r['应急优先系数']))

class World:
 def __init__(self):self.ds=rasterio.open(DEM);self.dem=self.ds.read(1);self.seg={};self.losc={}
 def seginfo(self,a,b):
  key=(a,b)
  if key in self.seg:return self.seg[key]
  na=NODES[a];nb=NODES[b];_,_,d=GEOD.inv(na[0],na[1],nb[0],nb[1]);line=LineString([(na[0],na[1]),(nb[0],nb[1])]);mask=geometry_mask([line.__geo_interface__],out_shape=self.ds.shape,transform=self.ds.transform,invert=True,all_touched=True);mx=float(np.max(self.dem[mask]));za=na[2]+(0 if a=='O01' else 30);zb=nb[2]+(0 if b=='O01' else 30);cr=max(mx+50,za,zb);v=(d,cr,max(0,cr-za),max(0,cr-zb));self.seg[key]=v;return v
 def arbitrary_seg(self,p):
  lon,lat,z=p;O=NODES['O01'];_,_,d=GEOD.inv(O[0],O[1],lon,lat);line=LineString([(O[0],O[1]),(lon,lat)]);mask=geometry_mask([line.__geo_interface__],out_shape=self.ds.shape,transform=self.ds.transform,invert=True,all_touched=True);mx=float(np.max(self.dem[mask]));cr=max(mx+50,O[2],z);return d,cr,cr-O[2],cr-z
 def obstruction(self,p1,p2):
  key=tuple(round(x,5) if i%3!=2 else round(x,0) for i,x in enumerate(p1+p2))
  if key in self.losc:return self.losc[key]
  inv=~self.ds.transform;c1,r1=inv*(p1[0],p1[1]);c2,r2=inv*(p2[0],p2[1]);n=max(2,int(max(abs(r2-r1),abs(c2-c1))*2)+1);f=np.linspace(0,1,n);rr=np.floor(r1+(r2-r1)*f).astype(int);cc=np.floor(c1+(c2-c1)*f).astype(int);valid=(rr>=0)&(cc>=0)&(rr<self.ds.height)&(cc<self.ds.width);rr=rr[valid];cc=cc[valid];ff=f[valid];obs=False
  if len(rr)>2:obs=bool(np.any(self.dem[rr[1:-1],cc[1:-1]]>=p1[2]+(p2[2]-p1[2])*ff[1:-1]-0.1))
  self.losc[key]=obs;return obs
 def link(self,p1,p2,lmax):
  _,_,dh=GEOD.inv(p1[0],p1[1],p2[0],p2[1]);D=math.sqrt(dh*dh+(p2[2]-p1[2])**2)/1000;fs=32.45+20*math.log10(FREQ)+20*math.log10(max(D,1e-9));obs=self.obstruction(p1,p2) if fs<=lmax else False;loss=fs+(LOBS if obs else 0);return loss<=lmax,loss,obs
w=World()

def chg_time(cfg,soc):
 if soc<.9:return cfg['charge']*(.65*(.9-soc)/.9+.35)
 return cfg['charge']*.35*(1-soc)/.1

def transport_profile(job):
 cfg=TYPES[job['type']]; ids=job['boxes'];mass=sum(BOX[x]['mass'] for x in ids);vol=sum(BOX[x]['vol'] for x in ids)
 if mass>cfg['Q']+1e-9 or vol>cfg['V']+1e-12:raise ValueError(('capacity',job['id'],mass,vol))
 by=defaultdict(list)
 for x in ids:by[BOX[x]['service']].append(x)
 t=cfg['prep']+cfg['load']*len(ids);payload=mass;prev='O01';energy=0;delivery={};phases=[]
 for dest in job['route']+['O01']:
  d,cr,hup,hdn=w.seginfo(prev,dest);na=NODES[prev];nb=NODES[dest];za=na[2]+(0 if prev=='O01' else 30);zb=nb[2]+(0 if dest=='O01' else 30)
  L=cfg['L0']-(cfg['L0']-cfg['LF'])*(payload/cfg['Q'])**1.5
  energy+=cfg['E']*d/L+(cfg['empty']+payload)*G*hup/(cfg['eta']*3.6e6)
  for ph,dur,z0,z1 in [('爬升',hup/cfg['climb'],za,cr),('巡航',d/cfg['speed'],cr,cr),('下降',hdn/cfg['desc'],cr,zb)]:phases.append((ph,t,t+dur,prev,dest,z0,z1,d));t+=dur
  if dest!='O01':
   hand=cfg['hand']+cfg['handbox']*len(by[dest]);phases.append(('交接',t,t+hand,dest,dest,zb,zb,0));t+=hand
   for x in by[dest]:delivery[x]=t
   payload-=sum(BOX[x]['mass'] for x in by[dest])
  prev=dest
 if energy>(1-cfg['rho'])*cfg['E']+1e-8:raise ValueError(('energy',job['id'],energy,(1-cfg['rho'])*cfg['E']))
 fail=[]
 for ph,t0,t1,a,b,z0,z1,d in phases:
  n=max(1,int((t1-t0)/5))
  for k in range(n+1):
   f=k/n;tt=t0+(t1-t0)*f;na=NODES[a];nb=NODES[b]
   if ph=='巡航':az,_,_=GEOD.inv(na[0],na[1],nb[0],nb[1]);lon,lat,_=GEOD.fwd(na[0],na[1],az,d*f);z=z0
   elif ph in ('爬升','下降'):pt=na if ph=='爬升' else nb;lon,lat=pt[0],pt[1];z=z0+(z1-z0)*f
   else:lon,lat,z=na[0],na[1],z0
   if not w.link((lon,lat,z),G01,LMAX_TG)[0]:fail.append((tt,(lon,lat,z),ph))
 return dict(duration=t,energy=energy,delivery=delivery,phases=phases,fail=fail,mass=mass,vol=vol)

with open(Q2_DIR/'Q2_transport_trips_balanced.csv',encoding='utf-8-sig') as f:orows=list(csv.DictReader(f))
orig={r['架次编号']:dict(id=r['架次编号'],type=r['机型编号'],boxes=r['货箱编号列表'].split(','),route=r['访问服务区顺序'].split('->')) for r in orows}
jobs=[]
def add(jid,typ,boxes,route,target,relay=None):jobs.append(dict(id=jid,type=typ,boxes=list(boxes),route=list(route),target=target,relay=relay))
add('Q3-001','C',orig['Q2-001']['boxes'],orig['Q2-001']['route'],1900,21)
add('Q3-002','C',orig['Q2-002']['boxes'],orig['Q2-002']['route'],1590,21)
add('Q3-003','B',['S007-WAT-01'],['S007'],0,16)
add('Q3-004','B',['S007-MED-01','S006-MED-01','S006-WAT-01'],['S007','S006'],0,16)
for q,targ,relay in [('Q2-005',0,35),('Q2-006',0,35),('Q2-007',0,35),('Q2-008',0,None),('Q2-009',1251,None),('Q2-010',7200,27),('Q2-011',5000,17),('Q2-012',2121,35),('Q2-013',4450,27),('Q2-014',4400,17)]:
 o=orig[q];add('Q3-'+q.split('-')[1],o['type'],o['boxes'],o['route'],targ,relay)
add('Q3-015A','A',['S008-MED-01','S008-WAT-01'],['S008'],4400,27)
add('Q3-015B','A',['S004-MED-01','S004-WAT-01'],['S004'],4400,27)
for q,targ,relay in [('Q2-016',10400,40),('Q2-017',7200,27),('Q2-018',4500,27),('Q2-019',9580,None),('Q2-020',7470,27),('Q2-021',7300,17)]:
 o=orig[q];add('Q3-'+q.split('-')[1],o['type'],o['boxes'],o['route'],targ,relay)
o=orig['Q2-022']; add('Q3-022',o['type'],o['boxes'],o['route'],4570,17)
add('Q3-023','A',['S015-MED-01','S015-WAT-01'],['S015'],4600,17)

allids=[x for j in jobs for x in j['boxes']]
assert len(allids)==80 and len(set(allids))==80 and set(allids)==set(BOX)
for j in jobs:j['profile']=transport_profile(j)

CANDS=[('O01', (109.2308517, 23.0085095, 428.7255401611328), 300, 89.02914065916661, False), ('S001', (109.2432319, 23.0335927, 453.96136474609375), 300, 109.7950025448353, False), ('S004', (109.2381714, 23.0778414, 495.1157531738281), 300, 117.80940012377017, False), ('S005', (109.2283003, 23.0561338, 469.03955078125), 300, 114.52395415135943, False), ('S006', (109.1997836, 23.007714, 575.1272277832031), 300, 120.19716852591934, True), ('S007', (109.1928191, 23.0294186, 614.2220458984375), 300, 113.23046613419528, False), ('S009', (109.2541424, 23.0552989, 489.4370880126953), 300, 125.19511305374017, True), ('S010', (109.2760168, 23.0194009, 621.5816650390625), 300, 123.69334320352277, True), ('S011', (109.2203356, 23.0319231, 478.04286193847656), 300, 109.08208754542953, False), ('S013', (109.2713839, 23.0310882, 621.7080688476562), 300, 123.80900184723905, True), ('S014', (109.2835966, 23.0052097, 620.9825134277344), 300, 124.7665668537652, True), ('S015', (109.1923786, 23.0494548, 736.229248046875), 300, 125.6722783611047, True), ('G01_00', (109.1788578, 22.997209699999992, 653.2118225097656), 300, 124.85932977180853, True), ('G01_01', (109.1788578, 23.015209699999993, 627.2563781738281), 300, 124.70661190344128, True), ('G01_02', (109.1788578, 23.033209699999993, 643.9039916992188), 300, 125.63346404131462, True), ('G02_00', (109.1968578, 22.997209699999992, 562.7937316894531), 300, 121.47935946413756, True), ('G02_01', (109.1968578, 23.015209699999993, 631.6434020996094), 300, 111.16982753923195, False), ('G02_02', (109.1968578, 23.033209699999993, 683.4054260253906), 300, 113.04535197092983, False), ('G02_03', (109.1968578, 23.051209699999994, 752.5244445800781), 300, 125.47853362019498, True), ('G03_00', (109.2148578, 22.997209699999992, 451.98785400390625), 300, 106.43629628216884, False), ('G03_01', (109.2148578, 23.015209699999993, 522.9584045410156), 300, 105.34295046459167, False), ('G03_02', (109.2148578, 23.033209699999993, 552.0204162597656), 300, 110.19683706226657, False), ('G03_03', (109.2148578, 23.051209699999994, 673.0047607421875), 300, 114.08974151094824, False), ('G04_00', (109.2328578, 22.997209699999992, 524.4058532714844), 300, 102.48503162366417, False), ('G04_01', (109.2328578, 23.015209699999993, 437.35142517089844), 300, 98.35861621209119, False), ('G04_02', (109.2328578, 23.033209699999993, 448.8580017089844), 300, 108.87116000443322, False), ('G04_03', (109.2328578, 23.051209699999994, 497.8214111328125), 300, 113.58116257723756, False), ('G04_04', (109.2328578, 23.069209699999995, 564.9332580566406), 300, 116.62521899721331, False), ('G05_00', (109.2508578, 22.997209699999992, 675.9715270996094), 300, 107.87305087792905, False), ('G05_01', (109.2508578, 23.015209699999993, 552.4236297607422), 300, 106.97436594758325, False), ('G05_02', (109.2508578, 23.033209699999993, 506.66180419921875), 300, 110.77926829104263, False), ('G05_03', (109.2508578, 23.051209699999994, 485.6751403808594), 300, 124.31623358476511, True), ('G05_04', (109.2508578, 23.069209699999995, 540.7806549072266), 300, 117.00441682819283, False), ('G05_05', (109.2508578, 23.087209699999995, 615.08154296875), 300, 119.10595157735604, False), ('G06_00', (109.2688578, 22.997209699999992, 603.4127502441406), 300, 122.34734883528759, True), ('G06_01', (109.2688578, 23.015209699999993, 642.9300842285156), 300, 122.08883616375019, True), ('G06_02', (109.2688578, 23.033209699999993, 559.7703247070312), 300, 113.63931286388788, False), ('G06_03', (109.2688578, 23.051209699999994, 595.6120300292969), 300, 115.82203063597623, False), ('G07_00', (109.2868578, 22.997209699999992, 585.1045227050781), 300, 125.46066862337713, True), ('G07_01', (109.2868578, 23.015209699999993, 694.3659057617188), 300, 125.34505267308899, True), ('G07_04', (109.2868578, 23.069209699999995, 882.3285522460938), 300, 119.01277184011181, False)]

for j in jobs:
 p=j['profile'];ci=j['relay']
 if ci is None:
  if p['fail']: raise ValueError(('unexpected direct outage',j['id'],len(p['fail'])))
 else:
  cp=CANDS[ci][1]
  if not w.link(cp,G01,LMAX_RG)[0]:raise ValueError(('backhaul',j['id'],ci))
  bad=[x for x in p['fail'] if not w.link(x[1],cp,LMAX_TR)[0]]
  if bad:raise ValueError(('relay coverage',j['id'],ci,len(bad),bad[0]))

resourcesD={g:[[f'U{n:02d}',0.0] for n in (range(1,5) if g=='A' else range(5,7) if g=='B' else range(7,9))] for g in TYPES}
resourcesB={g:[[f'{g}-BAT-{n:02d}',0.0] for n in range(1,TYPES[g]['nB']+1)] for g in TYPES}
for j in sorted(jobs,key=lambda x:(x['target'],x['id'])):
 g=j['type'];d=min(resourcesD[g],key=lambda x:x[1]);b=min(resourcesB[g],key=lambda x:x[1]);start=max(j['target'],d[1],b[1]);p=j['profile'];end=start+p['duration'];soc=1-p['energy']/TYPES[g]['E'];d[1]=end;b[1]=end+chg_time(TYPES[g],soc);j.update(start=start,end=end,drone=d[0],battery=b[0],soc=soc*100)
 for x,off in p['delivery'].items():
  hd=BOX[x]['hard']
  if hd is not None and start+off>hd+1e-6:raise ValueError(('deadline',j['id'],x,start+off,hd,start))

for j in jobs:
 if j['relay'] is not None and j['profile']['fail']:
  j['fail_start']=j['start']+min(x[0] for x in j['profile']['fail']);j['fail_end']=j['start']+max(x[0] for x in j['profile']['fail'])

wave_defs=[('R01-01','R01','R-BAT-01',16,['Q3-003','Q3-004']),('R01-02','R01','R-BAT-02',21,['Q3-001','Q3-002']),('R01-03','R01','R-BAT-03',17,['Q3-011','Q3-014','Q3-021','Q3-022','Q3-023']),('R02-01','R02','R-BAT-04',35,['Q3-005','Q3-006','Q3-007','Q3-012']),('R02-02','R02','R-BAT-05',27,['Q3-010','Q3-013','Q3-015A','Q3-015B','Q3-017','Q3-018','Q3-020']),('R02-03','R02','R-BAT-06',40,['Q3-016'])]
jobmap={j['id']:j for j in jobs};sorties=[]

def relay_profile(ci,serv_start,serv_end):
 pt=CANDS[ci][1];d,cr,hup,hdn=w.arbitrary_seg(pt);r=RELAY
 out_t=hup/r['climb']+d/r['speed']+hdn/r['desc'];ret_t=hdn/r['climb']+d/r['speed']+hup/r['desc']
 travel_e=r['cruiseP']*(2*d/r['speed'])/3600+r['mass']*G*(hup+hdn)/(r['eta']*3.6e6)
 service_e=(r['hoverP']+r['commP'])*(serv_end-serv_start)/3600;E=travel_e+service_e
 start=serv_start-(r['prep']+out_t+r['link']);build=serv_start;ret=serv_end+ret_t;soc=1-E/r['E']
 return dict(start=start,build=build,service_end=serv_end,return_time=ret,energy=E,soc=soc*100,out_t=out_t,ret_t=ret_t)
for sid,drone,comp,ci,jids in wave_defs:
 s=min(jobmap[x]['fail_start'] for x in jids)-5;e=max(jobmap[x]['fail_end'] for x in jids)+5;rp=relay_profile(ci,s,e)
 if rp['start']<0:raise ValueError(('relay start negative',sid,rp))
 if rp['energy']>(1-RELAY['rho'])*RELAY['E']+1e-9:raise ValueError(('relay energy',sid,rp['energy']))
 sorties.append(dict(id=sid,drone=drone,component=comp,candidate=ci,jobs=jids,service_start=s,**rp))

for drone in ['R01','R02']:
 ss=sorted([x for x in sorties if x['drone']==drone],key=lambda x:x['start'])
 for a,b in zip(ss,ss[1:]):
  if b['start']+1e-6<a['return_time']+RELAY['turn']:raise ValueError(('relay overlap',drone,a['id'],a['return_time'],b['id'],b['start']))

for j in jobs:
 if j['relay'] is None:continue
 srt=next(x for x in sorties if j['id'] in x['jobs'])
 assert srt['candidate']==j['relay'] and srt['service_start']<=j['fail_start']+1e-9 and srt['service_end']>=j['fail_end']-1e-9

out=OUT_DIR;out.mkdir(parents=True,exist_ok=True)
tr=[];boxout=[];comm=[]
for j in sorted(jobs,key=lambda x:(x['start'],x['id'])):
 p=j['profile'];tr.append(dict(架次编号=j['id'],无人机编号=j['drone'],机型编号=j['type'],电池编号=j['battery'],开始时刻_s=j['start'],访问服务区顺序='->'.join(j['route']),返回O01时刻_s=j['end'],架次能耗_kWh=p['energy'],返航SOC_pct=j['soc'],货箱编号列表=','.join(j['boxes'])))
 for x,off in p['delivery'].items():boxout.append(dict(货箱编号=x,架次编号=j['id'],服务区编号=BOX[x]['service'],交付完成时刻_s=j['start']+off,期望_s=BOX[x]['expected'],硬截止_s=BOX[x]['hard'] or '',加权延误=BOX[x]['priority']*max(0,j['start']+off-BOX[x]['expected'])))
 if j['profile']['fail']:
  fs=j['fail_start'];fe=j['fail_end'];comm.append(dict(运输架次编号=j['id'],通信阶段='需中继区间',开始时刻_s=fs,结束时刻_s=fe,保障方式='中继',中继架次编号=next(x['id'] for x in sorties if j['id'] in x['jobs'])))
 else:comm.append(dict(运输架次编号=j['id'],通信阶段='全程',开始时刻_s=j['start']+TYPES[j['type']]['prep']+TYPES[j['type']]['load']*len(j['boxes']),结束时刻_s=j['end'],保障方式='直连',中继架次编号=''))
rel=[]
for x in sorties:
 pt=CANDS[x['candidate']][1];rel.append(dict(中继架次编号=x['id'],中继无人机编号=x['drone'],能源组件编号=x['component'],开始时刻_s=x['start'],悬停经度=pt[0],悬停纬度=pt[1],悬停海拔_m=pt[2],建链完成时刻_s=x['build'],服务结束时刻_s=x['service_end'],返回O01时刻_s=x['return_time'],架次能耗_kWh=x['energy'],返航SOC_pct=x['soc'],候选点=CANDS[x['candidate']][0]))
for name,rows in [('Q3_transport_trips.csv',tr),('Q3_box_delivery.csv',boxout),('Q3_relay_sorties.csv',rel),('Q3_communication.csv',comm)]:
 with open(out/name,'w',encoding='utf-8-sig',newline='') as f:
  wr=csv.DictWriter(f,fieldnames=rows[0].keys());wr.writeheader();wr.writerows(rows)

print('TRANSPORT trips',len(tr),'energy',sum(x['架次能耗_kWh'] for x in tr),'makespan',max(x['返回O01时刻_s'] for x in tr),'weighted tardiness',sum(x['加权延误'] for x in boxout))
print('RELAY sorties',len(rel),'energy',sum(x['架次能耗_kWh'] for x in rel),'makespan',max(x['返回O01时刻_s'] for x in rel))
print('JOINT makespan',max(max(x['返回O01时刻_s'] for x in tr),max(x['返回O01时刻_s'] for x in rel)),'TOTAL energy',sum(x['架次能耗_kWh'] for x in tr)+sum(x['架次能耗_kWh'] for x in rel))
print('min hard slack',min(BOX[x['货箱编号']]['hard']-x['交付完成时刻_s'] for x in boxout if BOX[x['货箱编号']]['hard'] is not None))
