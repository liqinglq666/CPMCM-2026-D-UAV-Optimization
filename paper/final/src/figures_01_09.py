"""Final figures 01--09 from frozen published records; never runs a solver."""
from pathlib import Path
import csv, json, hashlib, math, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
from matplotlib.lines import Line2D
from matplotlib.colors import LinearSegmentedColormap
from matplotlib import font_manager, ticker

from paths import ROOT, REPO, OUT, WORK, RAW, FINAL, FONT_DIR, source_path
OUT.mkdir(parents=True,exist_ok=True)
COMMIT='bec20f1536458db47bac583c309c7b30637cb67a'
COLORS={'A':'#0072B2','B':'#E69F00','C':'#009E73'}
MARKERS={'A':'o','B':'s','C':'^'}
KINDS=['医疗物资','应急食品','生活卫生用品','饮用水']
KIND_LABELS=dict(zip(KINDS,['医疗物资','食品','卫生用品','饮用水']))
KC=['#A6566F','#5B8EAD','#C7A14A','#6B9B83']
INK='#222222'; SECONDARY='#5B6570'; GRID='#DDE2E7'; THRESHOLD='#B5484E'

def js(rel): return json.loads((REPO/rel).read_text(encoding='utf-8'))
def rows(rel): return list(csv.DictReader((REPO/rel).open(encoding='utf-8-sig',newline='')))
def f(r,k): return float(r[k])
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def setup():
    # Use shared static TrueType instances. CFF OTF cannot be embedded as Type42.
    cm.init_style()
    plt.rcParams.update({'legend.frameon':False,'svg.hashsalt':'uav-final-2026','hatch.linewidth':.35})
    return {'chinese':cm.FONT_CN,'chinese_path':str(cm.FONT_PATH),'chinese_bold_path':str(cm.FONT_BOLD_PATH),'latin':'DejaVu Sans','latin_path':font_manager.findfont('DejaVu Sans')}

import common as cm
FONT=setup()
A=js('paper/data/analysis.json'); BOXES={b['id']:b for b in A['boxes']}; NODES=A['nodes']; SERVICES=sorted(k for k in NODES if k!='O01')
Q1=sorted(rows('results/q1/Q1_batch_solution.csv'),key=lambda r:(r['服务区编号'],r['架次编号']))
LABELS=[r['架次编号'].replace('Q1-','') for r in Q1]
ALL_SPECS=[]

def fig(height): return plt.figure(figsize=(16.3/2.54,height/2.54))
def grid(ax,which='x'):
    ax.grid(axis=which,color=GRID,lw=.4);ax.set_axisbelow(True)
def title(ax,s): ax.set_title(s,loc='left',pad=9)
def shade_rows(ax,n):
    for i in range(0,n,2): ax.axhspan(i-.5,i+.5,fc='#F7F8FA',alpha=.65,zorder=0)
def yrows(ax,labels,show=True):
    ax.set_ylim(len(labels)-.5,-.5);ax.set_yticks(range(len(labels)));ax.set_yticklabels(labels if show else []);ax.tick_params(axis='y',length=0)
def write(n,g,caption,data,sources,purpose,mapping,derived=(),checks=None,missing=(),params=None):
    stem=f'fig_{n:02d}'
    g.savefig(OUT/(stem+'.svg'))
    g.savefig(OUT/(stem+'.pdf'))
    g.savefig(OUT/(stem+'.png'),dpi=600)
    g.savefig(WORK/f'{stem}_preview.png',dpi=150)
    spec={'figure':n,'scheme':COMMIT,'title':purpose,'caption':caption,'width_cm':16.3,'height_cm':round(g.get_figheight()*2.54,4),'png_dpi':600,'fonts':FONT,'sources':[{'path':s,'sha256':sha(REPO/s)} for s in sources],'field_mapping':mapping,'derived_formulas':list(derived),'parameters':params or {},'checks':checks or {},'missing_or_not_revalidated':list(missing),'quantity_source':'Frozen machine-readable records, no optimization or digitization','formats':['editable_text_svg','embedded_font_pdf','opaque_png_600dpi'],'visual_review':'pending','data_file':stem+'_data.json','script':'paper/final/src/figures_01_09.py'}
    spec['number']=n
    spec['data_file']=stem+'_data.json'
    (OUT/(stem+'_data.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/(stem+'_spec.json')).write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/(stem+'_caption.txt')).write_text(caption,encoding='utf-8')
    ALL_SPECS.append(spec);plt.close(g)

def figure01():
    g=fig(12.2);ax=g.add_axes([.035,.035,.95,.935]);ax.set_axis_off();ax.set(xlim=(0,1),ylim=(0,1))
    def box(x,y,w,h,text,face='#F7F8FA',fs=9,bold=False):
        ax.add_patch(Rectangle((x,y),w,h,facecolor=face,edgecolor='#CBD3DA',lw=.65))
        ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontsize=fs,fontweight='bold' if bold else 'normal',linespacing=1.4)
    box(.055,.885,.93,.085,'官方输入：节点、箱单、机型、通信参数、原始 DEM','#EEF3F6',9.5)
    box(.055,.747,.93,.102,'共同物理计算\n航段地形 → 动态载荷 → 时间与能量 → 资源占用','#EEF3F6',9.5)
    ax.annotate('',(.52,.855),(.52,.882),arrowprops=dict(arrowstyle='-|>',color=SECONDARY,lw=.85,mutation_scale=8))
    ax.text(.162,.700,'问题',ha='center',weight='bold',fontsize=10)
    ax.text(.484,.700,'决策方法',ha='center',weight='bold',fontsize=10)
    ax.text(.83,.700,'输出与核验',ha='center',weight='bold',fontsize=10)
    entries=[('Q1\n安全运输能力','安全载荷二分\n锚定集合划分 DP','载荷边界与单点批次\n箱级与物理约束核对'),('Q2\n可执行调度','架次列、时间索引\n无人机与电池分别排程','逐箱交付与双层资源\n冻结方案的可行性核验'),('Q3\n通信保障','指定中继与服务窗\n条件时序线性规划','运输—中继联合记录\n采样与区间数值核验'),('Q4\n独立资源配置','固定任务时序\n分区枚举与峰值计数','独立配置需求与缺口\n成员及分类资源核对')]
    centers=[]
    for i,(q,m,o) in enumerate(entries):
        y=.534-i*.15; centers.append(y+.058)
        box(.055,y,.222,.117,q,'#E3EDF3',9,True);box(.295,y,.373,.117,m);box(.685,y,.3,.117,o)
        ax.annotate('',(.292,y+.058),(.279,y+.058),arrowprops=dict(arrowstyle='-|>',color=SECONDARY,lw=.85,mutation_scale=7))
        ax.annotate('',(.683,y+.058),(.67,y+.058),arrowprops=dict(arrowstyle='-|>',color=SECONDARY,lw=.85,mutation_scale=7))
    ax.plot([.025,.025],[centers[-1],.793],color=SECONDARY,lw=.85)
    ax.plot([.025,.055],[.793,.793],color=SECONDARY,lw=.85)
    for y in centers: ax.annotate('',(.053,y),(.025,y),arrowprops=dict(arrowstyle='-|>',color=SECONDARY,lw=.85,mutation_scale=7))
    # Only Q3 -> Q4 is a fixed-plan inheritance arrow.
    ax.annotate('',(.485,.203),(.485,.231),arrowprops=dict(arrowstyle='-|>',color=INK,lw=.85,mutation_scale=8))
    ax.text(.67,.219,'固定正式任务与时序',fontsize=8,ha='center',va='center',bbox=dict(fc='white',ec='none',pad=1))
    ax.text(.055,.012,'Q2、Q3 继承计算规则，并分别重新选择离散任务。',fontsize=8,color=SECONDARY)
    modules=[{'question':'Q1','functions':['src/q1/physics_engine.py:max_safe_payload','src/q1/physics_engine.py:_optimize_service'],'input':['analysis.nodes','analysis.boxes','analysis.types'],'output':'results/q1/Q1_batch_solution.csv','verification':'src/validation.py:validate_q1'}, {'question':'Q2','functions':['src/q2/columns.py:enumerate_columns','src/q2/interval_master.py:IntervalMaster','src/core/discrete.py:TransportEvaluator'],'input':['official inputs','Q2 candidate plan'],'output':'results/q2/Q2_transport_trips_balanced.csv','verification':'src/core/constraints.py:validate_transport'},{'question':'Q3','functions':['src/q3/preparation.py:PlanPreparer','src/q3/solver.py:optimize_timing'],'input':['transport jobs','specified relays/windows'],'output':'results/q3/Q3_transport_trips.csv','verification':'src/core/continuous_radio.py:certify_profiles'},{'question':'Q4','functions':['src/q4/partition.py:solve_partitions','src/q4/partition.py:canonical_partitions'],'input':['frozen Q3 schedule/relations'],'output':'results/q4/Q4_partition_config.csv','verification':'results/q4/Q4_enumeration_certificate.json'}]
    sources=['src/core/physics.py','src/core/routes.py','src/core/constraints.py','src/q1/physics_engine.py','src/q2/columns.py','src/q2/interval_master.py','src/core/discrete.py','src/q3/preparation.py','src/q3/solver.py','src/core/continuous_radio.py','src/q4/partition.py']
    # Validate named members by source inspection, without executing solvers.
    for record in modules:
        for item in record['functions']:
            p,name=item.split(':'); assert ('def '+name in (REPO/p).read_text(encoding='utf-8') or 'class '+name in (REPO/p).read_text(encoding='utf-8')),item
    write(1,g,'四问共享地形、动态载荷、时间能量与资源占用计算。Q2与Q3重新选择离散任务，Q4固定Q3正式任务及其时序，再计算分组独立配置需求。',modules,sources,'共同基础、决策与证据','question_id → module/function/input/output/verification',checks={'four_questions':True,'method_members_exist':True,'only_Q3_Q4_fixed_inheritance':True})

def figure03():
    data=[]
    for s in SERVICES:
        bs=[b for b in BOXES.values() if b['service']==s]
        data.append({'service':s,'mass_by_kind':{k:sum(b['mass'] for b in bs if b['kind']==k) for k in KINDS},'mass_kg':sum(b['mass'] for b in bs),'box_ids':[b['id'] for b in bs],'count':len(bs),'hard_count':sum(b['hard_deadline'] is not None for b in bs)})
    assert sum(d['mass_kg'] for d in data)==758 and sum(d['count'] for d in data)==80 and sum(d['hard_count'] for d in data)==31
    assert all(sum(d['mass_by_kind'].values())==d['mass_kg'] for d in data)
    g=fig(12.8);gs=g.add_gridspec(1,2,width_ratios=[2.05,1.10],left=.115,right=.985,bottom=.105,top=.79,wspace=.25); ax,bx=[g.add_subplot(x) for x in gs]; y=np.arange(15)
    for a in [ax,bx]:shade_rows(a,15);yrows(a,SERVICES,a is ax);grid(a)
    base=np.zeros(15)
    for k,c in zip(KINDS,KC):
        vals=np.array([d['mass_by_kind'][k] for d in data]); ax.barh(y,vals,left=base,height=.64,color=c,ec='white',lw=.4,label=KIND_LABELS[k]);base+=vals
    for i,d in enumerate(data):ax.annotate(f"{d['mass_kg']:g}",(d['mass_kg'],i),xytext=(3,0),textcoords='offset points',va='center',fontsize=8)
    hard=np.array([d['hard_count'] for d in data]); total=np.array([d['count'] for d in data])
    bx.barh(y,hard,color=THRESHOLD,height=.64,ec='white',lw=.4,label='硬截止');bx.barh(y,total-hard,left=hard,color='#CAD3DB',height=.64,ec='white',lw=.4,label='其余货箱')
    for i,d in enumerate(data):
        bx.text(d['count']+.35,i,str(d['count']),fontsize=8,va='center')
        if d['hard_count']:bx.text(d['hard_count']/2,i,str(d['hard_count']),fontsize=8,ha='center',va='center',color='white')
    ax.set(xlim=(0,175),xticks=[0,50,100,150],xlabel='需求质量（kg）');bx.set(xlim=(0,17),xticks=[0,5,10,15],xlabel='货箱数（箱）')
    title(ax,'(a) 需求质量与物资构成');title(bx,'(b) 箱数与截止性质')
    ax.legend(loc='lower left',bbox_to_anchor=(-.01,1.075),ncol=2,columnspacing=1,handlelength=1.25)
    bx.legend(loc='lower left',bbox_to_anchor=(0,1.075),ncol=1,handlelength=1.25)
    g.text(.115,.968,'758 kg / 80 箱 / 31 箱硬截止',fontsize=8,color=SECONDARY)
    write(3,g,'各服务区的需求质量、物资构成与截止性质。左图条长为质量，右图按硬截止与其余货箱互斥分解箱数；31个硬截止货箱属于总计80箱。',data,['paper/data/analysis.json','src/core/inputs.py'],'需求构成与截止性质',{'boxes.id':'box_ids','boxes.service':'service','boxes.kind/mass':'mass_by_kind','boxes.hard_deadline is not None':'hard_count'},['按 service、kind 汇总 mass；唯一箱号计数；其余箱数=总箱数−有效硬截止箱数'],{'80_unique_boxes':len(BOXES)==80,'758_kg':True,'31_hard':True},params={'kind_order':KINDS,'bar_height':.64,'x_mass_max':175,'mass_axis_deviation':'175 provides label space beyond 154 kg; tick stops at150'})

def figure04():
    raw=rows('paper/data/terrain_profile.csv');intervals=[{k:float(v) for k,v in r.items()} for r in raw];cuts=sorted(set(v for r in intervals for v in (r['begin_m'],r['end_m'])))
    steps=[]
    for lo,hi in zip(cuts,cuts[1:]):
        mid=(lo+hi)/2;zs=[r['elevation_m'] for r in intervals if r['begin_m']<=mid<=r['end_m']]
        assert zs; steps.append({'begin_m':lo,'end_m':hi,'elevation_m':max(zs)})
    events=[{'distance_m':x,'elevation_m':max(r['elevation_m'] for r in intervals if r['begin_m']<=x<=r['end_m'])} for x in cuts]
    t=A['terrain_example'];mx=max(r['elevation_m'] for r in intervals);assert mx==t['max_dem'];assert cuts[-1]==t['distance'];assert t['cruise_alt']-mx==50
    start=A['nodes']['O01']['elev'];end=t['cruise_alt']-t['out_down'];assert math.isclose(start,t['cruise_alt']-t['out_up'],rel_tol=1e-12,abs_tol=1e-10);assert math.isclose(end,A['nodes']['S014']['elev']+30,rel_tol=1e-12,abs_tol=1e-10)
    x=np.array([r[k] for r in steps for k in ['begin_m','end_m']])/1000; z=np.array([r['elevation_m'] for r in steps for _ in range(2)]);d=t['distance']/1000;h=t['cruise_alt']
    g=fig(9.5);ax=g.add_axes([.095,.16,.875,.74]);ax.fill_between(x,0,z,color='#DCE3CE',alpha=.75);ax.plot(x,z,color='#788269',lw=.9)
    # Closed-edge singleton maxima are retained at their exact abscissae.
    for e in events:
        xx=e['distance_m'];adj=[s['elevation_m'] for s in steps if s['begin_m']<=xx<=s['end_m']]
        if adj and e['elevation_m']>max(adj):ax.vlines(xx/1000,max(adj),e['elevation_m'],color='#788269',lw=.9)
    ax.plot([0,d],[h,h],color=COLORS['A'],lw=1.3)
    ax.annotate('',(0,h),(0,start),arrowprops=dict(arrowstyle='->',color=COLORS['A'],lw=1.05));ax.annotate('',(d,end),(d,h),arrowprops=dict(arrowstyle='->',color=COLORS['A'],lw=1.05))
    ax.plot([0,d],[start,end],'o',ms=4,color=INK)
    ax.annotate('O01 作业点',(0,start),xytext=(7,-20),textcoords='offset points',fontsize=8)
    ax.annotate('S014 作业点',(d,end),xytext=(-7,-20),textcoords='offset points',fontsize=8,ha='right')
    peak=[s for s in steps if s['elevation_m']==mx];xp=(peak[0]['begin_m']+peak[0]['end_m'])/2000
    for p in peak:ax.plot([p['begin_m']/1000,p['end_m']/1000],[mx,mx],color='#B6A387',lw=2)
    ax.annotate(f'最高地形 {mx:.3f} m',(xp,mx),xytext=(1.7,442),textcoords='data',fontsize=8,arrowprops=dict(arrowstyle='-',lw=.65,color=SECONDARY))
    ax.annotate('',(xp,h),(xp,mx),arrowprops=dict(arrowstyle='<->',color=INK,lw=.75,shrinkA=0,shrinkB=0));ax.text(xp+.08,(mx+h)/2,'50 m',fontsize=8,va='center')
    ax.text(5.37,h+20,f'巡航海拔 {h:.3f} m',fontsize=8,ha='right')
    ax.text(.12,240,f'爬升\n{t["out_up"]:.3f} m',fontsize=8,color=COLORS['A'],bbox={'fc':'white','ec':'none','pad':1.5},zorder=6)
    ax.text(d-.12,443,f'下降\n{t["out_down"]:.3f} m',fontsize=8,color=COLORS['A'],ha='right',bbox={'fc':'white','ec':'none','pad':1.5},zorder=6)
    ax.set(xlim=(-.08,5.5),ylim=(0,650),xticks=range(6),yticks=range(0,651,100),xlabel='O01—S014 水平累计距离（km）',ylabel='海拔（m）');grid(ax,'y');ax.text(.04,.045,'纵横比例不同',transform=ax.transAxes,color=SECONDARY,fontsize=8)
    data={'saved_closed_cell_intervals':intervals,'display_envelope':steps,'boundary_maxima':events,'terrain_summary':t,'start_operation_altitude_m':start,'end_operation_altitude_m':end}
    write(4,g,'O01至S014已保存的原始DEM闭像元航段剖面及计划飞行阶段。沿线最高地形为541.947 m，巡航海拔为591.947 m；端点作业高度较低仍需完成跨越沿途高地的爬升。',data,['paper/data/terrain_profile.csv','paper/data/analysis.json','scripts/analyze_paper.py','src/core/terrain.py','src/core/physics.py','src/config.py'],'真实闭像元剖面与飞行阶段',{'terrain_profile.begin_m/end_m':'closed intervals along directed O01→S014','elevation_m':'source cell height','terrain_example':'distance/cruise/up/down'},['重叠闭像元区间取最大高程包络；边界点保留相接像元最大值；米÷1000为km'],{'max_dem_matches':True,'distance_matches':True,'50m_clearance':True,'operation_altitudes_match':True},missing=['原始DEM已由terrain.py只读重放并核对609条闭像元区间，高程逐项一致；图中沿用原保存值，未替换末位浮点差异'],params={'xlim_km':[-.08,5.5],'ylim_m':[0,650],'height_increased_cm':.7,'reason':'保留完整起降及最高点标注空间'})

def energy_view():
    ec=rows('paper/data/energy_components.csv');data=[]
    for batch in Q1:
        sub=[r for r in ec if r['trip']==batch['架次编号']];assert len(sub)==2 and {r['direction'] for r in sub}=={'outbound','return'}
        dd={r['direction']:r for r in sub};assert f(dd['return'],'payload_kg')==0
        vals=[f(dd[d],k) for d,k in [('outbound','horizontal_kwh'),('outbound','climb_kwh'),('return','horizontal_kwh'),('return','climb_kwh')]]
        total=sum(vals);assert math.isclose(total,f(batch,'架次能耗（kWh）'),rel_tol=0,abs_tol=1e-8)
        data.append({'batch':batch['架次编号'],'service':batch['服务区编号'],'type':batch['机型编号'],'components_kwh':vals,'total_kwh':total,'return_share_pct':100*(vals[2]+vals[3])/total,'raw':sub})
    return data

def figure05():
    data=energy_view();g=fig(13.4);gs=g.add_gridspec(1,2,width_ratios=[3,1.05],left=.155,right=.972,bottom=.095,top=.82,wspace=.29);ax,bx=[g.add_subplot(s) for s in gs]
    colors=['#506A85','#B8C7D4','#88715B','#D8C8B7']; labs=['去程水平','去程爬升','返程水平','返程爬升'];y=np.arange(18);base=np.zeros(18)
    for a in [ax,bx]:
        shade_rows(a,18);yrows(a,LABELS,a is ax);grid(a)
        for yy in [1.5,3.5,5.5]:a.axhline(yy,color='#98A2AD',lw=.55)
    for j,(c,l) in enumerate(zip(colors,labs)):
        vals=np.array([d['components_kwh'][j] for d in data]);ax.barh(y,vals,left=base,height=.66,color=c,ec='white',lw=.35,label=l,hatch='///' if j%2 else '');base+=vals
    for i,d in enumerate(data):ax.annotate(f"{d['total_kwh']:.3f}",(d['total_kwh'],i),xytext=(3,0),textcoords='offset points',fontsize=8,va='center')
    shares=[d['return_share_pct'] for d in data];bx.plot(shares,y,'o',color=colors[2],ms=4)
    for i,v in enumerate(shares):bx.annotate(f'{v:.1f}',(v,i),xytext=(5,0),textcoords='offset points',fontsize=8,va='center')
    ax.set(xlim=(0,math.ceil(max(base)*1.15*2)/2),xlabel='架次能耗（kWh）');ax.xaxis.set_major_locator(ticker.MultipleLocator(1));bx.set(xlim=(0,100),xticks=[0,25,50,75,100],xlabel='返程份额（%）')
    title(ax,'(a) 架次能量组成');title(bx,'(b) 空载返程份额')
    handles,labels=ax.get_legend_handles_labels();g.legend([handles[i] for i in [0,1,2,3]],[labels[i] for i in [0,1,2,3]],loc='upper center',bbox_to_anchor=(.54,.976),ncol=2,columnspacing=2.3)
    write(5,g,'Q1正式18个批次的去程、空载返程与爬升能耗。左图为绝对能耗分解，右图为返程两项之和占该批总能耗的比例；下降附加能耗按题设取零，返程储备不作为已消耗能量堆叠。',data,['paper/data/energy_components.csv','results/q1/Q1_batch_solution.csv','scripts/analyze_paper.py'],'去程与空载返程能耗',{'trip':'batch join key','direction':'outbound/return','horizontal_kwh/climb_kwh':'four components'},['total=out_horizontal+out_climb+return_horizontal+return_climb','return_share_pct=100×(return_horizontal+return_climb)/total'],{'18_batches':len(data)==18,'four_parts_close_to_formal_abs1e-8':True,'all_return_payload_zero':True,'total_display_59.130':f'{sum(d["total_kwh"] for d in data):.3f}'=='59.130'},params={'verification_tolerance_source':'scripts/analyze_paper.py energy replay abs_tol=1e-8','order':LABELS})

def figure06():
    rr=rows('results/q2/Q2_resource_check.csv');tasks=[r for r in rr if r['架次编号']=='Q2-001'];u=next(r for r in tasks if r['资源类型']=='无人机');b=next(r for r in tasks if r['资源类型']=='电池');s=f(u,'任务占用开始（s）');e=f(u,'任务占用结束（s）');ce=f(b,'充电结束（s）');cs=f(b,'充电开始（s）');assert s==f(b,'任务占用开始（s）') and e==f(b,'任务占用结束（s）') and cs==e
    rt=e-s;ct=ce-s;extra=ce-e;g=fig(7.5);ax=g.add_axes([.20,.23,.765,.56]);ax.barh([1,0],[rt,rt],left=0,color=COLORS[u['机型']],height=.3);ax.barh(0,extra,left=rt,height=.3,color='#EEF1F4',ec='#98A2AD',hatch='//',lw=.65)
    for t,lab,c,ls in [(0,'开始',SECONDARY,':'),(rt,'返航',INK,'--'),(ct,'充满','#98A2AD',':')]:ax.axvline(t,ymax=.87,color=c,ls=ls,lw=.7);ax.text(t,1.48,f'{lab} {t:.1f} s',fontsize=8.5,ha='left' if t==0 else 'center')
    for y in [1,0]:ax.text(rt/2,y,'准备、装载与运输作业',fontsize=8,color='white',ha='center',va='center')
    ax.text((rt+ct)/2,0,'充电',fontsize=8,ha='center',va='center');ax.plot(0,1,'o',ms=4,color=INK);ax.plot(rt,1,'o',ms=4,mfc='white',mec=INK)
    ax.annotate('',(rt,.58),(ct,.58),arrowprops=dict(arrowstyle='|-|',lw=.65,color=SECONDARY));ax.text((rt+ct)/2,.68,f'电池额外占用 {extra:.1f} s',fontsize=8,ha='center')
    ax.set(ylim=(-.45,1.6),yticks=[1,0],yticklabels=[f'无人机 {u["资源编号"]}',f'电池 {b["资源编号"]}'],xlim=(-20,math.ceil(ct*1.06/100)*100),xlabel='自架次开始的时间（s）');ax.xaxis.set_major_locator(ticker.MultipleLocator(500));ax.tick_params(axis='y',length=0);ax.spines['left'].set_visible(False);grid(ax)
    g.legend(handles=[Rectangle((0,0),1,1,fc=COLORS['A'],label='A 型任务占用'),Rectangle((0,0),1,1,fc='#EEF1F4',ec='#98A2AD',hatch='//',label='充电占用')],loc='upper center',bbox_to_anchor=(.59,.98),ncol=2)
    g.text(.20,.05,'Q2-001；资源占用按 [开始，释放) 衔接。',fontsize=8,color=SECONDARY)
    write(6,g,'正式架次Q2-001的双层资源占用。横轴以该架次开始为零点；无人机于返航时释放，电池继续占用至充满，二者均按左闭右开区间衔接后续任务。',{'source_rows':tasks,'relative_return_s':rt,'relative_charge_complete_s':ct,'extra_battery_occupation_s':extra},['results/q2/Q2_resource_check.csv'],'无人机与电池的释放时刻',{'架次编号':'sortie_id','资源编号':'uav_id/battery_id','任务占用开始（s）':'start_s','任务占用结束（s）':'return_s','充电结束（s）':'charge_complete_s'},['relative_time=absolute_time−sortie_start','extra=charge_complete−return'],{'ordered_times':s<e<ce,'same_task_interval':True,'return_display_1250.9':f'{rt:.1f}'=='1250.9','charge_display_2121.3':f'{ct:.1f}'=='2121.3'},missing=['未细分准备、装载、飞行子阶段；未画两阶段充电内部转折'],params={'height_cm':7.5,'height_change':'增加0.8 cm用于释放端点与占用括线，未缩小字号'})

def figure07():
    pay=rows('results/q1/Q1_max_safe_payload.csv');data=[]
    for r in pay:
        for typ in 'ABC':
            v=float(r[f'{typ}型最大安全载荷（kg）']);rated=A['types'][typ]['max_payload'];data.append({'service':r['服务区编号'],'type':typ,'safe_payload_kg':v,'rated_payload_kg':rated,'ratio_pct':100*v/rated,'reachable':r[f'{typ}型空载可达']=='True','restricted':v<rated-1e-8})
    assert len(data)==45 and sum(d['restricted'] for d in data if d['type']=='C')==5
    g=fig(13.2);gs=g.add_gridspec(1,2,width_ratios=[1.2,1],left=.115,right=.985,bottom=.095,top=.865,wspace=.24);ax,bx=[g.add_subplot(x) for x in gs]
    for a in [ax,bx]:yrows(a,SERVICES,a is ax);grid(a)
    offsets={'A':-.18,'B':0,'C':.18}
    for typ in 'ABC':
        dd=[d for d in data if d['type']==typ];ys=np.arange(15)+offsets[typ]
        for a,key in [(ax,'safe_payload_kg'),(bx,'ratio_pct')]:a.plot([d[key] for d in dd],ys,ls='',marker=MARKERS[typ],ms=4.2,color=COLORS[typ],mec='white',mew=.35,label=typ+' 型')
        rated=A['types'][typ]['max_payload'];ax.axvline(rated,color=COLORS[typ],ls=':',lw=.6,alpha=.3)
        for d,y in zip(dd,ys):
            if d['restricted']:
                dx=5;ha='left'; ax.annotate(f"{d['safe_payload_kg']:.2f}",(d['safe_payload_kg'],y),xytext=(dx,0),textcoords='offset points',ha=ha,va='center',fontsize=8)
                bx.annotate(f"{d['ratio_pct']:.1f}",(d['ratio_pct'],y),xytext=(-5,0),textcoords='offset points',ha='right',va='center',fontsize=8)
    for a in [ax,bx]:
        for y in np.arange(.5,15,1):a.axhline(y,lw=.55 if (y+.5)%5==0 else .35,color=GRID,zorder=0)
    bx.axvline(100,color=THRESHOLD,ls=(0,(4,2)),lw=1,zorder=1);ax.set(xlim=(0,94),xticks=[0,20,40,60,80],xlabel='安全载荷（kg）');bx.set(xlim=(0,105),xticks=[0,25,50,75,100],xlabel='占额定载荷（%）')
    title(ax,'(a) 最大安全载荷');title(bx,'(b) 占额定载荷比例')
    g.legend(*ax.get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.57,.981),ncol=3)
    g.text(.115,.92,'额定载荷：A 25 kg、B 30 kg、C 80 kg；返航储备 20%。',fontsize=8,color=SECONDARY)
    write(7,g,'15个服务区的单点往返安全载荷及其额定比例。A型均达到额定载荷，C型在5个服务区受能量限制；B型和C型的最小安全载荷分别为28.80 kg和58.91 kg。比例使用各机型自身额定载荷归一化。',data,['results/q1/Q1_max_safe_payload.csv','paper/data/analysis.json','src/q1/physics_engine.py','scripts/generate_paper_tables.py'],'安全载荷与额定比例',{'服务区编号':'service','A/B/C型最大安全载荷（kg）':'safe_payload_kg','A/B/C型空载可达':'reachable','analysis.types.max_payload':'rated_payload_kg'},['ratio=100×safe_payload/rated_payload'],{'45_combinations':len(data)==45,'C_restricted5':True,'A_all25':all(d['safe_payload_kg']==25 for d in data if d['type']=='A'),'B_min28.80':f'{min(d["safe_payload_kg"] for d in data if d["type"]=="B"):.2f}'=='28.80','C_min58.91':f'{min(d["safe_payload_kg"] for d in data if d["type"]=="C"):.2f}'=='58.91'},params={'restricted_comparison':'safe < rated−1e-8; matches scripts/generate_paper_tables.py','offsets':offsets,'payload_xlim':[0,94],'xlim_extension':'extra 4 kg for non-overlapping restricted-value labels'})

def batch_view():
    data=[];allids=[]
    for q in Q1:
        bs=[BOXES[x] for x in q['货箱编号列表'].split(',')];allids += [b['id'] for b in bs]
        d={'batch':q['架次编号'],'service':q['服务区编号'],'type':q['机型编号'],'box_ids':[b['id'] for b in bs],'total_mass_kg':sum(b['mass'] for b in bs),'total_volume_m3':sum(b['volume'] for b in bs),'by_kind':[{'kind':k,'mass_kg':sum(b['mass'] for b in bs if b['kind']==k),'count':sum(b['kind']==k for b in bs)} for k in KINDS]}
        assert d['total_mass_kg']==f(q,'总质量（kg）');assert math.isclose(d['total_volume_m3'],f(q,'总体积（m³）'),rel_tol=1e-12,abs_tol=1e-10)
        assert sum(x['mass_kg'] for x in d['by_kind'])==d['total_mass_kg'] and sum(x['count'] for x in d['by_kind'])==len(bs)
        data.append(d)
    assert len(allids)==80 and len(set(allids))==80 and set(allids)==set(BOXES);return data

def figure08():
    data=batch_view();g=fig(13.8);gs=g.add_gridspec(1,3,width_ratios=[.45,2.60,1.25],left=.15,right=.985,bottom=.105,top=.84,wspace=.14);tx,ax,bx=[g.add_subplot(x) for x in gs];y=np.arange(18)
    for a in [tx,ax,bx]:yrows(a,LABELS,a is tx);shade_rows(a,18)
    tx.set_xlim(0,1);tx.set_xticks([])
    for sp in tx.spines.values():sp.set_visible(False)
    for i,d in enumerate(data):tx.plot(.24,i,marker=MARKERS[d['type']],color=COLORS[d['type']],ms=4.2);tx.text(.53,i,d['type'],fontsize=8.5,va='center')
    base=np.zeros(18)
    for j,(k,c) in enumerate(zip(KINDS,KC)):
        v=np.array([d['by_kind'][j]['mass_kg'] for d in data]);ax.barh(y,v,left=base,height=.64,color=c,ec='white',lw=.4,label=KIND_LABELS[k]);base+=v
    for i,d in enumerate(data):ax.annotate(f"{d['total_mass_kg']:g}",(d['total_mass_kg'],i),xytext=(3,0),textcoords='offset points',fontsize=8,va='center')
    ax.set(xlim=(0,88),xticks=[0,20,40,60,80],xlabel='批次质量（kg）');grid(ax)
    bx.set(xlim=(-.5,3.5),xticks=range(4),xticklabels=['医','食','卫','水']);bx.xaxis.tick_top();bx.tick_params(axis='x',length=0,pad=4)
    for i,d in enumerate(data):
        for j,v in enumerate(d['by_kind']):bx.text(j,i,str(v['count']),fontsize=8.5,ha='center',va='center',color=INK if v['count'] else '#98A2AD')
    for j,c in enumerate(KC):bx.plot([j-.35,j+.35],[-.55,-.55],color=c,lw=1.3,clip_on=False)
    for i in np.arange(.5,18,1):bx.axhline(i,color=GRID,lw=.35)
    for i in [1.5,3.5,5.5]:
        for a in [tx,ax,bx]:a.axhline(i,color='#98A2AD',lw=.55)
    for s in bx.spines.values():s.set_visible(False)
    title(tx,'机型');title(ax,'质量构成');title(bx,'箱数')
    g.legend(*ax.get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.55,.988),ncol=4,handlelength=1.15,columnspacing=1.2)
    g.text(.15,.915,'机型以颜色和圆／方／三角区分；右表列出全部类别箱数。',fontsize=8,color=SECONDARY)
    write(8,g,'Q1正式18个不可拆货箱批次及所选机型。中图按物资类别分解批次质量，右表给出医疗、食品、卫生用品和饮用水的箱数；排列顺序表示服务区归属，不表示执行时序。',data,['results/q1/Q1_batch_solution.csv','paper/data/analysis.json'],'批次机型、质量与箱数',{'货箱编号列表':'box_ids; exact id join to analysis.boxes','机型编号':'type','boxes.kind/mass':'by_kind mass/count'},['按批次及物资类别对真实箱号求质量和计数'],{'18_batches':len(data)==18,'80_unique_boxes_once':True,'total758':sum(d['total_mass_kg'] for d in data)==758,'batch_mass_volume_match':True},params={'order':LABELS,'kind_order':KINDS,'mass_xlim':[0,88],'zero_count_shown':True})

def figure09():
    sl={r['trip']:r for r in rows('paper/data/constraint_slacks.csv') if r['question']=='q1'};data=[];counts=[0,0,0]
    for q in Q1:
        typ=A['types'][q['机型编号']];mass=f(q,'总质量（kg）');volume=f(q,'总体积（m³）');energy=f(q,'架次能耗（kWh）');values=[100*mass/typ['max_payload'],100*volume/typ['max_volume'],100*energy/((1-typ['rho'])*typ['energy_use'])]
        stored=[100*f(sl[q['架次编号']],k) for k in ['mass_fraction','volume_fraction','energy_fraction']]
        assert all(math.isclose(v,w,rel_tol=1e-12,abs_tol=1e-10) for v,w in zip(values,stored))
        # Classify using native full-precision values. No rank-specific epsilon exists
        # in the source; exact equality retains every actual tie, no rounded tie.
        hi=max(values);winners=[i for i,v in enumerate(values) if v==hi]
        for i in winners:counts[i]+=1
        assert mass<=typ['max_payload']+1e-10 and volume<=typ['max_volume']+1e-12 and energy<=(1-typ['rho'])*typ['energy_use']+1e-8
        data.append({'batch':q['架次编号'],'mass_kg':mass,'volume_m3':volume,'energy_kwh':energy,'rated_mass_kg':typ['max_payload'],'rated_volume_m3':typ['max_volume'],'capacity_kwh':typ['energy_use'],'reserve_ratio':typ['rho'],'rates_pct':values,'highest_indices':winners,'soc_pct':100*(1-energy/typ['energy_use'])})
    assert counts==[5,9,4];vals=np.array([d['rates_pct'] for d in data]);g=fig(13.2);gs=g.add_gridspec(1,2,width_ratios=[3.15,1.12],left=.155,right=.98,bottom=.185,top=.86,wspace=.12);ax,bx=[g.add_subplot(x) for x in gs]
    cmap=LinearSegmentedColormap.from_list('occupancy',['#F4F6F8','#D1DCE4','#95B5C9','#527D98','#214C66']);im=ax.imshow(vals,cmap=cmap,vmin=0,vmax=100,aspect='auto',interpolation='nearest')
    yrows(ax,LABELS);ax.set(xticks=range(3),xticklabels=['质量','体积','能量预算']);ax.xaxis.tick_top();ax.tick_params(axis='x',length=0,pad=7);ax.set_xticks(np.arange(-.5,3),minor=True);ax.set_yticks(np.arange(-.5,18),minor=True);ax.grid(which='minor',color='white',lw=.7);ax.tick_params(which='minor',length=0)
    cats=['质量','体积','能量'];cc=['#6F70A8','#B58C49','#5E8D87'];markers=['o','s','D']
    for i,d in enumerate(data):
        for j,v in enumerate(d['rates_pct']):
            rgb=cmap(v/100)[:3];lum=.2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2];ax.text(j,i,f'{v:.1f}%',ha='center',va='center',fontsize=8.5,color='white' if lum<.48 else INK)
        for j in d['highest_indices']:ax.add_patch(Rectangle((j-.47,i-.47),.94,.94,fill=False,ec=INK,lw=.95))
        k=d['highest_indices'][0];bx.plot(.16,i,marker=markers[k],ms=4,color=cc[k]);bx.text(.32,i,cats[k] if len(d['highest_indices'])==1 else '并列',fontsize=8.5,va='center')
    yrows(bx,LABELS,False);bx.set(xlim=(0,1),xticks=[]);bx.set_axis_off();title(ax,'(a) 各自可用预算占用');title(bx,'(b) 相对最高项')
    cax=g.add_axes([.23,.083,.49,.018]);g.colorbar(im,cax=cax,orientation='horizontal',ticks=[0,25,50,75,100],label='占各自可用预算（%）')
    g.text(.815,.072,'质量 5 批\n体积 9 批\n能量 4 批',fontsize=8,linespacing=1.3)
    g.text(.155,.958,'描框仅表示同一批次内的相对最高项。',fontsize=8,color=SECONDARY)
    write(9,g,'Q1各批次的质量、体积和可用能量预算占用率。描框表示该批相对占用最高的约束；质量、体积和能量分别为5、9、4批的最高项。相对最高不等于约束严格绑定，也不构成最优性证明。',{'batches':data,'highest_counts':dict(zip(cats,counts))},['results/q1/Q1_batch_solution.csv','paper/data/constraint_slacks.csv','paper/data/analysis.json','src/core/energy.py','src/q1/physics_engine.py','src/config.py','scripts/verify_paper.py'],'约束预算占用矩阵',{'Q1 mass/volume/energy':'numerators','types.max_payload/max_volume/energy_use/rho':'denominators','constraint_slacks':'cross-check saved fractions'},['mass%=100m/M','volume%=100v/V','energy%=100E/((1−ρ)B)','soc%=100(1−E/B)'],{'54_rates_match':True,'within_budget':True,'highest_counts5_9_4':True,'minSOC23.09':f'{min(d["soc_pct"] for d in data):.2f}'=='23.09'},params={'normalization':[0,100],'ties':'原代码无相对最高项容差；完整精度直接比较，完全相同全部保留；没有显示取整后判并列','feasibility_tolerances':'mass1e-10kg/volume1e-12m³/energy1e-8kWh from original implementation','rate_crosscheck':'scripts/verify_paper.py rel_tol1e-12 abs_tol1e-10','order':LABELS})

def figure02():
    # Shared map module is loaded late so that all figure batches use one map_spec.
    import common as cm
    data=[]
    for s in SERVICES:
        bs=[b for b in BOXES.values() if b['service']==s];data.append({'service':s,'lon':NODES[s]['lon'],'lat':NODES[s]['lat'],'elevation_m':NODES[s]['elev'],'box_count':len(bs),'marker_area_pt2':9*len(bs),'box_ids':[b['id'] for b in bs]})
    g=fig(12.5);gs=g.add_gridspec(1,2,width_ratios=[3.15,1],left=.08,right=.98,bottom=.23,top=.86,wspace=.33);ax,bx=[g.add_subplot(x) for x in gs]
    cm.map_base(ax,labels=False,draw_nodes=False)
    for d in data:
        x,y=cm.xy(d['service']);ax.scatter(x,y,s=d['marker_area_pt2'],color='#263F55',edgecolors='white',lw=.65,zorder=5)
        ax.annotate(d['service'],(x,y),xytext=cm.MAP_SPEC['label_offsets'][d['service']],textcoords='offset points',fontsize=8,zorder=8)
    x,y=cm.xy('O01');ax.scatter(x,y,s=80,marker='*',color=INK,ec='white',lw=.8,zorder=6);ax.annotate('O01',(x,y),xytext=cm.MAP_SPEC['label_offsets']['O01'],textcoords='offset points',fontsize=8,zorder=8)
    y=np.arange(15); bx.hlines(y,0,[d['elevation_m'] for d in data],color='#CAD3DB',lw=.5);bx.plot([d['elevation_m'] for d in data],y,'o',color='#566A7B',ms=4.9);yrows(bx,SERVICES);bx.set(xlim=(0,math.ceil(max(d['elevation_m'] for d in data)*1.04/50)*50),xticks=[0,200,400],xlabel='节点海拔（m）');grid(bx)
    title(ax,'(a) 任务节点与需求');title(bx,'(b) 节点海拔')
    handles=[ax.scatter([],[],s=9*n,color='#263F55',ec='white',lw=.65,label=f'{n} 箱') for n in [3,8,15]]
    g.legend(handles=handles,loc='upper center',bbox_to_anchor=(.42,.982),ncol=3,title='圆点面积表示箱数',title_fontsize=8.5,handletextpad=.7,columnspacing=1.4)
    cm.add_terrain_colorbar(g,ax,rect=[.08,.082,.57,.018])
    write(2,g,'原始30 m DEM上的调度中心、15个服务区及需求规模。圆点面积表示箱数，右侧列出输入表中的节点海拔；底图直接采用官方高程栅格，采用统一海拔色阶。节点海拔不替代逐航段的最高地形计算。',{'nodes':data,'origin':NODES['O01'],'map_spec':cm.MAP_SPEC},['paper/data/analysis.json','results/q3/Q3_relay_sorties.csv','paper/data/communication_critical_state.json'],'任务空间与节点海拔',{'nodes.lon/lat':'projected position','nodes.elev':'ground elevation','boxes.service/id':'unique box count'},['marker_area_pt2=9×count','位置按共享WGS84 ECEF→ENU局部东—北正射投影显示；不改变物理计算坐标'],{'15services':len(data)==15,'one_origin':True,'80boxes':sum(d['box_count'] for d in data)==80},missing=[],params={'map_spec':cm.MAP_SPEC,'fixed_label_offsets':cm.MAP_SPEC['label_offsets'],'size_legend_counts':[3,8,15]})

if __name__=='__main__':
    functions={1:figure01,2:figure02,3:figure03,4:figure04,5:figure05,6:figure06,7:figure07,8:figure08,9:figure09}
    selected=[int(x) for x in sys.argv[1:]] if len(sys.argv)>1 else list(functions)
    for n in selected: functions[n]();print('Saved',n,flush=True)
    (WORK/'figures_01_09_run.json').write_text(json.dumps(ALL_SPECS,ensure_ascii=False,indent=2),encoding='utf-8')



