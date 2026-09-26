"""Raw-input rebuild of figures 17--27; frozen result records are unchanged.

Every exported chart has a JSON data view and source/derivation specification.
All times are relative to the same official task origin and retain source precision.
"""
from pathlib import Path
import csv, json, math, hashlib, re, sys
from collections import defaultdict, Counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import MultipleLocator, FuncFormatter
import matplotlib.patheffects as pe

from paths import ROOT, REPO, OUT, WORK, RAW, FINAL, FONT_DIR, source_path
OUT.mkdir(parents=True,exist_ok=True)

DEM_SOURCE=next((RAW).rglob('*30米DEM.tif'))
COMMIT='bec20f1536458db47bac583c309c7b30637cb67a'
MODEL={'A':'#0072B2','B':'#E69F00','C':'#009E73'}
RELAY=['#6A51A3','#CC79A7','#8C6D31']
GROUP=['#4477AA','#EEAA33','#AA3377']
TEXT='#222222'; SECOND='#5B6570'; GRID='#DDE2E7'; RED='#B5484E'
TOL=1e-5 # src/core/constraints.py RESULT_TOLERANCE, not a new tolerance

def load(rel):return json.loads((REPO/rel).read_text(encoding='utf-8-sig'))
def rows(rel):return list(csv.DictReader((REPO/rel).open(encoding='utf-8-sig',newline='')))
def f(row,key):return float(row[key])
def check(name,passed,details=None):return {'name':name,'passed':bool(passed),'details':details}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def grid(ax,axis='both'):
    ax.set_axisbelow(True);ax.grid(axis=axis,color=GRID,lw=.4)
def title(ax,text):ax.set_title(text,loc='left',pad=9,fontweight='bold',fontsize=10)
def timeaxis(ax,end):
    ax.set_xlim(0,end);ax.xaxis.set_major_locator(MultipleLocator(20));ax.xaxis.set_minor_locator(MultipleLocator(10));grid(ax,'x')
def canvas(height):return plt.figure(figsize=(16.3/2.54,height/2.54),facecolor='white')
def source_list(files):return [{'path':str((REPO/p).relative_to(ROOT)).replace('\\','/'),'repo_path':p,'sha256':sha(REPO/p)} for p in files]

# The root task supplies shared fonts/projection. Importing never changes inputs.
import common as shared
if hasattr(shared,'setup_style'):shared.setup_style()
elif hasattr(shared,'setup'):shared.setup()

A=load('paper/data/analysis.json')
NODES=A['nodes']; SERVICES=sorted(k for k in NODES if k!='O01')
PLAN=load('results/q3/Q3_selected_plan.json')
TRIPS=sorted(rows('results/q3/Q3_transport_trips.csv'),key=lambda r:r['架次编号'])
TRIPMAP={r['架次编号']:r for r in TRIPS}
RELAYS=sorted(rows('results/q3/Q3_relay_sorties.csv'),key=lambda r:r['中继架次编号'])
RMAP={r['中继架次编号']:r for r in RELAYS}
RPLAN={r['id']:r for r in PLAN['relays']}
COMM=sorted(rows('results/q3/Q3_communication.csv'),key=lambda r:r['运输架次编号'])
CRITICAL=load('paper/data/communication_critical_state.json')
CERT=load('results/continuous_communication.json')
ATOMS=load('results/q4/Q4_enumeration_certificate.json')['atomic_components']
TURN=A['relay_spec']['turnaround_s']
JOINT=A['metrics']['q3']['joint_makespan_s']

def save(fig,num,caption,data,sources,fields,keys,derivations,checks,missing=None,layout=None):
    stem=f'fig_{num:02d}'
    fig.canvas.draw()
    dims=[float(x*2.54) for x in fig.get_size_inches()]
    for ext in ['svg','pdf']:fig.savefig(OUT/f'{stem}.{ext}',facecolor='white')
    fig.savefig(OUT/f'{stem}.png',dpi=600,facecolor='white')
    fig.savefig(WORK/f'{stem}_preview.png',dpi=160,facecolor='white')
    source_records=source_list(sources)
    if num in [17,23,24]:
        terrain_source={'path':source_path(DEM_SOURCE).replace('\\','/'),'scope':'workspace','sha256':sha(DEM_SOURCE),'kind':'original official DEM raster'}
        data={**data,'terrain':{'source':terrain_source,'display_map_spec':shared.MAP_SPEC,'scope':'display only; unchanged frozen task geometry and results'}}
        source_records.append(terrain_source)
        fields={**fields,'original DEM pixels':'shared low-saturation terrain background; no node-elevation interpolation'}
        derivations=[*derivations,'Project original DEM pixel footprint corners to the shared ENU display plane and retain flat piecewise-constant original cell values; no interpolation or resampled data are written. Common color normalization and metre elevation units are retained.']
    previous=json.loads((FINAL/f'baseline/{stem}_data.json').read_text(encoding='utf8'))['data']
    canonical=json.loads(json.dumps(data,ensure_ascii=False)) # normalize tuples to their unchanged JSON array representation
    unchanged=({k:v for k,v in canonical.items() if k!='terrain'}==previous) if isinstance(canonical,dict) else canonical==previous
    checks=[*checks,check('frozen plotted task data unchanged from final figure set',unchanged)]
    if not unchanged:raise ValueError(f'{stem}: frozen plotted records changed')
    view={'figure':num,'scenario_id':'frozen-2026-09-25-final','commit':COMMIT,'time_origin':'official task origin; seconds in source, minutes by /60 when plotted','data':data}
    (OUT/f'{stem}_data.json').write_text(json.dumps(view,ensure_ascii=False,indent=2),encoding='utf8')
    spec={'figure':num,'number':num,'caption':caption,'width_cm':dims[0],'height_cm':dims[1],'dpi':600,'source_commit':COMMIT,'sources':source_records,'source_files':source_records,'font':{'cn':shared.FONT_CN,'cn_path':str(shared.FONT_PATH),'latin':'DejaVu Sans'},'map_spec':shared.MAP_SPEC if num in [17,23,24] else None,
          'field_mapping':fields,'join_keys':keys,'derivations':derivations,
          'precision':'No recovery from rounded manuscript values; original float values retained in data view. Display precision only affects labels.',
          'plot_parameters':{'size_cm':dims,'png_dpi':600,'svg_editable_text':True,'pdf_fonttype':42,'layout':layout or {},
              'model_colors':MODEL,'relay_sortie_colors':RELAY,'group_colors':GROUP,'font_reference':'visual_system.json'},
          'checks':checks,'missing_or_limited_evidence':missing or [],'visual_review':'pending',
          'authoritative_tolerance':{'value':TOL,'unit':'seconds/kWh when applicable','source':'src/core/constraints.py:RESULT_TOLERANCE'},
          'no_optimization_rerun':True}
    (OUT/f'{stem}_spec.json').write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding='utf8')
    (OUT/f'{stem}_caption.txt').write_text(caption,encoding='utf8')
    plt.close(fig)
    print(stem,'saved',flush=True)

def projected(lon,lat):
    return shared.project(lon,lat)
def label_node(ax,sid):
    ax.annotate(sid,shared.xy(sid),xytext=shared.MAP_SPEC['label_offsets'][sid],textcoords='offset points',fontsize=8,zorder=8,path_effects=[pe.withStroke(linewidth=1.3,foreground='white')])
def mapbase(ax,labels=True):
    shared.map_base(ax,labels=False,draw_nodes=False)
    if labels:
        for sid in SERVICES:
            node=NODES[sid];x,y=projected(node['lon'],node['lat'])
            ax.scatter(x,y,s=16,facecolor='white',edgecolor='#88949E',lw=.65,zorder=5)
            label_node(ax,sid)
    base=NODES['O01'];ax.scatter(*projected(base['lon'],base['lat']),s=65,marker='*',color=TEXT,zorder=6)
    label_node(ax,'O01')

def fig17():
    fig=canvas(16.1);gs=fig.add_gridspec(3,1,height_ratios=[3.4,.10,1.55],left=.09,right=.98,bottom=.04,top=.94,hspace=.40)
    ax=fig.add_subplot(gs[0]);mapbase(ax)
    index=[]
    for i,r in enumerate(RELAYS):
        rp=RPLAN[r['中继架次编号']];xy=projected(f(r,'悬停经度'),f(r,'悬停纬度'))
        ax.scatter(*xy,marker=['o','s','D'][i],s=48,color=RELAY[i],edgecolor='white',lw=.7,zorder=6)
        off=[(-8,8),(5,10),(-22,7)][i]
        ax.annotate(f'R{i}',xy,xytext=off,textcoords='offset points',fontsize=8,fontweight='bold',color=RELAY[i],path_effects=[pe.withStroke(linewidth=1.5,foreground='white')],zorder=8)
        jobs=sorted([j for j in PLAN['jobs'] if j['relay']==r['中继架次编号']],key=lambda j:j['id'])
        index.append({'relay_sortie_id':r['中继架次编号'],'point_label':f'R{i}','physical_uav':rp['drone'],'component':rp['component'],'hover_agl_m':rp['agl_m'],'lon':rp['lon'],'lat':rp['lat'],'transport_sorties':[j['id'] for j in jobs],'services':sorted({s for j in jobs for s in j['route']})})
    st=CRITICAL['state'];xy=projected(st['longitude'],st['latitude'])
    ax.scatter(*xy,s=55,marker='*',color=RED,edgecolor='white',lw=.7,zorder=7)
    ax.annotate('column-019；指定 R2\n4684.446 s',xy,xytext=(15,-28),textcoords='offset points',fontsize=8,ha='left',va='top',arrowprops={'arrowstyle':'-','color':RED,'lw':.65},path_effects=[pe.withStroke(linewidth=1.5,foreground='white')],zorder=8)
    title(ax,'(a) 悬停位置与最紧采样状态')
    cax=fig.add_subplot(gs[1]);cax.axis('off');shared.add_terrain_colorbar(fig,ax,rect=list(cax.get_position().bounds))
    tx=fig.add_subplot(gs[2]);tx.axis('off')
    for i,item in enumerate(index):
        col=i/3
        tx.text(col,.97,f"R{i}  ·  {item['physical_uav']}  ·  {item['hover_agl_m']:.0f} m",transform=tx.transAxes,fontsize=9,fontweight='bold',color=RELAY[i],va='top')
        ids=[j[-3:] for j in item['transport_sorties']];ss=item['services']
        wrap=lambda z,n:'\n'.join('、'.join(z[j:j+n]) for j in range(0,len(z),n))
        body='保障架次（column 后缀）\n'+wrap(ids,4)+'\n涉及服务区\n'+wrap(ss,3)
        tx.text(col,.78,body,transform=tx.transAxes,fontsize=8,linespacing=1.45,va='top')
    caption='三处中继悬停位置与正式保障任务归属。R0、R1、R2的离地高度分别为300、225、75 m，由实体R01、R02、R01执行；归属索引不表示航线或覆盖边界。红星为column-019在4684.446 s的真实飞行状态，其水平位置与S009重合，由指定R2保障。底图采用原始30 m DEM，色条表示原始DEM高程。'
    checks=[check('3 relay sorties, 2 physical UAVs',len(index)==3 and len({r['physical_uav'] for r in index})==2),check('R01 R02 R01 identity',[r['physical_uav'] for r in index]==['R01','R02','R01']),check('critical assigned relay and active',CRITICAL['assigned_relay']=='fast-relay-2' and CRITICAL['relay_active']),check('critical margin display',f'{st["available_margin_db"]:.3f}'=='0.091')]
    save(fig,17,caption,{'nodes':NODES,'relay_assignment':index,'critical_state':CRITICAL},['paper/data/analysis.json','results/q3/Q3_relay_sorties.csv','results/q3/Q3_selected_plan.json','paper/data/communication_critical_state.json'],{'nodes.lon/lat':'projected task-node positions','relays.lon/lat/agl_m/drone/component':'relay position and identity','jobs.id/relay/route':'assignment index','state.longitude/latitude/time_s':'critical star and annotation'},['relay_sortie_id=jobs.relay=relays.id','service_id=nodes key'],['projection only for display; no changed coordinates','services = sorted unique route nodes among jobs with same assigned relay'],checks,[],{'map_spec':'shared','text_index_columns':3,'terrain_colorbar':'separate middle row','height_cm':16.1})

def fig18():
    fig=canvas(17.4);gs=fig.add_gridspec(2,1,height_ratios=[1.5,8.2],left=.13,right=.94,bottom=.075,top=.89,hspace=.32)
    top=fig.add_subplot(gs[0]);ax=fig.add_subplot(gs[1],sharex=top)
    for i,r in enumerate(RELAYS):
        lo,hi=f(r,'建链完成时刻_s')/60,f(r,'服务结束时刻_s')/60
        top.plot([lo,hi],[i,i],color=RELAY[i],lw=1.3);top.plot([lo,lo],[i-.16,i+.16],color=RELAY[i],lw=1.1);top.plot([hi,hi],[i-.16,i+.16],color=RELAY[i],lw=1.1)
    top.set(yticks=range(3),yticklabels=['R0','R1','R2'],ylim=(2.6,-.6));top.tick_params(labelbottom=False);title(top,'(a) 指定中继完整服务窗')
    view=[];checks=[]
    for y,c in enumerate(COMM):
        tr=TRIPMAP[c['运输架次编号']];start,end=f(tr,'开始时刻_s'),f(tr,'返回O01时刻_s')
        ax.barh(y,(end-start)/60,left=start/60,height=.18,color=GRID,zorder=2)
        rid=c['中继架次编号'];record={'sortie_id':c['运输架次编号'],'start_s':start,'return_s':end,'coverage_mode':c['保障方式'],'assigned_relay':rid or None}
        if rid:
            i=int(rid[-1]);lo,hi=f(c,'开始时刻_s'),f(c,'结束时刻_s');rr=RMAP[rid];b,e=f(rr,'建链完成时刻_s'),f(rr,'服务结束时刻_s')
            yy=y-.16;ax.plot([lo/60,hi/60],[yy,yy],color=RELAY[i],lw=.7,alpha=.8);ax.plot([lo/60,lo/60],[yy-.12,yy+.12],color=RELAY[i],lw=.85);ax.plot([hi/60,hi/60],[yy-.12,yy+.12],color=RELAY[i],lw=.85)
            ax.text(106,y,f'R{i}',fontsize=8,color=RELAY[i],va='center',clip_on=False)
            record.update(envelope_start_s=lo,envelope_end_s=hi,service_start_s=b,service_end_s=e,left_guard_s=lo-b,right_guard_s=e-hi)
            checks.append(check('service guard '+c['运输架次编号'],lo-b>=5-TOL and e-hi>=5-TOL,{'left_s':lo-b,'right_s':e-hi}))
        else:ax.text(106,y,'采样全直连',fontsize=7.5,color=SECOND,va='center',clip_on=False)
        view.append(record)
    ax.set(yticks=range(24),yticklabels=[r['运输架次编号'][-3:] for r in COMM],ylim=(23.6,-.6),xlabel='自任务起点计时（min）',ylabel='运输架次（column 后缀）')
    for p in [top,ax]:timeaxis(p,105)
    title(ax,'(b) 任务区间与不足采样首末包络')
    handles=[Line2D([],[],color=GRID,lw=4,label='任务区间'),Line2D([],[],color=SECOND,lw=.7,marker='|',markersize=6,label='不足采样首末包络'),Line2D([],[],color=RELAY[0],lw=1.3,marker='|',markersize=7,label='完整服务窗')]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.992),ncol=3,fontsize=8.5,frameon=False,handlelength=2)
    # An annotation column needs its own horizontal space, not smaller fonts.
    for p in [top,ax]:p.set_position([p.get_position().x0,p.get_position().y0,.71,p.get_position().height])
    checks.extend([check('24 unique transport rows',len(view)==24 and len({v['sortie_id'] for v in view})==24),check('all-direct classifications are explicit',all(v['coverage_mode']=='直连' for v in view if v['assigned_relay'] is None))])
    caption='Q3的24个运输架次与指定中继服务窗。灰条为完整任务区间，开括号仅表示设计用1 s与0.5 s联合采样中直连不足点的首末时刻包络，括号内部不表示每一时刻均直连不足。上方为三个完整服务窗，右侧列出正式指派。连续区间可用性另见图21。'
    save(fig,18,caption,{'transport_windows':view,'relay_windows':RELAYS},['results/q3/Q3_transport_trips.csv','results/q3/Q3_communication.csv','results/q3/Q3_relay_sorties.csv','src/q3/preparation.py','src/q3/solver.py','src/core/sampling.py','src/config.py','src/core/constraints.py'],{'运输架次编号':'sortie_id','任务开始/返回O01':'task base bar','communication.开始/结束':'absolute first/last outage sample envelope','保障方式':'explicit sampled-direct classification','建链完成/服务结束':'complete relay service window'},['运输架次编号=架次编号','中继架次编号'],['display_min=source_s/60','envelope exported by solver as start+first,last of PlanPreparer union-grid outage','guard_left=envelope_start-service_start; guard_right=service_end-envelope_end'],checks,['Dense 1 s and 0.5 s state streams unavailable; envelopes retained, internal samples omitted.'],{'row_count':24,'common_xlim_min':[0,105],'right_annotation_column':True})

def relay_records():
    return [{'id':r['中继架次编号'],'drone':r['中继无人机编号'],'component':r['能源组件编号'],'start_s':f(r,'开始时刻_s'),'service_start_s':f(r,'建链完成时刻_s'),'service_end_s':f(r,'服务结束时刻_s'),'return_s':f(r,'返回O01时刻_s'),'turnaround_end_s':f(r,'返回O01时刻_s')+TURN} for r in RELAYS]

def fig19():
    rr=relay_records();fig=canvas(11.8);gs=fig.add_gridspec(2,1,height_ratios=[1.35,1],left=.23,right=.98,bottom=.11,top=.84,hspace=.65)
    top=fig.add_subplot(gs[0]);ax=fig.add_subplot(gs[1],sharex=top);end=math.ceil(max(r['turnaround_end_s'] for r in rr)/600)*10
    for i,r in enumerate(rr):
        s,a,b,e=[r[k]/60 for k in ['start_s','service_start_s','service_end_s','return_s']]
        top.barh(i,a-s,left=s,height=.46,color='#CCD6E0');top.barh(i,b-a,left=a,height=.46,color=RELAY[i]);top.barh(i,e-b,left=b,height=.46,color='#EEF1F4',hatch='//',edgecolor='#98A2AD',lw=.5)
        top.text((a+b)/2,i,f'R{i}',ha='center',va='center',fontsize=8,color='white' if i==0 else TEXT)
        top.vlines([a,b],i-.3,i+.3,lw=.8,color=SECOND)
        y=0 if r['drone']=='R01' else 1
        ax.barh(y,e-s,left=s,height=.42,color=RELAY[i]);ax.barh(y,TURN/60,left=e,height=.42,color='white',edgecolor='#98A2AD',hatch='xx',lw=.6)
        ax.text((s+e)/2,y,f'R{i}',ha='center',va='center',fontsize=8,color='white' if i==0 else TEXT)
    free=rr[0]['turnaround_end_s']/60;nxt=rr[2]['start_s']/60
    ax.vlines([free,nxt],-.62,-.25,color=SECOND,lw=.65);ax.annotate('',xy=(free,-.53),xytext=(nxt,-.53),arrowprops={'arrowstyle':'<->','lw':.65,'color':SECOND});ax.text((free+nxt)/2,-.69,f'已排定空闲 {rr[2]["start_s"]-rr[0]["turnaround_end_s"]:.3f} s',ha='center',va='bottom',fontsize=8)
    top.set(yticks=range(3),yticklabels=[f'R{i} · {r["drone"]}\n组件 {i+1:02}' for i,r in enumerate(rr)],ylim=(2.55,-.55));top.tick_params(labelbottom=False,labelsize=8)
    ax.set(yticks=[0,1],yticklabels=['R01','R02'],ylim=(1.6,-1.03),xlabel='自任务起点计时（min）')
    title(top,'(a) 架次阶段及能源组件');title(ax,'(b) 实体中继机的复用与周转')
    for p in [top,ax]:timeaxis(p,end)
    handles=[Patch(fc='#CCD6E0',label='准备、出航与建链'),Patch(fc=RELAY[0],label='服务窗（按中继编号着色）'),Patch(fc='#EEF1F4',ec='#98A2AD',hatch='//',label='返航'),Patch(fc='white',ec='#98A2AD',hatch='xx',label='返航后 300 s 周转')]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.57,.99),ncol=2,frameon=False,fontsize=8.5)
    checks=[check('R01 reuse timing',rr[2]['start_s']>=rr[0]['turnaround_end_s']-TOL),check('joint return excludes turnaround',max(r['return_s'] for r in rr)==JOINT),check('nonnegative stages',all(r['start_s']<=r['service_start_s']<=r['service_end_s']<=r['return_s'] for r in rr))]
    save(fig,19,'三个中继架次的阶段时序与两架实体中继机的复用关系。服务窗按中继编号着色；准备、出航与建链采用已知合并阶段，返航与返航后300 s周转分别标识。R01依次执行中继0和中继2，R02执行中继1；可用间隔为正式时序中的空闲，不作成因推断。',rr,['results/q3/Q3_relay_sorties.csv','paper/data/analysis.json','src/core/constraints.py'],{'开始/建链完成/服务结束/返回O01':'four exact stage boundaries','中继无人机编号/能源组件编号':'physical identities','relay_spec.turnaround_s':'300 s turnaround'},['中继架次编号'],['turnaround_end=return+300 s','idle=start(relay2)-return(relay0)-300 s','all plotted positions=seconds/60'],checks,[],{'x_end_min':end,'turnaround_shown_after_joint_return':True})

def fig20():
    raw=rows('results/q3/Q3_resource_check.csv');rr=relay_records();fig=canvas(20.5)
    gs=fig.add_gridspec(4,1,height_ratios=[8,14,3.3,3.6],left=.145,right=.98,bottom=.065,top=.87,hspace=.50)
    axes=[];maxend=max([f(r,'充电结束（s）') for r in raw if r['充电结束（s）']]+[r['turnaround_end_s'] for r in rr]);end=math.ceil(maxend/600)*10
    for n in range(4):axes.append(fig.add_subplot(gs[n],sharex=axes[0] if n else None))
    checks=[];view=[]
    for ax,typ in zip(axes[:2],['无人机','电池']):
        rs=[r for r in raw if r['资源类型']==typ];ids=sorted({r['资源编号'] for r in rs})
        for r in rs:
            y=ids.index(r['资源编号']);s,e=f(r,'任务占用开始（s）'),f(r,'任务占用结束（s）');col=MODEL[r['机型']]
            ax.barh(y,(e-s)/60,left=s/60,height=.62,color=col,zorder=3)
            ax.text((s+e)/120,y,r['架次编号'][-3:],ha='center',va='center',color=TEXT if r['机型']=='B' else 'white',fontsize=8,zorder=5)
            ce=None
            if typ=='电池':
                cs,ce=f(r,'充电开始（s）'),f(r,'充电结束（s）');ax.barh(y,(ce-cs)/60,left=cs/60,height=.62,fc='#EEF1F4',ec='#98A2AD',hatch='//',lw=.4,zorder=2)
            view.append({'layer':typ,'resource':r['资源编号'],'sortie':r['架次编号'],'type':r['机型'],'start_s':s,'return_s':e,'charge_end_s':ce})
        ax.set(yticks=range(len(ids)),yticklabels=[i.replace('-BAT-','-') for i in ids],ylim=(len(ids)-.4,-.6))
        for id_ in ids:
            seq=sorted([v for v in view if v['layer']==typ and v['resource']==id_],key=lambda v:v['start_s'])
            checks.append(check(typ+' no overlap '+id_,all(x['start_s']>=(p['charge_end_s'] if typ=='电池' else p['return_s'])-TOL for p,x in zip(seq,seq[1:]))))
    for i,r in enumerate(rr):
        y=0 if r['drone']=='R01' else 1;s,e,t=r['start_s']/60,r['return_s']/60,r['turnaround_end_s']/60
        axes[2].barh(y,e-s,left=s,height=.62,color=RELAY[i]);axes[2].barh(y,t-e,left=e,height=.62,fc='white',ec='#98A2AD',hatch='xx',lw=.5)
        axes[2].text((s+e)/2,y,f'R{i}',ha='center',va='center',fontsize=8,color='white' if i==0 else TEXT)
        axes[3].barh(i,e-s,left=s,height=.62,color=RELAY[i]);axes[3].plot(e,i,marker='s',ms=4,mfc='white',mec=RELAY[i],zorder=5);axes[3].text((s+e)/2,i,f'R{i}',ha='center',va='center',fontsize=8,color='white' if i==0 else TEXT)
    axes[2].set(yticks=[0,1],yticklabels=['R01','R02'],ylim=(1.6,-.6));axes[3].set(yticks=[0,1,2],yticklabels=['R-BAT-01','R-BAT-02','R-BAT-03'],ylim=(2.6,-.6),xlabel='自任务起点计时（min）')
    titles=['(a) 运输无人机：任务占用至返航','(b) 运输电池：任务及充电占用','(c) 中继无人机：任务及返航后周转','(d) 中继能源组件任务分配（非完整充电占用）']
    for ax,t in zip(axes,titles):
        timeaxis(ax,end);title(ax,t);ax.axvline(JOINT/60,color=RED,lw=1,ls=(0,(4,2)),zorder=1)
    for ax in axes[:-1]:ax.tick_params(labelbottom=False)
    axes[0].annotate(f'联合返航 {JOINT:.3f} s',xy=(JOINT/60,0),xycoords=('data','axes fraction'),xytext=(-3,-14),textcoords='offset points',fontsize=8,color=RED,ha='right',va='top')
    handles=[Patch(fc=MODEL[t],label=t+'型')for t in 'ABC']+[Patch(fc=RELAY[i],label=f'中继{i}')for i in range(3)]+[Patch(fc='#EEF1F4',ec='#98A2AD',hatch='//',label='充电'),Patch(fc='white',ec='#98A2AD',hatch='xx',label='周转'),Line2D([],[],marker='s',mfc='white',mec=SECOND,ls='',label='组件返航端点')]
    fig.legend(handles=handles[:6],loc='upper center',bbox_to_anchor=(.56,.995),ncol=6,frameon=False,fontsize=8.5,columnspacing=.9,handlelength=1.2)
    fig.legend(handles=handles[6:],loc='upper center',bbox_to_anchor=(.56,.962),ncol=3,frameon=False,fontsize=8.5,columnspacing=1.2,handlelength=1.2)
    checks += [check('24 tasks on both transport layers',all(Counter(v['sortie'] for v in view if v['layer']==t)==Counter(TRIPMAP.keys()) for t in ['无人机','电池'])),check('8 UAV 14 battery entities',[len({v['resource'] for v in view if v['layer']==t}) for t in ['无人机','电池']]==[8,14]),check('3 relays on 2 UAVs and 3 components',len(rr)==3 and len({r['drone']for r in rr})==2 and len({r['component']for r in rr})==3)]
    save(fig,20,'Q3冻结方案的四类资源时序。运输机任务占用至返航，运输电池占用延续至充电完成；中继机返航后另含300 s周转。组件层显示每块组件的一次任务分配至返航，空心方块不代表充电完成。竖虚线为联合返航完工5931.735 s，之后的充电或周转仍如实显示。',{'transport_resource_intervals':view,'relay_intervals':rr},['results/q3/Q3_resource_check.csv','results/q3/Q3_transport_trips.csv','results/q3/Q3_relay_sorties.csv','paper/data/analysis.json','src/core/constraints.py'],{'资源类型/资源编号/架次编号':'layer/resource/task labels','任务占用开始/结束':'transport interval','充电开始/结束':'exact charge interval','relay return+turnaround':'relay UAV interval','relay start/return':'component task assignment only'},['scenario + 架次编号 + 资源编号','relay 中继架次编号'],['seconds/60','display end rounded upward to next 10 min; interval coordinates unchanged'],checks,['Relay component full-charge end is unavailable; task assignment endpoints are not asserted as release.'],{'x_end_min':end,'layers':[8,14,2,3]})

def fig21():
    fig=canvas(18.0);gs=fig.add_gridspec(2,2,height_ratios=[1,2.3],width_ratios=[1.1,1],left=.16,right=.97,bottom=.07,top=.91,hspace=.47,wspace=.47)
    left=fig.add_subplot(gs[0,0]);right=fig.add_subplot(gs[0,1]);bottom=fig.add_subplot(gs[1,:])
    vals=[CRITICAL[k]for k in ['direct_margin_db','access_margin_db','backhaul_margin_db']];cols=[RED,RELAY[0],RELAY[2]];markers=['x','o','D'];labs=['直连','接入','回传']
    for i,v in enumerate(vals):
        left.plot([0,v],[i,i],color=cols[i],lw=1.3);left.plot(v,i,marker=markers[i],color=cols[i],ms=4.8)
        left.annotate(f'{v:.6f}',(v,i),xytext=(3,-12),textcoords='offset points',fontsize=8,ha='left' if v<0 else 'right')
    left.axvline(0,color=TEXT,lw=.9);left.set(yticks=range(3),yticklabels=labs,xlim=(-3.6,1.1),ylim=(2.65,-.65),xlabel='链路余量（dB）');left.xaxis.set_major_locator(MultipleLocator(1));grid(left,'x');title(left,'(a) 最紧采样状态')
    for i,v in enumerate(vals[1:]):
        right.plot([0,v],[i,i],color=cols[i+1],lw=1.3);right.plot(v,i,marker=markers[i+1],color=cols[i+1],ms=4.8);right.annotate(f'{v:.6f}',(v,i),xytext=(0,-14),textcoords='offset points',fontsize=8,ha='center')
    right.plot(vals[1],0,marker='o',mfc='none',mec=RELAY[0],ms=8,lw=.7);right.set(yticks=[0,1],yticklabels=labs[1:],xlim=(0,.8),ylim=(1.65,-.65),xlabel='链路余量（dB）');right.xaxis.set_major_locator(MultipleLocator(.2));grid(right,'x');title(right,'(b) 同一状态正余量放大')
    vv=[{'sortie_id':k,'lower_bound_db':v['minimum_margin_bound_db'],'status':v['status'],'certified_intervals':v['certified_intervals'],'unresolved_intervals':v['unresolved_intervals']}for k,v in sorted(CERT['trips'].items())]
    assert all(r['lower_bound_db']>0 and not r['unresolved_intervals'] for r in vv)
    vals2=[r['lower_bound_db']for r in vv];minrow=int(np.argmin(vals2));bottom.scatter(vals2,range(24),s=16,color='#6F70A8');bottom.scatter([vals2[minrow]],[minrow],s=25,color=RED,zorder=4)
    bottom.set(xscale='log',yticks=range(24),yticklabels=[r['sortie_id'][-3:]for r in vv],ylim=(23.6,-.6),xlabel='连续区间余量下界（dB，对数刻度）',ylabel='运输架次（column 后缀）',xlim=(.006,10))
    bottom.xaxis.set_major_formatter(FuncFormatter(lambda x,pos:f'{x:g}'));grid(bottom,'x');title(bottom,'(c) 固定轨迹逐架次的保守数值下界')
    bottom.annotate(f'全局保守下界 {min(vals2):.6f} dB',(min(vals2),minrow),xytext=(.18,18.5),textcoords='data',fontsize=8,color=RED,arrowprops={'arrowstyle':'-','lw':.65,'color':RED},ha='left')
    fig.text(.16,.968,f'column-019 · {CRITICAL["state"]["time_s"]:.3f} s · fast-relay-2，服务窗内',fontsize=8.5,color=SECOND)
    fig.text(.16,.61,'中继可用余量取接入与回传的较小值',fontsize=8,color=SECOND)
    checks=[check('all 24 lower bounds positive and resolved',len(vv)==24 and all(v['lower_bound_db']>0 and not v['unresolved_intervals'] for v in vv)),check('global lower bound equals min trip bound',min(vals2)==CERT['minimum_margin_bound_db']),check('sample relay bottleneck',min(vals[1:])==CRITICAL['state']['available_margin_db']),check('critical state relay active',CRITICAL['relay_active']),check('certificate counts',CERT['summary']=={'phases':192,'geometric_intervals':352,'certified_intervals':360,'boundary_checks':544})]
    save(fig,21,'最紧采样状态的直连、指定中继接入和回传链路余量，以及逐架次保守连续区间下界。正余量放大使用同一状态记录。0.090906 dB为该采样状态的中继瓶颈余量，0.009866 dB为连续区间数值核验的全局下界，两者含义不同。证书覆盖192相位、360通过区间与544事件检查，并采用声明的浮点保护条件。',{'critical_state':CRITICAL,'per_trip_certificate_bounds':vv,'certificate_summary':CERT['summary']},['paper/data/communication_critical_state.json','results/continuous_communication.json'],{'direct/access/backhaul_margin_db':'top endpoints','trips.<id>.minimum_margin_bound_db':'per-trip recorded conservative lower bound','trips.<id>.unresolved_intervals':'log-axis admissibility'},['scenario + trip id; critical event retained at full precision'],['available margin=min(access,backhaul)','global displayed lower=min(recorded per-trip lower)','No sampled lower bounds substituted for certificates'],checks,['Per-trip recorded certificate aggregates are used directly; no absent interval numeric values reconstructed.'],{'log_axis':True,'minimum_value_point':vv[minrow]['sortie_id']})

def fig22():
    fig=canvas(9.6);gs=fig.add_gridspec(1,2,width_ratios=[5,1],left=.08,right=.97,bottom=.22,top=.85,wspace=.12);ax=fig.add_subplot(gs[0,0]);side=fig.add_subplot(gs[0,1],sharey=ax)
    columns=[s for a in ATOMS for s in a];matrix=[[int(s in atom)for s in columns]for atom in ATOMS]
    for i,row in enumerate(matrix):
        for j,member in enumerate(row):ax.scatter(j,i,s=36 if member else 6,marker='s'if member else'o',color='#6F70A8'if member else'#F0F2F5',zorder=3)
    start=0
    for i,atom in enumerate(ATOMS):
        end=start+len(atom)-1;ax.plot([start-.35,start-.35,end+.35,end+.35],[-.70,-.93,-.93,-.70],color=SECOND,lw=.65,clip_on=False);ax.text((start+end)/2,-1.15,f'C{i+1}',ha='center',fontsize=8,color=SECOND,clip_on=False);start=end+1
    ax.set(xticks=range(15),xticklabels=columns,yticks=range(9),yticklabels=[f'C{i+1}'for i in range(9)],xlim=(-.6,14.6),ylim=(8.6,-.6),xlabel='服务区');ax.tick_params(axis='x',rotation=45,labelsize=8)
    for lab in ax.get_xticklabels():lab.set_ha('right')
    counts=[len(a)for a in ATOMS];side.barh(range(9),counts,height=.52,color='#6F70A8');side.set(xlim=(0,4.8),xticks=[0,2,4],xlabel='分量规模\n（个服务区）');side.tick_params(left=False,labelleft=False);grid(side,'x')
    for i,v in enumerate(counts):side.text(v+.13,i,str(v),va='center',fontsize=8)
    fig.legend(handles=[Line2D([],[],marker='s',ms=5,ls='',color='#6F70A8',label='属于该分量')],loc='upper right',bbox_to_anchor=(.99,.995),frameon=False)
    # Check connectivity against frozen co-visit routes, excluding the shared base.
    parent={s:s for s in SERVICES}
    def find(s):
        while parent[s]!=s:s=parent[s]
        return s
    for j in PLAN['jobs']:
        for l,r in zip(j['route'],j['route'][1:]):parent[find(l)]=find(r)
    groups=defaultdict(set)
    for s in SERVICES:groups[find(s)].add(s)
    checks=[check('one component for each 15 services',len(columns)==15 and len(set(columns))==15),check('9 prescribed component sizes',counts==[4,3,2,1,1,1,1,1,1]),check('frozen route co-visits reproduce components',{frozenset(x)for x in groups.values()}=={frozenset(x)for x in ATOMS}),check('no base in components','O01'not in columns)]
    save(fig,22,'冻结Q3运输任务诱导的不可拆服务区分量。实心方块表示成员归属，右侧给出分量规模。15个服务区分别属于9个分量，独立任务组须由完整分量合并构成；矩阵不表示地理距离或飞行路径。',{'atomic_components':ATOMS,'display_columns':columns,'membership_matrix':matrix,'frozen_routes':[{k:j[k]for k in ['id','route']}for j in PLAN['jobs']]},['results/q4/Q4_enumeration_certificate.json','results/q3/Q3_selected_plan.json'],{'atomic_components':'matrix membership','jobs.route':'independent deterministic co-visit connectivity check'},['service_id'],['member[i,j]=1 if displayed service j belongs to atom i','size[i]=sum(member row i)','connectivity check excludes O01'],checks,[],{'axis_order':'frozen component member order','matrix_size':[9,15]})

def partition_data(k):
    raw=rows('results/q4/Q4_partition_config.csv');balanced=rows('results/q4/Q4_balanced_groups.csv');out=[]
    for policy,table in [('资源优先',raw),('均衡偏好',balanced)]:
        groups=[]
        for r in table:
            if int(r['K'])!=k:continue
            groups.append({'group':r.get('任务组编号',r.get('group')),'services':re.findall(r'S\d{3}',r.get('服务区列表',r.get('services',''))),'boxes':int(r.get('货箱数',r.get('boxes'))),'transport_trips':int(r.get('运输架次',r.get('transport_trips')))})
        resource_file='results/q4/Q4_gap_decomposition.csv' if policy=='资源优先' else 'results/q4/Q4_balanced_resources.csv'
        resource_gap=sum(int(r['deficit' if policy=='资源优先' else 'shortage']) for r in rows(resource_file) if int(r['K'])==k)
        out.append({'K':k,'policy':policy,'groups':groups,'resource_gap_total':resource_gap})
    return out

def fig_partition(k):
    fig=canvas(19.8);gs=fig.add_gridspec(2,2,width_ratios=[4,1.2],height_ratios=[1,1],left=.07,right=.985,bottom=.15,top=.92,hspace=.30,wspace=.08)
    data=partition_data(k);checks=[];background_edges=set()
    for j in PLAN['jobs']:
        route=['O01',*j['route'],'O01']
        for s,t in zip(route,route[1:]):background_edges.add(tuple(sorted((s,t))))
    for n,p in enumerate(data):
        ax=fig.add_subplot(gs[n,0]);tx=fig.add_subplot(gs[n,1]);tx.axis('off');mapbase(ax,False)
        for s,t in sorted(background_edges):
            p1=projected(NODES[s]['lon'],NODES[s]['lat']);p2=projected(NODES[t]['lon'],NODES[t]['lat']);ax.plot([p1[0],p2[0]],[p1[1],p2[1]],color='#697582',lw=.55,alpha=.28,zorder=3)
        for i,g in enumerate(p['groups']):
            for sid in g['services']:
                node=NODES[sid];ax.scatter(*projected(node['lon'],node['lat']),s=48 if i==2 else 38,marker=['o','s','^'][i],color=GROUP[i],edgecolor='white',lw=.65,zorder=5);label_node(ax,sid)
            tx.text(0,.95-i*.235,f"{g['group']}  {len(g['services'])}区\n{g['boxes']}箱\n{g['transport_trips']}运输架次",transform=tx.transAxes,fontsize=8.5,va='top',linespacing=1.5,color=TEXT)
        gap=p['resource_gap_total']
        tx.text(0,.06,f'分类资源\n缺口合计 {gap}',transform=tx.transAxes,fontsize=8.5,color=RED,va='bottom',linespacing=1.5)
        title(ax,f"({'ab'[n]}) {p['policy']}")
        members=[s for g in p['groups']for s in g['services']];sets=[set(g['services'])for g in p['groups']]
        checks.extend([check(p['policy']+' unique 15 service assignment',sorted(members)==SERVICES),check(p['policy']+' 80 boxes / 24 transport tasks',sum(g['boxes']for g in p['groups'])==80 and sum(g['transport_trips']for g in p['groups'])==24),check(p['policy']+' components intact',all(any(set(atom)<=s for s in sets)for atom in ATOMS)),check(p['policy']+' gap anchor',gap=={(2,0):1,(2,1):5,(3,0):3,(3,1):9}[(k,n)])])
    fig.legend(handles=[Line2D([],[],ls='',marker=['o','s','^'][i],color=GROUP[i],ms=5,label=f'G{i+1}')for i in range(k)],loc='upper center',bbox_to_anchor=(.45,.987),ncol=k,frameon=False)
    shared.add_terrain_colorbar(fig,ax,rect=[.12,.065,.55,.013])
    nums='13/2与7/8'if k==2 else'13/1/1与5/4/6';gaps='1和5'if k==2 else'3和9'
    caption=f'固定Q3任务在{k}组独立执行条件下的服务区归属。资源优先与均衡偏好的组规模分别为{nums}区，分类资源缺口分别为{gaps}。两图采用相同原始DEM、投影、范围与固定运输路线，颜色仅表示离散归属，未定义连续地域边界；完整中继按组复制。色条为原始DEM高程，两个面板采用共同色阶。'
    save(fig,21+k,caption,{'partitions':data,'frozen_unique_undirected_transport_edges':sorted(background_edges),'nodes':NODES},['results/q4/Q4_partition_config.csv','results/q4/Q4_balanced_groups.csv','results/q4/Q4_gap_decomposition.csv','results/q4/Q4_balanced_resources.csv','results/q4/Q4_enumeration_certificate.json','results/q3/Q3_selected_plan.json','paper/data/analysis.json'],{'服务区列表/services':'node group identity','货箱数/boxes':'group box count','运输架次/transport_trips':'frozen group task counts','jobs.route':'identical unoptimized background route edges','deficit/shortage':'sum per-resource positive gaps'},['K + policy + group','service_id = nodes key'],['merge repeated unordered route edges for quiet background; original ordered routes retained in source','group size=count(service member list)','gap_total=sum(deficit or shortage) for the same K and policy'],checks,[],{'shared_map_spec':True,'equal_map_axes':True,'fixed_route_gray_alpha':.28,'terrain_colorbar':'shared below two maps'})

def fig25():
    gap=rows('results/q4/Q4_gap_decomposition.csv');bal=rows('results/q4/Q4_balanced_resources.csv');keys=['A_uav','B_uav','C_uav','A_bat','B_bat','C_bat','relay_uav','relay_comp'];labels=['A运输机','B运输机','C运输机','A电池','B电池','C电池','中继机','中继能源组件']
    fig=canvas(12.5);axes=[fig.add_axes([.19,.27,.35,.57]),fig.add_axes([.61,.27,.35,.57])];view=[];checks=[]
    for ax,k in zip(axes,[2,3]):
        sub={r['resource']:r for r in gap if int(r['K'])==k};bs={r['resource']:r for r in bal if int(r['K'])==k};sums=[0,0]
        for i,key in enumerate(keys):
            r,b=sub[key],bs[key];stock,peak,rp,bp=[int(v)for v in [r['inventory'],r['pooled_peak'],r['independent_total'],b['required']]]
            d=[max(0,rp-stock),max(0,bp-stock)];sums=[x+y for x,y in zip(sums,d)]
            ax.vlines(stock,i-.37,i+.37,color=TEXT,lw=1.1,zorder=2)
            ax.plot(peak,i-.23,marker='o',mfc='white',mec='#88949E',ms=4,ls='',zorder=4);ax.plot(rp,i,marker='s',color='#4477AA',ms=4.5,ls='',zorder=4);ax.plot(bp,i+.23,marker='^',color='#AA3377',ms=5,ls='',zorder=4)
            for qty,dy,col in [(rp,0,'#4477AA'),(bp,.23,'#AA3377')]:
                if qty>stock:ax.plot([stock,qty],[i+dy,i+dy],color=col,lw=1);ax.text(qty+.18,i+dy,f'+{qty-stock}',va='center',fontsize=8,color=RED)
            view.append({'K':k,'resource':key,'stock':stock,'shared_peak':peak,'resource_priority_demand':rp,'balanced_demand':bp,'resource_priority_gap':d[0],'balanced_gap':d[1]})
            checks.append(check(f'K{k} {key} gaps',d==[int(r['deficit']),int(b['shortage'])]))
        ax.set(yticks=range(8),yticklabels=labels if k==2 else['']*8,ylim=(7.65,-.65),xlim=(0,10.5),xlabel='资源数量（份）');ax.xaxis.set_major_locator(MultipleLocator(2));ax.xaxis.set_minor_locator(MultipleLocator(1));grid(ax,'x');title(ax,f'({"ab"[k-2]}) {k}组独立配置')
        fig.text(ax.get_position().x0,.115,f'资源优先总缺口 {sums[0]}\n均衡偏好总缺口 {sums[1]}',fontsize=8.5,linespacing=1.45,va='top')
        checks.append(check(f'K{k} total gaps',sums==([1,5]if k==2 else[3,9])))
    handles=[Line2D([],[],marker='|',ms=9,color=TEXT,ls='',label='现有库存'),Line2D([],[],marker='o',mfc='white',mec='#88949E',ls='',label='共享峰值'),Line2D([],[],marker='s',color='#4477AA',ls='',label='资源优先需求'),Line2D([],[],marker='^',color='#AA3377',ls='',label='均衡偏好需求')]
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.58,.995),ncol=2,frameon=False,fontsize=8.5)
    fig.text(.19,.025,'中继组件：共享3／库存6／资源优先需求4，缺口为0。',fontsize=8,color=SECOND)
    save(fig,25,'冻结Q3共享峰值、现有库存与不同分区偏好的独立资源需求。标记仅在类别方向错位，横坐标始终为真实数量。红色数值为逐类正缺口；库存冗余不能跨类别抵消，资源数量指标不表示经济成本。',view,['results/q4/Q4_gap_decomposition.csv','results/q4/Q4_balanced_resources.csv'],{'pooled_peak':'shared peak','inventory':'stock','independent_total':'resource priority demand','required':'balanced demand','deficit/shortage':'independently checked class gap'},['K + resource','policy determined by source table'],['gap=max(0, demand-stock) by resource','total_gap=sum(class gaps)'],checks,[],{'offset_y':[-.23,0,.23],'xlim_both':[0,10.5]})

def fig26():
    raw=rows('paper/data/payload_reserve.csv');st=rows('paper/data/reserve_staircase.csv');sen=rows('results/q1/Q1_sensitivity_summary.csv')
    fig=canvas(16.5);gs=fig.add_gridspec(2,3,height_ratios=[1,1.45],left=.09,right=.97,bottom=.09,top=.92,wspace=.16,hspace=.48)
    highlights={};view=[]
    for n,typ in enumerate('ABC'):
        ax=fig.add_subplot(gs[0,n]);base={r['service']:f(r,'payload_kg')for r in raw if r['type']==typ and f(r,'reserve')==.2};lowest=min(base.values());hs=[s for s,v in base.items()if v==lowest];highlights[typ]=hs
        for sid in SERVICES:
            rr=sorted([r for r in raw if r['type']==typ and r['service']==sid],key=lambda r:f(r,'reserve'));x=[f(r,'reserve')*100 for r in rr];y=[f(r,'payload_kg')/f(r,'rated_payload_kg')*100 if r['reachable']=='True' else np.nan for r in rr]
            ax.plot(x,y,color=MODEL[typ],lw=1.4 if sid in hs else .65,alpha=1 if sid in hs else .30,marker='o',ms=2.5,markevery=10)
            view.extend({'type':typ,'service':sid,'reserve_fraction':f(r,'reserve'),'safe_payload_kg':f(r,'payload_kg') if r['payload_kg'] else None,'rated_payload_kg':f(r,'rated_payload_kg'),'reachable':r['reachable']=='True','safe_ratio_pct':None if np.isnan(v)else v}for r,v in zip(rr,y))
        ax.axvline(20,color='#98A2AD',lw=.8);ax.set(xlim=(10,40),ylim=(0,105),xticks=[10,20,30,40],xlabel='返航储备（%）');ax.set_yticks([0,25,50,75,100]);grid(ax);title(ax,f'({"abc"[n]}) {typ}型')
        if n==0:ax.set_ylabel('安全载荷／额定载荷（%）')
        else:ax.tick_params(labelleft=False)
        txt=hs[0] if len(hs)==1 else f'{len(hs)}区并列'
        ax.text(.04,.06,f'20%基准最低：\n{txt}',transform=ax.transAxes,fontsize=8,color=MODEL[typ],va='bottom')
    ax=fig.add_subplot(gs[1,:]);intervals=[]
    for i,r in enumerate(st):
        lo,hi=f(r,'reserve_lower')*100,f(r,'reserve_upper')*100;n=int(r['trips'])if r['trips']else None
        intervals.append({'reserve_lower':f(r,'reserve_lower'),'reserve_upper':f(r,'reserve_upper'),'trips':n,'lower_closed':i==0,'upper_closed':True,'reachable':r['reachable']=='True'})
        if n is not None:
            ax.plot([lo,hi],[n,n],color='#4477AA',lw=1.5);ax.plot(lo,n,marker='o',ms=3.4,mfc='#4477AA' if i==0 else 'white',mec='#4477AA',zorder=4);ax.plot(hi,n,marker='o',ms=3.4,mfc='#4477AA',mec='#4477AA',zorder=4)
        else:ax.axvspan(lo,hi,fc='#F4ECEC',ec='#DACACA',hatch='//',zorder=0);ax.text((lo+hi)/2,21,'不可行',ha='center',fontsize=8,color=RED)
    ax.scatter([f(r,'返航安全余量')*100 for r in sen],[f(r,'最少往返架次数')for r in sen],marker='o',s=30,facecolor='white',edgecolor='#4477AA',zorder=6,label='原五场景核验')
    ax.axvline(20,color='#98A2AD',lw=.8);ax.set(xlim=(10,40),ylim=(17,26),xlabel='返航储备（%）',ylabel='最少运输架次数');ax.yaxis.set_major_locator(MultipleLocator(1));ax.xaxis.set_major_locator(MultipleLocator(5));grid(ax);title(ax,'(d) 完整子集临界分析得到的阶梯')
    ax.legend(handles=[Line2D([],[],marker='o',ms=3.4,mfc='#4477AA',mec='#4477AA',ls='',label='闭端点'),Line2D([],[],marker='o',ms=3.4,mfc='white',mec='#4477AA',ls='',label='开端点'),Line2D([],[],marker='o',ms=5.5,mfc='white',mec='#4477AA',ls='',label='原五场景核验')],loc='upper left',frameon=False,fontsize=8,ncol=2)
    ax.plot(10,18,marker='o',ms=2.7,color='#4477AA',zorder=7)
    first=intervals[0]['reserve_upper']*100;last=intervals[-2]['reserve_upper']*100
    ax.annotate(f'{first:.2f}%',xy=(first,18),xytext=(first-4,18.8),fontsize=8,arrowprops={'arrowstyle':'-','lw':.65,'color':SECOND});ax.annotate(f'{last:.2f}%',xy=(last,25),xytext=(last-5,25.4),fontsize=8,arrowprops={'arrowstyle':'-','lw':.65,'color':SECOND})
    # Same saved final steps enlarged, not extra evaluations.
    ins=ax.inset_axes([.12,.35,.39,.36]);
    for r in intervals[3:-1]:
        lo,hi,n=r['reserve_lower']*100,r['reserve_upper']*100,r['trips'];ins.plot([lo,hi],[n,n],color='#4477AA',lw=1);ins.plot(lo,n,'o',ms=3,mfc='white',mec='#4477AA');ins.plot(hi,n,'o',ms=3,color='#4477AA')
    ins.set(xlim=(33.5,35.4),ylim=(20.4,25.6),xticks=[34,35],yticks=[21,23,25]);ins.tick_params(labelsize=7.5);ins.set_title('同一阶梯局部放大',fontsize=8,pad=3);grid(ins)
    checks=[check('2745 unique grid rows',len(raw)==2745 and len({(r['reserve'],r['service'],r['type'])for r in raw})==2745),check('61 reserve points',len({r['reserve']for r in raw})==61),check('45 service type combinations',len({(r['service'],r['type'])for r in raw})==45),check('rated denominators match types',all(f(r,'rated_payload_kg')==A['types'][r['type']]['max_payload']for r in raw)),check('five verification scenarios',len(sen)==5),check('last feasible trip step is 25',intervals[-2]['trips']==25 and intervals[-1]['trips']is None)]
    save(fig,26,'返航储备对安全载荷与最少运输架次数的影响。上排为已有61个储备点下全部45个服务区机型组合，以各自额定载荷为分母；计算点之间的直线仅辅助阅读。下排采用已有完整子集临界分析，并叠加原五场景核验，局部窗重复展示同一阶梯。临界点本身取较低架次数，约23.09%后架次增加，超过约35.27%后不可行。',{'capacity_grid':view,'highlight_at_20pct':highlights,'exact_staircase_intervals':intervals,'five_scenarios':sen},['paper/data/payload_reserve.csv','paper/data/reserve_staircase.csv','results/q1/Q1_sensitivity_summary.csv','paper/data/analysis.json','scripts/paper_sensitivity.py','paper/sections/08_sensitivity.tex','src/config.py'],{'reserve':'reserve_fraction','payload_kg/rated_payload_kg':'safe load ratio','reachable':'NaN gaps, never filled with zero','reserve_lower/upper,trips':'exact staircase endpoints'},['reserve + service + type','staircase ordered interval'],['ratio=100*payload_kg/rated_payload_kg','staircase first interval [lo,hi]; subsequent feasible intervals (lo,hi]; infeasible interval (last_feasible,0.4]','all lines connect saved points only'],checks,[],{'upper_panels':3,'same_x':[10,40],'same_y':[0,105],'same_data_zoom':True})

def fig27():
    soc=rows('paper/data/constraint_slacks.csv');deliveries=rows('results/q3/Q3_box_delivery.csv');hs=rows('paper/data/hard_deadline_slacks.csv');hm={r['box']:f(r,'slack_s')for r in hs}
    hard=[]
    for r in deliveries:
        if r['硬截止_s']:
            hard.append({'box_id':r['货箱编号'],'sortie_id':r['架次编号'],'hard_deadline_s':f(r,'硬截止_s'),'delivery_complete_s':f(r,'交付完成时刻_s'),'slack_s':f(r,'硬截止_s')-f(r,'交付完成时刻_s')})
    hard.sort(key=lambda r:(r['slack_s'],r['box_id']))
    fig=canvas(20.2);gs=fig.add_gridspec(2,1,height_ratios=[1.05,2.8],left=.22,right=.97,bottom=.065,top=.935,hspace=.40);ax=fig.add_subplot(gs[0]);bottom=fig.add_subplot(gs[1]);series={};mins=[]
    for q,col,marker in [('q1','#88949E','o'),('q2','#4477AA','s'),('q3','#6A51A3','^')]:
        rs=sorted([{'scenario':q,'sortie_id':r['trip'],'soc_pct':f(r,'soc_pct')}for r in soc if r['question']==q],key=lambda r:(r['soc_pct'],r['sortie_id']));series[q]=rs;mins.append(rs[0]);ax.scatter(range(1,len(rs)+1),[r['soc_pct']for r in rs],s=3.8**2,color=col,marker=marker,label=f'{q.upper()} n={len(rs)}')
    ax.axhline(20,color=RED,lw=1,ls=(0,(4,2)));ax.text(14,7,'20%储备阈值',fontsize=8,color=RED);ax.set(xlim=(.5,24.5),ylim=(0,100),xlabel='各方案内部SOC升序排名',ylabel='返航SOC（%）');grid(ax);title(ax,'(a) 各方案内部SOC排名');ax.legend(loc='upper left',ncol=3,fontsize=7.5,frameon=False,columnspacing=.55,handletextpad=.25)
    pos=ax.get_position();ax.set_position([.09,pos.y0,.53,pos.height]);ins=fig.add_axes([.735,pos.y0,.235,pos.height]);cols=['#88949E','#4477AA','#6A51A3'];markers=['o','s','^']
    for i,r in enumerate(mins):ins.plot(i,r['soc_pct'],marker=markers[i],ms=4,color=cols[i]);ins.annotate(f'{r["soc_pct"]:.2f}%',(i,r['soc_pct']),xytext=(0,6),textcoords='offset points',fontsize=7.5,ha='center')
    ins.axhline(20,color=RED,lw=.65,ls='--');ins.set(xticks=[0,1,2],xticklabels=['Q1','Q2','Q3'],xlim=(-.5,2.5),ylim=(19.8,max(r['soc_pct']for r in mins)+.7));ins.tick_params(labelsize=7.5);title(ins,'(b) 最低值放大');ins.set_yticks([20,22,24]);grid(ins,'y')
    fig.text(.97,pos.y0-.065,'最低值任务：'+ '；'.join(r['sortie_id']for r in mins),ha='right',va='top',fontsize=7.5,color=SECOND)
    xs=[r['slack_s']for r in hard];ys=range(31);bottom.hlines(ys,0,xs,color='#C8D0D8',lw=.75);bottom.scatter(xs,ys,s=3.8**2,color='#5E8D87');bottom.scatter([xs[0]],[0],s=25,color=RED,zorder=5)
    bottom.set(yticks=range(31),yticklabels=[r['box_id']for r in hard],ylim=(30.65,-.65),xlim=(0,math.ceil(max(xs)/1000)*1000),xlabel='硬截止余量（s）');bottom.tick_params(axis='y',labelsize=8);bottom.xaxis.set_major_locator(MultipleLocator(2000));bottom.xaxis.set_minor_locator(MultipleLocator(1000));grid(bottom,'x');title(bottom,'(c) 31个硬截止货箱，按余量升序排列')
    bottom.annotate(f'最小 {xs[0]:.3f} s',(xs[0],0),xytext=(4300,1.4),textcoords='data',fontsize=8,color=RED,arrowprops={'arrowstyle':'-','lw':.65,'color':RED});bottom.text(1,-.075,'交付按完成交接计',transform=bottom.transAxes,ha='right',fontsize=8,color=SECOND)
    row_mm=bottom.get_position().height*20.2*10/31
    checks=[check('SOC counts 18/24/24',[len(series[q])for q in ['q1','q2','q3']]==[18,24,24]),check('31 unique hard deadline boxes',len(hard)==31 and len({r['box_id']for r in hard})==31),check('all hard margins match saved values',all(abs(r['slack_s']-hm[r['box_id']])<=TOL for r in hard)),check('hard margins nonnegative',all(r['slack_s']>=-TOL for r in hard)),check('Q3 minimum SOC display',f'{mins[2]["soc_pct"]:.2f}'=='20.10'),check('minimum hard slack display',f'{xs[0]:.3f}'=='266.282'),check('minimum hard-row pitch 3.4 mm',row_mm>=3.4,{'actual_mm':row_mm})]
    save(fig,27,'正式方案的运输返航SOC与Q3逐箱硬截止余量。上图各方案分别排序，相同排名不构成跨方案任务配对；20%为返航储备阈值，局部窗显示各方案最低值及正文可定位的任务编号。下图按箱号关联后计算并排序，Q3最小硬截止余量为266.282 s，最低运输返航SOC为20.10%。这些量说明基准约束满足，不提供天气或能耗误差下的整体鲁棒性保证。',{'soc_series':series,'minimum_soc_records':mins,'hard_deadline_records':hard},['paper/data/constraint_slacks.csv','paper/data/hard_deadline_slacks.csv','results/q3/Q3_box_delivery.csv','src/core/constraints.py'],{'question+trip+soc_pct':'scenario-specific unpaired rank scatter','货箱编号':'box_id','硬截止_s-交付完成时刻_s':'hard slack'},['scenario + sortie_id','box_id'],['stable SOC sort by (soc_pct,trip)','hard_slack=hard_deadline-delivery_complete','stable hard sort by (slack,box id)','do not connect ranked scatter points'],checks,[],{'row_pitch_mm':row_mm,'soc_inset':True,'no_connecting_line':True})

if __name__=='__main__':
    functions={17:fig17,18:fig18,19:fig19,20:fig20,21:fig21,22:fig22,23:lambda:fig_partition(2),24:lambda:fig_partition(3),25:fig25,26:fig26,27:fig27}
    selected=[int(a)for a in sys.argv[1:]] or list(functions)
    for num in selected:functions[num]()
