"""Shared visual and display-projection contract. Does not change research geometry."""
import csv, json, hashlib, math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import MaxNLocator

from paths import REPO, OUT, FONT_DIR
OUT.mkdir(parents=True,exist_ok=True)
FONT_PATH=FONT_DIR/'NotoSansSC-Publication-Regular.ttf'
FONT_BOLD_PATH=FONT_DIR/'NotoSansSC-Publication-Bold.ttf'
FONT_CN='Noto Sans SC Publication'
C={'A':'#0072B2','B':'#E69F00','C':'#009E73'}
RELAY_COLORS=['#6A51A3','#CC79A7','#8C6D31']
GROUP_COLORS=['#4477AA','#EEAA33','#AA3377']
GOODS={'MED':'#A6566F','FOD':'#5B8EAD','HYG':'#C7A14A','WAT':'#6B9B83'}
THRESHOLD='#B5424A'; TEXT='#222222'; SECONDARY='#59636E'; GRID='#E5E9ED'
def init_style():
    for p in [FONT_PATH,FONT_BOLD_PATH]:font_manager.fontManager.addfont(str(p))
    plt.rcParams.update({'font.family':['DejaVu Sans',FONT_CN],'font.size':8.5,'axes.labelsize':9.5,'axes.titlesize':10,'axes.titleweight':'bold','xtick.labelsize':8.5,'ytick.labelsize':8.5,'legend.fontsize':8.5,'text.color':TEXT,'axes.labelcolor':TEXT,'xtick.color':TEXT,'ytick.color':TEXT,'axes.edgecolor':SECONDARY,'axes.linewidth':.65,'lines.linewidth':1.3,'axes.spines.top':False,'axes.spines.right':False,'axes.unicode_minus':False,'svg.fonttype':'none','pdf.fonttype':42,'mathtext.fontset':'stixsans','xtick.direction':'out','ytick.direction':'out','savefig.facecolor':'white','figure.facecolor':'white'})
init_style()
def js(rel):return json.loads((REPO/rel).read_text(encoding='utf-8'))
def rows(rel):return list(csv.DictReader((REPO/rel).open(encoding='utf-8-sig',newline='')))
analysis=js('paper/data/analysis.json'); nodes=analysis['nodes']; services=sorted(k for k in nodes if k!='O01')
lon0=nodes['O01']['lon'];lat0=nodes['O01']['lat']
def ecef(lon,lat):
    lon=np.radians(lon);lat=np.radians(lat);a=6378137.;f=1/298.257223563;e2=f*(2-f)
    n=a/np.sqrt(1-e2*np.sin(lat)**2)
    return np.array([n*np.cos(lat)*np.cos(lon),n*np.cos(lat)*np.sin(lon),n*(1-e2)*np.sin(lat)])
_origin=ecef(lon0,lat0);_lam=math.radians(lon0);_phi=math.radians(lat0)
_east=np.array([-math.sin(_lam),math.cos(_lam),0]);_north=np.array([-math.sin(_phi)*math.cos(_lam),-math.sin(_phi)*math.sin(_lam),math.cos(_phi)])
def project(lon,lat):
    d=ecef(lon,lat)-_origin
    return float(_east@d/1000),float(_north@d/1000)
def xy(k):return project(nodes[k]['lon'],nodes[k]['lat'])
_all=[xy(k) for k in nodes]
for r in rows('results/q3/Q3_relay_sorties.csv'):_all.append(project(float(r['悬停经度']),float(r['悬停纬度'])))
_crit=js('paper/data/communication_critical_state.json')['state'];_all.append(project(_crit['longitude'],_crit['latitude']))
_arr=np.array(_all);_lo=_arr.min(axis=0);_hi=_arr.max(axis=0);_pad=(_hi-_lo)*.05
_offsets={k:[3,4] for k in nodes}
_offsets.update({'O01':[4,-11],'S014':[-30,6],'S012':[-29,5],'S013':[-29,5],'S010':[4,-10],'S004':[3,-10],'S008':[-26,5],'S002':[3,4],'S009':[4,-11]})
MAP_SPEC={'projection':'WGS84椭球地表坐标到O01局部东—北切平面的正射显示投影（ECEF→ENU，节点高程不用于平面投影）','ellipsoid':{'a_m':6378137.,'inverse_flattening':298.257223563},'origin':{'longitude':lon0,'latitude':lat0},'units':'km','xlim':[_lo[0]-_pad[0],_hi[0]+_pad[0]],'ylim':[_lo[1]-_pad[1],_hi[1]+_pad[1]],'padding_fraction':.05,'label_offsets':_offsets,'dem_background':'original official 30 m GeoTIFF; displayed without terrain correction or smoothing','scale_bar_km':2.0,'research_geometry_unchanged':True}

def add_terrain_colorbar(fig,ax,rect=None):
    mappable=getattr(ax,'_terrain_mappable',None)
    assert mappable is not None,'Call map_base before adding terrain colorbar.'
    if rect is None:
        p=ax.get_position();rect=[p.x0,max(.055,p.y0-.125),p.width,.015]
    cax=fig.add_axes(rect)
    cb=fig.colorbar(mappable,cax=cax,orientation='horizontal')
    cb.set_label('海拔（m）',fontsize=9,labelpad=2)
    cb.ax.tick_params(labelsize=8.5,length=2,pad=2)
    cb.outline.set_linewidth(.4)
    return cb
def map_base(ax,labels=True,draw_nodes=True):
    import terrain
    ax._terrain_mappable=terrain.draw_terrain(ax,MAP_SPEC)
    MAP_SPEC['terrain']=terrain.TERRAIN_SPEC
    ax.set(xlim=MAP_SPEC['xlim'],ylim=MAP_SPEC['ylim'],xlabel='局部东向 (km)',ylabel='局部北向 (km)')
    ax.set_aspect('equal',adjustable='box');ax.grid(color='#AEB8BE',lw=.35,alpha=.4);ax.set_axisbelow(True)
    ax.xaxis.set_major_locator(MaxNLocator(5));ax.yaxis.set_major_locator(MaxNLocator(5))
    if draw_nodes:
        for k in services:ax.plot(*xy(k),'o',ms=4,mfc='white',mec=SECONDARY,mew=.65,zorder=5)
    ax.scatter(*xy('O01'),marker='*',s=65,color=TEXT,zorder=6)
    for spine in ax.spines.values():spine.set_visible(True);spine.set_linewidth(.65)
    if labels:
        for k in nodes:ax.annotate(k,xy(k),xytext=MAP_SPEC['label_offsets'][k],textcoords='offset points',fontsize=8.5,zorder=8)
    ax.annotate('N',xy=(.075,.90),xytext=(.075,.72),xycoords='axes fraction',ha='center',va='center',fontsize=9,arrowprops={'arrowstyle':'-|>','lw':.85,'color':TEXT},zorder=9)
    x0=MAP_SPEC['xlim'][0]+.07*np.ptp(MAP_SPEC['xlim']);y0=MAP_SPEC['ylim'][0]+.075*np.ptp(MAP_SPEC['ylim'])
    ax.plot([x0,x0+2],[y0,y0],color=TEXT,lw=1.5,zorder=9)
    ax.plot([x0,x0],[y0-.05,y0+.05],color=TEXT,lw=.7,zorder=9);ax.plot([x0+2,x0+2],[y0-.05,y0+.05],color=TEXT,lw=.7,zorder=9)
    ax.annotate('2 km',(x0+1,y0),xytext=(0,3),textcoords='offset points',ha='center',fontsize=8.5,zorder=9)
    return ax
mapbase=map_base
def grid(ax,axis='y'):ax.grid(axis=axis,color=GRID,lw=.4);ax.set_axisbelow(True)
def panel(ax,text):ax.set_title(text,loc='left',pad=7,fontsize=10,weight='bold')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump_json(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)),encoding='utf-8')
def save_figure(fig,number,caption,sources,data,extra=None):
    stem=f'fig_{number:02d}'; fig.set_figwidth(16.3/2.54)
    for ext in ['svg','pdf']:fig.savefig(OUT/(stem+'.'+ext),facecolor='white')
    fig.savefig(OUT/(stem+'.png'),dpi=600,facecolor='white')
    dump_json(OUT/(stem+'_data.json'),data)
    spec={'number':number,'caption':caption,'width_cm':16.3,'height_cm':fig.get_figheight()*2.54,'dpi':600,'sources':[{'path':s,'sha256':sha(REPO/s)} for s in sources],'font':{'cn':FONT_CN,'cn_path':str(FONT_PATH),'latin':'DejaVu Sans'},'map_spec':MAP_SPEC if number in [2,11,12,13,17,23,24] else None}
    if extra:spec.update(extra)
    dump_json(OUT/(stem+'_spec.json'),spec)
    (OUT/(stem+'_caption.txt')).write_text(caption,encoding='utf-8')
    plt.close(fig)
if __name__=='__main__':
    dump_json(OUT/'map_spec.json',MAP_SPEC)
    print(json.dumps(MAP_SPEC,ensure_ascii=False))

# Stage colours are used only in stage plots, not as model-type identity.
STAGE={'prep':'#AEB9C5','flight':'#75A8C8','handover':'#E7BF62','return':'#B8CCD8','charge':'#F3E7DD','turnaround':'#EEF0F3'}
STAGE_EDGE={'charge':'#A36D45','turnaround':'#7F8791'}
MARKERS={'A':'o','B':'s','C':'^'}

def terrain3d(ax, exaggeration=1, stride=4):
    """Display-only decimation; real altitudes in metres and common ENU km."""
    import terrain
    g=terrain._grid(terrain._map_key(MAP_SPEC))
    x=(g['x_edges'][:-1,:-1]+g['x_edges'][1:,1:])/2
    y=(g['y_edges'][:-1,:-1]+g['y_edges'][1:,1:])/2
    z=g['z']; cm=terrain._display_cmap()
    ax.plot_surface(x[::stride,::stride],y[::stride,::stride],z[::stride,::stride],cmap=cm,vmin=terrain.TERRAIN_SPEC['norm']['vmin'],vmax=terrain.TERRAIN_SPEC['norm']['vmax'],linewidth=0,antialiased=False,alpha=.70,rasterized=True)
    ax.set_proj_type('ortho');ax.view_init(elev=30,azim=-60)
    ax.set(xlim=MAP_SPEC['xlim'],ylim=MAP_SPEC['ylim'],zlim=(0,800))
    ax.set_box_aspect((np.ptp(MAP_SPEC['xlim']),np.ptp(MAP_SPEC['ylim']),.8*exaggeration))
    ax.set(xlabel='东向 (km)',ylabel='北向 (km)',zlabel='海拔 (m)')
    ax.tick_params(labelsize=8,pad=0)
    for axis in (ax.xaxis,ax.yaxis,ax.zaxis):axis.label.set_fontsize(8.5)
    ax.xaxis.set_major_locator(MaxNLocator(3));ax.yaxis.set_major_locator(MaxNLocator(3));ax.zaxis.set_major_locator(MaxNLocator(3))
    return {'stride':stride,'vertical_exaggeration':exaggeration,'altitude_unit':'m','horizontal_unit':'km','view_elev':30,'view_azim':-60}
