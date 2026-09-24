# 可复现论文交付

正文入口为 `main.tex`。本论文区分 Q1 精确组批、Q2 启发式候选和 Q3 固定离散方案下的时序最优性。通信采样不是连续安全证明；局限已写入摘要、正文和结论。

## 结构

```text
paper/main.tex              匿名论文入口
paper/sections/              摘要、正文、附录
paper/references.tex         七条已核验参考文献
paper/tables/                自动三线表、跨页表与数字宏
paper/data/                  场景诊断、统一数字与工作簿数据
paper/figure_contracts.json  九张图的主张、层级与边界
paper/figure_manifest.csv    图、来源、脚本、章节及来源 SHA256
paper/fonts/                字体及许可
paper/reports/              验证、一致性、科学与页面终审
scripts/figures/             原创 Matplotlib 图与公共视觉配置
outputs/figures/             PDF / SVG / 300 dpi PNG
outputs/paper/main.pdf       论文 PDF
```

大型派生通信轨迹、展示 DEM 网格、字体与渲染文件不进 Git，完整交付 ZIP 含这些文件。原始赛题、工作簿、DEM 和官方模板原样保留。

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

XeLaTeX 另需 TeX Live/MiKTeX 中的 ctex、xeCJK、zhnumber、Fandol 及常用数学/表格包。本次使用 ctex 2.5.10；须与发行版 expl3 匹配。实际 Python 版本见 `environment.json`。正文使用 Fandol 宋/黑体和 Latin Modern Roman；科研图用 Noto Sans SC TrueType，SVG 转字形路径。字体下载受 SHA256 校验。

全流程无随机仿真；没有虚构置信区间。绘图前核对全部正式结果摘要，拒绝混用新结果和旧诊断。图形在临时目录成功生成后发布；XeLaTeX 失败保留上一份完整 PDF 并输出错误日志。构建末尾显式嵌入 Adobe GB1 Unicode 映射，逐页检查中文可读性及全部字体嵌入；验证失败不发布。请使用上述构建脚本：单独调用 XeLaTeX 会跳过此兼容性处理与门禁。

## 官方 Excel

表格生成器同时输出 `data/workbook_payload.json`。导出依赖 Node.js 和 `@oai/artifact-tool`，保留官方六张表及表头，另加 Q3 运输、逐箱交付两张必要明细。该库不属于 Python 环境，仅安装 Python 依赖不能执行 Excel 导出。交付包包含已核验的 Excel 和可审计 JSON/CSV。

```bash
node scripts/export_submission.mjs /path/to/结果提交模板.xlsx paper/data/workbook_payload.json outputs/submission export
python scripts/verify_paper.py --workbook outputs/submission/D_results.xlsx --template /path/to/结果提交模板.xlsx --rebuild-figures
```

验证只读 Excel。`--rebuild-figures` 重画全部九图并比较相同环境、相同输入下 PNG 的 SHA256；计算来源是 CSV，Excel 是官方格式的静态结果视图。

## 状态与提交前信息

见 `reports/FINAL_AUDIT.md`、`VALIDATION.md`、`CONSISTENCY.md`、`FIGURE_QC.md` 和 `CITATIONS.md`。PDF 为匿名主体；身份封面及本次 AI 精确版本、发布日期须由参赛队提供。不得把候选计划或采样通过理解为实际飞行安全认证。

2026-09-24 已修复旧版中文乱码，详见 `reports/FONT_COMPATIBILITY.md`。正文与九张科研图保持原排版，修复后的 19 页渲染像素与原稿相同。
