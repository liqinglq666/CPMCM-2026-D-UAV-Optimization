"""Evidence-led publication figures 17--27 from frozen results and deterministic replay.

Only paper/figure_data_v2 and requested figure/QA outputs are written. No optimizer
is called and no source result, configuration or scientific model is changed.
"""
from pathlib import Path
import csv, json, math, hashlib, re, sys, subprocess
from collections import defaultdict
from functools import lru_cache
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import MultipleLocator
from matplotlib.text import Text
import matplotlib.patheffects as pe
from paths import REPO, OUT, WORK, RAW, DATA, source_path
import common as shared

sys.path.insert(0,str(REPO))
from src.core.energy import two_stage_charge_time
from src.core.constraints import RESULT_TOLERANCE

MODEL=shared.C; RELAY=shared.RELAY_COLORS; GROUP=shared.GROUP_COLORS
RED=shared.THRESHOLD; TEXT=shared.TEXT; SECOND=shared.SECONDARY
STAGE=shared.STAGE; TOL=RESULT_TOLERANCE
COMMIT='e71cdb13c0969a28d78f349e1ce79047e731e954'
RUN_HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
def load(rel):return json.loads((REPO/rel).read_text(encoding='utf-8-sig'))
def rows(rel):return list(csv.DictReader((REPO/rel).open(encoding='utf-8-sig',newline='')))
def f(row,key):return float(row[key])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(name,value,details=None):return {'name':name,'passed':bool(value),'details':details}
def clean(x):return json.loads(json.dumps(x,ensure_ascii=False,default=lambda v:v.item() if hasattr(v,'item') else str(v)))
def canvas(h):return plt.figure(figsize=(16.3/2.54,h/2.54),facecolor='white')
def title(ax,s,pad=8):ax.set_title(s,loc='left',fontsize=10,fontweight='bold',pad=pad)
def grid(ax,axis='y'):shared.grid(ax,axis)
def numid(s):return s.rsplit('-',1)[-1]
def dump(p,x):p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2),encoding='utf8')
def table(name,records):
    if records:
        with (DATA/name).open('w',encoding='utf8',newline='') as fh:
            w=csv.DictWriter(fh,fieldnames=list(records[0]));w.writeheader();w.writerows(records)

A=load('paper/data/analysis.json'); NODES=A['nodes']; SERVICES=sorted(k for k in NODES if k!='O01')
PLAN=load('results/q3/Q3_selected_plan.json')
TRIPS=sorted(rows('results/q3/Q3_transport_trips.csv'),key=lambda x:x['架次编号'])
TRIPMAP={r['架次编号']:r for r in TRIPS}
RELAYS=sorted(rows('results/q3/Q3_relay_sorties.csv'),key=lambda x:x['中继架次编号'])
RMAP={r['中继架次编号']:r for r in RELAYS}; RPLAN={r['id']:r for r in PLAN['relays']}
COMM=rows('results/q3/Q3_communication.csv')
CRITICAL=load('paper/data/communication_critical_state.json'); CERT=load('results/continuous_communication.json')
ATOMCERT=load('results/q4/Q4_enumeration_certificate.json');ATOMS=ATOMCERT['atomic_components']
TURN=A['relay_spec']['turnaround_s']; JOINT=A['metrics']['q3']['joint_makespan_s']

def save(fig,n,caption,claim,panels,data,sources,fields,joins,derived,checks,limits=None,parameters=None):
    """Publish actual plotted data, provenance, numerical checks and print contract."""
    stem=f'fig_{n:02d}';fig.canvas.draw()
    text_sizes=[t.get_fontsize() for t in fig.findobj(Text) if t.get_text().strip()]
    checks=[*checks,check('necessary text at least 8 pt',min(text_sizes)>=8,{'minimum_pt':min(text_sizes)}),check('publication width 16.3 cm',abs(fig.get_figwidth()*2.54-16.3)<1e-9)]
    failed=[x for x in checks if not x['passed']]
    if failed:raise AssertionError((n,failed))
    records=[]
    for p in sources:
        pp=Path(p);pp=pp if pp.is_absolute() else REPO/pp
        records.append({'path':source_path(pp),'sha256':sha(pp)})
    for ext in ['svg','pdf']:fig.savefig(OUT/f'{stem}.{ext}',facecolor='white')
    fig.savefig(OUT/f'{stem}.png',dpi=600,facecolor='white')
    fig.savefig(WORK/f'{stem}_preview.png',dpi=150,facecolor='white')
    view={'figure':n,'source_commit':COMMIT,'time_origin':'official task origin; source seconds, display minutes by division by 60','data':clean(data)}
    dump(OUT/f'{stem}_data.json',view);dump(DATA/f'{stem}_data.json',view)
    spec={'figure':n,'number':n,'caption':caption,'core_claim':claim,'panels':panels,'width_cm':16.3,'height_cm':fig.get_figheight()*2.54,'dpi':600,'source_commit':COMMIT,'runtime_git_head':RUN_HEAD,'sources':records,'field_mapping':fields,'join_keys':joins,'derived_formula':derived,'checks':checks,'missing_or_limited_evidence':limits or [],'plot_parameters':{'minimum_font_pt':min(text_sizes),'font_cn':shared.FONT_CN,'font_latin':'DejaVu Sans','font_math':'STIX Sans','svg_text':True,'pdf_fonttype':42,**(parameters or {})},'visual_review':'pending actual PDF inspection','no_optimization_rerun':True,'authoritative_tolerance':TOL}
    if n in [17,23,24]:spec['map_spec']=shared.MAP_SPEC
    dump(OUT/f'{stem}_spec.json',spec);dump(DATA/f'{stem}_spec.json',spec)
    (OUT/f'{stem}_caption.txt').write_text(caption,encoding='utf8')
    plt.close(fig);print(stem,'saved',flush=True)

def fig26():
    raw=rows('paper/data/payload_reserve.csv');st=rows('paper/data/reserve_staircase.csv');sen=rows('results/q1/Q1_sensitivity_summary.csv')
    reserves=sorted({f(r,'reserve') for r in raw});lookup={(r['type'],r['service'],f(r,'reserve')):r for r in raw}
    cmap=LinearSegmentedColormap.from_list('safe_capacity',['#F7FBFC','#BDD7DE','#5F9FAD','#1B5969'],256);cmap.set_bad('#E6E8EB')
    fig=canvas(15.0);heat=[];view=[];xedges=np.r_[np.array(reserves)*100-.25,reserves[-1]*100+.25]
    for j,typ in enumerate('ABC'):
        ax=fig.add_axes([.11+j*.288,.605,.248,.315]);heat.append(ax)
        z=np.empty((15,61));mask=np.zeros((15,61),bool)
        for i,s in enumerate(SERVICES):
            for k,rho in enumerate(reserves):
                r=lookup[typ,s,rho];valid=r['reachable']=='True';mask[i,k]=not valid
                z[i,k]=100*f(r,'payload_kg')/f(r,'rated_payload_kg') if valid else np.nan
                view.append({'type':typ,'service':s,'reserve_fraction':rho,'safe_payload_kg':f(r,'payload_kg') if r['payload_kg'] else None,'rated_payload_kg':f(r,'rated_payload_kg'),'reachable':valid,'safe_ratio_pct':float(z[i,k]) if valid else None})
        mesh=ax.pcolormesh(xedges,np.arange(16)-.5,np.ma.masked_invalid(z),cmap=cmap,vmin=0,vmax=100,shading='flat',rasterized=True)
        for i in range(15):
            ix=np.where(mask[i])[0]
            for kk in np.split(ix,np.where(np.diff(ix)>1)[0]+1):
                if len(kk):ax.add_patch(Rectangle((xedges[kk[0]],i-.5),xedges[kk[-1]+1]-xedges[kk[0]],1,facecolor='#E6E8EB',edgecolor='#9AA2AA',hatch='///',lw=0))
        ax.axvline(20,color=TEXT,lw=.8);ax.set(xlim=(10,40),ylim=(14.5,-.5),xticks=[10,20,30,40],yticks=range(15),yticklabels=SERVICES if j==0 else ['']*15)
        ax.tick_params(axis='y',length=0,labelsize=8.5);ax.tick_params(axis='x',labelsize=8.5)
        title(ax,f'({"abc"[j]}) {typ}型');ax._left_title.set_color(MODEL[typ])
    fig.text(.51,.554,'返航储备（%）',ha='center',fontsize=9.5)
    cb=fig.colorbar(mesh,cax=fig.add_axes([.24,.509,.55,.014]),orientation='horizontal',ticks=[0,25,50,75,100]);cb.ax.tick_params(labelsize=8.5,pad=2,length=2);cb.set_label('安全载荷／额定载荷（%）',fontsize=9.5,labelpad=2);cb.outline.set_linewidth(.4)
    fig.legend(handles=[Patch(fc='#E6E8EB',ec='#9AA2AA',hatch='///',label='不可达')],loc='center left',bbox_to_anchor=(.085,.514),frameon=False,fontsize=8.5,handlelength=1.25)
    main=fig.add_axes([.10,.125,.50,.285]);zoom=fig.add_axes([.715,.125,.25,.285]);intervals=[]
    for i,r in enumerate(st):intervals.append({'reserve_lower':f(r,'reserve_lower'),'reserve_upper':f(r,'reserve_upper'),'trips':int(r['trips']) if r['trips'] else None,'reachable':r['reachable']=='True','lower_closed':i==0,'upper_closed':True})
    for ax in [main,zoom]:
        for i,r in enumerate(intervals):
            lo,hi=r['reserve_lower']*100,r['reserve_upper']*100;n=r['trips']
            if n is None:ax.axvspan(lo,hi,fc='#F8ECEC',ec='#D9B5B8',hatch='///',lw=.4,zorder=0)
            else:
                ax.plot([lo,hi],[n,n],color='#4477AA',lw=1.55)
                ax.plot(lo,n,'o',ms=3.8,mfc='#4477AA' if i==0 else 'white',mec='#4477AA',mew=.9,zorder=4)
                ax.plot(hi,n,'o',ms=3.8,mfc='#4477AA',mec='#4477AA',mew=.9,zorder=5)
        ax.set(ylim=(17.5,25.8),xlabel='返航储备（%）');grid(ax);ax.yaxis.set_major_locator(MultipleLocator(1))
    main.set(xlim=(10,40),ylabel='最少运输架次');main.xaxis.set_major_locator(MultipleLocator(5));title(main,'(d) 完整子集临界阶梯')
    main.scatter([f(r,'返航安全余量')*100 for r in sen],[f(r,'最少往返架次数') for r in sen],s=33,marker='D',facecolors='white',edgecolors='#4477AA',linewidths=1,zorder=6)
    main.legend(handles=[Line2D([],[],ls='',marker='D',mfc='white',mec='#4477AA',ms=4,label='原五场景核验')],loc='upper left',frameon=False,fontsize=8.5)
    first,last=intervals[0]['reserve_upper']*100,intervals[-2]['reserve_upper']*100
    main.annotate(f'{first:.4f}%',(first,18),xytext=(16.4,19.7),fontsize=8.5,arrowprops={'arrowstyle':'-','lw':.65,'color':SECOND})
    main.text(38,21.1,'不可行',rotation=90,color=RED,ha='center',fontsize=8.5)
    zoom.set(xlim=(33,35.55),ylim=(20.5,25.8),xticks=[33,34,35],yticks=[21,22,23,24,25]);title(zoom,'(e) 同一阶梯放大')
    zoom.annotate(f'{last:.4f}%',(last,25),xytext=(33.05,25.42),fontsize=8.5,arrowprops={'arrowstyle':'-','lw':.65,'color':SECOND})
    fig.text(.10,.032,'端点：空心左开，实心右闭；23架次区间为 (34.3742%, 34.3923%]。',fontsize=8.5)
    checks=[check('2745 unique evaluations',len(raw)==2745 and len(lookup)==2745),check('61 reserves and 15x3 combinations',len(reserves)==61 and len({(r['type'],r['service'])for r in raw})==45),check('percent color normalization',all(r['safe_ratio_pct'] is None or 0<=r['safe_ratio_pct']<=100+1e-10 for r in view)),check('rated payload source',all(f(r,'rated_payload_kg')==A['types'][r['type']]['max_payload']for r in raw)),check('five archived scenarios',len(sen)==5),check('narrow 23-trip interval preserved',any(r['trips']==23 and r['reserve_upper']-r['reserve_lower']<.001 for r in intervals)),check('staircase intervals contiguous',all(a['reserve_upper']==b['reserve_lower']for a,b in zip(intervals,intervals[1:]))),check('last infeasible display-domain endpoint closed',intervals[-1]['upper_closed'] and intervals[-1]['reserve_upper']==.4)]
    table('fig_26_capacity_grid.csv',view);table('fig_26_staircase.csv',intervals)
    save(fig,26,'返航储备引起的安全载荷收缩与最少架次跃迁。上排为61个储备点、15区与3机型的既存离散评估，统一以额定载荷为分母；灰色斜纹表示不可达。下排为既存完整子集临界分析结果，右窗重复放大同一阶梯。临界点归入较低架次数，五场景仅作核验。','安全能力随储备收缩，离散组批在精确临界点改变最少架次。',{'a-c':'same 61x15 capacity evaluations per model, percent units','d':'full exact staircase with five archived scenario checks','e':'same saved intervals magnified, including narrow 23-trip interval'}, {'capacity_grid':view,'staircase':intervals,'five_scenarios':sen},['paper/data/payload_reserve.csv','paper/data/reserve_staircase.csv','results/q1/Q1_sensitivity_summary.csv','paper/data/analysis.json'],{'reserve/service/type':'heatmap cell identity','payload_kg/rated_payload_kg':'100x safe capacity fraction','reachable':'independent hatch mask','reserve_lower/reserve_upper/trips':'exact staircase geometry'},['reserve+service+type','ordered exact reserve interval'],['safe_ratio_pct=100*payload_kg/rated_payload_kg','first interval closed both sides; all subsequent (lower,upper]','no interpolation or new optimization'],checks,parameters={'heatmap_norm':[0,100],'discrete_grid_no_interpolation':True,'minimum_trip_zoom':[33,35.55]})

@lru_cache(maxsize=1)
def relay_resources():
    from src.core.inputs import load_relay_inputs,load_inputs
    from src.core.communication import relay_travel
    from src.core.physics import Physics
    inp=load_relay_inputs(RAW);records=[]
    nodes,types,_drones,_batteries,_boxes,dem=load_inputs(RAW);physics=Physics(nodes,types,dem)
    for r in RELAYS:
        start,ret=f(r,'开始时刻_s'),f(r,'返回O01时刻_s')
        charge=two_stage_charge_time(inp.full_charge_s,f(r,'返航SOC_pct')/100)
        travel=relay_travel(physics,inp.spec,(f(r,'悬停经度'),f(r,'悬停纬度'),f(r,'悬停海拔_m')))
        assert abs(start+travel['lead']-f(r,'建链完成时刻_s'))<=TOL
        assert abs(travel['inbound']+f(r,'服务结束时刻_s')-ret)<=TOL
        records.append({'trip_id':r['中继架次编号'],'entity':r['中继无人机编号'],'component':r['能源组件编号'],'start_s':start,'prep_end_s':start+inp.spec.prep_s,'outbound_end_s':start+inp.spec.prep_s+travel['outbound'],'service_start_s':f(r,'建链完成时刻_s'),'service_end_s':f(r,'服务结束时刻_s'),'return_s':ret,'turnaround_s':inp.spec.turnaround_s,'uav_release_s':ret+inp.spec.turnaround_s,'return_soc_pct':f(r,'返航SOC_pct'),'full_charge_s':inp.full_charge_s,'recharge_duration_s':charge,'component_release_s':ret+charge,'replayed_outbound_s':travel['outbound'],'replayed_inbound_s':travel['inbound'],'source_dem':source_path(dem)})
    return records,inp

def fig19():
    rdata,inp=relay_resources();fig=canvas(11.6)
    top=fig.add_axes([.235,.55,.735,.285]);bottom=fig.add_axes([.235,.12,.735,.235],sharex=top)
    end=math.ceil((max(r['uav_release_s'] for r in rdata)+120)/60)
    for i,r in enumerate(rdata):
        for a,b,col,hatch in [(r['start_s'],r['service_start_s'],STAGE['prep'],None),(r['service_start_s'],r['service_end_s'],RELAY[i],None),(r['service_end_s'],r['return_s'],STAGE['return'],'//')]:
            top.barh(i,(b-a)/60,left=a/60,height=.36,color=col,edgecolor='#8793A0' if hatch else 'none',hatch=hatch,lw=.5)
        top.text((r['service_start_s']+r['service_end_s'])/120,i,f'R{i}',ha='center',va='center',fontsize=8.5,color='white' if i==0 else TEXT)
        row=['R01','R02'].index(r['entity']);bottom.barh(row,(r['return_s']-r['start_s'])/60,left=r['start_s']/60,height=.35,color=RELAY[i])
        bottom.barh(row,r['turnaround_s']/60,left=r['return_s']/60,height=.35,color=STAGE['turnaround'],ec=shared.STAGE_EDGE['turnaround'],hatch='xx',lw=.5)
        bottom.text((r['start_s']+r['return_s'])/120,row,f'R{i}',ha='center',va='center',fontsize=8.5,color='white' if i==0 else TEXT)
    idle=rdata[2]['start_s']-rdata[0]['uav_release_s'];lo,hi=rdata[0]['uav_release_s']/60,rdata[2]['start_s']/60
    bottom.annotate('',(lo,-.47),(hi,-.47),arrowprops={'arrowstyle':'<->','lw':.7,'color':SECOND})
    bottom.text((lo+hi)/2,-.68,f'可用间隔 {idle:.3f} s',fontsize=8.5,ha='center')
    for ax in [top,bottom]:
        ax.set_xlim(0,end);ax.axvline(JOINT/60,color=RED,lw=.8,ls=(0,(4,2)));ax.xaxis.set_major_locator(MultipleLocator(20));grid(ax,'x')
    top.set(yticks=range(3),yticklabels=[f'R{i}｜{r["entity"]}\n组件{numid(r["component"])}' for i,r in enumerate(rdata)],ylim=(2.5,-.5));top.tick_params(axis='x',labelbottom=False)
    bottom.set(yticks=[0,1],yticklabels=['R01','R02'],ylim=(1.5,-1.0),xlabel='自任务起点计时（min）')
    title(top,'(a) 中继架次阶段');title(bottom,'(b) 两实体接续与周转')
    handles=[Patch(fc=STAGE['prep'],label='准备、出航与建链'),Patch(fc=RELAY[0],label='服务窗（中继任务色）'),Patch(fc=STAGE['return'],ec='#8793A0',hatch='//',label='返航'),Patch(fc=STAGE['turnaround'],ec=shared.STAGE_EDGE['turnaround'],hatch='xx',label='返航后周转')]
    fig.legend(handles=handles,ncol=2,loc='upper center',bbox_to_anchor=(.58,.995),frameon=False,fontsize=8.5,columnspacing=1.5)
    fig.text(.235,.425,f'联合最后返航 {JOINT:.3f} s；竖线后周转仍占用实体',fontsize=8.5,color=RED)
    table('fig_19_relay_resources.csv',rdata)
    save(fig,19,'三个中继架次的服务阶段与两架实体复用。上层阶段边界直接读取正式记录，准备、出航与建链保持合并；下层实体占用延伸至返航后300 s。R01先后执行R0、R2，间隔为正式时序中的可用时间。联合完工以最后返航计，后续周转另示。','服务窗口、实体资源占用与最后返航是不同时间量。',{'a':'three saved relay task phases','b':'two physical UAV schedules with actual 300 s turnaround'}, {'relay_resources':rdata,'R01_idle_s':idle,'joint_return_s':JOINT},['results/q3/Q3_relay_sorties.csv','paper/data/analysis.json',next(RAW.rglob('中继无人机数据.xlsx')),next(RAW.rglob('调度中心与服务区.xlsx')),next(p for p in RAW.rglob('*.mat')if 'DEM'in p.name or 'DEM'in p.parent.name),'src/core/communication.py','src/core/energy.py'],{'开始时刻_s/建链完成时刻_s/服务结束时刻_s/返回O01时刻_s':'three real phase boundaries','turnaround_s':'post-return entity occupation'},['relay trip_id to physical entity and component'],['uav_release_s=return_s+turnaround_s','idle_R01=R2.start-R0.uav_release','display_time_min=source_time_s/60'],[check('3 tasks 2 entities',len(rdata)==3 and len({r['entity'] for r in rdata})==2),check('R01 R02 R01', [r['entity']for r in rdata]==['R01','R02','R01']),check('300 second turnaround',inp.spec.turnaround_s==300),check('positive actual idle',idle>0),check('relay energy anchor',abs(sum(f(r,'架次能耗_kWh')for r in RELAYS)-2.6592740459755895)<=TOL)],parameters={'time_axis_same_both_panels':[0,end]})

def fig20():
    resource=rows('results/q3/Q3_resource_check.csv');phases=rows('paper/figure_data_v2/q3_task_phases.csv');rdata,inp=relay_resources()
    phase_by=defaultdict(list)
    for p in phases:phase_by[p['trip_id']].append(p)
    transport=[r for r in resource if r['资源类型']=='无人机'];battery=[r for r in resource if r['资源类型']=='电池']
    kinds=[transport,battery,rdata,rdata];names=[sorted({r['资源编号']for r in transport}),sorted({r['资源编号']for r in battery}),sorted({r['entity']for r in rdata}),sorted({r['component']for r in rdata})]
    end=math.ceil(max([f(r,'充电结束（s）')for r in battery]+[r['component_release_s']for r in rdata]+[r['uav_release_s']for r in rdata])/600)*10
    fig=canvas(18.6);gs=fig.add_gridspec(4,1,height_ratios=[8,14,2.7,3.7],left=.155,right=.975,top=.858,bottom=.07,hspace=.50)
    axes=[fig.add_subplot(gs[i])for i in range(4)];derived_rows=[];checks=[]
    for layer,ax in enumerate(axes):
        ns=names[layer];ax.set(xlim=(0,end),yticks=range(len(ns)),ylim=(len(ns)-.55,-.55));ax.set_yticklabels([(next(r['机型']for r in transport if r['资源编号']==res)+'·'+res)if layer==0 else res.replace('-BAT-','-')for res in ns]);ax.axvspan(JOINT/60,end,fc='#F7F8FA',zorder=0);ax.axvline(JOINT/60,color=RED,lw=.8,ls=(0,(4,2)),zorder=4);ax.xaxis.set_major_locator(MultipleLocator(20));grid(ax,'x');ax.tick_params(axis='y',labelsize=8.5)
        if layer<3:ax.tick_params(axis='x',labelbottom=False)
        else:ax.set_xlabel('自任务起点计时（min）')
        if layer<2:
            for r in kinds[layer]:
                y=ns.index(r['资源编号']);tid=r['架次编号'];start,ret=f(r,'任务占用开始（s）'),f(r,'任务占用结束（s）');ps=sorted(phase_by[tid],key=lambda p:f(p,'t_begin_s'))
                checks.append(check(f'{layer} {tid} phase endpoints',abs(f(ps[0],'t_begin_s')-start)<=TOL and abs(f(ps[-1],'t_end_s')-ret)<=TOL))
                for p in ps:
                    a,b=f(p,'t_begin_s'),f(p,'t_end_s');ax.barh(y,(b-a)/60,left=a/60,height=.61,color=STAGE[p['display_stage']],edgecolor='none',zorder=2)
                ax.text((start+ret)/120,y,numid(tid),ha='center',va='center',fontsize=8,color=TEXT,bbox={'fc':'white','ec':'none','alpha':.68,'pad':.12},zorder=5)
                release=ret
                if layer==1:
                    release=f(r,'充电结束（s）');cs=f(r,'充电开始（s）');ax.barh(y,(release-cs)/60,left=cs/60,height=.61,color=STAGE['charge'],edgecolor=shared.STAGE_EDGE['charge'],hatch='///',lw=.35,zorder=2)
                derived_rows.append({'layer':['transport_uav','transport_battery'][layer],'resource':r['资源编号'],'trip_id':tid,'start_s':start,'return_s':ret,'release_s':release,'release_event':'return' if layer==0 else 'full_charge'})
            # Model identity is confined to the row-label gutter.
            for y,res in enumerate(ns):
                model=next(r['机型']for r in kinds[layer]if r['资源编号']==res)
                ax.plot(-.135,y,marker=shared.MARKERS[model],ms=4.0,color=MODEL[model],transform=ax.get_yaxis_transform(),clip_on=False)
        else:
            for j,r in enumerate(rdata):
                rid=r['entity']if layer==2 else r['component'];y=ns.index(rid)
                for a,b,stage in [(r['start_s'],r['prep_end_s'],'prep'),(r['prep_end_s'],r['outbound_end_s'],'flight'),(r['outbound_end_s'],r['service_start_s'],'handover'),(r['service_start_s'],r['service_end_s'],'handover'),(r['service_end_s'],r['return_s'],'return')]:ax.barh(y,(b-a)/60,left=a/60,height=.56,color=STAGE[stage],edgecolor='none',zorder=2)
                ax.vlines(r['service_start_s']/60,y-.28,y+.28,color='white',lw=.45,zorder=3)
                stage='turnaround'if layer==2 else'charge';release=r['uav_release_s']if layer==2 else r['component_release_s']
                ax.barh(y,(release-r['return_s'])/60,left=r['return_s']/60,height=.56,color=STAGE[stage],edgecolor=shared.STAGE_EDGE[stage],hatch='xx'if layer==2 else'///',lw=.35,zorder=2)
                ax.text((r['start_s']+r['return_s'])/120,y,f'R{j}',ha='center',va='center',fontsize=8.5,bbox={'fc':'white','ec':'none','alpha':.68,'pad':.12},zorder=5)
                derived_rows.append({'layer':['relay_uav','relay_component'][layer-2],'resource':rid,'trip_id':r['trip_id'],'start_s':r['start_s'],'return_s':r['return_s'],'release_s':release,'release_event':'turnaround_complete'if layer==2 else'full_charge'})
    for ax,s in zip(axes,['(a) 运输无人机：8实体','(b) 运输电池：14块','(c) 中继无人机：2实体','(d) 中继组件：使用3／库存6']):title(ax,s,pad=7)
    handles=[Patch(fc=STAGE[s],ec=shared.STAGE_EDGE.get(s,'none'),hatch={'charge':'///','turnaround':'xx'}.get(s),label=lab)for s,lab in [('prep','准备／装载'),('flight','出航／区间飞行'),('handover','交接／建链／服务'),('return','返航'),('charge','补充电'),('turnaround','周转')]]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.55,.995),ncol=3,frameon=False,fontsize=8.5,columnspacing=1.3,handlelength=1.4)
    fig.text(.155,.909,f'联合最后返航：{JOINT/60:.3f} min（{JOINT:.3f} s）',fontsize=8.5,color=RED)
    fig.text(.972,.909,'线后：后续充电／周转',ha='right',fontsize=8.5,color=SECOND)
    for layer in set(r['layer']for r in derived_rows):
        for rid in set(r['resource']for r in derived_rows if r['layer']==layer):
            rr=sorted([r for r in derived_rows if r['layer']==layer and r['resource']==rid],key=lambda r:r['start_s'])
            checks.append(check(f'{layer} {rid} no overlap',all(b['start_s']>=a['release_s']-TOL for a,b in zip(rr,rr[1:]))))
    checks.extend([check('resource rows 8/14/2/3',[len(n)for n in names]==[8,14,2,3]),check('official component inventory 6',len(inp.component_ids)==6),check('each used component one task',all(sum(r['component']==c for r in rdata)==1 for c in names[3])),check('all charging release after return',all(r['component_release_s']>r['return_s']for r in rdata)),check('relay preparation 180s and link setup30s',all(abs(r['prep_end_s']-r['start_s']-inp.spec.prep_s)<=TOL and abs(r['service_start_s']-r['outbound_end_s']-inp.spec.link_setup_s)<=TOL for r in rdata))])
    fig.canvas.draw();pitches=[ax.get_position().height*18.6*10/(ax.get_ylim()[0]-ax.get_ylim()[1])for ax in axes]
    checks.append(check('row pitch at least 3.6 mm',min(pitches)>=3.6,{'mm':pitches}))
    table('fig_20_resource_release.csv',derived_rows);table('fig_20_relay_charge.csv',rdata)
    save(fig,20,'Q3固定方案的四类资源占用与完整释放。运输和中继阶段由原模型确定性重放核对：中继依次准备180 s、出航、建链30 s和服务，黄段内白线标服务开始。运输充电沿用正式记录；中继机返航后周转300 s，组件按原两阶段充电公式由返航SOC推导充满时刻。条内为任务后缀，行前符号表示机型。后续充电与周转仍占用资源，不计入5931.735 s联合完工。','四类资源有不同释放事件，联合最后返航不能替代完整资源占用。',{'a':'8 transport UAV real task phases to return','b':'14 batteries with same task phase IDs and formal full recharge','c':'2 physical relay UAVs including turnaround','d':'3 used relay components including deterministic full recharge'}, {'resource_release':derived_rows,'relay_charge_derivation':rdata,'transport_phases':phases,'joint_return_s':JOINT},['results/q3/Q3_resource_check.csv','results/q3/Q3_transport_trips.csv','results/q3/Q3_relay_sorties.csv','paper/figure_data_v2/q3_task_phases.csv','paper/figure_data_v2/q3_replay_verification.json',next(RAW.rglob('中继无人机数据.xlsx')),next(RAW.rglob('调度中心与服务区.xlsx')),next(p for p in RAW.rglob('*.mat')if 'DEM'in p.name or 'DEM'in p.parent.name),'src/core/communication.py','src/core/energy.py','src/q4/partition.py'],{'resource/trip':'row and phase identity','t_begin_s/t_end_s/display_stage':'deterministic phase bars','充电开始（s）/充电结束（s）':'transport charging','返航SOC_pct/full_charge_s':'relay component recharge','relay_travel.outbound/inbound + official preparation/setup':'relay exact phase boundaries'},['trip_id=架次编号','layer+resource'],['relay_component_release=return+two_stage_charge_time(official_full_charge_s,return_SOC_pct/100)','relay_uav_release=return+300','relay_prep_end=start+180; outbound_end=prep_end+relay_travel.outbound; service_start=outbound_end+30','transport and relay phases must reproduce formal start and return within RESULT_TOLERANCE'],checks,parameters={'row_pitch_mm':pitches,'same_time_axes_min':[0,end],'stage_colors':STAGE,'charge_hatch':'///','turnaround_hatch':'xx'})

def fig21():
    fig=canvas(13.1);a=fig.add_axes([.105,.635,.47,.245]);b=fig.add_axes([.72,.635,.25,.245]);c=fig.add_axes([.105,.15,.865,.30])
    vals=[CRITICAL['direct_margin_db'],CRITICAL['access_margin_db'],CRITICAL['backhaul_margin_db']];labels=['直连','接入','回传'];cols=[RED,RELAY[0],RELAY[2]];marks=['x','o','D']
    for i,(v,col,m)in enumerate(zip(vals,cols,marks)):
        a.hlines(i,min(0,v),max(0,v),color=col,lw=1.5);a.plot(v,i,marker=m,color=col,ms=4.5);a.annotate(f'{v:.6f}',(v,i),xytext=(3,-13),textcoords='offset points',ha='left'if i==0 else'center',fontsize=8.5)
    a.axvline(0,color=TEXT,lw=.9);a.set(xlim=(-3.6,1.12),ylim=(2.65,-.6),yticks=range(3),yticklabels=labels,xticks=[-3,-2,-1,0,1],xlabel='链路余量（dB）');grid(a,'x');title(a,'(a) 最紧采样状态')
    for i,j in enumerate([1,2]):b.hlines(i,0,vals[j],color=cols[j],lw=1.5);b.plot(vals[j],i,marker=marks[j],color=cols[j],ms=4.5);b.annotate(f'{vals[j]:.6f}',(vals[j],i),xytext=(0,-14),textcoords='offset points',ha='center',fontsize=8.5)
    b.set(xlim=(0,.82),ylim=(1.6,-.6),yticks=[0,1],yticklabels=['接入','回传'],xticks=[0,.4,.8],xlabel='链路余量（dB）');grid(b,'x');title(b,'(b) 同一状态放大')
    fig.text(.105,.953,'column-019｜4684.446 s｜指定 R2',fontsize=8.5,color=SECOND)
    fig.text(.105,.52,'指定中继余量＝min（接入，回传）；下图为不同证据。',fontsize=8.5,color=SECOND)
    bounds=[{'trip':k,'minimum_margin_bound_db':v['minimum_margin_bound_db']}for k,v in sorted(CERT['trips'].items())];ys=[r['minimum_margin_bound_db']for r in bounds];mi=int(np.argmin(ys))
    c.scatter(range(24),ys,s=22,color='#7770AE');c.scatter(mi,ys[mi],s=28,color=RED,zorder=5);c.set_yscale('log');c.set_yticks([.01,.1,1],['0.01','0.1','1']);c.set(xlim=(-.65,23.65),ylim=(.006,8.0),xticks=range(0,24,2),xticklabels=[f'{i:03d}'for i in range(0,24,2)],xlabel='运输架次（column 后缀）',ylabel='保守区间下界（dB）');grid(c,'y');title(c,'(c) 固定轨迹的连续区间数值核验')
    c.annotate(f'{ys[mi]:.6f} dB',(mi,ys[mi]),xytext=(11,.018),fontsize=8.5,color=RED,arrowprops={'arrowstyle':'-','lw':.7,'color':RED})
    ss=CERT['summary'];fig.text(.105,.032,f'{ss["phases"]}相位 · {ss["certified_intervals"]}通过区间 · {ss["boundary_checks"]}事件检查；浮点保护下的固定轨迹证书',fontsize=8.5,color=SECOND)
    table('fig_21_interval_bounds.csv',bounds)
    save(fig,21,'最紧采样状态与固定轨迹连续区间核验。上排两面板来自同一状态，指定R2的接入和回传均为正，取较小者得到0.090906 dB采样余量。下排各点为独立架次的保守区间下界，全局最小0.009866 dB；其适用范围为冻结轨迹、指定中继、原始分段常值DEM及已声明的浮点保护，不是精确算术证明。','采样最紧余量与全轨迹保守区间下界是互补且不同的证据。',{'a':'three original margins at critical sampled state','b':'same positive margins magnified','c':'24 archived continuous-interval lower bounds, no interpolation'}, {'critical_state':CRITICAL,'interval_bounds':bounds,'certificate_summary':ss,'replay':load('results/communication_replay.json')},['paper/data/communication_critical_state.json','results/continuous_communication.json','results/communication_replay.json'],{'direct/access/backhaul_margin_db':'critical lollipops','trips[id].minimum_margin_bound_db':'lower scatter','summary':'numeric certificate count note'},['critical trip/time','trip id'],['relay margin=min(access,backhaul)','24 lower bounds shown without connecting lines'],[check('24 positive bounds',len(bounds)==24 and min(ys)>0),check('global certificate minimum',min(ys)==CERT['minimum_margin_bound_db']),check('critical relay active',CRITICAL['relay_active']),check('sampled and continuous quantities distinct',min(ys)<min(vals[1:])),check('certificate scope guarded not formal',CERT['formal_exact_arithmetic_proof'] is False)],parameters={'lower_y_scale':'log','lower_all_24_data_points':True})

def fig22():
    edges=defaultdict(set)
    for r in TRIPS:
        route=r['访问服务区顺序'].split('->')
        for s,t in zip(route,route[1:]):edges[tuple(sorted((s,t)))].add(r['架次编号'])
    fig=canvas(10.8);axes=[fig.add_axes([.055+i*.322,.565,.285,.285])for i in range(3)]
    positions=[{'S009':(0,1),'S002':(1,1),'S013':(0,0),'S010':(1,0)}, {'S007':(0,.5),'S003':(.5,.5),'S015':(1,.5)}, {'S011':(.15,.5),'S005':(.85,.5)}]
    relation=[]
    for i,ax in enumerate(axes):
        pos=positions[i];ax.set(xlim=(-.24,1.24),ylim=(-.38,1.37));ax.axis('off');title(ax,f'({"abc"[i]}) C{i+1}共同任务关系',pad=5)
        for (s,t),ids in edges.items():
            if s not in pos or t not in pos:continue
            x,y=pos[s];xx,yy=pos[t];ax.plot([x,xx],[y,yy],color='#8C86B0',lw=1.25,zorder=1)
            text='、'.join(numid(z)for z in sorted(ids));dx=.13 if x==xx else 0;dy=0 if x==xx else -.20
            ax.text((x+xx)/2+dx,(y+yy)/2+dy,text,ha='left' if x==xx else'center',va='center',fontsize=8.5,color=SECOND,bbox={'fc':'white','ec':'none','pad':.8},zorder=4)
            relation.append({'component':f'C{i+1}','service_a':s,'service_b':t,'trip_ids':';'.join(sorted(ids))})
        for s,(x,y) in pos.items():ax.text(x,y,s,ha='center',va='center',fontsize=8.5,bbox={'boxstyle':'round,pad=.22','fc':'white','ec':'#6F6A93','lw':.7},zorder=5)
    fig.text(.055,.936,'关系边仅来自同架次相邻访问；边旁数字为 column 后缀',fontsize=8.5,color=SECOND)
    boxes=fig.add_axes([.055,.13,.91,.30]);boxes.axis('off');title(boxes,'(d) 9个不可拆分量及全部成员',pad=8)
    firstpos=[(0,.59,.37,.38),(.39,.59,.32,.38),(.73,.59,.27,.38)]
    for i,(x,y,w,h)in enumerate(firstpos):
        boxes.add_patch(Rectangle((x,y),w,h,fc='#F0EEF7',ec='#9B94B1',lw=.7));boxes.text(x+.025,y+h-.10,f'C{i+1}',fontsize=9,fontweight='bold',va='top');m='、'.join(ATOMS[i]);boxes.text(x+w/2,y+.10,m,ha='center',va='center',fontsize=8.5)
    for i,atom in enumerate(ATOMS[3:]):
        x=i/6;w=.155;boxes.add_patch(Rectangle((x,.05),w,.39,fc='#F0EEF7',ec='#9B94B1',lw=.7));boxes.text(x+w/2,.34,f'C{i+4}',ha='center',fontsize=9,fontweight='bold');boxes.text(x+w/2,.145,atom[0],ha='center',fontsize=8.5)
    fig.text(.055,.025,'先形成不可拆分量，再合并为独立任务组；关系布局不表示地理距离。',fontsize=8.5,color=SECOND)
    parent={s:s for s in SERVICES}
    def root(s):
        while parent[s]!=s:s=parent[s]
        return s
    for s,t in edges:parent[root(s)]=root(t)
    groups=defaultdict(set)
    for s in SERVICES:groups[root(s)].add(s)
    table('fig_22_relations.csv',relation);table('fig_22_membership.csv',[{'component':f'C{i+1}','service':s}for i,a in enumerate(ATOMS)for s in a])
    save(fig,22,'共同运输任务诱导不可拆服务区分量。上排仅绘正式访问序列中相邻服务区的关系，边旁列出对应架次后缀；规则布局不表示实际航路。下排按证书顺序列出9个分量的全部成员。固定任务分组须保持每个分量完整，15区不再作为相互独立的分配单元。','多个服务区由同一运输任务连接，独立分组必须以完整连通分量为单位。',{'a-c':'actual adjacent-route relations behind the three multi-service components','d':'all nine archived component membership sets'}, {'atomic_components':ATOMS,'adjacent_visit_relations':relation,'enumerated_partitions':ATOMCERT['enumerated_partitions']},['results/q4/Q4_enumeration_certificate.json','results/q3/Q3_transport_trips.csv'],{'访问服务区顺序':'adjacent edges only','atomic_components':'certificate member sets'},['service id','edge set to real trip IDs'],['edge=(adjacent route services), merge repeated edge while retaining all trip IDs','connected components independently recovered from edges'],[check('15 unique services',sorted(s for a in ATOMS for s in a)==SERVICES),check('edge-derived components equal certificate',{frozenset(g)for g in groups.values()}=={frozenset(a)for a in ATOMS}),check('9 components',len(ATOMS)==9)],parameters={'graph_layout':'nongeographical regular arrangement; no unobserved clique edges'})

def fig25():
    rp=rows('results/q4/Q4_gap_decomposition.csv');bal=rows('results/q4/Q4_balanced_resources.csv');keys=['A_uav','B_uav','C_uav','A_bat','B_bat','C_bat','relay_uav','relay_comp'];labels=['A运输机','B运输机','C运输机','A电池','B电池','C电池','中继机','中继组件']
    view=[];checks=[];mat=[];gaps=[]
    for key in keys:
        rr={int(r['K']):r for r in rp if r['resource']==key};bb={int(r['K']):r for r in bal if r['resource']==key};stock=int(rr[2]['inventory']);peak=int(rr[2]['pooled_peak']);dem=[int(rr[2]['independent_total']),int(bb[2]['required']),int(rr[3]['independent_total']),int(bb[3]['required'])];gg=[max(0,x-stock)for x in dem]
        checks.append(check(key+' repeated common values match',rr[2]['inventory']==rr[3]['inventory'] and rr[2]['pooled_peak']==rr[3]['pooled_peak']));checks.append(check(key+' saved class deficits',gg==[int(rr[2]['deficit']),int(bb[2]['shortage']),int(rr[3]['deficit']),int(bb[3]['shortage'])]))
        mat.append([peak,stock,*dem]);gaps.append(gg);view.append({'resource':key,'shared_peak':peak,'inventory':stock,'K2_resource_priority':dem[0],'K2_balanced':dem[1],'K3_resource_priority':dem[2],'K3_balanced':dem[3],'class_gaps':gg})
    mat=np.array(mat);gaps=np.array(gaps);totals=gaps.sum(axis=0);fig=canvas(11.9);ax=fig.add_axes([.17,.255,.53,.515]);side=fig.add_axes([.845,.255,.135,.515]);colors=['#FFFFFF','#FBE8E6','#E9B0AD','#C96E72']
    for i in range(8):
        for j in range(6):
            gap=0 if j<2 else int(gaps[i,j-2]);ax.add_patch(Rectangle((j-.5,i-.5),1,1,fc='#F3F5F7'if j<2 else colors[gap],ec='#D7DCE2',lw=.35));ax.text(j,i,str(mat[i,j]),ha='center',va='center',fontsize=9.5,color='white'if gap==3 else TEXT)
    ax.set(xlim=(-.5,5.5),ylim=(7.5,-.5),yticks=range(8),yticklabels=labels,xticks=range(6),xticklabels=['共享\n峰值','现有\n库存','2组\n资源优先','2组\n均衡','3组\n资源优先','3组\n均衡']);ax.xaxis.tick_top();ax.tick_params(length=0,labelsize=8.5,pad=5)
    for s in ax.spines.values():s.set_visible(False)
    categories=[('运输机',gaps[:3].sum(axis=0),'#93AFBE',''),('电池',gaps[3:6].sum(axis=0),'#B6A7C4','///'),('中继机',gaps[6],'#74658E','xx')]
    left=np.zeros(4)
    for name,vals,col,hatch in categories:
        side.barh(range(4),vals,left=left,height=.47,color=col,edgecolor='white',lw=.4,hatch=hatch,label=name);left+=vals
    for i,v in enumerate(totals):side.text(v+.25,i,str(v),va='center',fontsize=9.5,color=RED,fontweight='bold')
    side.set(xlim=(0,10.3),ylim=(3.6,-.6),yticks=range(4),yticklabels=['2组资源','2组均衡','3组资源','3组均衡'],xticks=[0,5,10]);side.tick_params(axis='y',length=0,labelsize=8.5);grid(side,'x')
    fig.text(.17,.948,'(a) 库存与四种独立需求',fontsize=10,fontweight='bold');fig.text(.785,.948,'(b) 缺口数量',fontsize=10,fontweight='bold')
    fig.legend(handles=[Patch(fc=c,ec='#D7DCE2',label=str(i))for i,c in enumerate(colors)],loc='center',bbox_to_anchor=(.405,.16),ncol=4,frameon=False,title='单格正缺口（仅需求列）',fontsize=8.5,title_fontsize=8.5)
    fig.legend(handles=[Patch(fc=c,ec='white',hatch=h,label=n)for n,_,c,h in categories],loc='center',bbox_to_anchor=(.835,.14),ncol=1,frameon=False,fontsize=8.5)
    fig.text(.08,.031,'中继组件：共享峰值3、库存6、资源优先独立需求4，缺口0。',fontsize=8.5,color=SECOND)
    table('fig_25_matrix.csv',[{k:(';'.join(map(str,v))if isinstance(v,list)else v)for k,v in r.items()}for r in view])
    checks.extend([check('inventory 4/2/2/6/4/4/2/6',list(mat[:,1])==[4,2,2,6,4,4,2,6]),check('totals 1/5/3/9',list(totals)==[1,5,3,9]),check('component replication not shortage',mat[7,0]==3 and mat[7,1]==6 and mat[7,2]==4 and gaps[7,0]==0)])
    save(fig,25,'共享峰值、库存与四种独立配置需求。矩阵数字为实际台/块数量，前两列用中性底色；后四列底色只编码该类需求超出库存的正缺口。右侧按运输机、电池和中继机汇总分类缺口，依次为1、5、3、9。资源冗余不能跨类抵消，数量合计不表示经济成本。','独立需求增加不等于库存短缺，必须逐资源类别核算。',{'a':'8 resources x shared peak/stock/four demands; cell color is class deficit only','b':'same class deficits aggregated by transport UAV/battery/relay UAV'}, {'matrix_records':view,'class_gap_totals':list(totals),'column_order':['shared_peak','inventory','K2_resource_priority','K2_balanced','K3_resource_priority','K3_balanced']},['results/q4/Q4_gap_decomposition.csv','results/q4/Q4_balanced_resources.csv'],{'pooled_peak/inventory':'neutral matrix columns','independent_total/required':'integer demand cells','deficit/shortage':'cell colors and grouped bars'},['K+resource'],['class_gap=max(demand-inventory,0)','total=sum(nonnegative class gaps)','transport_uav=sum(A/B/C_uav); battery=sum(A/B/C_bat)'],checks,parameters={'gap_colors':colors,'rows':keys})

def fig27():
    soc=rows('paper/data/constraint_slacks.csv');hard_saved={r['box']:f(r,'slack_s')for r in rows('paper/data/hard_deadline_slacks.csv')};hard=[]
    for r in rows('results/q3/Q3_box_delivery.csv'):
        if r['硬截止_s']:hard.append({'box_id':r['货箱编号'],'trip_id':r['架次编号'],'hard_deadline_s':f(r,'硬截止_s'),'delivery_complete_s':f(r,'交付完成时刻_s'),'slack_s':f(r,'硬截止_s')-f(r,'交付完成时刻_s')})
    hard.sort(key=lambda r:(r['slack_s'],r['box_id']))
    for i,r in enumerate(hard):r['rank']=i+1
    fig=canvas(14.2);a=fig.add_axes([.105,.625,.49,.275]);b=fig.add_axes([.715,.625,.255,.275]);c=fig.add_axes([.125,.115,.60,.285]);d=fig.add_axes([.86,.115,.11,.285]);series={};mins=[];ecdfs=[]
    scheme=[('q1','#7B8794','o','-'),('q2','#0072B2','s','--'),('q3','#6A51A3','^','-.')]
    for q,col,marker,ls in scheme:
        rr=sorted([{'question':q,'trip_id':r['trip'],'soc_pct':f(r,'soc_pct')}for r in soc if r['question']==q],key=lambda r:(r['soc_pct'],r['trip_id']));series[q]=rr;mins.append(rr[0]);xx,cnt=np.unique([r['soc_pct']for r in rr],return_counts=True);yy=np.cumsum(cnt)/len(rr)
        a.step(np.r_[0,xx,100],np.r_[0,yy,1],where='post',color=col,lw=1.45,ls=ls,label=f'{q.upper()} n={len(rr)}');a.plot(xx,yy,ls='',marker=marker,ms=2.4,color=col)
        ecdfs.extend({'question':q,'soc_pct':float(x),'cumulative_fraction':float(y),'equal_value_count':int(n)}for x,y,n in zip(xx,yy,cnt))
    a.axvline(20,color=RED,ls=(0,(4,2)),lw=.85);a.set(xlim=(0,100),ylim=(0,1.05),xticks=[0,20,40,60,80,100],yticks=[0,.5,1],xlabel='返航SOC（%）',ylabel='累计比例');grid(a);title(a,'(a) 各方案SOC经验累积分布');a.legend(loc='upper left',frameon=True,facecolor='white',edgecolor='none',framealpha=1,fontsize=8.5,handlelength=1.6,labelspacing=.25,borderpad=.15)
    for i,(r,(_,col,m,_))in enumerate(zip(mins,scheme)):
        b.plot(i,r['soc_pct'],marker=m,ms=4.8,color=col);b.annotate(f'{r["soc_pct"]:.2f}%',(i,r['soc_pct']),xytext=(0,7),textcoords='offset points',fontsize=8.5,ha='center')
    b.axhline(20,color=RED,ls='--',lw=.85);b.set(xlim=(-.6,2.6),ylim=(19.7,24.15),xticks=[0,1,2],xticklabels=['Q1','Q2','Q3'],yticks=[20,22,24]);grid(b,'y');title(b,'(b) 阈值附近放大')
    fig.text(.105,.532,'20%储备阈值；各方案为独立样本，不作任务配对。',fontsize=8.5,color=SECOND)
    fig.text(.71,.575,'\n'.join(f'{q.upper()}：{r["trip_id"]}'for (q,_,_,_),r in zip(scheme,mins)),fontsize=8.5,linespacing=1.3,va='top',color=SECOND)
    yy=[r['slack_s']for r in hard];c.scatter(range(1,32),yy,s=21,color='#4F8372');c.scatter([1],[yy[0]],s=28,color=RED,zorder=5);c.axhline(0,color=TEXT,lw=.8);c.set(xlim=(.3,31.7),ylim=(-150,10300),xticks=[1,5,10,15,20,25,31],yticks=[0,2500,5000,7500,10000],xlabel='按硬截止余量升序的货箱序号',ylabel='硬截止余量（s）');grid(c,'y');title(c,'(c) Q3的31个硬截止货箱')
    for i,ytext in enumerate([7200,5650,4100]):c.annotate(hard[i]['box_id'],(i+1,yy[i]),xytext=(5,ytext),fontsize=8.5,color=RED if i==0 else SECOND,arrowprops={'arrowstyle':'-','color':RED if i==0 else SECOND,'lw':.65,'connectionstyle':'angle,angleA=0,angleB=90,rad=0'})
    d.scatter([1],[yy[0]],s=30,color=RED);d.axhline(0,color=TEXT,lw=.8);d.set(xlim=(.5,1.5),ylim=(0,600),xticks=[1],xticklabels=['最紧箱'],yticks=[0,300,600]);grid(d,'y');d.set_title('(d) 最低箱\n同一数据放大',fontsize=8.5,loc='center',pad=8);d.annotate(f'{yy[0]:.3f} s',(1,yy[0]),xytext=(0,13),textcoords='offset points',ha='center',fontsize=8.5,color=RED)
    table('fig_27_soc_records.csv',[r for records in series.values()for r in records]);table('fig_27_ecdf.csv',ecdfs);table('fig_27_hard_deadline_rank.csv',hard)
    checks=[check('SOC sample sizes 18/24/24',[len(series[q])for q,_,_,_ in scheme]==[18,24,24]),check('ECDF each ends at one',all(max(r['cumulative_fraction']for r in ecdfs if r['question']==q)==1 for q,_,_,_ in scheme)),check('31 exact hard set',len(hard)==31 and {r['box_id']for r in hard}==set(hard_saved)),check('all box differences match saved margins',all(abs(r['slack_s']-hard_saved[r['box_id']])<=TOL for r in hard)),check('minimum box ID',hard[0]['box_id']=='S007-WAT-01'),check('minimum slack display',f'{yy[0]:.3f}'=='266.282'),check('Q3 minimum SOC display',f'{mins[2]["soc_pct"]:.2f}'=='20.10'),check('minimum-only zoom not artificial points',yy[0]<600<yy[1])]
    save(fig,27,'冻结方案的返航储备与硬截止余量。经验累积分布按各自任务集合计算，同SOC合并为一次右连续跳跃；右窗显示20%阈值附近的三个最小值及任务编号。下排31箱按真实交付完成时刻计算并排序，只标最紧三箱，其余ID随图保存；窄窗仅放大最低箱266.282 s。图示支持基准可行性，不代表天气或设备误差下的可靠概率。','总体SOC分布、最低SOC与逐箱时限余量共同定位基准方案的最紧约束。',{'a':'right-continuous ECDF of independent Q1/Q2/Q3 SOC sets','b':'same-set minima near 20 percent threshold with exact task IDs','c':'31 real hard-deadline slack scatter, rank linked to full CSV','d':'same minimum box only, 0-600 second view'}, {'soc_records':series,'ecdf':ecdfs,'minimum_soc':mins,'hard_deadline_rank':hard},['paper/data/constraint_slacks.csv','paper/data/hard_deadline_slacks.csv','results/q3/Q3_box_delivery.csv','src/core/constraints.py'],{'question/trip/soc_pct':'independent sample and ECDF','货箱编号':'hard-box association','硬截止_s/交付完成时刻_s':'direct slack subtraction'},['question+trip','box_id'],['F(s)=count(SOC<=s)/n; equal SOC pooled, right-continuous step','hard_slack=hard_deadline-delivery_complete','rank sort by (slack_s,box_id)'],checks,parameters={'ECDF_x':[0,100],'minimum_SOC_y':[19.7,24.15],'hard_minimum_zoom_y':[0,600],'no_slack_point_connecting_lines':True})

def compact_map(ax,groups=None):
    shared.map_base(ax,labels=False,draw_nodes=False)
    ax.set_xlabel('东向（km）',fontsize=8.5);ax.set_ylabel('北向（km）',fontsize=8.5);ax.set_xticks([-6,-3,0,3,6]);ax.set_yticks([0,4,8]);ax.tick_params(labelsize=8.5)
    membership={s:i for i,g in enumerate(groups or [])for s in g['services']}
    offsets={s:[3,3]for s in SERVICES};offsets.update({'S008':[-17,5],'S004':[3,-11],'S005':[-23,-5],'S014':[-19,4],'S012':[-22,5],'S013':[-20,4],'S010':[2,-12],'S009':[3,-10]})
    for s in SERVICES:
        i=membership.get(s);col=GROUP[i]if i is not None else'white';marker=['o','s','^'][i]if i is not None else'o'
        ax.plot(*shared.xy(s),marker=marker,ls='',ms=4.7,mfc=col,mec='white'if i is not None else SECOND,mew=.65,zorder=6)
        ax.annotate(s[1:],shared.xy(s),xytext=offsets[s],textcoords='offset points',fontsize=8.5,path_effects=[pe.withStroke(linewidth=1.3,foreground='white')],zorder=7)
    ax.annotate('O01',shared.xy('O01'),xytext=(3,-12),textcoords='offset points',fontsize=8.5,path_effects=[pe.withStroke(linewidth=1.3,foreground='white')],zorder=8)
    return ax

def partition_data(k):
    from src.q4.partition import normalized_gini
    raw=rows('results/q4/Q4_partition_config.csv');balanced=rows('results/q4/Q4_balanced_groups.csv');preference=rows('results/q4/Q4_preference_comparison.csv');out=[];checks=[]
    for policy,key,tab in [('资源优先','minimum_resources',raw),('均衡偏好','balanced',balanced)]:
        groups=[]
        for r in tab:
            if int(r['K'])!=k:continue
            services=re.findall(r'S\d{3}',r.get('服务区列表',r.get('services','')));sset=set(services)
            tids=[t['架次编号']for t in TRIPS if set(t['访问服务区顺序'].split('->'))<=sset]
            work=sum(f(TRIPMAP[tid],'返回O01时刻_s')-f(TRIPMAP[tid],'开始时刻_s')for tid in tids)
            if key=='balanced':checks.append(check(f'K{k} balanced {r["group"]} transport workload archived',abs(work-f(r,'transport_work_s'))<=TOL))
            else:
                relayids={c['中继架次编号']for c in COMM if c['运输架次编号']in tids and c['保障方式']=='中继'}
                servicework=sum(f(RMAP[rid],'服务结束时刻_s')-f(RMAP[rid],'建链完成时刻_s')for rid in relayids)
                checks.append(check(f'K{k} priority {r["任务组编号"]} mixed workload decomposed',abs(work+servicework-f(r,'工作量_s'))<=TOL))
            groups.append({'group':r.get('任务组编号',r.get('group')),'services':services,'boxes':int(r.get('货箱数',r.get('boxes'))),'transport_trips':int(r.get('运输架次',r.get('transport_trips'))),'trip_ids':tids,'transport_work_s':work,'transport_work_h':work/3600})
        p=next(r for r in preference if int(r['K'])==k and r['policy']==key);gini=normalized_gini(g['transport_work_s']for g in groups)
        checks.extend([check(f'K{k} {key} unique15',sorted(s for g in groups for s in g['services'])==SERVICES),check(f'K{k} {key} all80/24',sum(g['boxes']for g in groups)==80 and sum(g['transport_trips']for g in groups)==24),check(f'K{k} {key} whole atoms',all(any(set(a)<=set(g['services'])for g in groups)for a in ATOMS)),check(f'K{k} {key} pure transport Gini',abs(gini-f(p,'transport_gini'))<=TOL)])
        out.append({'K':k,'policy':policy,'policy_key':key,'groups':groups,'transport_gini':f(p,'transport_gini'),'resource_gap_total':int(p['shortage']),'independent_energy_kwh':f(p,'energy_kwh')})
    return out,checks

def fig_partition(k):
    data,checks=partition_data(k);fig=canvas(15.2)
    maps=[fig.add_axes([.08,.595,.405,.30]),fig.add_axes([.575,.595,.405,.30])];bars=[fig.add_axes([.08,.14,.405,.215]),fig.add_axes([.575,.14,.405,.215])]
    route_edges=set()
    for t in TRIPS:
        route=t['访问服务区顺序'].split('->')
        for s,u in zip(route,route[1:]):route_edges.add(tuple(sorted((s,u))))
    for i,(d,ax,bar)in enumerate(zip(data,maps,bars)):
        compact_map(ax,d['groups'])
        for s,u in sorted(route_edges):
            a,b=shared.xy(s),shared.xy(u);ax.plot([a[0],b[0]],[a[1],b[1]],color='#626B72',lw=.65,alpha=.65,zorder=4)
        if i:ax.set_ylabel('');ax.tick_params(labelleft=False)
        title(ax,f'({"ab"[i]}) {d["policy"]}',pad=8)
        for j,g in enumerate(d['groups']):
            y=j*2;v=g['transport_work_h'];bar.barh(y,v,height=.53,color=GROUP[j],edgecolor='white',lw=.5);bar.text(v+.15,y,f'{v:.2f}',va='center',fontsize=8.5)
            bar.text(0,y+.64,f'{len(g["services"])}区｜{g["boxes"]}箱｜{g["transport_trips"]}架次',fontsize=8.5,va='center',color=SECOND)
        bar.set(xlim=(0,14),ylim=(2*k-.3,-.8),yticks=np.arange(k)*2,yticklabels=[g['group']for g in d['groups']],xticks=[0,4,8,12],xlabel='运输累计占用（h）');grid(bar,'x');title(bar,f'({"cd"[i]}) 组工作量',pad=8)
        fig.text(bar.get_position().x0,.028,f'运输Gini {d["transport_gini"]:.4f}｜分类缺口 {d["resource_gap_total"]}',fontsize=8.5,color=TEXT)
    shared.add_terrain_colorbar(fig,maps[-1],rect=[.30,.495,.46,.014])
    fig.legend(handles=[Line2D([],[],ls='',marker=['o','s','^'][i],ms=5,color=GROUP[i],label=f'G{i+1}')for i in range(k)],loc='upper left',bbox_to_anchor=(.04,.995),ncol=k,frameon=False,fontsize=8.5,columnspacing=1.3)
    fig.text(.98,.968,'服务区省略 S 前缀；细线为共同任务关系',fontsize=8.5,ha='right',color=SECOND)
    table(f'fig_{21+k}_group_work.csv',[{**{kk:vv for kk,vv in g.items()if not isinstance(vv,list)},'K':k,'policy':d['policy_key'],'services':';'.join(g['services']),'trip_ids':';'.join(g['trip_ids'])}for d in data for g in d['groups']])
    checks.append(check('saved resource gaps', [d['resource_gap_total']for d in data]==([1,5]if k==2 else[3,9])))
    caption=f'固定Q3任务分为{k}组时，两种偏好的空间归属与运输工作量。地图采用同一原始DEM、范围与比例；节点形状和颜色仅表示成员归属，细线仅标共同运输任务关系，不定义连续边界。下排两侧均由正式运输架次求和，单位小时不表示完工时间。完整中继任务按组复制；资源优先与均衡偏好缺口分别为'+('1和5。'if k==2 else'3和9；资源优先缺口由C型运输机、C型电池与中继机各1组成。')
    save(fig,21+k,caption,'均衡偏好改变组成员与工作量分布，并提高固定任务下的独立资源缺口。',{'a-b':'same-extent side-by-side actual group membership maps','c-d':'same-definition pure transport workload and actual counts','footer':'archived normalized transport Gini and class gap total'}, {'partitions':data,'common_task_relation_edges':sorted(route_edges),'nodes':NODES,'terrain':shared.MAP_SPEC.get('terrain')},['results/q4/Q4_partition_config.csv','results/q4/Q4_balanced_groups.csv','results/q4/Q4_preference_comparison.csv','results/q4/Q4_enumeration_certificate.json','results/q3/Q3_transport_trips.csv','results/q3/Q3_communication.csv','results/q3/Q3_relay_sorties.csv',next(RAW.rglob('*30米DEM.tif')),'src/q4/partition.py'],{'服务区列表/services':'actual group membership','开始时刻_s/返回O01时刻_s':'same pure transport workload on both sides','transport_work_s':'balanced archive cross-check','工作量_s':'mixed original workload decomposed, not plotted as transport work','transport_gini/shortage':'footer archived comparisons'},['K+policy+group','service member set to whole route','trip_id to assigned relay'],['transport_work_s=sum(return-start) for tasks wholly contained in the group','transport_work_h=transport_work_s/3600','group counts retain source exact integers','normalized Gini independently recomputed on pure transport workload'],checks,parameters={'same_map_dimensions':True,'map_height_cm':15.2*.3,'statistics_same_x_h':[0,14],'service_labels':'S prefix omitted only in image','no_continuous_group_boundaries':True})

def fig18():
    streams=[(1.0,rows('paper/figure_data_v2/communication_states_1s.csv')),(.5,rows('paper/figure_data_v2/communication_states_05s.csv'))]
    insufficient=[];bad_by=defaultdict(list);summary=[]
    for step,rr in streams:
        summary.append({'step_s':step,'count':len(rr),'uncovered':sum(f(r,'available_margin_db')<0 for r in rr),'minimum_margin_db':min(f(r,'available_margin_db')for r in rr)})
        for r in rr:
            if f(r,'direct_margin_db')<0:
                v={'trip':r['trip'],'time_s':f(r,'time_s'),'direct_margin_db':f(r,'direct_margin_db'),'sampling_s':step};insufficient.append(v);bad_by[r['trip']].append(v['time_s'])
    cm={r['运输架次编号']:r for r in COMM};ordered=[];groups=[];y=0
    for rid in [r['中继架次编号']for r in RELAYS]+['']:
        subset=sorted([r for r in TRIPS if cm[r['架次编号']]['中继架次编号']==rid],key=lambda r:(f(r,'开始时刻_s'),r['架次编号']));ys=[]
        for r in subset:ordered.append({'trip':r['架次编号'],'relay':rid,'display_y':y,'start_s':f(r,'开始时刻_s'),'return_s':f(r,'返回O01时刻_s'),'envelope_start_s':f(cm[r['架次编号']],'开始时刻_s')if rid else None,'envelope_end_s':f(cm[r['架次编号']],'结束时刻_s')if rid else None});ys.append(y);y+=1
        groups.append({'relay':rid,'first_y':min(ys),'last_y':max(ys),'count':len(ys)});y+=.5
    fig=canvas(16.0);top=fig.add_axes([.16,.75,.81,.13]);ax=fig.add_axes([.16,.085,.81,.59],sharex=top)
    for i,r in enumerate(RELAYS):
        lo,hi=f(r,'建链完成时刻_s')/60,f(r,'服务结束时刻_s')/60
        top.plot([lo,hi],[i,i],color=RELAY[i],lw=1.5);top.plot([lo,hi],[i,i],ls='',marker=['o','s','D'][i],ms=4.2,color=RELAY[i])
        g=groups[i];ax.add_patch(Rectangle((lo,g['first_y']-.5),hi-lo,g['last_y']-g['first_y']+1,fc=RELAY[i],ec='none',alpha=.06,zorder=0));ax.vlines([lo,hi],g['first_y']-.5,g['last_y']+.5,color=RELAY[i],alpha=.32,lw=.65,zorder=1)
    for r in ordered:
        yy=r['display_y'];lo,hi=r['start_s']/60,r['return_s']/60
        ax.barh(yy,hi-lo,left=lo,height=.18,color='#CED5DD',edgecolor='none',zorder=2)
        if r['relay']:
            i=[x['中继架次编号']for x in RELAYS].index(r['relay']);co=RELAY[i];aa,bb=r['envelope_start_s']/60,r['envelope_end_s']/60
            ts=np.unique(bad_by[r['trip']])/60;ax.vlines(ts,yy+.08,yy+.22,color=co,lw=.35,alpha=.48,rasterized=True,zorder=3)
            ax.hlines(yy-.12,aa,bb,color=co,lw=1.15,zorder=4);ax.vlines([aa,bb],yy-.27,yy+.03,color=co,lw=1.15,zorder=4)
    for i,g in enumerate(groups):ax.text(-.12,(g['first_y']+g['last_y'])/2,f'R{i}'if i<3 else'采样\n全直连',transform=ax.get_yaxis_transform(),ha='center',va='center',fontsize=8.5,fontweight='bold',color=RELAY[i]if i<3 else SECOND)
    top.set(yticks=[0,1,2],yticklabels=['R0','R1','R2'],ylim=(2.55,-.55));top.tick_params(labelbottom=False);title(top,'(a) 指定中继的完整服务窗')
    ax.set(yticks=[r['display_y']for r in ordered],yticklabels=[numid(r['trip'])for r in ordered],ylim=(ordered[-1]['display_y']+.55,-.55),xlim=(0,105),xlabel='自任务起点计时（min）');ax.tick_params(axis='y',labelsize=8.5,pad=2);title(ax,'(b) 任务区间、不足包络与真实采样点')
    for a in [top,ax]:a.xaxis.set_major_locator(MultipleLocator(20));grid(a,'x')
    fig.legend(handles=[Patch(fc='#CED5DD',label='完整任务区间'),Line2D([],[],color=RELAY[0],lw=1.15,marker='|',ms=6,label='不足采样首末包络'),Line2D([],[],ls='',marker='|',color=RELAY[0],ms=3,label='直连不足采样点'),Patch(fc=RELAY[0],alpha=.10,label='指定完整窗投影')],loc='upper center',bbox_to_anchor=(.56,1.003),frameon=False,ncol=2,fontsize=8.5,handlelength=1.6,columnspacing=1.6)
    checks=[check('24 task rows',len(ordered)==24 and len({r['trip']for r in ordered})==24),check('relay groups 6/9/3/6',[g['count']for g in groups]==[6,9,3,6]),check('replay counts 35061/69843',[s['count']for s in summary]==[35061,69843]),check('no uncovered replay states',all(s['uncovered']==0 for s in summary)),check('minimum replay equals archived within tolerance',all(abs(s['minimum_margin_db']-CRITICAL['state']['available_margin_db'])<=TOL for s in summary))]
    for r in ordered:
        if r['relay']:
            rr=RMAP[r['relay']];checks.append(check(r['trip']+' actual envelope and 5s protection',abs(min(bad_by[r['trip']])-r['envelope_start_s'])<=TOL and abs(max(bad_by[r['trip']])-r['envelope_end_s'])<=TOL and r['envelope_start_s']-5>=f(rr,'建链完成时刻_s')-TOL and r['envelope_end_s']+5<=f(rr,'服务结束时刻_s')+TOL))
        else:checks.append(check(r['trip']+' no negative direct sample',not bad_by[r['trip']]))
    table('fig_18_ordered_tasks.csv',ordered);table('fig_18_direct_insufficient_samples.csv',insufficient)
    save(fig,18,'指定中继服务窗与固定运输任务的直连不足采样。24行按R0、R1、R2和采样全直连分组，再按任务开始排序；淡色背景仅为指定完整窗投影。开括号为已存不足采样首末包络，内部短刻度来自原模型1 s与0.5 s确定性重放，不表示内部始终不足或真实切换日志。连续通信结论见固定轨迹数值证书。','真实不足采样点及其首末包络均落在正式指定中继的服务窗内。',{'a':'three exact full service windows','b':'grouped 24 formal tasks with true insufficiency samples, saved envelopes and designated window projection'}, {'ordered_tasks':ordered,'groups':groups,'direct_insufficient_samples':insufficient,'relay_rows':RELAYS,'replay_summary':summary},['results/q3/Q3_transport_trips.csv','results/q3/Q3_relay_sorties.csv','results/q3/Q3_communication.csv','paper/figure_data_v2/communication_states_1s.csv','paper/figure_data_v2/communication_states_05s.csv','paper/figure_data_v2/q3_replay_verification.json'],{'task start/return':'gray task bars','saved communication start/end':'open brackets','direct_margin_db<0':'real negative sample ticks','relay service start/end':'full windows and light projection'},['trip=运输架次编号','assigned relay=中继架次编号'],['negative sampling ticks are not interpolated','row sort by assigned relay, formal start, trip ID','sampling minimum compared within original numerical tolerance, archived displayed value retained'],checks,limits=['Dense replay is deterministic plotting evidence for the frozen plan; it is not a flight switching log or continuous-time proof.'],parameters={'sampling_tick_height_rows':.14,'sampling_linewidth_pt':.35,'task_row_order':'R0/R1/R2/direct then start/id','shared_time_axis_min':[0,105]})

def fig17():
    from matplotlib.collections import LineCollection
    links=load('paper/figure_data_v2/q3_link_profiles.json');profiles=rows('paper/figure_data_v2/q3_link_profiles.csv');fig=canvas(16.8)
    left=fig.add_axes([.075,.565,.42,.325]);compact_map(left);title(left,'(a) 正式悬停位置')
    right=fig.add_axes([.56,.555,.375,.34],projection='3d');render3d=shared.terrain3d(right,exaggeration=2,stride=4);right.computed_zorder=False
    for surface in right.collections:surface.set_zorder(0)
    right.set_xlabel('E（km）',labelpad=1);right.set_ylabel('N（km）',labelpad=1);right.set_zlabel('');right.set_zticks([0,800])
    right.text2D(.99,.72,'海拔（m）',transform=right.transAxes,ha='right',fontsize=8.5)
    title(right,'(b) 同一状态的三维链路',pad=2)
    for i,r in enumerate(RELAYS):
        x,y=shared.project(f(r,'悬停经度'),f(r,'悬停纬度'));z=f(r,'悬停海拔_m');mark=['o','s','D'][i]
        left.plot(x,y,marker=mark,ls='',ms=5.3,color=RELAY[i],mec='white',mew=.7,zorder=9);left.annotate(f'R{i}',(x,y),xytext=[(-8,8),(4,9),(-21,9)][i],textcoords='offset points',fontsize=8.5,fontweight='bold',color=RELAY[i],path_effects=[pe.withStroke(linewidth=1.4,foreground='white')],zorder=10)
        right.scatter([x],[y],[z],marker=mark,s=28,color=RELAY[i],edgecolor='white',linewidth=.5,depthshade=False,zorder=20);right.text(x,y,z+40,f'R{i}',fontsize=8.5,color=RELAY[i],path_effects=[pe.withStroke(linewidth=1.4,foreground='white')],zorder=30)
    st=CRITICAL['state'];sx,sy=shared.project(st['longitude'],st['latitude']);left.plot(sx,sy,marker='*',ms=7,color=RED,mec='white',mew=.6,zorder=9);left.annotate('最紧状态',(sx,sy),xytext=(4,-23),textcoords='offset points',fontsize=8.5,color=RED,path_effects=[pe.withStroke(linewidth=1.3,foreground='white')],zorder=10)
    right.scatter([sx],[sy],[st['altitude_m']],marker='*',s=38,color=RED,depthshade=False,zorder=20);right.text(sx+.25,sy,st['altitude_m']+80,'最紧状态',fontsize=8.5,color=RED,path_effects=[pe.withStroke(linewidth=1.4,foreground='white')],zorder=30)
    gx,gy=shared.xy('O01');gz=NODES['O01']['elev']+20;right.scatter([gx],[gy],[gz],marker='*',s=40,color=TEXT,depthshade=False,zorder=20);right.text(gx,gy,gz+60,'G01',fontsize=8.5,path_effects=[pe.withStroke(linewidth=1.4,foreground='white')],zorder=30)
    style={'direct':(RED,'--','直连'),'access':(RELAY[2],'-','接入'),'backhaul':(RELAY[2],'-.','回传')}
    for link in links:
        col,ls,name=style[link['link']];p,q=link['from'],link['to'];px,py=shared.project(*p[:2]);qx,qy=shared.project(*q[:2]);right.plot([px,qx],[py,qy],[p[2],q[2]],color=col,ls=ls,lw=1.5,zorder=10)
    shared.add_terrain_colorbar(fig,left,rect=[.10,.505,.37,.012]);fig.text(.565,.485,'正交视图；显示垂直夸张×2',fontsize=8.5,color=SECOND)
    axs=[fig.add_axes([.09+i*.305,.13,.255,.23])for i in range(3)]
    for i,(link,ax)in enumerate(zip(links,axs)):
        key=link['link'];rr=[r for r in profiles if r['link']==key];col,ls,name=style[key];segments=[];zero=[]
        for r in rr:
            a,b,z=f(r,'frac_start'),f(r,'frac_end'),f(r,'terrain_m')
            if b>a:ax.add_patch(Rectangle((a,0),b-a,z,fc='#D7C7AD',ec='none',alpha=.40));segments.append([(a,z),(b,z)])
            else:zero.append((a,z))
        ax.add_collection(LineCollection(segments,colors='#7E775F',linewidths=.6));
        if zero:ax.scatter(*np.array(zero).T,marker='|',s=8,color='#7E775F',linewidth=.6)
        ax.plot([0,1],[link['from'][2],link['to'][2]],color=col,ls=ls,lw=1.5);ax.set(xlim=(0,1),ylim=(0,500),xticks=[0,.5,1],yticks=[0,250,500],xlabel='归一化沿程位置');grid(ax,'y');title(ax,f'({"cde"[i]}) {name}',pad=8)
        if i:ax.tick_params(labelleft=False)
        else:ax.set_ylabel('真实海拔（m）')
        ax.text(.025,.95,f'{link["distance_m"]/1000:.3f} km\n{link["margin_db"]:.6f} dB',transform=ax.transAxes,fontsize=8.5,va='top',linespacing=1.35)
    handles=[Line2D([],[],color=style[k][0],ls=style[k][1],lw=1.5,label=style[k][2]+'视线')for k in style]+[Patch(fc='#D7C7AD',ec='#7E775F',label='原闭像元地形')]
    fig.legend(handles=handles,loc='center',bbox_to_anchor=(.53,.418),ncol=4,frameon=False,fontsize=8.5,columnspacing=1.15,handlelength=1.65)
    fig.legend(handles=[Line2D([],[],ls='',marker=['o','s','D'][i],ms=5,color=RELAY[i],label=f'R{i} · {r["中继无人机编号"]} · 离地{RPLAN[r["中继架次编号"]]["agl_m"]:.0f} m')for i,r in enumerate(RELAYS)],loc='upper center',bbox_to_anchor=(.52,.995),ncol=3,frameon=False,fontsize=8.5,columnspacing=.8,handletextpad=.35)
    fig.text(.09,.025,'同一状态：4684.446 s、海拔230 m；遮挡附加损耗不等于链路不可用。',fontsize=8.5,color=SECOND)
    checks=[check('critical horizontal position equals S009',st['longitude']==NODES['S009']['lon'] and st['latitude']==NODES['S009']['lat']),check('critical altitude230',st['altitude_m']==230),check('3 real rays',set(x['link']for x in links)=={'direct','access','backhaul'}),check('R2 available despite obstructed access',next(x for x in links if x['link']=='access')['obstructed'] and next(x for x in links if x['link']=='access')['margin_db']>0),check('gateway source altitude',gz==147.7),check('all ray terrain and endpoints inside 0-500m profile scale',all(0<=f(r,'terrain_m')<=500 for r in profiles) and all(0<=p[2]<=500 for l in links for p in [l['from'],l['to']]))]
    for l in links:
        archived=CRITICAL[{'direct':'direct_margin_db','access':'access_margin_db','backhaul':'backhaul_margin_db'}[l['link']]];checks.append(check(l['link']+' replay margin archived',abs(l['margin_db']-archived)<=TOL))
    save(fig,17,'正式中继位置与最紧采样状态的链路几何。三条视线及原闭像元地形剖面均来自column-019在4684.446 s的同一真实状态；指定R2接入和回传余量同时为正。三维采用真实海拔、正交视图及明确的垂直显示夸张×2；节点输入海拔与原始DEM高程分别保留。剖面逐闭像元区间绘制，零长边界接触保留为短标记；遮挡按原模型附加损耗计入，不直接判为断链。','真实位置、视线高度和地形共同解释最紧状态为何需指定R2且仍可用。',{'a':'all actual relay positions on common terrain extent','b':'same critical state direct/access/backhaul rays at real altitude; 2x visual vertical scale','c-e':'three independently retained closed-cell ray profiles, common true elevation scale'}, {'critical_state':CRITICAL,'relay_rows':RELAYS,'link_endpoints':links,'closed_cell_profiles':profiles,'terrain':shared.MAP_SPEC.get('terrain')},['results/q3/Q3_relay_sorties.csv','results/q3/Q3_selected_plan.json','paper/data/communication_critical_state.json','paper/figure_data_v2/q3_link_profiles.csv','paper/figure_data_v2/q3_link_profiles.json','paper/figure_data_v2/q3_replay_verification.json',next(RAW.rglob('*30米DEM.tif'))],{'relay lon/lat/altitude':'true suspended relay positions','critical state lon/lat/altitude/time':'same source point in maps and rays','frac_start/end,terrain_m':'per closed-cell terrain interval','from/to and line_start/end':'actual linearly varying sightline altitude'},['link identity','relay trip ID','critical state trip/time'],['ENU projection changes display only','profile plots each closed-cell interval independently; no row-order polyline interpolation','display 3D box aspect converts km/m correctly with stated 2x vertical exaggeration'],checks,parameters={'three_dimensional_display':render3d,'profile_shared_elevation_m':[0,500],'three_dimensional_labels_and_rays_overlay_surface':True,'terrain_zero_length_contacts_preserved':True})

FUNCTIONS={17:fig17,18:fig18,19:fig19,20:fig20,21:fig21,22:fig22,23:lambda:fig_partition(2),24:lambda:fig_partition(3),25:fig25,26:fig26,27:fig27}
if __name__=='__main__':
    for n in ([int(a) for a in sys.argv[1:]] or sorted(FUNCTIONS)):FUNCTIONS[n]()
