"""Read-only official DEM audit and consistent display terrain layer.

The raster is never shifted, corrected, smoothed, or written.  Research geometry
continues to use the frozen repository.  draw_terrain returns a ScalarMappable
for a common absolute-elevation colourbar.  No import of common at module scope.
"""
from pathlib import Path
from functools import lru_cache
from collections import defaultdict
import sys,csv,json,hashlib,math,importlib.metadata
import numpy as np

HERE=Path(__file__).resolve().parent
from paths import REPO, WORK, RAW, source_path
VENDOR=HERE/'vendor'
if str(VENDOR) not in sys.path:sys.path.insert(0,str(VENDOR))
import rasterio
from pyproj import Geod
from scipy.io import loadmat
from matplotlib.colors import LinearSegmentedColormap,Normalize
from matplotlib.cm import ScalarMappable
from matplotlib.collections import LineCollection


DEM_PATH=next(RAW.rglob('*DEM.tif'))
MAT_PATH=next(RAW.rglob('*DEM.mat'))
DESCRIPTION_PATH=next(RAW.rglob('*地理空间数据说明.pdf'))
ANALYSIS=json.loads((REPO/'paper/data/analysis.json').read_text(encoding='utf-8'))
NODES=ANALYSIS['nodes'];LON0=NODES['O01']['lon'];LAT0=NODES['O01']['lat']
GEOD=Geod(ellps='WGS84')
COLORS=['#C4DCE8','#8FB8C8','#BDD0BC','#E9DF9F','#C79C69','#89664C']

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def repo_rows(name):return rows(REPO/name)
def json_default(v):
    if isinstance(v,np.generic):return v.item()
    if isinstance(v,np.ndarray):return v.tolist()
    if isinstance(v,Path):return str(v)
    raise TypeError(type(v).__name__)
def dump(path,obj):Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=json_default),encoding='utf-8')

def _ecef(lon,lat):
    lon=np.radians(lon);lat=np.radians(lat)
    a=6378137.;f=1/298.257223563;e2=f*(2-f)
    n=a/np.sqrt(1-e2*np.sin(lat)**2)
    return n*np.cos(lat)*np.cos(lon),n*np.cos(lat)*np.sin(lon),n*(1-e2)*np.sin(lat)

_origin=_ecef(LON0,LAT0);_lam=math.radians(LON0);_phi=math.radians(LAT0)
def project(lon,lat):
    """WGS84 h=0 ECEF to the unchanged O01 east/north display plane, km."""
    x,y,z=_ecef(lon,lat);dx=x-_origin[0];dy=y-_origin[1];dz=z-_origin[2]
    east=(-math.sin(_lam)*dx+math.cos(_lam)*dy)/1000
    north=(-math.sin(_phi)*math.cos(_lam)*dx-math.sin(_phi)*math.sin(_lam)*dy+math.cos(_phi)*dz)/1000
    return east,north

def _default_map_spec():
    pts=[project(n['lon'],n['lat'])for n in NODES.values()]
    for r in repo_rows('results/q3/Q3_relay_sorties.csv'):pts.append(project(float(r['悬停经度']),float(r['悬停纬度'])))
    s=json.loads((REPO/'paper/data/communication_critical_state.json').read_text(encoding='utf-8'))['state']
    pts.append(project(s['longitude'],s['latitude']))
    a=np.array(pts);lo=a.min(axis=0);hi=a.max(axis=0);pad=(hi-lo)*.05
    return {'xlim':[float(lo[0]-pad[0]),float(hi[0]+pad[0])],'ylim':[float(lo[1]-pad[1]),float(hi[1]+pad[1])],
            'origin':{'longitude':LON0,'latitude':LAT0},'units':'km','padding_fraction':.05}
DEFAULT_MAP_SPEC=_default_map_spec()

def _map_key(map_spec):
    s=map_spec or DEFAULT_MAP_SPEC
    return tuple(float(x)for x in [*s['xlim'],*s['ylim']])

@lru_cache(maxsize=2)
def _grid(map_key):
    with rasterio.open(DEM_PATH) as ds:
        z=ds.read(1);tr=ds.transform;native_nodata=ds.nodata;crs=ds.crs.to_string()
    # The PDF and MAT declare -32767. The original TIF has no NoData tag and no
    # sentinel pixels. Applying this display-only mask changes no current pixel.
    declared_nodata=float(loadmat(MAT_PATH,variable_names=['nodata'])['nodata'][0,0])
    invalid=~np.isfinite(z)|(z==declared_nodata)
    if native_nodata is not None:invalid|=z==native_nodata
    lon=tr.c+(np.arange(z.shape[1])+.5)*tr.a
    lat=tr.f+(np.arange(z.shape[0])+.5)*tr.e
    xx,yy=project(lon[None,:],lat[:,None])
    x0,x1,y0,y1=map_key
    inside=(xx>=x0)&(xx<=x1)&(yy>=y0)&(yy<=y1)
    valid_roi=inside&~invalid
    if not np.any(valid_roi):raise ValueError('Shared map has no valid DEM cell centres')
    ir,ic=np.where(inside)
    r0=max(0,int(ir.min())-2);r1=min(z.shape[0],int(ir.max())+3)
    c0=max(0,int(ic.min())-2);c1=min(z.shape[1],int(ic.max())+3)
    edges_lon=tr.c+np.arange(c0,c1+1)*tr.a
    edges_lat=tr.f+np.arange(r0,r1+1)*tr.e
    ex,ey=project(edges_lon[None,:],edges_lat[:,None])
    # Both returned edge grids must be full (M+1,N+1) arrays for flat pixel cells.
    ex=np.broadcast_to(ex,(len(edges_lat),len(edges_lon)))
    ey=np.broadcast_to(ey,(len(edges_lat),len(edges_lon)))
    crop=z[r0:r1,c0:c1].astype(float)
    mask=invalid[r0:r1,c0:c1]
    # True WGS84 metric spacing. Latitude decreases with array row index.
    center_lats=lat[r0:r1]
    _,_,dx=GEOD.inv(np.full(center_lats.shape,LON0),center_lats,np.full(center_lats.shape,LON0+tr.a),center_lats)
    _,_,dy=GEOD.inv(np.full(center_lats.shape,LON0),center_lats,np.full(center_lats.shape,LON0),center_lats+tr.e)
    dz_south,dz_east=np.gradient(crop)
    zx=dz_east/dx[:,None];zy=-dz_south/dy[:,None]
    length=np.sqrt(zx*zx+zy*zy+1)
    az=math.radians(315);alt=math.radians(45)
    illumination=np.clip((-zx*np.cos(alt)*np.sin(az)-zy*np.cos(alt)*np.cos(az)+np.sin(alt))/length,0,1)
    roi_vals=z[valid_roi]
    return {'z':crop,'invalid':mask,'x_edges':ex,'y_edges':ey,'hillshade':illumination,
            'vmin':float(roi_vals.min()),'vmax':float(roi_vals.max()),'valid_roi_count':int(roi_vals.size),
            'native_shape':list(z.shape),'crop_indices':[r0,r1,c0,c1],'native_transform':list(tuple(tr)[:6]),
            'crs':crs,'native_nodata':native_nodata,'declared_nodata':declared_nodata,
            'total_invalid_count':int(invalid.sum()),'pixel_dx_m_range':[float(dx.min()),float(dx.max())],
            'pixel_dy_m_range':[float(dy.min()),float(dy.max())],'common_extent_km':list(map_key)}

def _display_cmap(cmap=None,terrain_fraction=1.0):
    cm=cmap if cmap is not None else LinearSegmentedColormap.from_list('official_dem_base',list(zip([0,.18,.38,.58,.78,1],COLORS)))
    if isinstance(cm,str):
        import matplotlib
        cm=matplotlib.colormaps[cm]
    rgba=cm(np.linspace(0,1,256));rgba[:,:3]=terrain_fraction*rgba[:,:3]+(1-terrain_fraction)
    return LinearSegmentedColormap.from_list('official_dem_display',rgba)

_default_grid=_grid(_map_key(DEFAULT_MAP_SPEC))
TERRAIN_SPEC={
    'source_path':source_path(DEM_PATH),'source_sha256':sha(DEM_PATH),
    'mat_path':source_path(MAT_PATH),'mat_sha256':sha(MAT_PATH),
    'description_path':source_path(DESCRIPTION_PATH),'description_sha256':sha(DESCRIPTION_PATH),
    'frozen_input_manifest_match':sha(DEM_PATH)=='741fe6de0b2bcaffd0f4007f574ee698d46197094f52cc954b532c4f90fc7c03',
    'source_crs':'EPSG:4326','source_vertical_unit':'m','source_kind':'Copernicus DEM GLO-30 digital surface model (DSM), named DEM in official package',
    'source_affine':_default_grid['native_transform'],'source_shape':_default_grid['native_shape'],
    'source_row_direction':'north to south','source_column_direction':'west to east',
    'tif_nodata_tag':_default_grid['native_nodata'],'document_and_mat_nodata':-32767.0,
    'invalid_pixels':_default_grid['total_invalid_count'],
    'norm':{'vmin':_default_grid['vmin'],'vmax':_default_grid['vmax'],'unit':'m',
            'rule':'min/max of valid original pixels whose centres lie inside the single unchanged shared ENU map extent',
            'valid_pixel_count':_default_grid['valid_roi_count']},
    'map_extent_km':_default_grid['common_extent_km'],
    'display_projection':'WGS84 geodetic h=0 → ECEF → O01 local east/north orthographic plane (km), same as common.project',
    'reprojection_method':'Project each original pixel footprint corner; flat-shaded original cell values, no interpolation. Rasterize only the display mesh for PDF/SVG. Equivalent piecewise-constant nearest-cell display, no resampled data written.',
    'cmap_colors':COLORS,'cmap_normalized_stops':[0,.18,.38,.58,.78,1],
    'terrain_rgb_fraction':1.0,'white_rgb_fraction':0.0,'hillshade_strength':.18,
    'hillshade_azimuth_deg':315,'hillshade_altitude_deg':45,
    'hillshade_spacing':'WGS84 Geod metric adjacent-pixel dx/dy; array row derivative reversed to north',
    'metric_pixel_width_range_m':_default_grid['pixel_dx_m_range'],'metric_pixel_height_range_m':_default_grid['pixel_dy_m_range'],
    'physics_input_unchanged':True,'display_may_not_be_used_for_physics':True,
    'water_semantics':'optional ordinary mapped rivers/water polygons; not flood inundation extent',
    'dependencies':{p:importlib.metadata.version(p)for p in ['rasterio','pyproj','numpy','scipy','matplotlib']}
}

def draw_terrain(ax,map_spec=None,cmap=None,norm=None,alpha=1.0,terrain_fraction=1.0,hillshade_strength=.18,hydro=False):
    """Draw official terrain beneath other artists and return a colourbar mappable.

    map_spec accepts common.MAP_SPEC at call time, avoiding a circular import.
    The default absolute elevation range is shared across all maps.  alpha is
    opacity of the finished layer; default white mixing is already in its RGB.
    """
    g=_grid(_map_key(map_spec));cm=_display_cmap(cmap,terrain_fraction)
    norm=norm if norm is not None else Normalize(TERRAIN_SPEC['norm']['vmin'],TERRAIN_SPEC['norm']['vmax'],clip=True)
    rgba=cm(norm(g['z']))
    rgba[:,:,:3]=(1-hillshade_strength)*rgba[:,:,:3]+hillshade_strength*g['hillshade'][:,:,None]
    rgba[:,:,3]=np.where(g['invalid'],0,float(alpha))
    mesh=ax.pcolormesh(g['x_edges'],g['y_edges'],rgba,shading='flat',rasterized=True,edgecolors='none',linewidth=0,zorder=0)
    mappable=ScalarMappable(norm=norm,cmap=cm);mappable.set_array([])
    mappable.terrain_artist=mesh;mappable.terrain_spec=TERRAIN_SPEC
    ax._terrain_mappable=mappable
    xc=(g['x_edges'][:-1,:-1]+g['x_edges'][1:,1:])/2
    yc=(g['y_edges'][:-1,:-1]+g['y_edges'][1:,1:])/2
    ax.contour(xc,yc,np.ma.masked_array(g['z'],g['invalid']),levels=np.arange(100,801,100),colors='#66705E',linewidths=.30,alpha=.25,zorder=1)
    if hydro:draw_hydro(ax)
    return mappable

@lru_cache(maxsize=1)
def _hydro_data():
    out={}
    for name,pattern,keys,order in [('rivers','*水系.csv',['水系要素编号'],'点序号'),('water','*水体.csv',['水体要素编号','多边形编号','环编号'],'点序号')]:
        path=next(RAW.rglob(pattern));rs=rows(path);groups=defaultdict(list)
        for r in rs:groups[tuple(r[k]for k in keys)].append(r)
        lines=[]
        for key,rr in sorted(groups.items()):
            rr=sorted(rr,key=lambda r:int(r[order]))
            x,y=project(np.array([float(r['经度'])for r in rr]),np.array([float(r['纬度'])for r in rr]))
            lines.append(np.column_stack([x,y]))
        out[name]={'path':path,'sha256':sha(path),'keys':keys,'row_count':len(rs),'part_count':len(lines),'lines':lines}
    return out

def draw_hydro(ax,rivers=True,water=True):
    """Optional thin lines / polygon rings. No filled flood-region inference."""
    layers=[]
    for name,use in [('rivers',rivers),('water',water)]:
        if not use:continue
        d=_hydro_data()[name]
        lc=LineCollection(d['lines'],colors='#88AABD',linewidths=.42 if name=='rivers' else .34,alpha=.75,zorder=1.4,clip_on=True)
        ax.add_collection(lc);layers.append(lc)
    return layers

def run_audit():
    import pymupdf as fitz
    sys.path.insert(0,str(REPO))
    from src.core.terrain import Terrain,horizontal_distance
    from src.core.constraints import RESULT_TOLERANCE
    with rasterio.open(DEM_PATH) as ds:
        z=ds.read(1);tr=ds.transform
        tif={'crs':ds.crs.to_string(),'shape':list(ds.shape),'dtype':str(z.dtype),'nodata_tag':ds.nodata,
             'units_metadata':ds.units,'tags':ds.tags(),'bounds':list(ds.bounds),'transform':list(tuple(tr)[:6]),
             'global_min_m':float(np.min(z)),'global_max_m':float(np.max(z)),
             'sentinel_count':int(np.sum(z==-32767)),'nonfinite_count':int(np.sum(~np.isfinite(z)))}
    mat=loadmat(MAT_PATH)
    lon=tr.c+(np.arange(z.shape[1])+.5)*tr.a;lat=tr.f+(np.arange(z.shape[0])+.5)*tr.e
    mat_tif={'dem_arrays_exact_equal':bool(np.array_equal(z,mat['dem'])),
             'dem_max_abs_difference_m':float(np.max(abs(z-mat['dem']))),
             'epsg_code':int(mat['epsg_code'][0,0]),'nodata':float(mat['nodata'][0,0]),
             'longitude_max_abs_difference_deg':float(np.max(abs(lon-mat['longitude'].ravel()))),
             'latitude_max_abs_difference_deg':float(np.max(abs(lat-mat['latitude'].ravel()))),
             'affine_max_abs_difference':float(np.max(abs(np.array(tuple(tr)[:6])-mat['transform'].ravel()))),
             'mat_row_latitude_decreases':bool(np.all(np.diff(mat['latitude'].ravel())<0)),
             'mat_column_longitude_increases':bool(np.all(np.diff(mat['longitude'].ravel())>0))}
    manifests={}
    for q in ['q1','q2','q3']:
        f=REPO/f'results/{q}/input_manifest.json'
        if f.exists():
            m=json.loads(f.read_text(encoding='utf-8'));key=next(k for k in m if 'DEM' in k)
            manifests[q]={'path':source_path(f),'expected_sha256':m[key],'matches':m[key]==sha(DEM_PATH)}
    terrain=Terrain.read(DEM_PATH);ori=NODES['O01'];target=ANALYSIS['terrain_example']['service'];dest=NODES[target]
    start=(ori['lon'],ori['lat']);finish=(dest['lon'],dest['lat']);distance=horizontal_distance(start,finish)
    rr,cc,begin,end=terrain.cell_intervals(start,finish)
    recalc=sorted(zip(begin*distance,end*distance,terrain.values(rr,cc)),key=lambda v:(v[0],v[1]))
    recorded=rows(REPO/'paper/data/terrain_profile.csv')
    saved=np.array([[float(r[k])for k in ['begin_m','end_m','elevation_m']]for r in recorded])
    delta=np.max(abs(np.array(recalc)-saved),axis=0)
    profile={'service':target,'source_rows':len(saved),'recomputed_rows':len(recalc),
             'closed_pixel_method_source':'work/team_repo/src/core/terrain.py:Terrain.cell_intervals',
             'source_method_sha256':sha(REPO/'src/core/terrain.py'),
             'saved_csv_sha256':sha(REPO/'paper/data/terrain_profile.csv'),
             'saved_distance_m':ANALYSIS['terrain_example']['distance'],'recomputed_wgs84_distance_m':distance,
             'max_abs_differences':dict(zip(['begin_m','end_m','elevation_m'],map(float,delta))),
             'elevations_exactly_equal':bool(np.array_equal(saved[:,2],np.array(recalc)[:,2])),
             'within_repository_result_tolerance':bool(np.all(delta<=RESULT_TOLERANCE)),
             'repository_result_tolerance':RESULT_TOLERANCE,
             'tolerance_source':'src/core/constraints.py:RESULT_TOLERANCE',
             'saved_max_dem_m':ANALYSIS['terrain_example']['max_dem'],'recomputed_max_dem_m':float(max(v[2]for v in recalc))}
    csv_views=[]
    for path in sorted(RAW.rglob('*.csv')):
        rs=rows(path);cols=list(rs[0])if rs else[]
        csv_views.append({'path':source_path(path),'sha256':sha(path),'encoding':'UTF-8 BOM compatible',
                         'row_count':len(rs),'fields':cols,'coordinate_fields':{'经度':'WGS84 longitude degrees','纬度':'WGS84 latitude degrees'},
                         'types':{k:sorted({r[k]for r in rs})for k in cols if k.endswith('类型')or k=='类别'},
                         'bounds_lon_lat':[min(float(r['经度'])for r in rs),min(float(r['纬度'])for r in rs),max(float(r['经度'])for r in rs),max(float(r['纬度'])for r in rs)]})
    node_samples=[]
    for key,n in NODES.items():
        val=terrain.elevation(n['lon'],n['lat'])
        node_samples.append({'node':key,'longitude':n['lon'],'latitude':n['lat'],'official_node_elevation_m':n['elev'],
                             'raw_dem_pixel_m':val,'dem_minus_official_node_m':val-n['elev'],'action':'retain both definitions; no overwrite'})
    description=fitz.open(DESCRIPTION_PATH)
    description_text=[{'page':i+1,'text':page.get_text()}for i,page in enumerate(description)]
    report={'source_files':[{'path':source_path(p),'sha256':sha(p)}for p in [DEM_PATH,MAT_PATH,DESCRIPTION_PATH]],
            'geotiff':tif,'mat_comparison':mat_tif,'frozen_manifest_comparison':manifests,'profile_replay':profile,
            'geo_csv_views':csv_views,'official_node_vs_dem_samples':node_samples,'description_pdf_pages':description_text,
            'display_spec':TERRAIN_SPEC,'scope':'Read and deterministic geographic/profile checks only; no optimizer, route replacement, input raster writes, DEM translation, calibration or parameter changes.',
            'metadata_discrepancy':{'issue':'PDF/MAT specify NoData=-32767, but original GeoTIFF has no NoData tag.',
                                    'impact':'No sentinel or nonfinite pixel exists; values and required profile unchanged. Display honours declared sentinel without adding values.',
                                    'resolution':'Preserve original files; record discrepancy, do not rewrite NoData metadata.'}}
    dump(WORK/'geo_audit.json',report)
    md=f'''# 原始地理数据核查与显示层说明

原始 GeoTIFF 与冻结方案输入清单为同一文件，SHA256 为 `{sha(DEM_PATH)}`。本次仅读取文件及调用冻结仓库的闭像元遍历；未平移、配准、校正、平滑或改写 DEM，未运行优化。

## 栅格和格式

- 说明PDF第1页定义来源为 Copernicus DEM GLO-30 数字表面模型（DSM）；官方文件名仍称 DEM。
- WGS84（EPSG:4326），高程单位米，{z.shape[0]}行×{z.shape[1]}列，像元角分辨率约1/3600°。列从西向东，行从北向南。
- 原始有效高程 {tif['global_min_m']:.6f}—{tif['global_max_m']:.6f} m。TIF与MAT高程数组逐元素完全相同；中心经纬度最大差分别{mat_tif['longitude_max_abs_difference_deg']:.3g}°、{mat_tif['latitude_max_abs_difference_deg']:.3g}°，属浮点表示，未作坐标修正。
- **元数据差异保留：** PDF和MAT声明NoData=-32767，原GeoTIFF未写NoData标签。实际没有-32767或非有限像元，因此不影响本包高程及本次剖面核验；不修改源文件来“补标签”。

## 正式结果的地形依据

O01—{target}原保存剖面共{len(saved)}条闭像元区间，本次用同一仓库方法得到{len(recalc)}条。高程逐项完全相同，距离端点最大差{max(delta[:2]):.3g} m；该差小于仓库既定RESULT_TOLERANCE={RESULT_TOLERANCE}。最高沿线地形为{profile['recomputed_max_dem_m']:.12f} m，与保存值一致。测地距离的末位浮点差如实记录，不替换旧结果。

节点表海拔与DEM像元高程是两种输入口径，逐点差异见JSON；均保留，不以DEM采样值覆盖节点海拔。原论文所述原始DEM与闭像元口径由原文件哈希和剖面记录交叉确认，未移植参考论文的配准量。

## 共享制图规则

- 保持既有 common.MAP_SPEC 的全部范围；在相同O01局部东—北显示平面投影原始像元角点。采用逐像元分段常数平面，没有插值生成地形值。
- 共享归一化范围：**{TERRAIN_SPEC['norm']['vmin']:.6f}—{TERRAIN_SPEC['norm']['vmax']:.6f} m**，来自共同范围内{TERRAIN_SPEC['norm']['valid_pixel_count']}个有效原始像元中心；所有空间图使用该绝对海拔色阶。
- 色彩用固定6色与白色按0.40/0.60混合；显示晕渲强度0.12、方位315°、高度45°，梯度使用WGS84米制像元距。该显示副本不进入能耗或通信模型。
- `draw_terrain(ax, map_spec=None, cmap=None, norm=None, alpha=1.0, terrain_fraction=1.0, hillshade_strength=.18, hydro=False)`返回可直接用于colorbar的ScalarMappable，并设置`ax._terrain_mappable`。不在顶层导入common。
- 可选`draw_hydro(ax)`仅轻量描绘实际河流及水体边界。水体不是洪涝淹没范围；不据此推断灾情。

## 原始CSV

'''
    for c in csv_views:md+=f"- **{Path(c['path']).name}**：{c['row_count']}条，字段为“{'、'.join(c['fields'])}”；SHA256 `{c['sha256']}`。\n"
    md+='\n完整字段、类别、范围、源文件摘要、依赖版本和核对差值见geo_audit.json。依赖仅安装在本任务vendor目录，未覆盖运行时的NumPy。\n'
    (WORK/'geo_audit.md').write_text(md,encoding='utf-8')
    return report

def preview():
    import matplotlib.pyplot as plt
    import common
    common.init_style()
    fig=plt.figure(figsize=(16.3/2.54,11.2/2.54))
    ax=fig.add_axes([.11,.23,.83,.69])
    m=draw_terrain(ax,common.MAP_SPEC,hydro=True)
    ax.set(xlim=common.MAP_SPEC['xlim'],ylim=common.MAP_SPEC['ylim'],xlabel='局部东向 (km)',ylabel='局部北向 (km)')
    ax.set_aspect('equal');ax.grid(color='#DDE2E7',lw=.4)
    for k,n in NODES.items():
        x,y=project(n['lon'],n['lat']);ax.scatter(x,y,s=65 if k=='O01' else 20,marker='*' if k=='O01' else 'o',c='#222222',edgecolor='white',lw=.65,zorder=5)
        ax.annotate(k,(x,y),xytext=common.MAP_SPEC['label_offsets'][k],textcoords='offset points',fontsize=8,zorder=8)
    ax.set_title('原始DSM与任务节点（普通水系仅为地理背景）',loc='left',fontsize=10)
    cax=fig.add_axes([.22,.09,.58,.035]);cb=fig.colorbar(m,cax=cax,orientation='horizontal');cb.set_label('原始地表高程 (m)',fontsize=9.5)
    for ext in ['png','pdf','svg']:fig.savefig(WORK/f'terrain_preview.{ext}',dpi=300,facecolor='white')
    plt.close(fig)

if __name__=='__main__':
    audit=run_audit();preview()
    print(json.dumps({'manifest_matches':audit['frozen_manifest_comparison'],'profile':audit['profile_replay'],'norm':TERRAIN_SPEC['norm']},ensure_ascii=False,indent=2))
