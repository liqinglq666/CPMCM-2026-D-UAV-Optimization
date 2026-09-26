"""Q2 publication figures from frozen outputs and deterministic phase replay."""
import sys
from collections import defaultdict,Counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator
import matplotlib.patheffects as pe
import common as co
from paths import REPO,OUT,WORK,DATA

Q2='results/q2/'
C=co.C; STAGE={**co.STAGE,'prep_load':co.STAGE['prep']}
LABELS={'prep_load':'准备装载','flight':'飞行','handover':'交接','return':'返航','charge':'充电'}
TH=co.THRESHOLD;TXT=co.TEXT;SUB=co.SECONDARY
def rc(rel):return co.rows(rel)
def f(row,key):return float(row[key])
TRIPS=rc(Q2+'Q2_transport_trips_balanced.csv');RES=rc(Q2+'Q2_resource_check.csv')
SUM=rc('paper/figure_data_v2/q2_trip_summary.csv');PH=rc('paper/figure_data_v2/q2_task_phases.csv')
TRAJ=rc('paper/figure_data_v2/q2_trajectory.csv');EVENTS=rc('paper/figure_data_v2/q2_delivery_events.csv')
MET=co.js(Q2+'Q2_metrics.json');RET=MET['makespan'];BY={r['架次编号']:r for r in TRIPS}
TB={r['trip_id']:r for r in SUM};PB=defaultdict(list);XB=defaultdict(list)
for r in PH:PB[r['trip_id']].append(r)
for r in TRAJ:XB[r['trip_id']].append(r)
plt.rcParams['hatch.linewidth']=.35

def panel(ax,s):co.panel(ax,s)
def grid(ax,axis='both'):co.grid(ax,axis)
def pad(vals,frac=.08):
    lo=min(vals);hi=max(vals);d=max(hi-lo,.1);return lo-frac*d,hi+frac*d
def check(name,yes,**kw):return {'check':name,'passed':bool(yes),**kw}
def fig(h):return plt.figure(figsize=(16.3/2.54,h/2.54))
def stage_legend(figure,y,charge=False):
    kinds=['prep_load','flight','handover','return']+(['charge']if charge else [])
    handles=[Patch(facecolor=STAGE[k],edgecolor=co.STAGE_EDGE['charge']if k=='charge'else SUB,
       hatch='/'if k=='charge'else None,linewidth=.45,label=LABELS[k])for k in kinds]
    figure.legend(handles=handles,loc='upper center',bbox_to_anchor=(.56,y),ncol=len(kinds),frameon=False,
                  fontsize=8,handlelength=1.3,columnspacing=.9)
def save(figure,n,caption,claim,data,sources,derivations,checks,parameters=None):
    assert all(c['passed']for c in checks),(n,checks)
    sources=list(sources)
    if n in [11,12,13]:
        for required in ['paper/data/analysis.json','paper/figure_data_v2/q2_trajectory.csv','paper/figure_data_v2/q2_task_phases.csv']:
            if required not in sources:sources.append(required)
    source_entries=[{'path':s,'sha256':co.sha(REPO/s)}for s in sources]
    if n in [11,12,13]:
        import terrain
        source_entries.append({'path':str(terrain.DEM_PATH),'sha256':co.sha(terrain.DEM_PATH),'scope':'raw_input'})
    co.save_figure(figure,n,caption,sources,data,extra={'core_claim':claim,'sources':source_entries,
      'derivations':derivations,'join_keys':['trip_id / 架次编号','box_id / 货箱编号','phase_id'],
      'data_checks':checks,'parameters':parameters or {},'minimum_necessary_font_pt':8,
      **figure_metadata(n),
      'replay_audit':'paper/figure_data_v2/q2_replay_audit.json',
      'verification_scope':'Frozen-output and deterministic physical replay comparisons; no optimization.',
      'visual_review':{'status':'pending'}})
    (DATA/f'q2_fig{n:02d}_data.json').write_text((OUT/f'fig_{n:02d}_data.json').read_text(encoding='utf-8'),encoding='utf-8')
    import pymupdf as fitz
    from PIL import Image
    doc=fitz.open(OUT/f'fig_{n:02d}.pdf');pix=doc[0].get_pixmap(dpi=180,alpha=False)
    pix.save(WORK/f'fig_{n:02d}_color.png')
    Image.open(WORK/f'fig_{n:02d}_color.png').convert('L').save(WORK/f'fig_{n:02d}_gray.png')
    print('saved',n)

def figure_metadata(n):
    phase_fields=['trip_id','type_code','uav_id','battery_id','phase_id','phase_kind','display_phase','t_begin_s','t_end_s','source','target','payload_kg','altitude_begin_m','altitude_end_m','cumulative_distance_begin_m','cumulative_distance_end_m']
    trajectory_fields=['trip_id','phase_id','phase_kind','relative_time_s','lon','lat','altitude_m','payload_kg','cumulative_distance_m']
    formal_fields=['架次编号','无人机编号','机型编号','电池编号','开始时刻（s）','访问服务区顺序','返回O01时刻（s）','架次能耗（kWh）','返航SOC（%）','货箱编号列表']
    resource_fields=['架次编号','资源类型','资源编号','机型','任务占用开始（s）','任务占用结束（s）','充电开始（s）','充电结束（s）','充电时长（s）']
    mappings={
     10:({'Q2_pareto_frontier.csv':['plan_id','weighted_tardiness','trips','makespan','energy','hard_violations'],'Q2_preference_frontier.csv':['preference','epsilon','horizon_s','makespan_s','energy_kwh','trips','source'],'Q2_metrics.json':['trips','makespan','energy']},
         {'a':'x=makespan/60; y=energy; star=formal metrics match','b':'x=energy; y=weighted_tardiness/1000','c':'x=makespan_s/60; y=energy_kwh; label=epsilon'},
         {'a':'weighted_tardiness<=1e-5 and hard_violations==0','b':'all 42 archived rows','c':'all 4 preference rows'},
         ['(a) 正式选择在全准时候选中的位置','(b) 全档案的能耗与延误取舍','(c) 已存返航完工上限偏好的节能效果']),
     11:({'Q2_transport_trips_balanced.csv':formal_fields,'q2_task_phases.csv':phase_fields,'q2_trajectory.csv':trajectory_fields,'q2_delivery_events.csv':['box_id','trip_id','service','mass_kg','delivery_s'],'analysis.json':['nodes.lon','nodes.lat','nodes.elev','boxes.id','boxes.mass']},
         {'a':'x,y=ENU(lon,lat) from exact cruise samples; route grouping by ordered service IDs','b':'x,y=ENU(lon,lat), z=absolute altitude_m','c':'x=phase end relative seconds/60; y=remaining assigned box mass; stage band=display_phase'},
         {'a':'type_code=A, all 12 trips','b,c':'trip_id=Q2-018'},
         ['(a) A型12架次的完整有向空间组织','(b) 同一真实多点任务的垂直航迹','(c) 交接完成后的载荷阶梯与阶段长度']),
     12:({'Q2_transport_trips_balanced.csv':formal_fields,'q2_trip_summary.csv':['trip_id','route','initial_payload_kg','energy_kwh','soc_pct','uav_id'],'q2_trajectory.csv':trajectory_fields,'q2_task_phases.csv':phase_fields,'analysis.json':['nodes.lon','nodes.lat','nodes.elev']},
         {'a':'x,y=ENU(lon,lat); B long-dash routes','b':'common row=trip_id sorted by destination then ID; separate x axes=mass kg, energy kWh, SOC percent'},
         {'all':'type_code=B, all 6 trips; no numerical aggregation across same destination'},
         ['(a) B型5条路线与6架次的关系','(b) 相同目的地的真实装载与能量属性逐条对照']),
     13:({'Q2_transport_trips_balanced.csv':formal_fields,'q2_trip_summary.csv':['trip_id','initial_payload_kg','energy_kwh','soc_pct'],'q2_020_profile.csv':['leg_id','row','col','begin_m','end_m','elevation_m','cruise_altitude_m'],'q2_trajectory.csv':trajectory_fields,'q2_task_phases.csv':phase_fields,'analysis.json':['nodes.lon','nodes.lat','nodes.elev']},
         {'a':'x,y=ENU; highlight=min-SOC C trip','b':'x=initial_payload_kg, y=soc_pct; text=trip suffix and energy_kwh','c':'x=cumulative horizontal metres/1000; y=raw closed-cell elevation and actual model altitude; strip=payload_kg'},
         {'a,b':'type_code=C, all 6 trips','c':'trip_id=min C SOC=Q2-020, full outward and reverse closed-cell intervals'},
         ['(a) C型正式路线与关键架次','(b) 全部C型任务的实际装载和返航储备','(c) 最低SOC任务的固定路线原地形、航高与卸货口径']),
     14:({'Q2_box_delivery_balanced.csv':['货箱编号','架次编号','服务区编号','交付完成时刻（s）','期望送达时间（s）','硬截止时间（s）'],'Q2_metrics.json':['makespan'],'q2_delivery_events.csv':['box_id','first_batch','hard_deadline_s']},
         {'a':'x=delivery time/60; y=cumulative exact integer box count','b':'x=box rank by expected slack; y=(expected-delivery)/60','c':'independent box rank by hard slack; y=(hard deadline-delivery)/60'},
         {'a,b':'all 80 unique box IDs','c':'hard deadline present, 31 boxes; first batch OR medical'},
         ['(a) 末箱交付与返航结束的不同时间含义','(b) 全部期望时间余量','(c) 真实硬约束集合的独立余量']),
     15:({'Q2_resource_check.csv':resource_fields,'Q2_transport_trips_balanced.csv':formal_fields,'q2_task_phases.csv':phase_fields},
         {'a':'x=absolute phase start/end divided by60; y=UAV ID; fill=display_phase; row stripe=type','b':'x=global event time/60; y=count(start<=t<end) by type'},
         {'all':'resource type=无人机; all 24 tasks and 8 entities'},
         ['(a) 固定无人机分配内的真实阶段和释放时间','(b) 半开占用区间给出的同型实体峰值']),
     16:({'Q2_resource_check.csv':resource_fields,'Q2_transport_trips_balanced.csv':formal_fields,'q2_task_phases.csv':phase_fields},
         {'a':'x=phase/charging absolute intervals divided by60; y=battery ID; fill=stage and charging hatch','b':'same actual intervals for the smallest refill-to-reuse gap; entity label joined by trip ID'},
         {'a':'resource type=电池; all 24 task records and 14 batteries','b':'minimum nonnegative next-start minus prior-charge-end; tie by battery ID then trip ID'},
         ['(a) 返航以后仍持续的真实电池占用','(b) 一个零等待复用边界及跨实体使用证据'])}
    fields,mapping,filters,purposes=mappings[n]
    return {'source_fields':fields,'field_mapping':mapping,'filters':filters,'panel_purposes':purposes}

def route_map(ax,typ,highlight=None,short=False):
    co.map_base(ax,labels=False,draw_nodes=False)
    records=[r for r in SUM if r['type_code']==typ]
    edge_rows={};routes=defaultdict(list)
    for r in records:
        tid=r['trip_id'];routes[r['route']].append(tid)
        for p in PB[tid]:
            if p['phase_kind']=='cruise':edge_rows[(p['source'],p['target'])]=(tid,p['phase_id'])
    ls={'A':'-','B':(0,(5,2)),'C':(0,(5,2,1,2))}[typ]
    for (a,b),(tid,pid)in edge_rows.items():
        ss=[r for r in XB[tid]if r['phase_id']==pid];pts=np.array([co.project(f(r,'lon'),f(r,'lat'))for r in ss])
        line,=ax.plot(pts[:,0],pts[:,1],color=C[typ],lw=.8 if highlight else 1.35,ls=ls,zorder=3,alpha=.55 if highlight else .95)
        line.set_path_effects([pe.Stroke(linewidth=2.3,foreground='white',alpha=.8),pe.Normal()])
        j=max(1,int(len(pts)*.45));k=min(len(pts)-1,j+max(1,int(len(pts)*.025)))
        ax.annotate('',xy=pts[k],xytext=pts[j],arrowprops={'arrowstyle':'-|>','color':C[typ],'lw':.6,'mutation_scale':5},zorder=4)
    if highlight:
        ps=np.array([co.project(f(r,'lon'),f(r,'lat'))for r in XB[highlight]])
        li,=ax.plot(ps[:,0],ps[:,1],color=C[typ],lw=1.6,zorder=4)
        li.set_path_effects([pe.Stroke(linewidth=2.8,foreground='white',alpha=.85),pe.Normal()])
        for p in PB[highlight]:
            if p['phase_kind']=='cruise':
                a=np.array(co.project(f(p,'lon_begin'),f(p,'lat_begin')));b=np.array(co.project(f(p,'lon_end'),f(p,'lat_end')))
                ax.annotate('',xy=a+.55*(b-a),xytext=a+.50*(b-a),arrowprops={'arrowstyle':'-|>','color':C[typ],'lw':.8,'mutation_scale':6},zorder=6)
    visited={s for r in records for s in r['route'].split('->')}
    for k in co.nodes:
        if k!='O01':ax.scatter(*co.xy(k),s=23 if k in visited else 12,marker=co.MARKERS[typ]if k in visited else 'o',facecolor='white',edgecolor=C[typ]if k in visited else '#8D969E',linewidth=.7,zorder=7)
        label=k[1:]if short and k!='O01'else k
        off=co.MAP_SPEC['label_offsets'][k]
        if typ=='B':off={'S001':(-7,8),'S013':(-14,-14)}.get(k,off)
        ax.annotate(label,co.xy(k),xytext=off,textcoords='offset points',fontsize=8.5,zorder=9,
            bbox={'facecolor':'white','edgecolor':'none','alpha':.80,'pad':.25})
    return {'type':typ,'trip_ids':[r['trip_id']for r in records],
      'routes':[{'route':route,'trip_ids':ids,'multiplicity':len(ids)}for route,ids in routes.items()],
      'ordered_directed_edges':[list(e)for e in edge_rows],
      'positions_source':'q2_trajectory.csv exact cruise sampling; ENU display projection only'}

def figure11():
    figure=fig(17.0)
    ax=figure.add_axes([.085,.48,.88,.475])
    route_view=route_map(ax,'A','Q2-018')
    panel(ax,'(a) A型：12架次 · 4实体 · 8条路线')
    ax.text(.98,.963,'重点：018  O01→S003→S015→O01',transform=ax.transAxes,ha='right',fontsize=8.5,
            bbox={'facecolor':'white','alpha':.9,'edgecolor':'none','pad':2},zorder=10)
    co.add_terrain_colorbar(figure,ax,[.29,.396,.50,.012])
    ax3=figure.add_axes([.015,.02,.46,.315],projection='3d',computed_zorder=False)
    meta=co.terrain3d(ax3,exaggeration=2,stride=4)
    tr=XB['Q2-018'];ps=np.array([(*co.project(f(r,'lon'),f(r,'lat')),f(r,'altitude_m'))for r in tr])
    ax3.plot(ps[:,0],ps[:,1],ps[:,2],color='white',lw=3,zorder=8)
    ax3.plot(ps[:,0],ps[:,1],ps[:,2],color=C['A'],lw=1.6,zorder=9)
    for node,offset in [('O01',(0,-10)),('S003',(-5,4)),('S015',(3,4))]:
        x,y=co.xy(node);z=co.nodes[node]['elev']+(0 if node=='O01'else 30)
        ax3.scatter(x,y,z,s=14,color=C['A'],depthshade=False,zorder=10)
        ax3.text(x,y,z+35,node,fontsize=8,zorder=11)
    ax3.text2D(.02,.99,'(b) 018真实航迹',transform=ax3.transAxes,fontsize=10,weight='bold')
    ax3.text2D(.02,.90,'显示垂直夸张×2',transform=ax3.transAxes,fontsize=8)
    ax3.xaxis.labelpad=0;ax3.yaxis.labelpad=0;ax3.zaxis.labelpad=0
    al=figure.add_axes([.605,.11,.36,.205]);panel(al,'(c) 018卸货与阶段')
    ps=PB['Q2-018'];x=[0.];mass=[f(TB['Q2-018'],'initial_payload_kg')];unloads=[]
    for p in ps:
        if p['phase_kind']=='handover':
            end=f(p,'t_end_relative_s')/60;unload=sum(f(e,'mass_kg')for e in EVENTS if e['trip_id']=='Q2-018'and e['service']==p['source'])
            x.append(end);mass.append(mass[-1]-unload);unloads.append({'service':p['source'],'time_min':end,'unload_kg':unload,'remaining_kg':mass[-1]})
    x.append(f(TB['Q2-018'],'duration_s')/60);mass.append(0.)
    al.step(x,mass,where='post',color=C['A'],lw=1.6)
    for i,u in enumerate(unloads):
        al.scatter(u['time_min'],u['remaining_kg'],s=20,color=C['A'],zorder=4)
        al.annotate(f"{u['service']}\n卸{u['unload_kg']:g} kg",(u['time_min'],u['remaining_kg']),xytext=(-5,18 if i else 15),textcoords='offset points',ha='right',fontsize=8.5,arrowprops={'arrowstyle':'-','color':SUB,'lw':.5})
    for p in ps:
        al.broken_barh([(f(p,'t_begin_relative_s')/60,(f(p,'t_end_relative_s')-f(p,'t_begin_relative_s'))/60)],(-4.7,1.7),facecolor=STAGE[p['display_phase']],edgecolor='white',linewidth=.2)
    al.set(xlabel='任务内时间 (min)',ylabel='剩余载荷 (kg)',xlim=(0,x[-1]),ylim=(-5,23),yticks=[0,10,20]);grid(al)
    stage_legend(figure,.066)
    caption='A型正式路线与Q2-018多点任务过程。二维图保留全部12架次的几何关系，重点路线为O01—S003—S015—O01；三维航迹和载荷阶梯由冻结方案确定性重放，交付后重新爬升且按实际卸货更新载荷。三维显示垂直夸张为2倍，海拔刻度保留真实值；节点作业高度与原始DSM分别来自官方节点表与栅格。'
    save(figure,11,caption,'全部A型任务的空间组织与同一多点架次的垂直阶段、载荷更新互证。',
      {'routes':route_view,'representative_summary':TB['Q2-018'],'phases':ps,'trajectory':tr,'unloads':unloads},
      [Q2+'Q2_transport_trips_balanced.csv','paper/figure_data_v2/q2_018_trajectory.csv','paper/figure_data_v2/q2_task_phases.csv','paper/figure_data_v2/q2_trip_summary.csv','paper/figure_data_v2/q2_delivery_events.csv','paper/figure_data_v2/q2_replay_audit.json'],
      ['phase geometry from evaluate_route + sample_states; prep duration from official type','payload is reduced at each true handover completion','all 12 trips retained; repeated route count recorded in attached data'],
      [check('A_trip_count',len(route_view['trip_ids'])==12),check('A_ordered_routes',len(route_view['routes'])==8),check('Q2018_initial_mass',f(TB['Q2-018'],'initial_payload_kg')==20),check('remaining_zero',mass[-1]==0)],
      {'three_dimensional':meta,'map_spec':co.MAP_SPEC,'layout':'large 2D map above 3D trajectory and load-stage evidence','minimum_font_pt':8})

def figure10():
    raw=rc(Q2+'Q2_pareto_frontier.csv');pref=rc(Q2+'Q2_preference_frontier.csv')
    formal=[r for r in raw if int(r['trips'])==MET['trips']and abs(f(r,'makespan')-RET)<1e-5 and abs(f(r,'energy')-MET['energy'])<1e-5][0]
    on=[r for r in raw if f(r,'weighted_tardiness')<=1e-5 and int(r['hard_violations'])==0]
    best=min(on,key=lambda r:f(r,'energy'))
    figure=fig(13.7);gs=figure.add_gridspec(2,2,height_ratios=[1.15,1],left=.10,right=.975,bottom=.10,top=.935,hspace=.66,wspace=.39)
    a=figure.add_subplot(gs[0,:]);b=figure.add_subplot(gs[1,0]);c=figure.add_subplot(gs[1,1])
    for ax,records,xkey,ykey,xdiv,ydiv in [(a,on,'makespan','energy',60,1),(b,raw,'energy','weighted_tardiness',1,1000)]:
        xx=[f(r,xkey)/xdiv for r in records];yy=[f(r,ykey)/ydiv for r in records]
        ax.scatter(xx,yy,s=24,color='#8799AA',alpha=.75,zorder=3)
        ax.scatter(f(formal,xkey)/xdiv,f(formal,ykey)/ydiv,s=90,marker='*',facecolor='#234F70',edgecolor='white',lw=.7,zorder=5)
        ax.set(xlim=pad(xx),ylim=pad(yy));grid(ax)
    panel(a,'(a) 全准时候选：12个');a.set(xlabel='返航完工 (min)',ylabel='能耗 (kWh)')
    a.annotate(f"正式方案 · {formal['trips']}架次\n{f(formal,'makespan'):.3f} s · {f(formal,'energy'):.3f} kWh",(f(formal,'makespan')/60,f(formal,'energy')),xytext=(15,15),textcoords='offset points',fontsize=8.5,arrowprops={'arrowstyle':'-','lw':.5,'color':SUB})
    a.annotate(f"最低能耗候选 · {best['trips']}架次",(f(best,'makespan')/60,f(best,'energy')),xytext=(-7,18),textcoords='offset points',ha='right',fontsize=8.5,arrowprops={'arrowstyle':'-','lw':.5,'color':SUB})
    panel(b,'(b) 已保存档案：42个');b.set(xlabel='能耗 (kWh)',ylabel='加权延误 (10³系数·s)')
    panel(c,'(c) 返航上限偏好：4种')
    for i,r in enumerate(pref):
        x=f(r,'makespan_s')/60;y=f(r,'energy_kwh');epsilon=f(r,'epsilon')
        c.scatter(x,y,s=48 if epsilon==.2 else 36,marker='D'if epsilon==.2 else 'o',facecolor='#7C5295'if epsilon==.2 else 'white',edgecolor='#7C5295',lw=1,zorder=4)
        offsets={0:(4,-15),1:(0,-18),2:(0,-18),3:(-5,16)}
        c.annotate(f'{epsilon:.0%}',(x,y),xytext=offsets[i],textcoords='offset points',ha='right'if i==3 else 'left',fontsize=8.5)
    c.set(xlabel='返航完工 (min)',ylabel='能耗 (kWh)',xlim=pad([f(r,'makespan_s')/60 for r in pref]),ylim=pad([f(r,'energy_kwh')for r in pref],.16));grid(c)
    lastpref=next(r for r in pref if f(r,'epsilon')==.2)
    c.text(.98,.92,f"20%：{lastpref['trips']}架次\n{f(lastpref,'makespan_s'):.3f} s\n{f(lastpref,'energy_kwh'):.3f} kWh",transform=c.transAxes,ha='right',va='top',fontsize=8.5)
    caption='有限搜索候选与返航完工上限偏好。主图为12个全准时候选，下方分别为42条已保存档案与4种上限偏好；正式方案优先满足及时性与返航完工，20%放宽选项为22架次、63.370 kWh。逐箱时限保持不变，各点不构成原问题的完整Pareto前沿。'
    save(figure,10,caption,'正式方案、完整档案和已有节能偏好分别提供不同集合证据。',
      {'archive':raw,'ontime':on,'formal':formal,'preferences':pref,'overlap_multiplicities':[{ 'makespan':x,'energy':y,'count':n}for(x,y),n in Counter((f(r,'makespan'),f(r,'energy'))for r in on).items()if n>1]},
      [Q2+'Q2_pareto_frontier.csv',Q2+'Q2_preference_frontier.csv',Q2+'Q2_metrics.json'],
      ['time_min=time_s/60','weighted_delay_display=weighted_tardiness/1000','ontime=weighted_tardiness<=1e-5 and hard_violations=0; no jitter or connecting line'],
      [check('candidate_counts',len(raw)==42 and len(on)==12 and len(pref)==4),check('hard_violations_zero',all(int(r['hard_violations'])==0 for r in raw)),check('preference_caps',all(f(r,'makespan_s')<=f(r,'horizon_s')+1e-5 for r in pref))])

def figure12():
    records=sorted([r for r in SUM if r['type_code']=='B'],key=lambda r:(r['route'],r['trip_id']))
    figure=fig(10.8);ax=figure.add_axes([.075,.22,.445,.65]);rv=route_map(ax,'B')
    panel(ax,'(a) B型：6架次 · 2实体')
    co.add_terrain_colorbar(figure,ax,[.13,.125,.35,.016])
    figure.text(.625,.90,'(b) 六个正式架次',fontsize=10,weight='bold')
    xs=[.665,.78,.888];cols=[('initial_payload_kg','装载 (kg)',(0,30),[0,30]),('energy_kwh','能耗 (kWh)',(0,3.5),[0,3]),('soc_pct','SOC (%)',(0,100),[0,100])]
    for j,(key,title,limits,ticks)in enumerate(cols):
        a=figure.add_axes([xs[j],.28,.085,.50]);a.set(ylim=(-.7,5.7),xlim=limits,xticks=ticks);a.invert_yaxis()
        a.set_title(title,fontsize=8.5,pad=10);a.set_yticks(range(6));a.set_yticklabels([f"{r['trip_id'][-3:]}·{r['route']}"for r in records]if j==0 else [])
        if j==0:a.tick_params(axis='y',length=0,pad=5,labelsize=8)
        else:a.tick_params(axis='y',length=0)
        a.spines['left'].set_visible(False)
        for i,r in enumerate(records):
            if r['route']=='S008':a.axhspan(i-.45,i+.45,color='#F4F0E8',zorder=0)
            v=f(r,key);a.scatter(v,i,marker='s',s=22,color=C['B'],edgecolor='#5E574A',lw=.5,zorder=3)
            label=f'{v:.0f}'if j==0 else f'{v:.3f}'if j==1 else f'{v:.1f}'
            a.annotate(label,(v,i),xytext=(0,-13),textcoords='offset points',ha='center',fontsize=8)
        if key=='soc_pct':a.axvline(20,color=TH,ls='--',lw=.8,zorder=1)
        a.grid(axis='x',color=co.GRID,lw=.4)
    figure.text(.625,.095,'017 / 021：同赴S008，不同批次\nSOC红虚线：20%储备',fontsize=8.5)
    save(figure,12,'B型6个正式架次的空间路线与任务属性。Q2-017和Q2-021同赴S008，分别装载20 kg与25 kg；全部属性按正式箱级分配与能耗记录生成。相同路线可重复执行，路线数量不等于架次数，不能单独据此推断机型选择的最优性。',
       '路线几何与六个真实批次的质量、能耗和返航SOC逐行对应。',{'routes':rv,'records':records},
       [Q2+'Q2_transport_trips_balanced.csv','paper/figure_data_v2/q2_trip_summary.csv','paper/figure_data_v2/q2_trajectory.csv','paper/figure_data_v2/q2_replay_audit.json'],
       ['mass=sum official box mass by frozen box IDs','row join trip_id; destination sort only affects display'],
       [check('six_trips_five_routes',len(records)==6 and len(rv['routes'])==5),check('two_entities',len({r['uav_id']for r in records})==2)],{'map_spec':co.MAP_SPEC})

def figure13():
    records=[r for r in SUM if r['type_code']=='C'];critical=min(records,key=lambda r:f(r,'soc_pct'));tid=critical['trip_id']
    terrain=rc('paper/figure_data_v2/q2_020_profile.csv');traj=XB[tid]
    figure=fig(16.0);ax=figure.add_axes([.075,.56,.48,.37]);rv=route_map(ax,'C',tid,short=True)
    panel(ax,'(a) C型：6架次 · 2实体');ax.text(.98,.02,'服务区省略S前缀',transform=ax.transAxes,ha='right',fontsize=8,bbox={'facecolor':'white','edgecolor':'none','pad':1})
    a=figure.add_axes([.69,.585,.275,.285]);panel(a,'(b) 质量与返航储备')
    a.set(xlabel='装载质量 (kg)',ylabel='返航SOC (%)',xlim=(0,80),ylim=(0,100),xticks=[0,40,80]);a.axhline(20,color=TH,ls='--',lw=.8)
    offsets={'Q2-007':(.44,.74),'Q2-008':(.08,.86),'Q2-011':(.05,.35),'Q2-013':(.05,.14),'Q2-020':(.49,.03),'Q2-023':(.05,.52)}
    for r in records:
        x=f(r,'initial_payload_kg');y=f(r,'soc_pct');a.scatter(x,y,marker='^',s=36,color=C['C'],edgecolor='white',lw=.5,zorder=4)
        dx,dy=offsets[r['trip_id']];a.annotate(f"{r['trip_id'][-3:]} · {f(r,'energy_kwh'):.3f}",(x,y),xytext=(dx,dy),textcoords='axes fraction',ha='left',fontsize=8,arrowprops={'arrowstyle':'-','lw':.4,'color':SUB})
    grid(a);a.text(.02,.98,'点旁数值：kWh',transform=a.transAxes,va='top',fontsize=8)
    co.add_terrain_colorbar(figure,ax,[.12,.480,.36,.012])
    p=figure.add_axes([.10,.105,.86,.26]);panel(p,'(c) Q2-020沿程剖面')
    for r in terrain:p.plot([f(r,'begin_m')/1000,f(r,'end_m')/1000],[f(r,'elevation_m')]*2,color='#927955',lw=.8,zorder=2)
    xx=[f(r,'cumulative_distance_m')/1000 for r in traj];zz=[f(r,'altitude_m')for r in traj]
    p.plot(xx,zz,color=C['C'],lw=1.5,zorder=4,label='实际模型航高')
    p.set(xlabel='累计水平路程 (km)',ylabel='海拔 (m)',xlim=(0,max(xx)),ylim=(0,max(zz)*1.1));grid(p)
    for r in PB[tid]:
        if r['phase_kind']=='cruise':
            x0=f(r,'cumulative_distance_begin_m')/1000;x1=f(r,'cumulative_distance_end_m')/1000
            p.broken_barh([(x0,x1-x0)],(0,22),facecolor=C['C']if f(r,'payload_kg')else '#D8E4DE',edgecolor='white',lw=.4)
            p.text((x0+x1)/2,31,f"载荷 {f(r,'payload_kg'):g} kg",ha='center',fontsize=8)
    p.legend(handles=[Line2D([],[],color='#927955',lw=1,label='原始闭像元地形'),Line2D([],[],color=C['C'],lw=1.5,label='模型航高')],loc='lower right',bbox_to_anchor=(1,1.005),frameon=False,ncol=2,fontsize=8)
    save(figure,13,'C型6个正式任务与最低返航SOC架次Q2-020的地形剖面。上图比较实际装载、能耗与返航状态，下图沿O01—S004—O01累计水平路程展示原始闭像元地形与分段航高，交接不增加水平路程。Q2-020初载59 kg，返航SOC为23.09%；节点作业海拔与DSM保留各自官方来源。',
       '按真实最低SOC选择剖面，展示C型任务的装载、返航储备与航高。',{'routes':rv,'records':records,'critical_trip':critical,'terrain_profile':terrain,'trajectory':traj},
       [Q2+'Q2_transport_trips_balanced.csv','paper/figure_data_v2/q2_trip_summary.csv','paper/figure_data_v2/q2_020_profile.csv','paper/figure_data_v2/q2_trajectory.csv','paper/figure_data_v2/q2_replay_audit.json'],
       ['critical trip=min C-type formal SOC','cumulative distance only increases during cruise; closed-pixel intervals retained including zero-width boundary records'],
       [check('C_trips',len(records)==6),check('minimum_soc_trip',tid=='Q2-020'),check('profile_distance',abs(max(f(r,'end_m')for r in terrain)-max(xx)*1000)<1e-5)],{'map_spec':co.MAP_SPEC})

def figure14():
    raw=rc(Q2+'Q2_box_delivery_balanced.csv');records=[]
    for r in raw:
        records.append({**r,'expected_slack_s':f(r,'期望送达时间（s）')-f(r,'交付完成时刻（s）'),
           'hard_slack_s':None if not r['硬截止时间（s）']else f(r,'硬截止时间（s）')-f(r,'交付完成时刻（s）')})
    expected=sorted(records,key=lambda r:(r['expected_slack_s'],r['货箱编号']));hard=sorted([r for r in records if r['hard_slack_s']is not None],key=lambda r:(r['hard_slack_s'],r['货箱编号']))
    events=Counter(f(r,'交付完成时刻（s）')for r in records);tt=[0.]+sorted(events);cum=[0]+list(np.cumsum([events[t]for t in sorted(events)]));last=max(events)
    figure=fig(13.6);gs=figure.add_gridspec(2,2,height_ratios=[1.25,1],left=.10,right=.975,bottom=.10,top=.935,hspace=.66,wspace=.36)
    a=figure.add_subplot(gs[0,:]);b=figure.add_subplot(gs[1,0]);c=figure.add_subplot(gs[1,1])
    panel(a,'(a) 交接完成事件累计');a.step(np.array(tt+[105*60])/60,cum+[80],where='post',color=C['A'],lw=1.6)
    a.axvline(last/60,color=SUB,ls=':',lw=.8);a.axvline(RET/60,color=TH,ls=':',lw=.8)
    a.annotate('',xy=(last/60,81.5),xytext=(RET/60,81.5),arrowprops={'arrowstyle':'|-|','lw':.8,'color':SUB})
    a.annotate(f'返航历时差 {RET-last:.3f} s',(last/60,81.5),xytext=(-13,-33),textcoords='offset points',ha='right',fontsize=8.5,arrowprops={'arrowstyle':'-','color':SUB,'lw':.5})
    a.set(xlim=(0,105),ylim=(0,84),xlabel='全局时间 (min)',ylabel='累计交付 (箱)');grid(a)
    counts=Counter(f(r,'期望送达时间（s）')for r in records)
    a.text(0,-.38,'期望时限：'+'；'.join(f'{t/60:g} min / {n}箱'for t,n in sorted(counts.items())),transform=a.transAxes,fontsize=8)
    for ax,rs,key,title,marker in [(b,expected,'expected_slack_s','(b) 80箱期望余量','o'),(c,hard,'hard_slack_s','(c) 31箱硬截止余量','D')]:
        values=np.array([r[key]/60 for r in rs]);ranks=np.arange(1,len(rs)+1)
        ax.scatter(ranks,values,s=23,marker=marker,facecolor='white',edgecolor=C['A']if key=='expected_slack_s'else '#4F8372',lw=.8,zorder=3)
        ax.axhline(0,color=TH,lw=.8);ax.set(xlim=(0,len(rs)+1),ylim=(0,max(values)*1.08),xlabel='按余量升序的箱序号',ylabel='余量 (min)');panel(ax,title);grid(ax)
        for i in range(3):
            ax.annotate(rs[i]['货箱编号'],(ranks[i],values[i]),xytext=(.12,.49+i*.16),textcoords='axes fraction',fontsize=8,arrowprops={'arrowstyle':'-','lw':.4,'color':SUB})
    save(figure,14,'Q2箱级交付进度及两种时限余量。累计数按交接完成事件统计，期望余量与硬截止余量分别由对应时限减去实际交付时刻；最后交付与最后返航相差532.163 s。两个排序集合分别含80箱和31箱，排序仅用于展示，逐箱可行性按唯一箱号核验。',
       '同一正式方案的交付进度、期望余量与硬截止余量分别核验。',{'boxes':records,'expected_rank_box_ids':[r['货箱编号']for r in expected],'hard_rank_box_ids':[r['货箱编号']for r in hard],'delivery_events':[{'time_s':t,'boxes':events[t]}for t in sorted(events)],'last_delivery_s':last,'last_return_s':RET,'expected_deadline_counts':[{'time_s':t,'count':n}for t,n in sorted(counts.items())]},
       [Q2+'Q2_box_delivery_balanced.csv',Q2+'Q2_metrics.json','paper/figure_data_v2/q2_delivery_events.csv'],
       ['event aggregation by exact delivery time; right-continuous step','slack=corresponding deadline minus actual handover completion; separate box-ID-ranked views'],
       [check('unique_80boxes',len(records)==len({r['货箱编号']for r in records})==80),check('hard_31boxes',len(hard)==31),check('all_deadlines',min(r['expected_slack_s']for r in expected)>=0 and min(r['hard_slack_s']for r in hard)>=0),check('event_total',cum[-1]==80)])

def occupancy(records,end_key):
    events=defaultdict(int)
    for r in records:
        a=f(r,'任务占用开始（s）');b=f(r,end_key)
        if a<b:events[a]+=1;events[b]-=1
    counts=[];times=[];current=0
    for time,delta in sorted(events.items()):current+=delta;times.append(time);counts.append(current)
    return {'time_s':times,'count':counts,'peak':max(counts)}

def draw_stage_task(ax,tid,y,height=.55,label=True):
    for p in PB[tid]:
        x=f(p,'t_begin_s')/60;w=(f(p,'t_end_s')-f(p,'t_begin_s'))/60
        ax.broken_barh([(x,w)],(y-height/2,height),facecolors=STAGE[p['display_phase']],edgecolors='white',linewidth=.2,zorder=3)
    if label:
        a=f(TB[tid],'start_s')/60;b=f(TB[tid],'return_s')/60
        ax.text((a+b)/2,y-height/2-.07,tid[-3:],ha='center',va='bottom',fontsize=8,zorder=5)

def time_axis(ax):
    ax.set_xlim(0,150);ax.xaxis.set_major_locator(MultipleLocator(30));ax.xaxis.set_minor_locator(MultipleLocator(10));grid(ax,'x')

def resource_label(ax,y,label,typ):
    ax.text(-.018,y,label,transform=ax.get_yaxis_transform(),ha='right',va='center',fontsize=8.5)
    ax.plot([-.105,-.087],[y,y],color=C[typ],lw=3,transform=ax.get_yaxis_transform(),clip_on=False)

def figure15():
    records=[r for r in RES if r['资源类型']=='无人机'];groups=defaultdict(list)
    for r in records:groups[r['资源编号']].append(r)
    figure=fig(11.4);a=figure.add_axes([.14,.335,.84,.535]);b=figure.add_axes([.14,.105,.84,.125]);stage_legend(figure,.995)
    panel(a,'(a) 8架实体的真实任务阶段')
    positions={k:i+(.3 if i>=4 else 0)+(.3 if i>=6 else 0)for i,k in enumerate(sorted(groups))}
    for u,rs in sorted(groups.items()):
        y=positions[u];typ=rs[0]['机型'];resource_label(a,y,u,typ)
        for r in rs:draw_stage_task(a,r['架次编号'],y)
    a.set(ylim=(max(positions.values())+.65,-.95),yticks=[]);time_axis(a);a.tick_params(axis='x',labelbottom=False)
    a.axvspan(RET/60,150,facecolor='#F5F6F7',zorder=0);a.axvline(RET/60,color=TH,lw=1,ls='--',zorder=4)
    a.text(RET/60+2,1.2,'运输已结束\n电池充电见图16',fontsize=8.5,va='top')
    a.text(RET/60-1,-.68,f'{RET:.3f} s',ha='right',fontsize=8.5,color=TH)
    panel(b,'(b) 同型运输机并发占用');views={}
    for typ in C:
        v=occupancy([r for r in records if r['机型']==typ],'任务占用结束（s）');views[typ]=v
        b.step(np.array(v['time_s']+[9000])/60,v['count']+[0],where='post',color=C[typ],lw=1.3,ls={'A':'-','B':'--','C':'-.'}[typ],label=f'{typ}：峰值{v["peak"]}')
    b.set(ylim=(-.1,4.5),yticks=[0,2,4],xlabel='全局时间 (min)',ylabel='占用数');time_axis(b)
    b.legend(frameon=False,ncol=1,loc='upper right',fontsize=8,handlelength=1.4,labelspacing=.25)
    save(figure,15,'Q2运输无人机的任务阶段与同型并发占用。行标签短条表示机型，任务内部色彩表示固定路线确定性重放的准备装载、飞行、交接与末段返航；无人机在返回O01后释放。并发按半开占用区间计算，空档本身不用于推断电池或时限的因果作用。',
       '实体身份、真实任务阶段与同型并发分别编码，8实体执行24架次。',{'resource_records':records,'phases':PH,'occupancy':views,'row_positions':positions,'last_return_s':RET},
       [Q2+'Q2_resource_check.csv',Q2+'Q2_transport_trips_balanced.csv','paper/figure_data_v2/q2_task_phases.csv','paper/figure_data_v2/q2_replay_audit.json'],
       ['merge climb/cruise/descent as flight; last leg to O01 as return; preserve exact intervals','concurrency is count(start<=t<end); same-time releases precede new occupancy'],
       [check('24_tasks_8_entities',len(records)==24 and len(groups)==8),check('concurrency_peaks',[views[t]['peak']for t in C]==[4,2,2]),check('phase_boundary_coverage',all(abs(f(PB[r['架次编号']][0],'t_begin_s')-f(r,'任务占用开始（s）'))<1e-5 and abs(f(PB[r['架次编号']][-1],'t_end_s')-f(r,'任务占用结束（s）'))<1e-5 for r in records))],
       {'xlim_min':[0,150],'axis_position':[.14,.84],'physical_axis_width_cm':16.3*.84,'display_semantics':'stage fills are distinct from model type identity'})

def figure16():
    records=[r for r in RES if r['资源类型']=='电池'];groups=defaultdict(list)
    for r in records:groups[r['资源编号']].append(r)
    reused=[]
    for bat,rs in groups.items():
        ordered=sorted(rs,key=lambda r:f(r,'任务占用开始（s）'))
        for first,second in zip(ordered,ordered[1:]):reused.append({'battery_id':bat,'first':first,'second':second,'gap_s':f(second,'任务占用开始（s）')-f(first,'充电结束（s）')})
    key=min(reused,key=lambda r:(r['gap_s'],r['battery_id'],r['first']['架次编号']))
    figure=fig(15.4);a=figure.add_axes([.14,.32,.84,.565]);b=figure.add_axes([.14,.092,.84,.105]);stage_legend(figure,.995,charge=True)
    panel(a,'(a) 14块电池的作业与充电')
    positions={k:i+(.3 if i>=6 else 0)+(.3 if i>=10 else 0)for i,k in enumerate(sorted(groups))}
    for bat,rs in sorted(groups.items()):
        y=positions[bat];resource_label(a,y,bat.replace('-BAT-','-'),rs[0]['机型'])
        for r in rs:
            draw_stage_task(a,r['架次编号'],y,height=.52)
            a.broken_barh([(f(r,'充电开始（s）')/60,f(r,'充电时长（s）')/60)],(y-.26,.52),facecolors=STAGE['charge'],edgecolors=co.STAGE_EDGE['charge'],linewidth=.45,hatch='/',zorder=2)
    a.set(ylim=(max(positions.values())+.65,-.95),yticks=[]);time_axis(a);a.set_xlabel('全局时间 (min)')
    a.axvspan(RET/60,150,facecolor='#F5F6F7',zorder=0);a.axvline(RET/60,color=TH,lw=1,ls='--',zorder=4)
    figure.text(.98,.94,'末次充电不计入\n运输返航完工',fontsize=8.5,va='top',ha='right')
    first,second=key['first'],key['second'];t1=first['架次编号'];t2=second['架次编号']
    panel(b,f"(b) {key['battery_id']}：充满后立即再用")
    draw_stage_task(b,t1,0,height=.50,label=False);draw_stage_task(b,t2,0,height=.50,label=False)
    b.broken_barh([(f(first,'充电开始（s）')/60,f(first,'充电时长（s）')/60)],(-.25,.5),facecolors=STAGE['charge'],edgecolors=co.STAGE_EDGE['charge'],linewidth=.45,hatch='/')
    begin=f(first,'任务占用开始（s）')/60;end=f(second,'任务占用结束（s）')/60
    b.set(xlim=(begin,end),ylim=(-.8,.7),yticks=[],xlabel='局部全局时间 (min)');grid(b,'x')
    for x,text in [(f(first,'任务占用结束（s）')/60,'返回'),(f(first,'充电结束（s）')/60,'充满＝再用')]:
        b.axvline(x,color=SUB,lw=.5,ls=':');b.text(x,.42,text,ha='center',fontsize=8.5)
    b.text((begin+f(first,'任务占用结束（s）')/60)/2,-.6,f"{t1[-3:]} · {BY[t1]['无人机编号']}",ha='center',fontsize=8.5)
    b.text((f(second,'任务占用开始（s）')/60+end)/2,-.6,f"{t2[-3:]} · {BY[t2]['无人机编号']}",ha='center',fontsize=8.5)
    views={t:occupancy([r for r in records if r['机型']==t],'充电结束（s）')for t in C}
    save(figure,16,'Q2共享电池的阶段占用与充电。所有作业阶段与运输机图按架次对应，充电边界取自正式资源记录；局部窗展示A-BAT-01在Q2-001后充满并立即供Q2-015复用，实体身份按各自架次注明。最后返航后的充电仍属于资源占用，但不延长运输返航完工。',
       '同一块电池跨任务复用以充满为界，任务结束与电池释放不是同一时刻。',{'resource_records':records,'phases':PH,'reuse_records':reused,'critical_reuse':key,'occupancy':views,'last_charge_s':max(f(r,'充电结束（s）')for r in records)},
       [Q2+'Q2_resource_check.csv',Q2+'Q2_transport_trips_balanced.csv','paper/figure_data_v2/q2_task_phases.csv','paper/figure_data_v2/q2_replay_audit.json'],
       ['battery occupancy=[task_start,charge_end); task stage table identical to figure15','reuse gap=next task start - previous charge end; minimum tie broken by battery then earlier trip ID'],
       [check('24_tasks_14batteries',len(records)==24 and len(groups)==14),check('all_reuse_feasible',min(r['gap_s']for r in reused)>=-1e-5),check('battery_peaks',[views[t]['peak']for t in C]==[6,4,4])],
       {'xlim_min':[0,150],'axis_position':[.14,.84],'physical_axis_width_cm':16.3*.84,'row_label_BAT_prefix_omitted':True,'zoom_full_battery_id':key['battery_id']})

if __name__=='__main__':
    requested=[int(a)for a in sys.argv[1:]]or[10,11,12,13,14,15,16]
    for n in requested:globals()[f'figure{n}']()
