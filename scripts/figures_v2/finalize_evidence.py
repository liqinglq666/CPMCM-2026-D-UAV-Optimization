"""Assemble the real 27-figure manifest and traceable shared visual metadata."""
from pathlib import Path
import csv,json,hashlib
from docx import Document
from paths import REPO,RAW,OUT,DATA,FONT_DIR,source_path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def resolve(path):
    path=str(path).replace('\\','/')
    if path.startswith('raw-input/'):return RAW/path[len('raw-input/'):]
    p=Path(path)
    return p if p.is_absolute() else REPO/p

def main():
    import common,terrain
    common.MAP_SPEC['terrain']=terrain.TERRAIN_SPEC
    captions={}
    for p in Document(REPO/'paper/final/manuscript.docx').paragraphs:
        if p.text.startswith('图 '):
            parts=p.text.split(maxsplit=2)
            if len(parts)==3 and parts[1].isdigit():captions[int(parts[1])]=p.text
    manifest=[]
    for n in range(1,28):
        stem=f'fig_{n:02d}'
        spec=json.loads((OUT/(stem+'_spec.json')).read_text(encoding='utf-8'))
        sources=spec['sources']
        for record in sources:
            p=resolve(record['path'])
            assert p.exists(),(n,record)
            assert sha(p)==record['sha256'],(n,record,'source changed after figure export')
            record['path']=source_path(p)
        group='01_09' if n<10 else '10_16' if n<17 else '17_27'
        script='scripts/figures_v2/figures_'+group+'.py'
        shared=[REPO/'scripts/figures_v2/common.py',REPO/'scripts/figures_v2/paths.py',
                FONT_DIR/'NotoSansSC-Publication-Regular.ttf',FONT_DIR/'NotoSansSC-Publication-Bold.ttf']
        if n in [2,11,12,13,17,23,24]:
            shared += [REPO/'scripts/figures_v2/terrain.py',terrain.DEM_PATH,terrain.MAT_PATH]
            spec['map_spec']=common.MAP_SPEC
            spec['terrain_spec']=terrain.TERRAIN_SPEC
        spec['shared_visual_sources']=[{'path':source_path(p),'sha256':sha(p)}for p in shared]
        if 'font' in spec and 'cn_path' in spec['font']:
            spec['font']['cn_path']=source_path(FONT_DIR/'NotoSansSC-Publication-Regular.ttf')
        spec['script']=script;spec['script_sha256']=sha(REPO/script)
        spec['base_word_caption']=captions[n]
        spec['base_word_sha256']=sha(REPO/'paper/final/manuscript.docx')
        spec['repository_input_commit']='e71cdb13c0969a28d78f349e1ce79047e731e954'
        spec['research_commit']='bec20f1536458db47bac583c309c7b30637cb67a'
        spec['data_file']=stem+'_data.json'
        spec['data_sha256']=sha(OUT/(stem+'_data.json'))
        spec['output_sha256']={ext:sha(OUT/(stem+'.'+ext))for ext in ['pdf','svg','png']}
        if n<=9:
            spec['join_keys']={1:[],2:['service=node.code'],3:['box.id','service'],
              4:['trip=Q1-S014-01','service=S014','direction'],5:['trip','direction'],
              6:['trip_id=Q2-001','box_id','resource_id'],7:['service','type'],
              8:['trip_id','box_id'],9:['trip_id=trip']}[n]
            spec['filters']={1:['Source-defined modules and decision dependencies'],2:['All 15 service areas and O01','Unique box IDs by service','Q1 single-destination maximum terrain'],
              3:['All 80 official boxes','Hard deadline is first-batch OR medical, as defined in the existing reader'],
              4:['service=S014','trip=Q1-S014-01','type=B'],5:['All 18 formal Q1 batches','Both outbound and return energy components'],
              6:['trip=Q2-001','U01 and A-BAT-01'],7:['All 15 services x 3 types','Current official reserve fractions'],
              8:['All 18 formal Q1 batches','All 80 assigned box IDs'],9:['constraint_slacks.question=q1','All 18 batches']}[n]
        dump(OUT/(stem+'_spec.json'),spec)
        dump(DATA/(stem+'_spec.json'),spec)
        (DATA/(stem+'_data.json')).write_bytes((OUT/(stem+'_data.json')).read_bytes())
        mapping=spec.get('source_fields',spec.get('field_mapping',{}))
        formula=spec.get('derived_formula',spec.get('derived_formulas',spec.get('derivations',[])))
        assert mapping,(n,'missing per-figure source-field mapping')
        manifest.append({'figure_id':stem,'word_caption':captions[n],'updated_caption':spec['caption'],
          'core_claim':spec.get('core_claim',spec.get('title','')),
          'source_paths':json.dumps([r['path']for r in sources],ensure_ascii=False),
          'source_fields':json.dumps(mapping,ensure_ascii=False),
          'filters':json.dumps(spec.get('filters',spec.get('parameters',{})),ensure_ascii=False),
          'join_keys':json.dumps(spec.get('join_keys',[]),ensure_ascii=False),
          'derived_formula':json.dumps(formula,ensure_ascii=False),
          'script':script,'output':'outputs/figures_v2/'+stem+'.{pdf,svg,png}',
          'source_sha256':json.dumps({r['path']:r['sha256']for r in sources},ensure_ascii=False)})
    with(REPO/'paper/figure_manifest_v2.csv').open('w',encoding='utf-8-sig',newline='')as f:
        w=csv.DictWriter(f,fieldnames=list(manifest[0]));w.writeheader();w.writerows(manifest)
    dump(OUT/'visual_system.json',{'width_cm':16.3,'minimum_necessary_font_pt':8,'png_dpi':600,
        'model_colors':common.C,'model_markers':common.MARKERS,'relay_colors':common.RELAY_COLORS,
        'group_colors':common.GROUP_COLORS,'goods_colors':common.GOODS,'stage_colors':common.STAGE,
        'threshold_color':common.THRESHOLD,'font_cn':common.FONT_CN,'math':'STIX Sans',
        'map_spec':common.MAP_SPEC,'terrain_spec':terrain.TERRAIN_SPEC,
        'visual_references':[{'url':'https://github.com/TAO-QKV/Icarus-Figures','used':'Core claim and complementary panel evidence organization only.'},
         {'url':'https://github.com/garrettj403/SciencePlots','used':'Consistent physical figure size, axes, typography and grayscale readability only.'},
         {'url':'https://github.com/chrischoy/figura','used':'Render, inspect, identify concrete defects and correct actual output.'}],
        'external_figure_data_or_layout_copied':False})
    print('Manifest assembled for',len(manifest),'figures')

if __name__=='__main__':main()
