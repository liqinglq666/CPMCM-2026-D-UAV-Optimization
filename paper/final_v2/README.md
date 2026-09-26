# 科研图终稿重构 v2

当前论文为 [65 页 PDF](manuscript.pdf)，并提供 [可编辑 Word](manuscript.docx)。自动目录、27 幅图、170 个原生数学表达式和全部方案附录保留。研究输入版本为 `bec20f1536458db47bac583c309c7b30637cb67a`；本次编辑以 `e71cdb13c0969a28d78f349e1ce79047e731e954` 的 Word 为基准。

## 图形重构

27 图均按具体分析问题重构，交付矢量 PDF、保留文字对象的 SVG 和 600 dpi PNG。统一宽度 16.3 cm、必要文字不小于 8 pt，使用一致的机型、资源阶段、中继和分组编码。地图共用原始 DEM、显示投影、范围、高程色阶和比例尺；三维图只展示真实轨迹或链路，并标注显示夸张。

载荷图保留不可拆箱号，候选图分开基础候选、保存的非支配档案和完工偏好；资源图展示准备、飞行、交接、返航及充电/周转。通信图区分直连不足采样点、完整服务窗口与连续区间数值下界。分区图同时展示两类偏好与分类资源缺口。

每图的数据、字段、筛选、连接键、派生公式、图注、源码和 SHA-256 见 [逐图清单](figure_manifest.csv) 及 `figures/fig_NN_spec.json`。真实输入和计算代码没有变动，没有运行优化器替换正式方案。

## 检查与重建

```bash
python scripts/figures_v2/verify_bundle.py
python -m pip install -r paper/final_v2/requirements.txt
python scripts/figures_v2/build_figures.py --raw /path/to/official_D --out outputs/figures_v2 --qa outputs/figure_qa_v2
# 可选：先从冻结箱号、路线、实体和时刻重放 Q2/Q3，再制图
python scripts/figures_v2/build_figures.py --raw /path/to/official_D --out outputs/figures_v2 --replay
```

也可用 `UAV_DATA_ROOT`、`UAV_FIGURE_OUT`、`UAV_FIGURE_QA`。原始 D 题附件不重复提交仓库；完整解压后保留原目录和文件名。重绘用到 TIF、MAT、官方工作簿及既有 CSV/JSON。默认仅读取已保存的绘图重放数据；`--replay` 仅确定性重放固定方案，不执行搜索优化。

```bash
python scripts/figures_v2/build_manuscript.py --out outputs/manuscript_v2.docx
```

Word 构建读取 `UAV_FIGURE_OUT`，默认 `outputs/figures_v2`，保留上一版 `paper/final/manuscript.docx` 作为编辑基准。在安装 Microsoft Word 的 Windows/PowerShell 7 环境更新目录并导出：

```powershell
./scripts/figures_v2/export_word.ps1 -DocumentPath outputs/manuscript_v2.docx -PdfPath outputs/manuscript_v2.pdf
```

字体在 `paper/final/fonts/`，附原许可。重建后应重新检查实际 PDF 页面；PDF/Word 的创建时间等元数据可能使二进制摘要变化。当前验收文件原字节已保存，不需要为阅读而重建。

## 核验范围

整套 27 图在独立目录复绘，PNG 像素和逐图数据相同。全部单图实际查看彩色/灰度 PDF 预览，全文 65 页实际逐页查看；170 个数学表达式及表格逐单元格与编辑基准对照。正文仅改图注、面板解释和缺漏图号引用，方法归属与热启动来源保留。完整记录见 `reports/`。

Q2/Q3 的阶段、交付和通信由原物理引擎确定性重放；另一次审计独立检查轨迹几何、全部占用/归属以及部分链路损耗，并明确其覆盖范围。已有连续区间证书为带浮点保护的数值核验；此次未新增统计实验、实飞、全局最优性证明或精确算术证明。灰度预览中部分很短的资源阶段明度相近，任务编号、边界及充电/周转纹理仍保留，颜色版可完整区分阶段。

`CHECKSUMS.txt` 是当前文件完整性记录，不代表已上传比赛系统或登记 MD5。上一版 65 页文件仍保留在 `paper/final/` 供追溯。
