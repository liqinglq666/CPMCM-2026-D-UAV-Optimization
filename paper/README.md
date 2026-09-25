# 论文与科研图重构

本轮在已合并最快方案基础上研读用户提供的62页论文，冻结Q1及官方DEM，新增Q2限时节能偏好、Q3连续区间数值核验与Q4均衡分区。正式方案与证明边界见 `reports/FINAL_AUDIT.md` 及 `../docs/external_benchmark_algorithm_audit.md`。


## 重建

先按仓库README放置官方数据，再执行：

```bash
python -m pip install -r requirements-paper-lock.txt
python scripts/setup_paper_fonts.py
python run_all.py
python scripts/diagnose_transport_load.py
python scripts/diagnose_relay_cover.py
python scripts/replay_communication.py --out results/communication_replay.json
python scripts/analyze_paper.py
python scripts/build_paper.py --compatible
```

默认 `analyze_paper.py` 会在加密通信失败时抛错；当前正常构建不使用允许失败选项；历史负余量保留为回归反例。Q2/Q3邻域搜索使用固定随机种子，整数主问题受时间预算限制并保留明确的离散热启动；派生诊断和绘图无随机步骤。所有图先验证正式结果和派生文件SHA256，拒绝混用旧结果。

使用Python3.12的记录依赖环境。论文构建还需XeLaTeX（ctex、xeCJK、Fandol、unicode-math）、Ghostscript；字体为Noto Sans SC、SIL OFL许可。主输出：

- `outputs/paper/main.pdf`：可检索、字体嵌入的论文。
- `outputs/paper/main-compatible.pdf`：文字矢量转曲兼容版，无法搜索复制；真实DEM背景仍为栅格。
- `outputs/figures/fig*.{pdf,svg,png}`：12图、三格式、300 dpi PNG。
- `outputs/figure-qa/`：每图160 mm宽度、字号和画布裁切检查。
- `figure_contracts.json`、`figure_manifest.csv`：主张、来源、脚本与来源摘要。

## 图级检查

图2/8直接使用原DEM像元及轻量显示晕渲。仅高程背景允许栅格嵌入，坐标、轮廓、轨迹、数据点和文字为矢量。图6黄色星号是当前完工时间偏好的正式方案；其余架次数是搜索预算不同的代表候选。图9保留20 s展示窗内最小值的原始时刻，不平滑、不改变通信突变。图11通过完整货箱子集的储备临界DP补算阶梯，并与原Q1求解器逐区间交叉核对，不用五个场景插值。

`verify_paper.py` 核查来源、数字宏、图序、PNG重现、A4宽度、字号、目录、引用和字体。其PASS表示图文数据一致性；通信另由结果验证器的三组采样及连续区间数值证书核验；浮点保护量不等于精确算术形式化证明。详见当前 `reports/FIGURE_QC.md`、`reports/consistency.json`；历史日志不可替代本轮证据。

官方工作簿导出入口保持原有 `scripts/export_submission.mjs`，自动表格生成器仍生成最新 `data/workbook_payload.json`。本轮主要交付论文和图件；临时工作簿仅用于与官方模板逐单元格核验。
