"""Replace figure plates and their direct prose descriptions, preserving results."""
from pathlib import Path
import hashlib,json,re
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.oxml.ns import qn
from docx.opc.constants import RELATIONSHIP_TYPE as RT
import pymupdf as fitz

import argparse
from paths import REPO,OUT,WORK
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out',type=Path,default=REPO/'outputs/manuscript_v2.docx')
args=parser.parse_args()
W=WORK;FIG=OUT
BASE=REPO/'paper/final/manuscript.docx'
FINAL=args.out.resolve();FINAL.parent.mkdir(parents=True,exist_ok=True)
assert hashlib.sha256(BASE.read_bytes()).hexdigest()=='9b4ced7a81957fd9fc3a097aa91f2636757b0b9a9fbdebaf5f1ae625c9b1f19c'
d=Document(BASE);edits=[]

def replace(p,text,reason):
    assert not p._p.xpath('.//m:oMath'), 'Never replace a paragraph containing an equation'
    old=p.text;p.text=text
    for run in p.runs:
        run.font.name='Times New Roman';run.font.size=Pt(12);run.font.color.rgb=RGBColor(0,0,0)
        run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'宋体')
    edits.append({'before':old,'after':text,'reason':reason})

assert len(d.inline_shapes)==27
for n,shape in enumerate(d.inline_shapes,1):
    stem=f'fig_{n:02d}'
    caption=(FIG/(stem+'_caption.txt')).read_text(encoding='utf-8').strip()
    assert caption
    with fitz.open(FIG/(stem+'.pdf'))as doc:height=doc[0].rect.height/72*2.54
    rid,part=d.part.get_or_add_image(str(FIG/(stem+'.png')))
    shape._inline.graphic.graphicData.pic.blipFill.blip.set(qn('r:embed'),rid)
    shape.width=Cm(16.3);shape.height=Cm(height)
    shape._inline.docPr.set('descr',f'图{n}：{caption}')
    paragraph=next(p for p in d.paragraphs if re.match(rf'^图\s+{n}\s+',p.text))
    replace(paragraph,f'图 {n}  {caption}','同步重构面板的图注；图号保持')
    paragraph.paragraph_format.keep_together=True;paragraph.paragraph_format.keep_with_next=False

changes={
104:'图2将原始30 m DEM、服务区需求、节点海拔与单点往返沿线最高地形配对呈现，地图圆点面积表示货箱数量。各空间图采用以O01为原点的WGS84局部东—北切平面显示投影，并使用相同地图范围和海拔色阶。图3按相同服务区顺序展示物资质量构成、首批与医疗共同形成的硬截止集合，以及真实截止时刻。空间上相近的节点仍可能穿越不同山脊，因此物理计算逐一读取原始DEM，不能以节点海拔或平面距离替代沿线最高地形。',
143:'图6以实际架次展示两类释放时刻。运输无人机与电池的任务占用均从准备装载开始，经过飞行、交接和返航；返航后的充电继续占用电池，使其可用时刻晚于无人机释放时刻。用两套资源编号和两套前驱关系描述复用，既允许更换满电电池后继续使用无人机，也阻止尚未充满的电池被提前再次调用。',
172:'Q1得到18架次、59.130 kWh和累计作业32776.016 s。全部80箱恰好交付一次，最大安全载荷与完整批次见附录。图8以不可拆货箱为单元展示正式组批，并列出所选机型与箱数；图9按最大预算占用降序比较质量、体积和可用能量占用及最紧相对余量，把组批结果与可行性依据联系起来。',
210:'图10(a)首先展示基础搜索保存的12个全准时候选，(b)给出42个已发现非支配候选的完整档案，(c)比较保持逐箱时限的4个完工上限偏好选项。表4列出正式选择及相邻架次数的基础搜索代表。每个架次数只保留实际访问到的候选，预算和邻域不相同，因而该表用于说明选点依据，不表示每个架次数均已达到最优。',
217:'图11至图13按机型展示正式路线，并分别连接多点卸货过程、架次属性和关键任务的地形剖面。A型执行12架次，B型和C型各执行6架次；重复的有序路线保留全部架次对应关系，完整路线与货箱分配见附录。三图采用相同显示投影、范围和尺度；三维航迹与阶段图由冻结路线、箱号和时刻确定性重放。机型选择需同时满足质量、体积、能源和时限，不能从单一额定载荷推断其任务数量。',
224:'图14展示实际交付的累计箱数，并分别检查80箱期望送达余量和31箱硬截止余量。累计曲线便于展示进度，但逐箱时限是否满足仍由箱号匹配后的差值判定。末箱交付时刻为5370.875 s，比运输返航完工早532.163 s；这段时间用于剩余返航，不能按交付结束时刻提前释放无人机。',
234:'独立验证器对全部保存候选逐箱重算卸货后载荷、交接完成时刻、能源与SOC，分别核对无人机占用和电池充电占用，并检查非支配关系。图15与图16在同一时间尺度下分别展示运输无人机与电池：任务占用包括准备、装载、飞行和交接，至返航释放无人机；电池其后仍需充满，才能投入下一任务。',
239:'图15与图16通过行标签识别机型，通过相同架次编号对应任务，条内颜色统一表示准备装载、飞行、交接与返航阶段。飞机返航后的空档可能来自电池尚未可用，也可能来自已确定的资源先后关系和截止约束；仅凭空档图形不判定因果。完整安排见附录表16及箱级对应表，基本搜索代表见表28。',
286:'图17将悬停位置、最紧采样状态以及同一状态下的直连、接入与回传链路对应。正式方案的1 s回放检查35061条状态，0.5 s回放检查69843条，均无未覆盖状态；两组最小余量均为0.090905647 dB，正文显示为0.091 dB。最紧状态位于column-019的4684.446 s，需由fast-relay-2保障。',
296:'图20把运输无人机、运输电池、中继无人机及组件占用放到共同时间轴。中继无人机占用延至返航后300 s周转结束；中继组件则按返航SOC和原两阶段充电公式确定充满时刻。每块组件仅用于一架次，补充电时长由固定方案确定性派生，不改变已选任务的组件复用可行性。最后返航后的充电与周转继续占用资源，但均不计入联合完工。',
337:'图23和图24分别比较两组、三组下资源优先与均衡偏好的服务区归属及累计运输工作量。资源优先的两组方案把S001与S004分在同一小组，其余13个服务区属于另一组；三组方案将S001与S004各自独立成组，其余13区仍同组。两种划分均未拆开多服务区不可拆分量。地图表示服务区成员归属，不表示连续地域边界；累计运输工作量也不等同于分组完工时间。'
}
for index,text in changes.items():
    p=d.paragraphs[index]
    assert '图' in p.text
    replace(p,text,'仅同步面板结构或阶段/资源释放说明；正式研究结果保留')

replace(d.paragraphs[289], '图18将完整运输任务、直连不足采样点的首末包络与指定中继完整服务窗对应。括号内不代表直连连续不足，图中也不表示通信切换日志。未参与搜索的0.25 s独立回放进一步检查139402条状态，未覆盖数为0，最小余量0.091 dB；这是额外采样证据，遮挡变化事件仍可能落在采样点之间。', '补足图18正文引用，去除不再对应重构面板的较优方式描述')
replace(d.paragraphs[312], '图22'+d.paragraphs[312].text, '补足图22的不可拆任务关系与正文的明确对应')
replace(d.paragraphs[353], d.paragraphs[353].text.replace('图中端点和数值容差', '图26中的端点和数值容差'), '补足图26临界阶梯的正文引用')

# Bind formula introductions to their display equations; preserve every math run.
layout_edits=[]
for index in [265,276,332]:
    d.paragraphs[index].paragraph_format.keep_with_next=True
    d.paragraphs[index].paragraph_format.keep_together=False
    layout_edits.append({'paragraph_index':index,'action':'Keep formula introduction with next display equation; text and math unchanged'})
# Keep the two demand headings legible without splitting the word or math object.
table=d.tables[31]
assert [c.text.strip() for c in table.rows[0].cells]==['资源','库存','需求','缺口','需求','缺口']
widths=[4.8,2.1,2.6,2.1,2.6,2.1]
for column,width in zip(table.columns,widths):column.width=Cm(width)
for row in table.rows:
    for cell,width in zip(row.cells,widths):cell.width=Cm(width)
layout_edits.append({'table_index':31,'action':'Redistribute widths only; keep total16.3cm and every cell/mathematical object unchanged','widths_cm':widths})
# The five sensitivity scenarios form one small table, not a one-row continuation.
table=d.tables[34]
assert table.rows[0].cells[0].text=='储备 / %' and len(table.rows)==6
for row in table.rows[:-1]:
    for cell in row.cells:
        for p in cell.paragraphs:p.paragraph_format.keep_with_next=True
layout_edits.append({'table_index':34,'action':'Keep header and all five scenario rows together; contents unchanged'})

# Drop obsolete media relationships, leaving only actually referenced images.
used={x.get(qn('r:embed')) for x in d._element.xpath('//a:blip')}
removed=[]
for rid,rel in list(d.part.rels.items()):
    if rel.reltype==RT.IMAGE and rid not in used:
        d.part.drop_rel(rid);removed.append(rid)
assert any('TOC ' in (x.text or '') for x in d._element.xpath('//w:instrText'))
d.save(FINAL)
(W/'word_edits.json').write_text(json.dumps({'edits':edits,'layout_edits':layout_edits,'obsolete_image_relationships_removed':len(removed)},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'file':str(FINAL),'figures':27,'paragraph_edits':len(edits),'obsolete_media_removed':len(removed)},ensure_ascii=False))
