# 论文与科研图重构

本轮基于算法优化合并后的 main `6772cb9`，重绘12张科研图并同步论文。算法内核、官方输入和正式 results 保持不变。

**新的科学发现：Q3在1 s采样下通过，但0.5 s独立回放发现1个未覆盖状态，最小链路余量−0.154251 dB。当前方案不能声称满足全过程通信。** 图8、9、12和摘要、正文、结论均如实呈现；Q4仍是固定该输出的条件配置分析。详见 `reports/FINAL_AUDIT.md`。

## 重建

先按仓库README放置官方数据，再执行：

```bash
python -m pip install -r requirements-paper-lock.txt
python scripts/setup_paper_fonts.py
python scripts/analyze_paper.py --allow-diagnostic-failures
python scripts/build_paper.py --compatible
```

默认 `analyze_paper.py` 会在加密通信失败时抛错；上述显式选项只允许导出失败证据，不改变正式结果、物理判据或失败状态。Q2/Q3上游搜索使用固定随机种子；派生诊断和绘图无随机步骤。所有图先验证正式结果和派生文件SHA256，拒绝混用旧结果。

使用Python3.12的记录依赖环境。论文构建还需XeLaTeX（ctex、xeCJK、Fandol、unicode-math）、Ghostscript；字体为Noto Sans SC、SIL OFL许可。主输出：

- `outputs/paper/main.pdf`：可检索、字体嵌入的论文。
- `outputs/paper/main-compatible.pdf`：文字矢量转曲兼容版，无法搜索复制；真实DEM背景仍为栅格。
- `outputs/figures/fig*.{pdf,svg,png}`：12图、三格式、300 dpi PNG。
- `outputs/figure-qa/`：每图160 mm宽度、字号和画布裁切检查。
- `figure_contracts.json`、`figure_manifest.csv`：主张、来源、脚本与来源摘要。

## 图级检查

图2/8直接使用原DEM像元及轻量显示晕渲。仅高程背景允许栅格嵌入，坐标、轮廓、轨迹、数据点和文字为矢量。图6黄色星号是当前23架次正式方案；22架次只作对照。图9保留20 s展示窗内最小值的原始时刻，不平滑、不改变通信突变。图11通过完整货箱子集的储备临界DP补算阶梯，并与原Q1求解器逐区间交叉核对，不用五个场景插值。

`verify_paper.py` 核查来源、数字宏、图序、PNG重现、A4宽度、字号、目录、引用和字体。其PASS只表示图文数据一致性，不代表通信加密可行。详见当前 `reports/FIGURE_QC.md`、`reports/consistency.json`；历史日志不可替代本轮证据。

官方工作簿导出入口保持原有 `scripts/export_submission.mjs`，自动表格生成器仍生成最新 `data/workbook_payload.json`。本轮主要交付论文和图件；临时工作簿仅用于与官方模板逐单元格核验。
