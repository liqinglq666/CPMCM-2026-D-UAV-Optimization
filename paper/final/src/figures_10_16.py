"""Final, deterministic Q2 figures 10–16 from the frozen team outputs.

No solver is imported or run. Plot views retain every original key/value.
"""
from pathlib import Path
import csv, json, hashlib, math, sys
from collections import Counter, defaultdict
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator, MaxNLocator
import matplotlib.patheffects as pe
import common as common

from paths import ROOT, REPO, OUT, WORK, RAW, FINAL, FONT_DIR, source_path
OUT.mkdir(parents=True, exist_ok=True)
COMMIT = 'bec20f1536458db47bac583c309c7b30637cb67a'
C = {'A':'#0072B2','B':'#E69F00','C':'#009E73'}
TEXT='#222222'; SECONDARY='#5B6570'; AUX='#98A2AD'; THRESH='#B5484E'; GRID='#DDE2E7'
Q2='results/q2/'
TOL=1e-5  # src/core/constraints.py: RESULT_TOLERANCE

def read_csv(rel):
    with (REPO/rel).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))
def read_json(rel): return json.loads((REPO/rel).read_text(encoding='utf-8'))
def numeric(v): return None if v=='' else float(v)
def source(rel):
    p=REPO/rel
    return {'path':rel,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def panel(ax,s): ax.set_title(s,loc='left',fontsize=10,fontweight='bold',pad=8)
def grid(ax,axis='both'):
    ax.grid(axis=axis,color=GRID,linewidth=.4)
    ax.set_axisbelow(True)
def padded(vals,include_zero=False):
    lo,hi=min(vals),max(vals)
    if include_zero: lo=min(lo,0);hi=max(hi,0)
    d=max(hi-lo,1e-9)
    return lo-.08*d,hi+.08*d
def style():
    # The shared module supplies the actual verified CJK font configuration.
    if hasattr(common,'init_style'): common.init_style()
    elif hasattr(common,'setup_style'): common.setup_style()
    plt.rcParams.update({'font.size':8.5,'axes.labelsize':9.5,'axes.titlesize':10,
                         'xtick.labelsize':8.5,'ytick.labelsize':8.5,'legend.fontsize':8.5,
                         'axes.spines.top':False,'axes.spines.right':False,'axes.linewidth':.65,
                         'text.color':TEXT,'axes.labelcolor':TEXT,'xtick.color':TEXT,'ytick.color':TEXT,
                         'svg.fonttype':'none','pdf.fonttype':42,'savefig.facecolor':'white',
                         'hatch.linewidth':.45})
def save(fig,n,caption,purpose,data,sources,mapping,keys,derived,checks,parameters,missing=None):
    assert all(c['passed'] for c in checks), (n, checks)
    name=f'fig_{n:02d}'
    for ext in ('svg','pdf','png'):
        fig.savefig(OUT/f'{name}.{ext}',dpi=600,facecolor='white')
    # Exact A4-width preview, used only for visual review.
    fig.savefig(WORK/f'{name}_preview.png',dpi=180,facecolor='white')
    spec={'number':n,'figure':n,'name':name,'caption':caption,'purpose':purpose,'width_cm':16.3,'height_cm':round(fig.get_figheight()*2.54,4),'dpi':600,
          'font':{'cn':common.FONT_CN,'cn_path':str(common.FONT_PATH),'latin':'DejaVu Sans'},
          'scenario':'Q2 formal frozen result; saved alternatives only when explicitly labelled',
          'repository':'https://github.com/liqinglq666/CPMCM-2026-D-UAV-Optimization',
          'commit':COMMIT,'sources':[source(s) for s in sources],
          'field_mapping':mapping,'join_keys':keys,'derivations':derived,
          'units':parameters.get('units',{}),'time_origin':'正式任务全局时间起点 t=0',
          'precision':'CSV/JSON完整精度用于坐标；图中文字单独按论文显示精度格式化。',
          'parameters':{'width_cm':16.3,'height_cm':round(fig.get_figheight()*2.54,4),'png_dpi':600,
                        'editable_svg_text':True,'pdf_fonttype':42,**parameters},
          'data_checks':checks,'missing_materials':missing or [],
          'verification_scope':'对冻结输出做记录、键、数值和区间一致性核对；未重跑优化或原始DEM物理评价。',
          'visual_review':{'status':'pending','required':['16.3 cm彩色','16.3 cm灰度','无碰撞裁切乱码']}}
    (OUT/f'{name}_data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/f'{name}_spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf-8')
    (OUT/f'{name}_caption.txt').write_text(caption,encoding='utf-8')
    plt.close(fig)
    print(name,'saved')

trips=read_csv(Q2+'Q2_transport_trips_balanced.csv')
resources=read_csv(Q2+'Q2_resource_check.csv')
metrics=read_json(Q2+'Q2_metrics.json')
analysis=read_json('paper/data/analysis.json')
nodes=analysis['nodes']
trip_by_id={r['架次编号']:r for r in trips}
return_s=metrics['makespan']

def check(name,passed,**detail): return {'check':name,'passed':bool(passed),**detail}

def figure10():
    raw=read_csv(Q2+'Q2_pareto_frontier.csv')
    candidates=[{'candidate_id':r['plan_id'],'source_stage':'基础搜索保存档案',
                 'weighted_delay_s':float(r['weighted_tardiness']),'sortie_count':int(r['trips']),
                 'transport_return_s':float(r['makespan']),'energy_kwh':float(r['energy']),
                 'hard_violations':int(r['hard_violations'])} for r in raw]
    formal_matches=[r for r in candidates if r['sortie_count']==metrics['trips']
                    and math.isclose(r['transport_return_s'],return_s,abs_tol=TOL,rel_tol=1e-10)
                    and math.isclose(r['energy_kwh'],metrics['energy'],abs_tol=TOL,rel_tol=1e-10)
                    and r['weighted_delay_s']<=TOL]
    assert len(formal_matches)==1
    formal=formal_matches[0]
    for r in candidates:r['is_formal']=r['candidate_id']==formal['candidate_id']
    ontime=[r for r in candidates if r['weighted_delay_s']<=TOL and r['hard_violations']==0]
    pref=[{'option_id':r['preference'],'relaxation_ratio':float(r['epsilon']),
           'allowed_return_s':float(r['horizon_s']),'actual_return_s':float(r['makespan_s']),
           'energy_kwh':float(r['energy_kwh']),'sortie_count':int(r['trips']),
           'weighted_delay_s':float(r['weighted_tardiness']),'source':r['source']} for r in read_csv(Q2+'Q2_preference_frontier.csv')]
    fig,axs=plt.subplots(3,1,figsize=(16.3/2.54,17.8/2.54),gridspec_kw={'height_ratios':[1,1,1.12]})
    fig.subplots_adjust(left=.13,right=.975,bottom=.075,top=.95,hspace=.62)
    panels=[(candidates,'energy_kwh','weighted_delay_s',1,60),(ontime,'transport_return_s','energy_kwh',60,1)]
    duplicate_keys=[]
    for ax,(records,xkey,ykey,xscale,yscale) in zip(axs,panels):
        xx=[r[xkey]/xscale for r in records];yy=[r[ykey]/yscale for r in records]
        ax.scatter(xx,yy,s=20,color=AUX,alpha=.65,linewidths=0,zorder=3)
        counts=Counter((r[xkey]/xscale,r[ykey]/yscale) for r in records)
        for (x,y),n in counts.items():
            if n>1: ax.annotate(f'×{n}',(x,y),xytext=(6,6),textcoords='offset points',fontsize=8);duplicate_keys.append([x,y,n])
        ax.scatter(formal[xkey]/xscale,formal[ykey]/yscale,marker='*',s=85,color=TEXT,edgecolor='white',linewidth=.6,zorder=5)
        ax.set_xlim(padded(xx));ax.set_ylim(padded(yy,include_zero=ykey=='weighted_delay_s'))
        grid(ax)
    panel(axs[0],'(a) 基础搜索档案 · 42个候选')
    axs[0].set(xlabel='运输能耗 / kWh',ylabel='加权延误 / (系数·min)')
    axs[0].legend(handles=[Line2D([],[],ls='',marker='o',ms=4.5,color=AUX,label='档案候选'),Line2D([],[],ls='',marker='*',ms=9,color=TEXT,label='正式方案')],frameon=False,loc='upper left',ncol=2)
    axs[0].annotate('正式方案', (formal['energy_kwh'],0),xytext=(12,12),textcoords='offset points',fontsize=8)
    panel(axs[1],'(b) 其中全准时候选 · 12个')
    axs[1].set(xlabel='运输返航完工 / min',ylabel='运输能耗 / kWh')
    axs[1].annotate('24架次正式方案',(return_s/60,metrics['energy']),xytext=(9,8),textcoords='offset points',fontsize=8)
    ax=axs[2];panel(ax,'(c) 限时节能选项 · 散点比较')
    offsets=[(10,6),(8,-14),(8,-15),(-8,12)]
    for i,r in enumerate(pref):
        x=r['actual_return_s']/60;y=r['energy_kwh']
        if i==0: ax.scatter(x,y,s=85,marker='*',color=TEXT,edgecolor='white',lw=.6,zorder=5)
        elif i==3:ax.scatter(x,y,s=42,marker='D',color='#6A51A3',zorder=4)
        else:ax.scatter(x,y,s=32,marker='o',facecolor='white',edgecolor='#6A51A3',lw=1.1,zorder=4)
        text=f'{r["relaxation_ratio"]:.0%}上限放宽 · {r["sortie_count"]}架次'
        if i in (0,3):text+=f'\n{r["actual_return_s"]:.3f} s / {r["energy_kwh"]:.3f} kWh'
        ax.annotate(text,(x,y),xytext=offsets[i],textcoords='offset points',fontsize=8,
                    ha='right' if i==3 else 'left',va='bottom' if i in (0,3) else 'top',
                    arrowprops={'arrowstyle':'-','color':SECONDARY,'lw':.5},annotation_clip=False)
    ax.set(xlabel='运输返航完工 / min',ylabel='运输能耗 / kWh',
           xlim=padded([r['actual_return_s']/60 for r in pref]),ylim=(63.19,66.4))
    grid(ax)
    checks=[check('archive_count',len(candidates)==42,count=len(candidates)),check('preference_count',len(pref)==4),
            check('formal_unique_and_matches_metrics',len(formal_matches)==1,id=formal['candidate_id']),
            check('ontime_count',len(ontime)==12),check('all_four_options_ontime',all(r['weighted_delay_s']<=TOL for r in pref)),
            check('all_options_within_full_precision_cap',all(r['actual_return_s']<=r['allowed_return_s']+TOL for r in pref)),
            check('caps_from_full_precision_formal_T',all(math.isclose(r['allowed_return_s'],(1+r['relaxation_ratio'])*return_s,abs_tol=TOL,rel_tol=1e-10) for r in pref))]
    caption='基础搜索档案、其中全准时候选及限时节能选项。正式方案为24架次、65.566 kWh、5903.038 s；20%返航完工上限选项为22架次、63.370 kWh、7070.178 s，逐箱时限保持不变。各点为已保存并核验的有限候选，不构成原问题的完整Pareto前沿。'
    save(fig,10,caption,'区分基础搜索档案、正式选点与既有完工上限偏好。',
         {'candidates':candidates,'ontime_candidate_ids':[r['candidate_id'] for r in ontime],'preferences':pref,'formal_candidate_id':formal['candidate_id'],'overlapping_display_coordinates':duplicate_keys},
         [Q2+'Q2_pareto_frontier.csv',Q2+'Q2_preference_frontier.csv',Q2+'Q2_metrics.json','src/core/constraints.py'],
         {'plan_id':'candidate_id','weighted_tardiness':'weighted_delay_s','trips':'sortie_count','makespan':'transport_return_s','energy':'energy_kwh',
          'preference':'option_id','epsilon':'relaxation_ratio','horizon_s':'allowed_return_s','makespan_s':'actual_return_s'},
         ['candidate_id','option_id','formal objectives matched to Q2_metrics.json'],
         ['display_min=time_s/60','cap_s=(1+epsilon)*formal_makespan_s','ontime: weighted_delay_s<=1e-5 and hard_violations==0'],
         checks,{'units':{'time':'min','energy':'kWh','weighted_delay':'系数·min'},'layout':'3 stacked panels','nonzero_energy_axis':True,'c_panel_ylim':[63.19,66.4],'annotation_y_padding_reason':'为两个端点的完整结果标签预留空间，避免与面板标题碰撞','no_fitted_frontier':True})

def xy(k):
    if hasattr(common,'project'):return common.project(nodes[k]['lon'],nodes[k]['lat'])
    return common.project_lonlat(nodes[k]['lon'],nodes[k]['lat'])

def base_map(ax):
    if hasattr(common,'map_base'): return common.map_base(ax,labels=False,draw_nodes=False)
    if hasattr(common,'mapbase'): return common.mapbase(ax,labels=False)
    raise RuntimeError('Shared common map_base interface missing')

def label_offset(k):
    ms=getattr(common,'MAP_SPEC',getattr(common,'map_spec',{}))
    return tuple(ms.get('label_offsets',{}).get(k, [4,4]))

def figure_routes(n,typ):
    records=[r for r in trips if r['机型编号']==typ]
    routes=defaultdict(list)
    for r in records: routes[tuple(['O01']+r['访问服务区顺序'].split('->')+['O01'])].append(r['架次编号'])
    ordered=sorted(routes)
    fig=plt.figure(figsize=(16.3/2.54,13.5/2.54))
    gs=fig.add_gridspec(1,2,width_ratios=[2.2,1],left=.09,right=.985,bottom=.205,top=.91,wspace=.14)
    ax=fig.add_subplot(gs[0]);index=fig.add_subplot(gs[1]);index.axis('off')
    base_map(ax)
    color=C[typ];ls={'A':'-','B':(0,(4,2)),'C':(0,(5,2,1,2))}[typ]
    marker={'A':'o','B':'s','C':'^'}[typ]
    visited={k for path in ordered for k in path if k!='O01'}
    directed_edges=sorted({(a,b) for path in ordered for a,b in zip(path,path[1:])})
    # One geometrical stroke per edge; independently placed direction heads preserve both directions.
    unordered_edges=sorted({tuple(sorted((a,b))) for a,b in directed_edges})
    for a,b in unordered_edges:
        p0=np.asarray(xy(a));p1=np.asarray(xy(b))
        ax.plot([p0[0],p1[0]],[p0[1],p1[1]],color=color,ls=ls,lw=1.3,zorder=3)
    for a,b in directed_edges:
        p0=np.asarray(xy(a));p1=np.asarray(xy(b));d=p1-p0
        # canonical a<b forward at38%; reverse at62% of canonical segment.
        t=.38 if a<b else .38
        end=p0+t*d;start=p0+(t-.045)*d
        ax.annotate('',xy=end,xytext=start,arrowprops={'arrowstyle':'-|>','color':color,'lw':.7,'mutation_scale':7},zorder=4)
    for k in sorted(nodes):
        p=xy(k)
        if k=='O01':ax.scatter(*p,marker='*',s=65,color=TEXT,zorder=6)
        elif k in visited:ax.scatter(*p,marker=marker,s={'A':20,'B':22,'C':24}[typ],facecolor='white',edgecolor=color,lw=.8,zorder=5)
        else:ax.scatter(*p,marker='o',s=14,facecolor='white',edgecolor=AUX,lw=.65,zorder=5)
        offset=label_offset(k)
        ax.annotate(k,p,xytext=offset,textcoords='offset points',fontsize=8,color=TEXT,zorder=8,
                    path_effects=[pe.withStroke(linewidth=1.2,foreground='white')],
                    bbox={'facecolor':'white','edgecolor':'none','pad':.45},
                    arrowprops={'arrowstyle':'-','color':AUX,'lw':.5} if abs(offset[0])>8 or abs(offset[1])>8 else None)
    fig.text(.09,.955,f'{typ}型｜{len(records)}架次｜{len(set(r["无人机编号"] for r in records))}架实体',fontsize=10,fontweight='bold')
    index.text(0,1.025,'有序路线 / 正式架次后缀',fontsize=8.5,fontweight='bold',va='bottom')
    y=1.0
    index_rows=[]
    for i,path in enumerate(ordered):
        route_text='→'.join(path)
        # A full route remains explicit; line break is only typesetting.
        if len(path)==4:shown='→'.join(path[:2])+'→\n'+'→'.join(path[2:])
        else:shown=route_text
        suffixes=[s.split('-')[-1] for s in routes[path]]
        ids=' / '.join(suffixes)
        if len(ids)>20: ids=' / '.join(suffixes[:2])+'\n'+' / '.join(suffixes[2:])
        text=f'T{i+1}  {shown}\n{ids}  ×{len(suffixes)}'
        index.text(0,y,text,fontsize=8,va='top',linespacing=1.25,color=TEXT)
        y-= .105 + (.029 if len(path)==4 else 0) + (.029 if len(suffixes)>3 else 0)
        index_rows.append({'route_index':f'T{i+1}','ordered_nodes':list(path),'sortie_ids':routes[path],'multiplicity':len(suffixes)})
    legend=[Line2D([],[],color=color,ls=ls,lw=1.3,label=f'{typ}型路线'),Line2D([],[],ls='',marker=marker,mfc='white',mec=color,ms=4.5,label='实际访问区'),Line2D([],[],ls='',marker='o',mfc='white',mec=AUX,ms=4,label='其他服务区'),Line2D([],[],ls='',marker='*',color=TEXT,ms=8,label='调度中心')]
    fig.legend(handles=legend,frameon=False,ncol=4,loc='lower center',bbox_to_anchor=(.52,.008),columnspacing=1.25,handletextpad=.5)
    common.add_terrain_colorbar(fig,ax,rect=[.09,.124,.52,.015])
    expanded=[s for r in index_rows for s in r['sortie_ids']]
    data={'aircraft_type':typ,'formal_trips':records,'route_index':index_rows,'directed_edges':[list(e) for e in directed_edges],
          'nodes':nodes,'projected_nodes_km':{k:list(xy(k)) for k in nodes},'label_offsets_pt':{k:list(label_offset(k)) for k in nodes}}
    checks=[check('sortie_count',len(records)=={'A':12,'B':6,'C':6}[typ]),check('aircraft_count',len(set(r['无人机编号'] for r in records))=={'A':4,'B':2,'C':2}[typ]),
            check('route_index_exactly_covers_sorties',sorted(expanded)==sorted(r['架次编号'] for r in records) and len(set(expanded))==len(records)),
            check('all_routes_start_end_O01',all(p[0]==p[-1]=='O01' for p in ordered)),
            check('node_keys_resolve',all(k in nodes for p in ordered for k in p)),
            check('box_ids_belong_to_delivery_sortie',all(set(r['货箱编号列表'].split(','))=={d['货箱编号'] for d in read_csv(Q2+'Q2_box_delivery_balanced.csv') if d['架次编号']==r['架次编号']} for r in records))]
    caption=f'Q2正式方案中{typ}型无人机执行{len(records)}个运输架次。重复有序路线合并显示，箭头及右侧架次索引共同确定实际访问顺序；线段经过服务区附近不表示在该区交付。三机型地图采用相同投影、空间范围、比例及海拔色阶，底图为官方原始30 m DEM。'
    ms=getattr(common,'MAP_SPEC',getattr(common,'map_spec',{}))
    save(fig,n,caption,'以同尺度路线几何与完整架次索引表达正式空间任务分工。',data,
         [Q2+'Q2_transport_trips_balanced.csv',Q2+'Q2_box_delivery_balanced.csv','paper/data/analysis.json','results/q3/Q3_relay_sorties.csv','paper/data/communication_critical_state.json'],
         {'架次编号':'sortie_id','机型编号':'aircraft_type','无人机编号':'aircraft_id','访问服务区顺序':'ordered_nodes between O01 endpoints','nodes.*.lon/lat':'node coordinates'},
         ['sortie_id','node_id'],['route_key=tuple([O01]+ordered_service_ids+[O01])','map geometry=shared display projection only; physical engine unchanged','deduplicate only identical directed edges; index retains all sorties'],checks,
         {'units':{'map':'km'},'map_spec':ms,'layout':'same 2.2:1 map/index columns for figures 11–13','map_axes_position':list(ax.get_position().bounds),'line_style':str(ls),'color':color,'width_ratio_deviation_reason':'完整有序路线及架次后缀可读，三机型同步调整索引栏宽度','height_deviation_reason':'A型8条唯一路线的完整节点顺序与12架次索引需要行距'},
         [])

def figure14():
    records=[]
    for r in read_csv(Q2+'Q2_box_delivery_balanced.csv'):
        v={'box_id':r['货箱编号'],'sortie_id':r['架次编号'],'service_id':r['服务区编号'],
           'actual_delivery_s':float(r['交付完成时刻（s）']),'expected_s':float(r['期望送达时间（s）']),
           'hard_deadline_s':numeric(r['硬截止时间（s）'])}
        v['has_hard_deadline']=v['hard_deadline_s'] is not None
        v['expected_slack_s']=v['expected_s']-v['actual_delivery_s']
        v['hard_slack_s']=None if not v['has_hard_deadline'] else v['hard_deadline_s']-v['actual_delivery_s']
        records.append(v)
    ranked=sorted(records,key=lambda r:(r['expected_slack_s'],r['box_id']))
    for i,r in enumerate(ranked,1):r['rank']=i
    max_expected_min=math.ceil(max(r['expected_s'] for r in records)/60/30)*30
    last=max(r['actual_delivery_s'] for r in records)
    def event_steps(key,end):
        counts=Counter(r[key] for r in records);x=[0.];y=[0];n=0
        for t,count in sorted(counts.items()):x.append(t/60);n+=count;y.append(n)
        if x[-1]<end:x.append(end);y.append(n)
        return x,y
    fig=plt.figure(figsize=(16.3/2.54,15/2.54))
    gs=fig.add_gridspec(2,1,height_ratios=[1,1.05],left=.12,right=.98,bottom=.09,top=.94,hspace=.47)
    upper=gs[0].subgridspec(1,2,width_ratios=[1,1.35],wspace=.33)
    axes=[fig.add_subplot(upper[0]),fig.add_subplot(upper[1]),fig.add_subplot(gs[1])]
    for ax,limit in zip(axes[:2],[max_expected_min,110]):
        for key,color,ls,label in [('actual_delivery_s',C['A'],'-','实际交付'),('expected_s',THRESH,(0,(4,2)),'期望累计')]:
            xx,yy=event_steps(key,max_expected_min)
            ax.step(xx,yy,where='post',color=color,ls=ls,lw=1.3 if key=='actual_delivery_s' else 1,label=label)
        ax.set(xlim=(0,limit),ylim=(0,84),yticks=[0,20,40,60,80],xlabel='任务时间 / min')
        grid(ax)
    axes[0].set_ylabel('累计交付 / 箱');axes[0].xaxis.set_major_locator(MultipleLocator(60))
    axes[1].xaxis.set_major_locator(MultipleLocator(20))
    panel(axes[0],'(a) 全期望时间范围');panel(axes[1],'(b) 早期交付细节')
    axes[0].legend(frameon=False,loc='lower right',fontsize=8)
    axes[1].axvline(last/60,color=SECONDARY,lw=.8,ls=':')
    axes[1].axvline(return_s/60,color=SECONDARY,lw=.8,ls=':')
    axes[1].annotate('末箱交付',(last/60,80),xytext=(-8,-19),textcoords='offset points',ha='right',fontsize=8,arrowprops={'arrowstyle':'-','lw':.5,'color':SECONDARY})
    axes[1].annotate('最后返航',(return_s/60,35),xytext=(-8,13),textcoords='offset points',ha='right',fontsize=8,arrowprops={'arrowstyle':'-','lw':.5,'color':SECONDARY})
    ax=axes[2];panel(ax,'(c) 逐箱期望时限余量')
    for hard,marker,fc,ec,label in [(False,'o','white',AUX,'其余货箱'),(True,'D',TEXT,TEXT,'具有硬截止的货箱')]:
        rr=[r for r in ranked if r['has_hard_deadline']==hard]
        ax.scatter([r['rank'] for r in rr],[r['expected_slack_s']/60 for r in rr],s=20 if hard else 18,marker=marker,facecolors=fc,edgecolors=ec,lw=.7,label=label,zorder=3)
    ax.axhline(0,color=THRESH,lw=1,ls=(0,(4,2)),zorder=2)
    ax.set(xlim=(.5,80.5),ylim=(0,max(r['expected_slack_s'] for r in ranked)/60*1.08),
           xlabel='按期望时限余量升序排列的货箱序号',ylabel='期望时限余量 / min',xticks=[1,10,20,30,40,50,60,70,80])
    minimum=ranked[0]
    ax.annotate(f'{minimum["box_id"]}\n最小 {minimum["expected_slack_s"]:.3f} s',
                (1,minimum['expected_slack_s']/60),xytext=(8,35),textcoords='offset points',fontsize=8,
                arrowprops={'arrowstyle':'-','color':SECONDARY,'lw':.5})
    ax.legend(frameon=False,loc='upper left',bbox_to_anchor=(.32,.99),ncol=2,fontsize=8)
    grid(ax)
    checks=[check('unique_box_count',len(records)==len({r['box_id'] for r in records})==80),
            check('hard_deadline_count',sum(r['has_hard_deadline'] for r in records)==31),
            check('expected_slacks_nonnegative',all(r['expected_slack_s']>=-TOL for r in records)),
            check('hard_slacks_nonnegative',all(r['hard_slack_s'] is None or r['hard_slack_s']>=-TOL for r in records)),
            check('step_endpoint_80',event_steps('actual_delivery_s',max_expected_min)[1][-1]==80 and event_steps('expected_s',max_expected_min)[1][-1]==80),
            check('last_delivery_matches_preference_record',math.isclose(last,float(read_csv(Q2+'Q2_preference_frontier.csv')[0]['last_delivery_s']),abs_tol=TOL,rel_tol=1e-10)),
            check('trip_join_exact',set(r['sortie_id'] for r in records)==set(trip_by_id))]
    caption=f'Q2逐箱交付进度与期望时限余量。累计曲线按箱级交接完成时刻构造，全部80箱按期；下图按期望时限余量排序，菱形仅标识具有硬截止的货箱。末箱交付为{last:.3f} s，运输最后返航为{return_s:.3f} s，相差{return_s-last:.3f} s；逐箱匹配核验是时限可行性的依据。'
    save(fig,14,caption,'通过事件累计与箱级余量验证按期交付，区分末箱交付与返航。',
         {'boxes':ranked,'actual_events':dict(zip(*event_steps('actual_delivery_s',max_expected_min))),
          'expected_events':dict(zip(*event_steps('expected_s',max_expected_min))),'last_delivery_s':last,'transport_return_s':return_s},
         [Q2+'Q2_box_delivery_balanced.csv',Q2+'Q2_metrics.json',Q2+'Q2_preference_frontier.csv',Q2+'Q2_transport_trips_balanced.csv','src/core/constraints.py'],
         {'货箱编号':'box_id','架次编号':'sortie_id','服务区编号':'service_id','交付完成时刻（s）':'actual_delivery_s',
          '期望送达时间（s）':'expected_s','硬截止时间（s）':'hard_deadline_s; blank remains null'},
         ['box_id one-to-one','sortie_id'],['slack=expected_s-actual_delivery_s','hard_slack=hard_deadline_s-actual_delivery_s, only where non-null',
          'rank=sort(expected_slack_s,box_id)','cumulative=sum(box events at t<=time)','minutes=seconds/60'],checks,
         {'units':{'time_and_slack':'min','count':'箱'},'layout':'two cumulative panels above one ranked slack scatter','local_xlim_min':[0,110],
          'global_xlim_min':[0,max_expected_min],'step_where':'post','no_sloping_interpolation':True})

def resource_view(kind):
    return [{'sortie_id':r['架次编号'],'resource_id':r['资源编号'],'aircraft_type':r['机型'],
             'task_start_s':float(r['任务占用开始（s）']),'return_s':float(r['任务占用结束（s）']),
             'charge_start_s':numeric(r['充电开始（s）']),'full_charge_s':numeric(r['充电结束（s）'])}
            for r in resources if r['资源类型']==kind]

def interval_ok(rows,battery=False):
    for rid in set(r['resource_id'] for r in rows):
        rr=sorted([r for r in rows if r['resource_id']==rid],key=lambda r:r['task_start_s'])
        latest=-math.inf
        for r in rr:
            if r['return_s']<r['task_start_s'] or r['task_start_s']<latest-TOL:return False
            if battery:
                if r['charge_start_s']<r['return_s']-TOL or r['full_charge_s']<r['charge_start_s']:return False
                latest=max(latest,r['full_charge_s'])
            else:latest=max(latest,r['return_s'])
    return True

def fig_gantt(n,battery=False):
    uav=resource_view('无人机');bats=resource_view('电池');rows=bats if battery else uav
    xmax=math.ceil(max(r['full_charge_s'] for r in bats)/60/10)*10
    rid_types={r['resource_id']:r['aircraft_type'] for r in rows}
    ordered=sorted(rid_types,key=lambda k:(rid_types[k],k))
    ys={};y=0;last=None
    for rid in ordered:
        typ=rid_types[rid]
        if last is not None and typ!=last:y+=.35
        ys[rid]=y;y+=1;last=typ
    fig=plt.figure(figsize=(16.3/2.54,(14.6 if battery else 9.5)/2.54))
    ax=fig.add_axes([.14,.09 if battery else .12,.84,.79 if battery else .73])
    for r in rows:
        y=ys[r['resource_id']];typ=r['aircraft_type'];s=r['task_start_s']/60;e=r['return_s']/60
        if battery:
            cs=r['charge_start_s']/60;ce=r['full_charge_s']/60
            ax.barh(y,ce-cs,left=cs,height=.56,color='#EEF1F4',edgecolor=AUX,hatch='///',linewidth=.4,zorder=2)
            # None of the frozen Q2 records has a waiting interval; draw only if explicitly supplied.
            if cs>e+TOL/60:ax.barh(y,cs-e,left=e,height=.56,color='white',edgecolor=AUX,linewidth=.4,zorder=2)
        ax.barh(y,e-s,left=s,height=.56 if battery else .60,color=C[typ],edgecolor='white',linewidth=.45,zorder=3)
        ax.text((s+e)/2,y,r['sortie_id'][-3:],ha='center',va='center',fontsize=8,color='white' if typ=='A' else TEXT,zorder=4)
    ax.set(yticks=[ys[r] for r in ordered],yticklabels=[r.replace('-BAT-','-') if battery else f'{rid_types[r]} · {r}' for r in ordered],
           xlim=(0,xmax),ylim=(max(ys.values())+.7,-.7),xlabel='任务时间 / min')
    ax.xaxis.set_major_locator(MultipleLocator(20));ax.xaxis.set_minor_locator(MultipleLocator(10));grid(ax,'x')
    for rid in ordered:
        ax.plot([-.018,-.013],[ys[rid],ys[rid]],transform=ax.get_yaxis_transform(),color=C[rid_types[rid]],lw=2,clip_on=False)
    ax.axvline(return_s/60,color=THRESH,lw=1,ls=(0,(4,2)),zorder=5)
    handles=[]
    for typ in 'ABC':
        label=typ+'型' if battery else f'{typ}型：{sum(v==typ for v in rid_types.values())}实体 / {sum(r["aircraft_type"]==typ for r in rows)}架次'
        handles.append(Patch(facecolor=C[typ],label=label))
    if battery: handles.append(Patch(facecolor='#EEF1F4',edgecolor=AUX,hatch='///',label='充电'))
    fig.legend(handles=handles,frameon=False,ncol=4 if battery else 3,loc='upper center',bbox_to_anchor=(.56,.99),columnspacing=1.2,handlelength=1.2)
    text=f'运输返航完工 {return_s:.3f} s'
    if battery:text+='；末次充电不计入完工'
    fig.text(.14,.915 if battery else .89,text,fontsize=8.5,color=THRESH,ha='left')
    if battery:
        ax.annotate('后续充电展示',xy=(return_s/60,-.55),xytext=((return_s/60+xmax)/2,-.55),ha='center',va='center',fontsize=8,color=SECONDARY,
                    arrowprops={'arrowstyle':'-','lw':.65,'color':AUX})
    matching=all(next(u for u in uav if u['sortie_id']==r['sortie_id'])['task_start_s']==r['task_start_s'] and next(u for u in uav if u['sortie_id']==r['sortie_id'])['return_s']==r['return_s'] for r in bats)
    checks=[check('exact_24_tasks',len(rows)==len(set(r['sortie_id'] for r in rows))==24),
            check('resource_count',len(ordered)==(14 if battery else 8)),
            check('type_sortie_counts',Counter(r['aircraft_type'] for r in rows)==Counter({'A':12,'B':6,'C':6})),
            check('half_open_intervals_no_overlap',interval_ok(rows,battery)),
            check('uav_battery_task_endpoints_exactly_equal',matching),
            check('all_trips_match_formal_plan',all(r['task_start_s']==float(trip_by_id[r['sortie_id']]['开始时刻（s）']) and r['return_s']==float(trip_by_id[r['sortie_id']]['返回O01时刻（s）']) for r in rows)),
            check('max_return_matches_formal_metric',math.isclose(max(r['return_s'] for r in rows),return_s,abs_tol=TOL,rel_tol=1e-10))]
    if battery:
        caption='Q2同型电池的任务占用与充电安排。实色条对应图15的运输架次，灰色斜纹仅表示正式记录中的充电区间；电池标签省略BAT，同型电池可以跨实体无人机复用。返航后电池须满足完整充电条件才再次使用，最后返航后的充电不计入5903.038 s的运输完工。'
    else:
        caption='Q2的8架实体运输无人机执行24个架次。颜色表示机型，条内数字为正式架次编号后缀；任务占用自正式开始时刻至返航，包含准备、装载、飞行和交接。同一行区间不重叠，竖虚线为运输返航完工5903.038 s。空档本身不说明其形成原因。'
    save(fig,n,caption,'对照实体机体与电池不同释放终点，忠实展示资源复用。',
         {'records':rows,'resource_order':ordered,'row_coordinates':ys,'time_xlim_min':[0,xmax],'transport_return_s':return_s,
          'max_battery_full_charge_s':max(r['full_charge_s'] for r in bats),'task_join_equal':matching},
         [Q2+'Q2_resource_check.csv',Q2+'Q2_transport_trips_balanced.csv',Q2+'Q2_metrics.json','src/core/constraints.py'],
         {'架次编号':'sortie_id','资源编号':'resource_id','机型':'aircraft_type','任务占用开始（s）':'task_start_s',
          '任务占用结束（s）':'return_s','充电开始（s）':'charge_start_s','充电结束（s）':'full_charge_s'},
         ['sortie_id','resource_id'],['minutes=seconds/60','xmax_min=ceil(max(full_charge_s)/600)*10',
          'resource occupancy intervals half-open; overlap tolerance from src/core/constraints.py=1e-5 s',
          'charge intervals read directly; no charging values reconstructed'],checks,
         {'units':{'time':'min'},'axes_left':.14,'axes_right':.98,'physical_axes_width_cm':13.692,'time_xlim_min':[0,xmax],
          'major_tick_min':20,'minor_tick_min':10,'group_gap_rows':.35,'row_height':.56 if battery else .60,
          'waiting_charge_intervals':sum(r['charge_start_s']>r['return_s']+TOL for r in bats),
          'task_text_color':{'A':'white','B':TEXT,'C':TEXT}})

def main():
    style()
    requested={int(x) for x in sys.argv[1:]} if len(sys.argv)>1 else set(range(10,17))
    if 10 in requested:figure10()
    for n,typ in [(11,'A'),(12,'B'),(13,'C')]:
        if n in requested:figure_routes(n,typ)
    if 14 in requested:figure14()
    if 15 in requested:fig_gantt(15,False)
    if 16 in requested:fig_gantt(16,True)

if __name__=='__main__':main()
