"""Publication reconstruction 01--09: read-only frozen inputs and solutions.

No solver is invoked. New quantities are keyed deterministic plotting views.
Run with the same UAV_DATA_ROOT/UAV_FIGURE_OUT/UAV_FIGURE_QA as common.py.
"""
from pathlib import Path
import csv, json, hashlib, math, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.lines import Line2D
from matplotlib.colors import LinearSegmentedColormap
from matplotlib import patheffects
import common as cm
from paths import REPO, RAW, OUT, DATA, source_path

cm.init_style()
plt.rcParams.update({'hatch.linewidth':.25, 'legend.frameon':False, 'svg.hashsalt':'uav-publication-v2'})
C=cm.C; MARK=cm.MARKERS; INK=cm.TEXT; GRAY=cm.SECONDARY; GRID=cm.GRID; RED=cm.THRESHOLD
KIND=['医疗物资','应急食品','生活卫生用品','饮用水']
KL=['医疗','食品','卫生','饮水']; KC=list(cm.GOODS.values())
COMMIT='e71cdb13c0969a28d78f349e1ce79047e731e954'
RESEARCH_COMMIT='bec20f1536458db47bac583c309c7b30637cb67a'

def readj(p): return json.loads((REPO/p).read_text(encoding='utf-8'))
def rows(p): return list(csv.DictReader((REPO/p).open(encoding='utf-8-sig',newline='')))
def f(r,k): return float(r[k])
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jdefault(v):
    if isinstance(v,np.ndarray): return v.tolist()
    if isinstance(v,np.generic): return v.item()
    if isinstance(v,Path): return str(v)
    raise TypeError(type(v).__name__)
def dump(p,obj): Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=jdefault),encoding='utf-8')
A=readj('paper/data/analysis.json'); NODES=A['nodes']; SERVICES=sorted(k for k in NODES if k!='O01')
BOXES={b['id']:b for b in A['boxes']}
Q1=sorted(rows('results/q1/Q1_batch_solution.csv'),key=lambda r:(r['服务区编号'],r['架次编号']))
LABELS=[r['架次编号'].removeprefix('Q1-') for r in Q1]

def paperfig(h): return plt.figure(figsize=(16.3/2.54,h/2.54))
def panel(ax,t): ax.set_title(t,loc='left',pad=8,fontsize=10,weight='bold')
def grid(ax,axis='x'): ax.grid(axis=axis,color=GRID,lw=.45);ax.set_axisbelow(True)
def yrows(ax,labs,show=True):
    ax.set_ylim(len(labs)-.5,-.5);ax.set_yticks(range(len(labs)));ax.set_yticklabels(labs if show else []);ax.tick_params(axis='y',length=0)
def white_text(**kw): return dict(path_effects=[patheffects.withStroke(linewidth=1.3,foreground='white')],**kw)
def make_source(s):
    p=Path(s) if Path(s).is_absolute() else REPO/s
    return {'path':source_path(p),'sha256':sha(p)}
def write(n,fig,caption,data,sources,claim,panels,fields,formula,checks,changes,params=None):
    stem=f'fig_{n:02d}'
    fig.canvas.draw()
    text_artists=[t for t in fig.findobj(matplotlib.text.Text) if t.get_text() and t.get_visible()]
    min_font=min(t.get_fontsize() for t in text_artists)
    assert min_font>=8-1e-8,(n,min_font)
    assert all(v for v in checks.values()),(n,checks)
    for ext in ['svg','pdf']: fig.savefig(OUT/f'{stem}.{ext}',facecolor='white')
    fig.savefig(OUT/f'{stem}.png',dpi=600,facecolor='white')
    dump(DATA/f'{stem}_data.json',data);dump(OUT/f'{stem}_data.json',data)
    spec={'figure_id':n,'number':n,'title':claim,'core_claim':claim,'caption':caption,
          'width_cm':16.3,'height_cm':round(fig.get_figheight()*2.54,3),'dpi':600,'minimum_required_font_pt':8,'actual_minimum_font_pt':min_font,
          'repository_head':COMMIT,'research_commit':RESEARCH_COMMIT,'sources':[make_source(s) for s in sources],
          'source_fields':fields,'field_mapping':fields,'derived_formula':formula,'derived_formulas':formula,
          'panel_purposes':panels,'checks':checks,'structural_changes':changes,'parameters':params or {},
          'script':'scripts/figures_v2/figures_01_09.py','data_file':f'{stem}_data.json',
          'data_layer':f'paper/figure_data_v2/{stem}_data.json',
          'fonts':{'cn':cm.FONT_CN,'regular':source_path(cm.FONT_PATH),'bold':source_path(cm.FONT_BOLD_PATH),'latin':'DejaVu Sans','math':'STIX'},
          'scope':'Frozen inputs and outputs; no optimization, no changed route/assignment/parameter/time/result.',
          'missing_or_not_revalidated':[], 'visual_qa':{'status':'pending_actual_pdf_color_and_grayscale_review'}}
    dump(OUT/f'{stem}_spec.json',spec);dump(DATA/f'{stem}_spec.json',spec)
    (OUT/f'{stem}_caption.txt').write_text(caption,encoding='utf-8')
    plt.close(fig)

_official=None
def official():
    global _official
    if _official is None:
        sys.path.insert(0,str(REPO))
        from src.core.inputs import load_inputs
        values=load_inputs(RAW); nodes,types,drones,batteries,boxes,dem_file=values
        assert set(nodes)==set(NODES) and {b.id for b in boxes}==set(BOXES)
        for k,n in nodes.items():
            for key in ('lon','lat','elev'): assert getattr(n,key)==NODES[k][key]
        for k,t in types.items():
            for key,value in A['types'][k].items():assert getattr(t,key)==value,(k,key)
        for b in boxes:
            for key in ('id','service','kind','mass','volume','first','expected','hard_deadline'): assert getattr(b,key)==BOXES[b.id][key],(b.id,key)
        _official=values
    return _official

def figure01():
    modules=[
      {'question':'Q1','constraint':'单点往返与能量储备','method':'安全载荷二分\n锚定集合划分DP','output':'载荷边界与正式批次','functions':['src/q1/physics_engine.py:max_safe_payload','src/q1/physics_engine.py:_optimize_service']},
      {'question':'Q2','constraint':'箱级时限与双层资源','method':'重新选择架次列\n无人机／电池时序','output':'运输任务与交付时刻','functions':['src/q2/columns.py:enumerate_columns','src/q2/interval_master.py:IntervalMaster']},
      {'question':'Q3','constraint':'通信链路与中继窗口','method':'离散任务／中继选择\n固定离散方案的时序LP','output':'联合任务、指定中继','functions':['src/q3/search.py:search_plan','src/q3/solver.py:optimize_timing']},
      {'question':'Q4','constraint':'固定Q3任务与时序','method':'不可拆分量枚举\n独立资源峰值计数','output':'独立配置与分类缺口','functions':['src/q4/partition.py:solve_partitions','src/q4/partition.py:canonical_partitions']},
    ]
    # Names are independently checked against source, without importing solvers.
    for m in modules:
        for item in m['functions']:
            p,name=item.split(':');text=(REPO/p).read_text(encoding='utf-8')
            assert 'def '+name in text or 'class '+name in text,item
    g=paperfig(10.8);ax=g.add_axes([0,0,1,1]);ax.set(xlim=(0,16.3),ylim=(0,10.8));ax.set_axis_off()
    ax.text(8.15,10.36,'官方输入：原始DEM、节点、货箱、机型及通信参数',ha='center',fontsize=9,color=GRAY)
    ax.add_patch(Rectangle((.55,8.46),15.2,1.45,fc='#F1F5F7',ec='none'))
    ax.text(.78,9.53,'共同物理评价',fontsize=9.5,weight='bold')
    for x,t in zip([2.15,6.12,10.16,14.07],['原始地形','逐段载荷','时间／能量','资源区间']):ax.text(x,8.99,t,ha='center',va='center',fontsize=9.5)
    for x0,x1 in [(3.40,4.82),(7.32,8.88),(11.44,12.76)]: ax.annotate('',(x1,8.99),(x0,8.99),arrowprops={'arrowstyle':'-|>','lw':.9,'color':GRAY,'mutation_scale':8})
    xs=[.525,4.325,8.325,12.325]; widths=[3.45,3.65,3.65,3.45]; titles=['安全能力','运输调度','通信协同','独立配置']
    cols=['#CBDCE7','#C7DCE9','#DAD3E7','#DDD9D1']
    for x,w,m,t,c in zip(xs,widths,modules,titles,cols):
        cx=x+w/2
        ax.text(cx,7.81,m['question']+' '+t,ha='center',fontsize=10,weight='bold')
        ax.text(cx,7.10,m['constraint'],ha='center',fontsize=9,weight='bold' if m['question']=='Q4' else 'normal')
        ax.add_patch(Rectangle((x,4.15),w,2.35,fc='white',ec='none'))
        ax.add_patch(Rectangle((x,4.15),.08,2.35,fc=c,ec='none'))
        ax.text(x+.21,6.15,'实际决策',fontsize=9.5,color=GRAY)
        if m['question']=='Q3':
            ax.text(cx,5.50,'离散任务／中继选择',ha='center',fontsize=9)
            ax.plot([x+.22,x+w-.12],[5.14,5.14],color='#D4DBE1',lw=.55)
            ax.text(cx,4.67,'固定离散方案\n时序线性规划',ha='center',va='center',fontsize=9,linespacing=1.4)
        else:ax.text(cx,5.11,m['method'],ha='center',va='center',fontsize=9,linespacing=1.7)
        ax.text(cx,3.50,m['output'],ha='center',fontsize=9)
        ax.annotate('',(cx,3.92),(cx,4.13),arrowprops={'arrowstyle':'-|>','lw':.9,'color':GRAY,'mutation_scale':8})
        ax.annotate('',(cx,2.18),(cx,3.19),arrowprops={'arrowstyle':'-|>','lw':.8,'linestyle':(0,(3,3)),'color':GRAY,'mutation_scale':8})
    # Unique fixed-plan inheritance: branch from the Q3 output to the Q4 condition.
    ax.plot([10.15,11.97,11.97],[3.25,3.25,6.96],color=INK,lw=.9)
    ax.annotate('',(12.30,6.96),(11.97,6.96),arrowprops={'arrowstyle':'-|>','lw':.9,'color':INK,'mutation_scale':8})
    ax.add_patch(Rectangle((.55,1.15),15.2,1.08,fc='#F5F6F7',ec='none'))
    for x,w,t in zip(xs,widths,['箱号覆盖','交付记录','链路状态','资源峰值']):ax.text(x+w/2,1.68,t,ha='center',va='center',fontsize=9.5)
    ax.text(.70,.55,'—— 固定方案继承',fontsize=8.5);ax.text(6.52,.55,'- - - 核验关系',fontsize=8.5)
    sources=['src/core/physics.py','src/core/routes.py','src/q1/physics_engine.py','src/q2/columns.py','src/q2/interval_master.py','src/q3/search.py','src/q3/solver.py','src/q4/partition.py']
    write(1,g,'统一物理评价连接四问的决策与核验；Q2、Q3重新选择任务，Q4在冻结Q3任务及其时序后计算独立配置。虚线表示结果核验关系，实线仅表示Q3至Q4的固定方案继承。',modules,sources,
      '共同物理模型保证可比较，各问分别增加决策与约束',{'common':'共同地形、载荷、时间能量和资源区间','decisions':'四问独立决策层；Q3条件LP；Q4固定继承','evidence':'四类结果核验'},
      {'source functions':'method text and decision boundary'},[],{'four_questions':len(modules)==4,'named_source_members_exist':True,'only_Q3_Q4_fixed_inheritance':True},
      ['由四行三列表改为共同计算带、四列决策和证据带','Q3分开离散选择与条件时序LP','Q4只接Q3冻结输出'])

def figure02():
    official();legs={r['service']:r for r in rows('results/q1/Q1_leg_physics.csv')}
    data=[]
    for s in SERVICES:
        ids=sorted(b['id'] for b in BOXES.values() if b['service']==s)
        data.append({'service':s,**NODES[s],'box_ids':ids,'box_count':len(ids),'marker_area_pt2':7*len(ids),'max_dem_m':f(legs[s],'max_dem'),'paired_difference_m':f(legs[s],'max_dem')-NODES[s]['elev']})
    highlights={d['service'] for d in sorted(data,key=lambda d:abs(d['paired_difference_m']),reverse=True)[:2]}|{'S014'}
    g=paperfig(11.8);ax=g.add_axes([.083,.27,.564,.53]);bx=g.add_axes([.738,.185,.242,.60])
    cm.map_base(ax,labels=False,draw_nodes=False)
    for d in data:
        ax.scatter(*cm.xy(d['service']),s=d['marker_area_pt2'],fc='#263F55',ec='white',lw=.6,zorder=6)
        ax.annotate(d['service'],cm.xy(d['service']),xytext=cm.MAP_SPEC['label_offsets'][d['service']],textcoords='offset points',fontsize=8.5,zorder=9,**white_text())
    ax.annotate('O01',cm.xy('O01'),xytext=cm.MAP_SPEC['label_offsets']['O01'],textcoords='offset points',fontsize=8.5,zorder=9,**white_text())
    for i,d in enumerate(data):
        bx.plot([d['elev'],d['max_dem_m']],[i,i],color='#BBC4CB',lw=.7)
        bx.plot(d['elev'],i,'o',mfc='white',mec='#7D8A95',ms=4,mew=.8)
        bx.plot(d['max_dem_m'],i,'D',mfc='#89664C',mec='white',ms=4.3,mew=.35)
        if d['service'] in highlights:
            bx.annotate(f"Δ {d['paired_difference_m']:.0f}",(max(d['elev'],d['max_dem_m']),i),xytext=(3,0),textcoords='offset points',fontsize=8,va='center')
    mx=math.ceil(max(max(d['elev'],d['max_dem_m']) for d in data)/100)*100
    yrows(bx,SERVICES);bx.set(xlim=(0,mx+110),xticks=[0,200,400,600],xlabel='高程属性（m）');grid(bx)
    panel(ax,'(a) 地形与需求');panel(bx,'(b) 节点与沿线山脊')
    handles=[Line2D([],[],ls='',marker='o',markersize=math.sqrt(7*n),mfc='#263F55',mec='white',label=f'{n}箱') for n in [3,8,15]]
    g.legend(handles=handles,ncol=3,loc='upper left',bbox_to_anchor=(.075,.972),handletextpad=.5,columnspacing=1.2,title='需求点面积',title_fontsize=8.5)
    bx.legend(handles=[Line2D([],[],ls='',marker='o',mfc='white',mec='#7D8A95',label='节点输入海拔'),Line2D([],[],ls='',marker='D',mfc='#89664C',mec='white',label='沿线最高DEM')],loc='lower left',bbox_to_anchor=(-.07,1.105),ncol=1,handletextpad=.5)
    cm.add_terrain_colorbar(g,ax,[.14,.118,.43,.018]);g.text(.74,.075,'Δ为两属性差值（m）',fontsize=8,color=GRAY)
    import terrain
    sources=['paper/data/analysis.json','results/q1/Q1_leg_physics.csv','src/core/inputs.py',terrain.DEM_PATH,next(RAW.rglob('调度中心与服务区.xlsx')),next(RAW.rglob('物资需求与配送时限.xlsx'))]
    write(2,g,'需求空间及节点高程与单点航段最高地形的对照。地图圆点面积表示箱数；右侧连接节点输入海拔和O01至该区沿线最高DEM，二者为不同来源的高程属性，差值并非额外爬升或净空。沿途地形仍按原始DEM逐像元检查。',{'nodes':data,'origin':NODES['O01'],'highlighted_services':sorted(highlights),'map_spec':cm.MAP_SPEC},sources,
      '需求分布与地形共同构成任务空间，节点海拔不能替代沿线地形',{'a':'原始DEM上15服务区需求规模','b':'逐区节点海拔与沿线最高地形配对'},
      {'official workbook nodes':'nodes.lon/lat/elev checked against analysis','boxes.id/service':'unique box_count','Q1_leg_physics.service/max_dem':'max_dem_m, join on service'},['marker_area=7×unique_box_count','paired_difference=max_dem−node_elev','map display=shared WGS84 ENU'],
      {'16_nodes':len(NODES)==16,'15_dem_pairs':len(data)==15,'80_boxes':sum(d['box_count'] for d in data)==80,'official_nodes_boxes_equal_analysis':True},
      ['统一连续高程色带、0.18晕渲及细等高线','节点海拔列升级为沿线最高DEM配对','去除地图与色条过大空白'],{'map_spec':cm.MAP_SPEC,'paired_x_limit':[0,mx+110],'x_axis_extension_reason':'右侧三个Δ注记保留真实坐标之外的标注空间，不截断数据'})

def figure03():
    official();cats=sorted({b['hard_deadline'] for b in BOXES.values() if b['hard_deadline'] is not None});assert cats==[3600.,7200.,10800.]
    data=[]
    for s in SERVICES:
        bs=[b for b in BOXES.values() if b['service']==s]
        data.append({'service':s,'box_ids':[b['id'] for b in bs],'mass_by_kind':[sum(b['mass'] for b in bs if b['kind']==k) for k in KIND],
                     'count_by_deadline':[sum(b['hard_deadline']==c for b in bs) for c in cats]+[sum(b['hard_deadline'] is None for b in bs)],'mass_kg':sum(b['mass'] for b in bs),'box_count':len(bs)})
    g=paperfig(11.6);ax=g.add_axes([.098,.115,.506,.655]);bx=g.add_axes([.705,.115,.277,.655])
    for a in [ax,bx]:
        yrows(a,SERVICES,a is ax);grid(a)
        for yy in [4.5,9.5]:a.axhline(yy,color='#9BA6B0',lw=.55)
    y=np.arange(15);base=np.zeros(15)
    for j,(k,c) in enumerate(zip(KIND,KC)):
        v=np.array([d['mass_by_kind'][j] for d in data]);ax.barh(y,v,left=base,height=.62,fc=c,ec='white',lw=.35,hatch='.' if j==0 else ('//' if j==2 else ''),label=KL[j]);base+=v
    for i,d in enumerate(data):ax.annotate(f"{d['mass_kg']:g}",(d['mass_kg'],i),xytext=(3,0),textcoords='offset points',va='center',fontsize=8.5)
    base=np.zeros(15);cl=['#B5424A','#CC7E83','#E2B9BC','#CAD3DB'];labs=['1 h硬截止','2 h硬截止','3 h硬截止','无硬截止']
    for j,(c,l) in enumerate(zip(cl,labs)):
        v=np.array([d['count_by_deadline'][j] for d in data]);bx.barh(y,v,left=base,height=.62,fc=c,ec='white',lw=.35,hatch='//' if j==2 else '',label=l)
        if j<3:
            for i,(a,vv) in enumerate(zip(base,v)):
                if vv:bx.text(a+vv/2,i,str(vv),ha='center',va='center',fontsize=8,color='white' if j==0 else INK)
        base+=v
    for i,d in enumerate(data):bx.annotate(str(d['box_count']),(d['box_count'],i),xytext=(3,0),textcoords='offset points',fontsize=8.5,va='center')
    ax.set(xlim=(0,170),xticks=[0,50,100,150],xlabel='需求质量（kg）');bx.set(xlim=(0,16.5),xticks=[0,5,10,15],xlabel='货箱数（箱）')
    panel(ax,'(a) 物资质量组成');panel(bx,'(b) 箱级截止结构')
    for aa,anchor,hlen,csp in [(ax,(-.02,1.10),1.0,1.8),(bx,(-.11,1.10),.8,.7)]:
        hh,ll=aa.get_legend_handles_labels();jj=[0,2,1,3]
        aa.legend([hh[j] for j in jj],[ll[j] for j in jj],ncol=2,loc='lower left',bbox_to_anchor=anchor,handlelength=hlen,columnspacing=csp,handletextpad=.35)
    hard=sum(b['hard_deadline'] is not None for b in BOXES.values());first=sum(b['first'] for b in BOXES.values());med=sum(b['kind']==KIND[0] for b in BOXES.values())
    write(3,g,'各服务区的质量组成与箱级截止结构，共80箱、758 kg、2.011 m³。右图按有效硬截止时刻及无硬截止互斥分解，31箱硬截止为首批与医疗箱的并集；无硬截止的货箱仍保留期望送达时间。',{'services':data,'boxes':list(BOXES.values()),'hard_deadline_categories_s':cats,'first_count':first,'medical_count':med,'hard_count':hard},
      ['paper/data/analysis.json','src/core/inputs.py',next(RAW.rglob('物资需求与配送时限.xlsx'))],
      '需求规模与硬截止紧迫性在相同服务区顺序下共同呈现',{'a':'四类需求质量','b':'1/2/3小时硬截止与无硬截止互斥箱数'},
      {'boxes.id/service/kind/mass':'left panel group sums','boxes.hard_deadline':'right actual deadline categories','boxes.first/expected':'hard definition crosscheck'},
      ['mass_by_kind=sum(mass) by service,kind','count_by_deadline=count(unique id) by service,effective hard_deadline'],
      {'80_unique':len(BOXES)==80,'758_kg':sum(b['mass'] for b in BOXES.values())==758,'2.011_m3':math.isclose(sum(b['volume'] for b in BOXES.values()),2.011,abs_tol=1e-12),'31_hard':hard==31,'30_first':first==30,'16_medical':med==16,'nonfirst_med_included':BOXES['S001-MED-02']['hard_deadline'] is not None,'per_service_totals':all(sum(d['count_by_deadline'])==d['box_count'] for d in data)},
      ['将有/无硬截止二分类改为真实1/2/3小时结构','减少横向分隔、缩短图例','保留逐箱硬截止定义'])

def energy_view():
    ec=rows('paper/data/energy_components.csv');data=[]
    for q in Q1:
        sub=[r for r in ec if r['trip']==q['架次编号']];dd={r['direction']:r for r in sub}
        assert len(sub)==2 and set(dd)=={'outbound','return'} and f(dd['return'],'payload_kg')==0
        vals=[f(dd[d],k) for d,k in [('outbound','horizontal_kwh'),('outbound','climb_kwh'),('return','horizontal_kwh'),('return','climb_kwh')]]
        total=sum(vals);assert math.isclose(total,f(q,'架次能耗（kWh）'),abs_tol=1e-8,rel_tol=0)
        data.append({'trip':q['架次编号'],'service':q['服务区编号'],'type':q['机型编号'],'components_kwh':vals,'total_kwh':total,'return_share_pct':100*(vals[2]+vals[3])/total,'climb_share_pct':100*(vals[1]+vals[3])/total,'source_components':sub})
    return data

def figure04():
    raw=[{k:float(v) for k,v in r.items()} for r in rows('paper/data/terrain_profile.csv')]
    cuts=sorted({v for r in raw for v in [r['begin_m'],r['end_m']]});steps=[]
    for lo,hi in zip(cuts,cuts[1:]):steps.append({'begin_m':lo,'end_m':hi,'elevation_m':max(r['elevation_m'] for r in raw if r['begin_m']<=(lo+hi)/2<=r['end_m'])})
    events=[{'distance_m':x,'elevation_m':max(r['elevation_m'] for r in raw if r['begin_m']<=x<=r['end_m'])} for x in cuts]
    t=A['terrain_example'];leg=next(r for r in rows('results/q1/Q1_leg_physics.csv') if r['service']=='S014')
    assert all(math.isclose(t[k],f(leg,k),abs_tol=1e-10,rel_tol=0) for k in t if k!='service')
    q=next(r for r in Q1 if r['架次编号']=='Q1-S014-01');e=next(d for d in energy_view() if d['trip']==q['架次编号']);typ=A['types'][q['机型编号']]
    durations={'去程':[t['out_up']/typ['climb_speed'],t['distance']/typ['cruise_speed'],t['out_down']/typ['descent_speed']], '返程':[t['ret_up']/typ['climb_speed'],t['distance']/typ['cruise_speed'],t['ret_down']/typ['descent_speed']]}
    g=paperfig(12.5);ax=g.add_axes([.09,.515,.887,.40]);tx=g.add_axes([.09,.135,.403,.245]);ex=g.add_axes([.594,.135,.383,.245])
    xx=np.array(cuts)/1000;zz=np.array([r['elevation_m'] for r in steps]+[steps[-1]['elevation_m']])
    ax.fill_between(xx,0,zz,step='post',color='#BDD0BC',alpha=.9);ax.step(xx,zz,where='post',color='#66705E',lw=1)
    for event in events:
        adjacent=[r['elevation_m'] for r in steps if r['begin_m']<=event['distance_m']<=r['end_m']]
        if adjacent and event['elevation_m']>max(adjacent):ax.vlines(event['distance_m']/1000,max(adjacent),event['elevation_m'],color='#66705E',lw=1)
    dist=t['distance']/1000;z0=t['cruise_alt']-t['out_up'];z1=t['cruise_alt']-t['out_down']
    ax.plot([0,0,dist,dist],[z0,t['cruise_alt'],t['cruise_alt'],z1],color='#234F70',lw=1.6)
    ax.annotate('',(0,t['cruise_alt']),(0,z0),arrowprops={'arrowstyle':'-|>','color':'#234F70','lw':1})
    ax.annotate('',(dist,z1),(dist,t['cruise_alt']),arrowprops={'arrowstyle':'-|>','color':'#234F70','lw':1})
    peak=next(r for r in steps if r['elevation_m']==t['max_dem']);px=(peak['begin_m']+peak['end_m'])/2000
    ax.annotate(f"最高地形 {t['max_dem']:.3f} m",(px,t['max_dem']),xytext=(3.20,483),fontsize=8.5,arrowprops={'arrowstyle':'-','lw':.65,'color':GRAY},bbox={'fc':'white','ec':'none','pad':1})
    ax.text(1.45,611,f"巡航 {t['cruise_alt']:.3f} m",fontsize=8.5,color='#234F70')
    ax.annotate('',(4.83,t['max_dem']),(4.83,t['cruise_alt']),arrowprops={'arrowstyle':'|-|','lw':.8,'color':INK});ax.text(4.96,562,'50 m',fontsize=8.5,va='center')
    ax.text(.17,230,f"爬升\n{t['out_up']:.3f} m",fontsize=8.5,bbox={'fc':'white','ec':'none','pad':1})
    ax.text(5.20,270,f"下降\n{t['out_down']:.3f} m",ha='right',fontsize=8.5,bbox={'fc':'white','ec':'none','pad':1})
    ax.set(xlim=(-.06,5.5),ylim=(0,650),xticks=np.arange(0,6),yticks=[0,200,400,600],xlabel='水平距离（km）',ylabel='海拔（m）');grid(ax,'y');panel(ax,'(a) O01 → S014原始地形与计划航高')
    phase_hatch=['//','','..']
    for i,(name,vv) in enumerate(durations.items()):
        left=0
        for j,v in enumerate(vv):tx.barh(i,v,left=left,height=.45,fc=cm.STAGE['flight'] if i==0 else cm.STAGE['return'],ec='white',lw=.4,hatch=phase_hatch[j]);left+=v
        tx.annotate(f'{left:.1f}',(left,i),xytext=(3,0),textcoords='offset points',va='center',fontsize=8.5)
    tx.set(yticks=[0,1],yticklabels=['去程','返程'],ylim=(1.7,-.7),xlim=(0,830),xticks=[0,300,600],xlabel='飞行时长（s）');grid(tx);panel(tx,'(b) 飞行阶段时长')
    tx.legend(handles=[Rectangle((0,0),1,1,fc='white',ec=GRAY,lw=.4,hatch=h,label=l) for h,l in zip(phase_hatch,['爬升','巡航','下降'])],ncol=3,loc='upper center',bbox_to_anchor=(.49,1.01),handlelength=.7,columnspacing=.7,handletextpad=.3,fontsize=8)
    for i,vals in enumerate([e['components_kwh'][:2],e['components_kwh'][2:]]):
        ex.barh(i,vals[0],height=.45,fc='#506A85',ec='white',lw=.4,label='水平' if i==0 else None)
        ex.barh(i,vals[1],left=vals[0],height=.45,fc='#B8C7D4',ec='#506A85',lw=.4,hatch='///',label='爬升' if i==0 else None)
        ex.annotate(f'{sum(vals):.3f}',(sum(vals),i),xytext=(3,0),textcoords='offset points',fontsize=8.5,va='center')
    ex.set(yticks=[0,1],yticklabels=['去程','返程'],ylim=(1.7,-.7),xlim=(0,2.2),xticks=[0,1,2],xlabel='能耗（kWh）');grid(ex);panel(ex,'(c) 同任务能耗')
    ex.legend(ncol=2,loc='upper center',bbox_to_anchor=(.55,1.01),handlelength=.8,columnspacing=1,handletextpad=.4,fontsize=8)
    g.text(.09,.035,'飞行阶段不含准备装载与交接；剖面纵、横显示比例不同。',fontsize=8.5,color=GRAY)
    full_duration=sum(sum(v) for v in durations.values())+typ['prep_time']+typ['load_time_per_box']*len(q['货箱编号列表'].split(','))+typ['handover_base']+typ['handover_per_box']*len(q['货箱编号列表'].split(','))
    assert math.isclose(full_duration,f(q,'往返时间（s）'),rel_tol=0,abs_tol=1e-7)
    data={'trip':q,'profile_raw_closed_intervals':raw,'display_upper_envelope':steps,'boundary_maxima':events,'terrain_example':t,'flight_durations_s':durations,'full_operation_duration_s_crosscheck_only':full_duration,'energy':e}
    write(4,g,'Q1-S014-01（B型，25 kg）同一冻结任务的原始地形剖面、去返程飞行阶段和能耗。剖面按闭像元区间保守包络展示，最高地形541.947 m、巡航591.947 m；两条飞行时长不含准备装载与交接，下降附加能耗为零。端点作业高程保留原输入定义，纵横显示比例不同。',data,
      ['paper/data/terrain_profile.csv','paper/data/analysis.json','paper/data/energy_components.csv','results/q1/Q1_leg_physics.csv','results/q1/Q1_batch_solution.csv','src/core/physics.py','src/core/routes.py','src/core/energy.py'],
      '沿线山脊决定同一正式任务的升降与飞行能耗',{'a':'同任务地形、巡航及净空','b':'按原速度确定的去返飞行阶段时长','c':'载货去程与空载返程能耗'},
      {'terrain_profile.begin_m/end_m/elevation_m':'closed cell profile and upper envelope','Q1_leg_physics.service':'join S014','types.climb_speed/cruise_speed/descent_speed':'duration denominators','energy_components.trip/direction':'four energy terms'},
      ['phase_duration=climb/climb_speed, distance/cruise_speed, descent/descent_speed','profile display=max elevation on overlapping closed intervals','energy_out+energy_return=formal batch energy'],
      {'distance_matches':cuts[-1]==t['distance'],'max_dem_matches':max(r['elevation_m'] for r in raw)==t['max_dem'],'clearance50':t['cruise_alt']-t['max_dem']==50,'B25':q['机型编号']=='B' and f(q,'总质量（kg）')==25,'four_energy_sum_matches':True,'full_duration_replay_matches_formal':True,'closed_boundary_maxima_retained':True},
      ['单剖面升级为同任务地形—时间—能耗证据链','高度注释缩短并使用局部白底','辅助量纲独立，不把飞行和写成完整作业时间'])

def figure05():
    data=energy_view();g=paperfig(12.7);ax=g.add_axes([.148,.105,.498,.718]);bx=g.add_axes([.757,.555,.219,.268]);cx=g.add_axes([.757,.16,.219,.238])
    yrows(ax,LABELS);grid(ax);colors=['#506A85','#B8C7D4','#88715B','#D8C8B7'];labs=['去程水平','去程爬升','返程水平','返程爬升'];base=np.zeros(18)
    for j,(c,l) in enumerate(zip(colors,labs)):
        vals=np.array([d['components_kwh'][j] for d in data]);ax.barh(range(18),vals,left=base,height=.64,fc=c,ec='white',lw=.4,hatch='///' if j%2 else '',label=l);base+=vals
    for i,d in enumerate(data):ax.annotate(f"{d['total_kwh']:.3f}",(d['total_kwh'],i),xytext=(3,0),textcoords='offset points',va='center',fontsize=8.5)
    ax.set(xlim=(0,7),xticks=range(8),xlabel='架次能耗（kWh）');panel(ax,'(a) 18批能耗组成')
    special={max(data,key=lambda d:d[k])['trip'] for k in ['total_kwh','return_share_pct','climb_share_pct']}
    for d in data:
        hi=d['trip'] in special;bx.scatter(d['return_share_pct'],d['climb_share_pct'],s=25,fc='white' if hi else '#B8C7D4',ec=INK if hi else '#506A85',lw=.6,zorder=3)
        if hi:
            off={'Q1-S004-01':(-49,15),'Q1-S008-01':(-48,-13)}.get(d['trip'],(-47,5))
            bx.annotate(d['trip'].removeprefix('Q1-'),(d['return_share_pct'],d['climb_share_pct']),xytext=off,textcoords='offset points',fontsize=8,arrowprops={'arrowstyle':'-','lw':.5,'color':GRAY})
    bx.set(xlim=(0,math.ceil(max(d['return_share_pct'] for d in data)/5)*5),ylim=(0,math.ceil(max(d['climb_share_pct'] for d in data)/5)*5),xlabel='返程份额（%）',ylabel='爬升份额（%）');grid(bx,'both');panel(bx,'(b) 相对贡献')
    sums=np.sum([d['components_kwh'] for d in data],axis=0);total=float(sum(sums));return_pct=100*(sums[2]+sums[3])/total
    for i,vals in enumerate([sums[:2],sums[2:]]):
        cx.barh(i,vals[0],height=.5,fc=colors[2*i],ec='white',lw=.4)
        cx.barh(i,vals[1],left=vals[0],height=.5,fc=colors[2*i+1],ec='white',lw=.4,hatch='///')
        cx.annotate(f'{sum(vals):.3f}',(sum(vals),i),xytext=(3,0),textcoords='offset points',fontsize=8.5,va='center')
    cx.set(yticks=[0,1],yticklabels=['去程','返程'],ylim=(1.7,-.7),xlim=(0,52),xticks=[0,25,50],xlabel='总能耗（kWh）');grid(cx);panel(cx,'(c) 总体去返程')
    g.text(.734,.025,f'总体返程份额 {return_pct:.1f}%',fontsize=8.5)
    hh,ll=ax.get_legend_handles_labels();jj=[0,2,1,3]
    g.legend([hh[j] for j in jj],[ll[j] for j in jj],loc='upper center',bbox_to_anchor=(.57,.986),ncol=2,handlelength=1.2,columnspacing=1.8)
    write(5,g,'固定Q1批次的能耗组成、返程与爬升相对贡献及总体去返程代价，总计59.130 kWh。散点只描述18个已选批次；强调标记分别覆盖总能耗、返程份额和爬升份额最大批次。总体份额先对能耗求和再相除，下降附加能耗为零。',{'batches':data,'component_sums_kwh':sums,'overall_return_share_pct':return_pct,'highlighted_trips':sorted(special)},
      ['paper/data/energy_components.csv','results/q1/Q1_batch_solution.csv'],
      '全体批次的微小爬升贡献与空载返程代价均可读',{'a':'全量18批四项能耗','b':'返程与爬升占比配对散点','c':'全体去返程能耗汇总'},
      {'trip+direction':'exact component join','horizontal_kwh/climb_kwh/payload_kg':'four components and payload validation','Q1_batch_solution.架次能耗（kWh）':'formal energy check'},
      ['return_share=100*(return_horizontal+return_climb)/batch_total','climb_share=100*(out_climb+return_climb)/batch_total','overall_return_share=100*sum(return_energy)/sum(all_energy)'],
      {'18_batches':len(data)==18,'4_terms_match_each':True,'all_return_payload_zero':True,'59.130_display':f'{total:.3f}'=='59.130'},
      ['右列逐批返程点列换为配对散点与整体去返程汇总','微小爬升项保持真实宽度并加纹理','全部正式批次及四项能耗仍保留'])

def figure06():
    phases=[r for r in rows('paper/figure_data_v2/q2_task_phases.csv') if r['trip_id']=='Q2-001']
    assert phases
    resources=[r for r in rows('results/q2/Q2_resource_check.csv') if r['架次编号']=='Q2-001'];u=next(r for r in resources if r['资源类型']=='无人机');b=next(r for r in resources if r['资源类型']=='电池')
    trip=next(r for r in rows('results/q2/Q2_transport_trips_balanced.csv') if r['架次编号']=='Q2-001');deliveries=[r for r in rows('results/q2/Q2_box_delivery_balanced.csv') if r['架次编号']=='Q2-001']
    start=f(u,'任务占用开始（s）');end=f(u,'任务占用结束（s）')-start;charge=f(b,'充电结束（s）')-start
    delivery_values={float(r['交付完成时刻（s）'])-start for r in deliveries};assert len(delivery_values)==1;delivery=next(iter(delivery_values))
    starts=[f(p,'t_begin_relative_s') for p in phases];ends=[f(p,'t_end_relative_s') for p in phases]
    assert starts[0]==0 and all(math.isclose(a,z,rel_tol=0,abs_tol=1e-7) for a,z in zip(starts[1:],ends[:-1])) and math.isclose(ends[-1],end,abs_tol=1e-7,rel_tol=0)
    assert math.isclose(sum(f(p,'phase_energy_kwh') for p in phases),f(trip,'架次能耗（kWh）'),rel_tol=0,abs_tol=1e-8)
    assert ends[0]==A['types']['A']['prep_time']+A['types']['A']['load_time_per_box']*len(deliveries)
    assert math.isclose(next(f(p,'t_end_relative_s') for p in phases if p['phase_kind']=='handover'),delivery,rel_tol=0,abs_tol=1e-7)
    g=paperfig(7.4);ax=g.add_axes([.177,.205,.796,.52]);barh=.235
    def stage(p):
        if p['phase_kind']=='prep_load':return 'prep'
        if p['phase_kind']=='handover':return 'handover'
        return 'return' if p['target']=='O01' else 'flight'
    for p in phases:
        k=stage(p);a=f(p,'t_begin_relative_s');z=f(p,'t_end_relative_s')
        for y in [1,0]:ax.barh(y,z-a,left=a,height=barh,fc=cm.STAGE[k],ec='white',lw=.4)
    ax.barh(0,charge-end,left=end,height=barh,fc=cm.STAGE['charge'],ec=cm.STAGE_EDGE['charge'],lw=.5,hatch='///')
    for y,z in [(1,end),(0,charge)]:
        ax.plot(0,y,'o',ms=4,mfc=INK,mec=INK,zorder=5);ax.plot(z,y,'o',ms=4,mfc='white',mec=INK,zorder=5)
    for t,name,level in [(delivery,'交付',1.52),(end,'返航',1.82),(charge,'充满',1.52)]:
        ax.axvline(t,color=GRAY,lw=.7 if name=='交付' else 1.0,ls=(0,(2,3)),ymin=.11,ymax=.84)
        ax.text(t,level,f'{name} {t:.1f} s',ha='center',fontsize=8.5)
    outbound=[p for p in phases if stage(p)=='flight'];returns=[p for p in phases if stage(p)=='return']
    for ps,lab in [(outbound,'去程'),(returns,'返航')]:
        a=f(ps[0],'t_begin_relative_s');z=f(ps[-1],'t_end_relative_s')
        ax.annotate('',(a,1.22),(z,1.22),arrowprops={'arrowstyle':'|-|','lw':.6,'color':GRAY});ax.text((a+z)/2,1.30,lab,ha='center',fontsize=8.5)
    ax.annotate('',(end,.49),(charge,.49),arrowprops={'arrowstyle':'|-|','lw':.65,'color':GRAY})
    ax.text((end+charge)/2,.62,f'额外充电 {charge-end:.1f} s',fontsize=8.5,ha='center')
    ax.text((end+charge)/2,0,'充电',ha='center',va='center',fontsize=8.5)
    ax.set(xlim=(0,2300),ylim=(-.36,1.96),xticks=[0,500,1000,1500,2000],yticks=[1,0],yticklabels=[],xlabel='自架次开始的时间（s）');ax.tick_params(axis='y',length=0,pad=12);ax.spines['left'].set_visible(False);grid(ax)
    for y,label in [(1,'U01'),(0,'A-BAT-01')]:
        ax.text(-.035,y,label,transform=ax.get_yaxis_transform(),ha='right',va='center',fontsize=8.5)
        ax.plot(-.155,y,transform=ax.get_yaxis_transform(),marker='o',ms=4,color=C['A'],clip_on=False)
    handles=[Rectangle((0,0),1,1,fc=cm.STAGE[k],ec=cm.STAGE_EDGE.get(k,'white'),hatch='///' if k=='charge' else '',label=l) for k,l in [('prep','准备装载'),('flight','去程飞行'),('handover','交接'),('return','返航'),('charge','充电')]]
    g.legend(handles=[handles[j] for j in [0,3,1,4,2]],loc='upper center',bbox_to_anchor=(.54,.98),ncol=3,handlelength=1.1,columnspacing=1.2)
    g.text(.177,.015,'Q2-001：●开始、○释放；资源占用为左闭右开区间。',fontsize=8.5,color=GRAY)
    write(6,g,'Q2-001的实际作业阶段与双层资源释放。两箱在908.6 s交付，早于1250.9 s返航；无人机返航后释放，电池继续充电至2121.3 s，额外占用870.4 s。去返程细分爬升、巡航与下降；充电完成不计入运输返航完工。',
      {'phases':phases,'trip':trip,'resources':resources,'deliveries':deliveries,'return_s':end,'delivery_s':delivery,'charge_complete_s':charge,'extra_battery_s':charge-end},
      ['paper/figure_data_v2/q2_task_phases.csv','paper/figure_data_v2/q2_replay_audit.json','results/q2/Q2_transport_trips_balanced.csv','results/q2/Q2_resource_check.csv','results/q2/Q2_box_delivery_balanced.csv','src/core/routes.py','src/core/physics.py'],
      '交付、无人机返航释放与电池充满释放是三种真实时刻',{'single':'真实阶段对齐的无人机与电池占用'},
      {'q2_task_phases.trip_id/phase_kind/t_begin_relative_s/t_end_relative_s':'stage intervals','Q2_resource_check.资源编号/任务占用结束（s）/充电结束（s）':'identity and resource releases','Q2_box_delivery_balanced.交付完成时刻（s）':'actual delivery event'},
      ['prep_load=prep_time+load_time_per_box*number_of_formal_boxes','all plotted times=absolute_time−formal_start','extra_battery=charge_complete−return'],
      {'continuous_phases':True,'final_phase_equals_formal_return':True,'two_boxes_same_delivery':len(deliveries)==2,'phase_handover_matches_delivery':True,'prep_load_matches_definition':True,'phase_energy_sum_matches_formal':True,'energy_1.2823207080116534':math.isclose(f(trip,'架次能耗（kWh）'),1.2823207080116534,rel_tol=0,abs_tol=1e-10),'correct_resources':u['资源编号']=='U01' and b['资源编号']=='A-BAT-01'},
      ['整块任务条拆为模型定义的准备、飞行、交接、返航','新增实际交付时刻','双层资源前段严格共用x坐标，充电独立纹理'])

def figure07():
    data=[]
    for r in rows('results/q1/Q1_max_safe_payload.csv'):
        for typ in 'ABC':
            safe=f(r,f'{typ}型最大安全载荷（kg）');rated=A['types'][typ]['max_payload']
            data.append({'service':r['服务区编号'],'type':typ,'safe_kg':safe,'rated_kg':rated,'ratio':safe/rated,'ratio_pct':100*safe/rated,'shortfall_kg':rated-safe,'loss_pct':100*(1-safe/rated),'reachable':r[f'{typ}型空载可达']=='True'})
    bykey={(d['service'],d['type']):d for d in data};order=sorted(SERVICES,key=lambda s:(-bykey[(s,'C')]['shortfall_kg'],s))
    g=paperfig(12.3);ax=g.add_axes([.122,.18,.455,.605]);bx=g.add_axes([.654,.18,.324,.605])
    yrows(ax,order);grid(ax);offset={'A':-.18,'B':0,'C':.18}
    for i,s in enumerate(order):
        for typ in 'ABC':
            d=bykey[(s,typ)];y=i+offset[typ];restricted=d['shortfall_kg']>1e-8
            if not d['reachable']:ax.text(2,y,'× 不可达',fontsize=8.5,va='center');continue
            if restricted:
                ax.plot([d['safe_kg'],d['rated_kg']],[y,y],color=C[typ],lw=1.5)
                ax.plot(d['rated_kg'],y,MARK[typ],mfc='white',mec=C[typ],ms=4.5,mew=.8)
            ax.plot(d['safe_kg'],y,MARK[typ],color=C[typ],alpha=1 if restricted else .48,ms=4.5)
            if restricted:ax.annotate(f"{d['safe_kg']:.2f}",(d['safe_kg'],y),xytext=(-5,0),textcoords='offset points',ha='right',va='center',fontsize=8)
    loss=np.array([[bykey[(s,t)]['loss_pct'] for t in 'ABC'] for s in order]);cap=max(30,math.ceil(loss.max()/10)*10)
    cmap=LinearSegmentedColormap.from_list('capacity_loss',['#F4F7F8','#315E79']);im=bx.imshow(loss,aspect='auto',vmin=0,vmax=cap,cmap=cmap,interpolation='nearest')
    yrows(bx,order,False);bx.set_xticks(range(3),['A\n25 kg','B\n30 kg','C\n80 kg']);bx.xaxis.tick_top();bx.tick_params(axis='x',length=0,pad=5)
    bx.set_xticks(np.arange(-.5,3,1),minor=True);bx.set_yticks(np.arange(-.5,15,1),minor=True);bx.grid(which='minor',color='white',lw=.7);bx.tick_params(which='minor',length=0)
    for i,s in enumerate(order):
        for j,t in enumerate('ABC'):
            d=bykey[(s,t)];v=d['ratio_pct'];restricted=d['shortfall_kg']>1e-8
            bx.text(j,i,f'{v:.1f}' if restricted else '100',ha='center',va='center',fontsize=8.5,color='white' if d['loss_pct']>cap*.58 else INK)
            if restricted:bx.add_patch(Rectangle((j-.48,i-.47),.96,.94,fill=False,ec=INK,lw=.8))
    ax.set(xlim=(0,90),xticks=[0,20,40,60,80],xlabel='安全载荷与额定载荷（kg）')
    g.text(.122,.90,'(a) 绝对能力与损失',fontsize=10,weight='bold');g.text(.654,.90,'(b) 占额定比例（%）',fontsize=10,weight='bold')
    g.legend(handles=[Line2D([],[],ls='',marker=MARK[t],color=C[t],label=t+'型') for t in 'ABC']+[Line2D([],[],ls='',marker='o',mfc='white',mec=GRAY,label='空心：额定')],loc='upper center',bbox_to_anchor=(.58,.985),ncol=4,columnspacing=.9,handletextpad=.4)
    ax.annotate('',(-.155,-.35),(-.155,4.35),xycoords=ax.get_yaxis_transform(),arrowprops={'arrowstyle':'|-|','lw':.6,'color':GRAY},annotation_clip=False)
    ax.text(-.198,2,'C型受能量限制',rotation=90,transform=ax.get_yaxis_transform(),ha='center',va='center',fontsize=8.5,color=GRAY)
    cax=g.add_axes([.683,.092,.271,.018]);g.colorbar(im,cax=cax,orientation='horizontal',ticks=[0,10,20,cap],label='额定损失率（%）')
    g.text(.122,.035,'B型仅S008受限；实心与空心之间为实际载荷损失。',fontsize=8.5,color=GRAY)
    write(7,g,'安全载荷相对各机型额定能力的差额及比例，按C型载荷损失降序、同值按服务区编号排列。左侧实心为安全载荷、空心为额定能力；右侧数字是占额定比例，底色是额定损失率，未按列单独归一化。单点往返边界不直接替代多点路线可行性。',
      {'long_table':data,'service_order':order,'loss_color_limit_pct':cap},['results/q1/Q1_max_safe_payload.csv','paper/data/analysis.json'],
      '相对额定能力的真实损失集中于六个机型—服务区组合',{'a':'同形额定与安全载荷的真实kg差','b':'占额定数字与损失率共同尺度'},
      {'service+type':'join and row ordering','max_safe_payload':'safe_kg','analysis.types.max_payload/rho':'rated_kg and original reserve'},
      ['ratio=safe_kg/rated_kg','shortfall_kg=rated_kg−safe_kg','loss_pct=100*(1−ratio)','sort by C shortfall descending then service'],
      {'45_rows':len(data)==45,'15_A25':all(d['safe_kg']==25 for d in data if d['type']=='A'),'5_Climited':sum(d['shortfall_kg']>1e-8 for d in data if d['type']=='C')==5,'1_Blimited':sum(d['shortfall_kg']>1e-8 for d in data if d['type']=='B')==1,'Bmin28.80':f"{min(d['safe_kg'] for d in data if d['type']=='B'):.2f}"=='28.80','Cmin58.91':f"{min(d['safe_kg'] for d in data if d['type']=='C'):.2f}"=='58.91'},
      ['右侧重复100%点列改为比例数字/损失率矩阵','左图新增额定空心参照及实际损失连接','按C型损失统一排序，受限组合成为焦点'])

def figure08():
    data=[];ids=[]
    for q in Q1:
        bs=sorted([BOXES[b] for b in q['货箱编号列表'].split(',')],key=lambda b:(KIND.index(b['kind']),b['id']))
        left=0.;display=[]
        for b in bs:
            display.append({**b,'left_mass_kg':left,'right_mass_kg':left+b['mass'],'label':str(int(b['id'].split('-')[-1]))});left+=b['mass'];ids.append(b['id'])
        assert left==f(q,'总质量（kg）')
        data.append({'trip':q['架次编号'],'service':q['服务区编号'],'type':q['机型编号'],'boxes':display,'total_mass_kg':left,'box_count':len(bs)})
    g=paperfig(12.4);tx=g.add_axes([.141,.10,.054,.72]);ax=g.add_axes([.212,.10,.670,.72]);nx=g.add_axes([.935,.10,.045,.72])
    yrows(tx,LABELS);yrows(ax,LABELS,False);yrows(nx,LABELS,False)
    tx.set_xlim(0,1);tx.set_xticks([]);nx.set_xlim(0,1);nx.set_xticks([])
    for a in [tx,nx]:
        for sp in a.spines.values():sp.set_visible(False)
    for i,d in enumerate(data):
        tx.plot(.18,i,marker=MARK[d['type']],color=C[d['type']],ms=4.5);tx.text(.53,i,d['type'],fontsize=8.5,va='center')
        for b in d['boxes']:
            k=KIND.index(b['kind']);hatch='.' if k==0 else ('//' if k==2 else '')
            ax.barh(i,b['mass'],left=b['left_mass_kg'],height=.64,fc=KC[k],ec='white',lw=.55,hatch=hatch)
            ax.text((b['left_mass_kg']+b['right_mass_kg'])/2,i,b['label'],fontsize=8.5,ha='center',va='center',color='white' if k in [0,1] else INK,bbox={'fc':KC[k],'ec':'none','pad':.05} if k==0 else None)
        ax.annotate(f"{d['total_mass_kg']:g}",(d['total_mass_kg'],i),xytext=(3,0),textcoords='offset points',fontsize=8.5,va='center')
        nx.text(.5,i,str(d['box_count']),ha='center',va='center',fontsize=8.5)
    for lo,hi in [(0,1),(2,3),(4,5)]:
        tx.annotate('',(-1.77,lo-.32),(-1.77,hi+.32),xycoords=tx.get_yaxis_transform(),arrowprops={'arrowstyle':'|-|','lw':.6,'color':GRAY},annotation_clip=False)
    ax.set(xlim=(0,85),xticks=[0,20,40,60,80],xlabel='批次质量（kg）');grid(ax)
    panel(tx,'机型');panel(ax,'真实货箱编组');panel(nx,'箱数n')
    g.legend(handles=[Rectangle((0,0),1,1,fc=c,ec='white',hatch='..' if j==0 else ('//' if j==2 else ''),label=l) for j,(c,l) in enumerate(zip(KC,KL))],loc='upper center',bbox_to_anchor=(.55,.982),ncol=4,columnspacing=1.3,handlelength=1.1)
    g.text(.141,.885,'条内数字：同服务区、同物资的箱序号；每个分隔单元是一箱。',fontsize=8.5,color=GRAY)
    write(8,g,'Q1正式不可拆货箱编组。80个分隔矩形各对应一个真实货箱，宽度为质量，颜色与纹理为物资；条内数字是同服务区同物资的箱序号，不是数量。机型、每批总质量及总箱数按正式分配标注；箱内类别/编号排序仅用于显示。',
      {'batches':data,'display_kind_order':KIND,'box_count':len(ids),'total_mass_kg':sum(d['total_mass_kg'] for d in data)},['results/q1/Q1_batch_solution.csv','paper/data/analysis.json'],
      '80个不可拆货箱以真实单箱质量直接构成18个正式批次',{'single':'每箱矩形、正式机型、批质量和箱数，服务区双批次括线'},
      {'Q1_batch_solution.货箱编号列表':'exact id join to boxes','boxes.id/kind/mass/service':'individual unit identity, fill and true width','总质量（kg）/机型编号':'batch sum and model identity'},
      ['display boxes sorted by kind then full id','rectangle width=box.mass','left edge=cumulative sum of previous display box masses'],
      {'80_unique_once':len(ids)==len(set(ids))==80 and set(ids)==set(BOXES),'18_batches':len(data)==18,'mass_total758':sum(d['total_mass_kg'] for d in data)==758,'batch_mass_exact':True},
      ['类别聚合条改为80个真实单箱单元','去除重复四列计数表，只保留箱数','医疗/卫生增加稀疏纹理支持灰度'])

def figure09():
    sl={r['trip']:r for r in rows('paper/data/constraint_slacks.csv') if r['question']=='q1'};data=[];counts=[0,0,0]
    for q in Q1:
        typ=A['types'][q['机型编号']];nums=[f(q,k) for k in ['总质量（kg）','总体积（m³）','架次能耗（kWh）']];den=[typ['max_payload'],typ['max_volume'],(1-typ['rho'])*typ['energy_use']];fractions=[v/w for v,w in zip(nums,den)]
        saved=[f(sl[q['架次编号']],k) for k in ['mass_fraction','volume_fraction','energy_fraction']]
        assert all(math.isclose(v,w,rel_tol=1e-12,abs_tol=1e-10) for v,w in zip(fractions,saved))
        assert all(v<=w+tol for v,w,tol in zip(nums,den,[1e-10,1e-12,1e-8]))
        hi=max(fractions);winning=[j for j,v in enumerate(fractions) if math.isclose(v,hi,rel_tol=1e-12,abs_tol=1e-10)]
        for j in winning:counts[j]+=1
        data.append({'trip':q['架次编号'],'type':q['机型编号'],'fractions':fractions,'numerators':nums,'denominators':den,'max_fraction':hi,'highest_indices':winning,'relative_headroom_pp':100*(1-hi),'soc_pct':100*(1-nums[2]/typ['energy_use'])})
    data.sort(key=lambda d:(-d['max_fraction'],d['trip']));vals=np.array([d['fractions'] for d in data])*100
    g=paperfig(12.0);ax=g.add_axes([.148,.205,.470,.635]);bx=g.add_axes([.707,.205,.271,.635]);labs=[d['trip'].removeprefix('Q1-') for d in data]
    cmap=LinearSegmentedColormap.from_list('budget_occupancy',['#F4F6F8','#D1DCE4','#95B5C9','#527D98','#214C66']);im=ax.imshow(vals,cmap=cmap,vmin=0,vmax=100,aspect='auto',interpolation='nearest')
    yrows(ax,labs);yrows(bx,labs,False);ax.set_xticks(range(3),['质量','体积','可用能量']);ax.xaxis.tick_top();ax.tick_params(axis='x',length=0,pad=7)
    ax.set_xticks(np.arange(-.5,3),minor=True);ax.set_yticks(np.arange(-.5,18),minor=True);ax.grid(which='minor',color='white',lw=.7);ax.tick_params(which='minor',length=0)
    cc=['#6F70A8','#B58C49','#5E8D87'];mk=['o','s','D'];cats=['质量','体积','能量']
    for i,d in enumerate(data):
        for j,v in enumerate(vals[i]):
            rgba=cmap(v/100);lum=.2126*rgba[0]+.7152*rgba[1]+.0722*rgba[2]
            ax.text(j,i,f'{v:.1f}%',ha='center',va='center',fontsize=8.5,color='white' if lum<.48 else INK)
        for j in d['highest_indices']:ax.add_patch(Rectangle((j-.47,i-.47),.94,.94,fill=False,ec=INK,lw=.9))
        j=d['highest_indices'][0];v=d['relative_headroom_pp'];bx.hlines(i,0,v,color='#BBC4CB',lw=.7);bx.plot(v,i,marker=mk[j],ms=5,color=cc[j])
        if i<3:bx.annotate(f'{v:.1f} · {cats[j]}',(v,i),xytext=(5,0),textcoords='offset points',fontsize=8.5,va='center')
    cap=math.ceil(max(d['relative_headroom_pp'] for d in data)/10)*10;bx.set(xlim=(0,cap),xticks=np.arange(0,cap+1,10),xlabel='最紧相对余量（百分点）');grid(bx)
    panel(ax,'(a) 三类预算占用');panel(bx,'(b) 最紧相对余量')
    bx.legend(handles=[Line2D([],[],ls='',marker=m,color=c,label=t) for m,c,t in zip(mk,cc,cats)],loc='lower center',bbox_to_anchor=(.45,1.095),ncol=3,columnspacing=.5,handletextpad=.25,fontsize=8)
    cax=g.add_axes([.18,.099,.40,.018]);g.colorbar(im,cax=cax,orientation='horizontal',ticks=[0,25,50,75,100],label='占各自可用预算（%）')
    g.text(.699,.086,'最高项：质量5／体积9／能量4批',fontsize=8)
    write(9,g,'固定Q1批次的三类预算占用及最紧归一化余量，按最大占用降序、同值按架次编号排列。描框为相对最高项；右图为100减去最大占用率，单位为百分点。最高项分别为质量5批、体积9批、能量4批，不等于严格绑定，也不证明整体最优或扰动鲁棒性。',
      {'batches':data,'highest_counts':dict(zip(cats,counts))},['paper/data/constraint_slacks.csv','results/q1/Q1_batch_solution.csv','paper/data/analysis.json','src/core/energy.py','scripts/verify_paper.py'],
      '归一化预算占用中最紧的相对余量可直接比较',{'a':'54个共同尺度预算占用与最高项','b':'每批最大占用对应的剩余百分点'},
      {'constraint_slacks.question=q1/trip/type':'filter and complete trip join','mass_fraction/volume_fraction/energy_fraction':'54 saved ratios independently recalculated','types.max_payload/max_volume/rho/energy_use':'correct separate denominators'},
      ['energy_fraction=E/((1−rho)*energy_use)','max_fraction=max(mass_fraction,volume_fraction,energy_fraction)','relative_headroom_pp=100*(1−max_fraction)','ranking uses full precision, ties retain all within original table verification tolerance'],
      {'54_ratios_match':len(data)==18,'source_feasibility_tolerances_pass':True,'highest_counts5_9_4':counts==[5,9,4],'minSOC23.09':f"{min(d['soc_pct'] for d in data):.2f}"=='23.09'},
      ['右侧重复最高项文字列改为真实相对余量点图','按完整精度最大占用排序','仅前三条标数值与最高项，保留全量54比例'],{'tie_tolerance':'scripts/verify_paper.py table comparison rel_tol=1e-12, abs_tol=1e-10; current rows have unique winners','x_headroom_max_pp':cap})

if __name__=='__main__':
    funcs={i:globals()[f'figure{i:02d}'] for i in range(1,10)}
    for n in ([int(v) for v in sys.argv[1:]] if len(sys.argv)>1 else funcs):
        funcs[n]();print(f'Saved figure {n:02d}',flush=True)
