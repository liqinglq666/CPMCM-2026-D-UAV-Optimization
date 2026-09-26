# 当前正式论文：65 页、27 幅图

[论文 PDF](manuscript.pdf) 是当前交付正文；[Word 源文件](manuscript.docx) 用于后续编辑。PDF 为 Microsoft Word 刷新自动目录后导出的可检索版本，包含摘要、两页目录、正文、参考文献和附录。2026-09-26 的图文重构保留冻结研究结果，不重新运行优化。

## 文件与来源

- `figures/`：27 幅图的 SVG、嵌入字体 PDF、600 dpi PNG，以及逐图数据、图注、字段和来源说明。图宽 16.3 cm；7 张空间图使用同一原始 DEM、地图范围和海拔色阶。
- `src/`：当前制图程序和仓库相对路径适配。只读取已保存结果与原始地理数据，不调用优化器。
- `fonts/`：实际使用的静态 TrueType 中文字体、DejaVu 字体及许可。SVG 保留可编辑文字；编辑时应加载相应字体。
- `reports/`：原始输入、地理数据、结果保持和逐页版面检查记录。历史报告原样保存，其路径映射见下文。
- `baseline/`：图 17–27 改绘 DEM 前的数据视图，用于核对任务数据保持。
- `manifest.json`：本目录交付文件与冻结研究来源的 SHA-256 清单；`CHECKSUMS.txt` 记录论文摘要。

论文交付目录禁止 Git 换行转换，以保持文件原字节。冻结研究来源清单同时记录本次 Windows 工作副本及冻结提交 Git 对象的摘要；校验仅接受这两个已知版本，兼容仓库既有的文本换行转换。

研究来源为提交 `bec20f1536458db47bac583c309c7b30637cb67a`。论文沿“安全运输能力—可执行调度—通信保障—独立资源配置”展开。Q1 保留 18 架次、59.130 kWh、累计作业 32776.016 s；Q2 正式方案保留 24 架次、65.566 kWh、运输返航完工 5903.038 s、80 箱按期交付；Q2 节能备选保留 22 架次、7070.178 s、63.370 kWh。Q3 保留 24 个运输架次、3 个中继架次、69.141 kWh、联合完工 5931.735 s；采样最小通信余量约 0.091 dB、连续区间保守下界 0.009866 dB、硬截止余量 266.282 s、最低运输返航 SOC 20.10%。Q4 固定 Q3 任务与时序，资源优先缺口为 1/3，原有均衡条件下为 5/9。

## 校验现有交付

下列命令只校验文件和 Word 结构，标准库即可运行：

```text
python paper/final/src/verify_bundle.py
python paper/final/src/verify_bundle.py --raw-root "D题原始附件解压目录"
```

已完成的检查包括 703 项编辑与数据保持检查、271 项图表数据及媒体检查，以及全部 65 页的渲染目视检查。详细证据保留在 `reports/`。这些是本版本的编辑核对，不能当作新优化、实飞验证或连续时间精确算术证明。部分中间报告保留 `pending` 字段；最终逐页检查记录和逐项汇总记录给出其后完成的验收，不覆盖历史记录。

## 重新绘制

完整解压用户提供的原始 D 题 ZIP，保持目录与文件名。默认使用仓库 `data/raw/`，也可设置 `UAV_DATA_ROOT`。按仓库既定策略不提交原始赛题附件；`reports/raw_manifest.json` 提供 19 个原始文件的指纹。

```text
python -m pip install -r paper/final/requirements.txt
python paper/final/src/build_figures.py
```

PowerShell 指定数据目录示例：

```powershell
$env:UAV_DATA_ROOT = 'D:\比赛\D题原始附件'
python paper/final/src/build_figures.py
```

生成文件位于忽略版本控制的 `outputs/final-paper/figures/`，检查预览位于 `outputs/final-paper/review/`。可用 `UAV_PAPER_BUILD` 改变生成目录。程序先验证原始文件与冻结结果指纹，再重绘 27 图，并对全部绘图数据及 PNG 像素进行比较。数值不一致会报错；依赖或字体差异可能使像素不同，报告会明确记录。重绘不会覆盖本目录已检查的论文或图件，不会重算并替换既有方案。再编辑后的版面需重新检查。

## Word 编辑与 PDF 输出

可直接编辑 `manuscript.docx`。其 170 个公式对象、正文、表格和自动目录可编辑；本目录不声称旧 LaTeX 源能够生成此版本。制图代码生成 SVG/PDF/PNG 后，在 Word 中替换相应图片。使用 Microsoft Word 刷新目录、分页与交叉引用后导出 PDF。

仓库提供可选的 Windows Word 自动导出脚本。先在 `outputs/` 创建工作副本，避免无意改变已经核对的正式文件：

```powershell
New-Item -ItemType Directory -Force outputs/final-paper | Out-Null
Copy-Item paper/final/manuscript.docx outputs/final-paper/manuscript.docx
powershell -ExecutionPolicy Bypass -File paper/final/src/export_word.ps1 -DocumentPath outputs/final-paper/manuscript.docx -PdfPath outputs/final-paper/manuscript.pdf
```

正文使用宋体、黑体和 Times New Roman。更换办公软件或缺失字体可能改变分页。正式提交前应检查实际导出的 PDF，并重新计算该文件摘要；当前同步没有向比赛系统提交文件。

## 历史路径映射

图表数据、图形、原始验收记录原样入库，保留其原始哈希和记录中的工作区路径。历史路径用于追溯，不是要求在本机创建相同绝对目录：

| 记录中的位置 | 本仓库位置或含义 |
|---|---|
| `work/team_repo/` | 仓库根目录，冻结研究来源提交见上文 |
| `outputs/原始数据重绘图/` | `paper/final/figures/` |
| `work/raw_rebuild/fonts/` | `paper/final/fonts/` |
| `work/raw_rebuild/` 下检查 JSON/MD | `paper/final/reports/` |
| `work/raw_rebuild/` 下制图程序 | `paper/final/src/`，仅作路径适配 |
| `work/raw_input/` | 用户原始附件目录，由 `UAV_DATA_ROOT` 指定 |
| `outputs/终稿科研图/fig_17…27_data.json` | `paper/final/baseline/` |
| 渲染页面 PNG、旧版 Word 与原始素材 ZIP | 保留在本地交付包，未重复纳入仓库 |

旧的 35 页 LaTeX 论文与 12 图流水线仍保留在 `paper/`，用于研究版本追溯；当前阅读、编辑和提交入口均以本目录为准。
