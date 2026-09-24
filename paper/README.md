# 可复现论文交付

正文入口为 `main.tex`。本论文区分 Q1 精确组批、Q2 启发式候选、Q3 固定离散方案下的时序最优性和 Q4 固定计划的精确分区。通信采样不是连续安全证明；局限已写入摘要、正文和结论。

## 结构

```text
paper/main.tex              匿名论文入口
paper/sections/              摘要、正文、附录
paper/references.tex         七条已核验参考文献
paper/tables/                自动三线表、跨页表与数字宏
paper/data/                  场景诊断、统一数字与工作簿数据
paper/figure_contracts.json  十二张图的主张、层级与边界
paper/figure_manifest.csv    图、来源、脚本、章节及来源 SHA256
paper/fonts/                字体及许可
paper/reports/              验证、一致性、科学与页面终审
scripts/figures/             原创 Matplotlib 图与公共视觉配置
outputs/figures/             PDF / SVG / 300 dpi PNG
outputs/paper/main.pdf       论文 PDF
```

大型派生通信轨迹、原始 DEM 裁剪网格、字体与渲染文件不进 Git，完整交付 ZIP 含这些文件。原始赛题、工作簿、DEM 和官方模板原样保留。

## 重建

在项目根目录执行；先按主 README 放置官方输入。支持 Python 3.11/3.12。

```bash
python -m pip install -r requirements-dev.txt -r requirements-paper.txt
python run_all.py
python -m pytest -q
python scripts/analyze_paper.py
python scripts/setup_paper_fonts.py
python scripts/build_paper.py
```

XeLaTeX 另需 TeX Live/MiKTeX 中的 ctex、xeCJK、zhnumber、Fandol、unicode-math、Latin Modern Math 及常用数学/表格包。本次使用 ctex 2.5.10；须与发行版 expl3 匹配。实际 Python 版本见 `environment.json`。正文使用 Fandol 宋/黑体和 Latin Modern Roman，数学使用 Unicode Latin Modern Math；科研图用 Noto Sans SC TrueType，SVG 转字形路径。字体下载受 SHA256 校验。

全流程无随机仿真；没有虚构置信区间。绘图前核对全部正式结果摘要，拒绝混用新结果和旧诊断。图形在临时目录成功生成后发布；XeLaTeX 失败保留上一份完整 PDF 并输出错误日志。构建末尾显式嵌入 Adobe GB1 Unicode 映射，逐页检查中文可读性及全部字体嵌入；验证失败不发布。请使用上述构建脚本：单独调用 XeLaTeX 会跳过此兼容性处理与门禁。

## 官方 Excel

表格生成器同时输出 `data/workbook_payload.json`。导出依赖 Node.js 和 `@oai/artifact-tool`，保留官方六张表及表头，另加 Q3 运输、逐箱交付两张必要明细。该库不属于 Python 环境，仅安装 Python 依赖不能执行 Excel 导出。交付包包含已核验的 Excel 和可审计 JSON/CSV。

```bash
node scripts/export_submission.mjs /path/to/结果提交模板.xlsx paper/data/workbook_payload.json outputs/submission export
python scripts/verify_paper.py --workbook outputs/submission/D_results.xlsx --template /path/to/结果提交模板.xlsx --rebuild-figures
```

验证只读 Excel。`--rebuild-figures` 重画全部十二图并比较相同环境、相同输入下 PNG 的 SHA256；计算来源是 CSV，Excel 是官方格式的静态结果视图。

## 状态与提交前信息

见 `reports/FINAL_AUDIT.md`、`VALIDATION.md`、`CONSISTENCY.md`、`FIGURE_QC.md` 和 `CITATIONS.md`。PDF 为匿名主体；身份封面及本次 AI 精确版本、发布日期须由参赛队提供。不得把候选计划或采样通过理解为实际飞行安全认证。

历史字体映射修复见 `reports/FONT_COMPATIBILITY.md`。它未解决用户实际预览器的全部显示问题；当前重构版继续保留矢量兼容输出，不能用历史 19 页证据替代新稿检查。

## 字体无关的显示兼容版（2026-09-24）

用户反馈表明，补齐 ToUnicode 后其实际预览器仍丢失中文。原生文字版的该环境兼容性尚未解决。因此额外提供全矢量转曲版：

```bash
python scripts/build_paper.py --compatible
# 已有验证过的正文 PDF 时，只需转换，不必重新计算或排版：
python scripts/export_compatible_pdf.py
```

需要安装 Ghostscript（Linux/macOS 的 `gs`，Windows 的 `gswin64c` 或 `gswin32c`）。
`outputs/paper/main-compatible.pdf` 是显示/打印兼容版，字形转为矢量轮廓，零字体资源、零页面栅格图；当前页数见终审报告，保留正文排版和科研图形。正文无法直接搜索、复制或被屏幕阅读器读取。
`outputs/paper/main.pdf` 保留文字与 Unicode 映射，供提取核验；LaTeX 源文件继续用于编辑。数值验证器检查此原生文字版，兼容版另外检查页面与图形。
详见 `reports/OUTLINED_COMPATIBILITY.md`，不能把某个渲染器上的 PASS 当成用户端已解决的证据。

## 本轮结构重构

详细目录及每节的论证任务见 `blueprint.md`；重写前发现见 `reports/STRUCTURE_AUDIT.md`。Q4 现位于第 7 节，敏感性和验证分别位于第 8、9 节。图形文件 ID 已按 01–12 的正文顺序统一，显示编号随引用顺序自动生成。

终稿加入摘要后的自动目录（两级标题、参考文献、附录），保留页码与内部跳转。12 图统一采用用户指定的语义色板；A/B/C 机型使用圆/方/三角及实线/虚线/点划线，货类与资源以纹理补充灰度识别。Q1 组批的相对最紧约束统计自动生成，不冒充最低架次数证明。

`analyze_paper.py` 额外保存完整 0.5 s 通信状态，并记录八个派生数据文件的 SHA256。绘图和表格生成前同时核对正式结果与诊断摘要。`verify_paper.py` 验证图形清单来源、细化采样最紧状态、目录条目页码和链接，以及图形顺序、表格、引用、中文字体。目录排版分页不硬写正文页码；三次 XeLaTeX 更新交叉引用。

旧图已从绘图入口和交付包移除；旧审计运行日志按历史证据保留，不能代替当前 `reports/FINAL_AUDIT.md` 的验收。
