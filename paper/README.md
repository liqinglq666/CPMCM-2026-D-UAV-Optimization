# 论文与科研图重构

本轮在已完成的12图重构基础上，修复 main `2a98f09` 的Q3加密通信缺口，重新计算Q3/Q4并同步论文。官方物理公式与参数不变；Q1/Q2正式决策不变。

**已修复0.5 s回放中的通信反例。** 最终1 s、0.5 s及独立0.25 s回放均无未覆盖状态，最小余量0.02877762 dB。图8、9、12、摘要、正文和Q4继承结果均已更新。采样检查通过仍不构成连续时间证明，详见 `reports/FINAL_AUDIT.md`。

## 重建

先按仓库README放置官方数据，再执行：

```bash
python -m pip install -r requirements-paper-lock.txt
python scripts/setup_paper_fonts.py
python run_all.py
python scripts/replay_communication.py --out results/communication_replay.json
python scripts/analyze_paper.py
python scripts/build_paper.py --compatible
```

默认 `analyze_paper.py` 会在加密通信失败时抛错；当前正常构建不使用允许失败选项；历史负余量保留为回归反例。Q2/Q3上游搜索使用固定随机种子；派生诊断和绘图无随机步骤。所有图先验证正式结果和派生文件SHA256，拒绝混用旧结果。

使用Python3.12的记录依赖环境。论文构建还需XeLaTeX（ctex、xeCJK、Fandol、unicode-math）、Ghostscript；字体为Noto Sans SC、SIL OFL许可。主输出：

- `outputs/paper/main.pdf`：可检索、字体嵌入的论文。
- `outputs/paper/main-compatible.pdf`：文字矢量转曲兼容版，无法搜索复制；真实DEM背景仍为栅格。
- `outputs/figures/fig*.{pdf,svg,png}`：12图、三格式、300 dpi PNG。
- `outputs/figure-qa/`：每图160 mm宽度、字号和画布裁切检查。
- `figure_contracts.json`、`figure_manifest.csv`：主张、来源、脚本与来源摘要。

## 图级检查

图2/8直接使用原DEM像元及轻量显示晕渲。仅高程背景允许栅格嵌入，坐标、轮廓、轨迹、数据点和文字为矢量。图6黄色星号是当前23架次正式方案；22架次只作对照。图9保留20 s展示窗内最小值的原始时刻，不平滑、不改变通信突变。图11通过完整货箱子集的储备临界DP补算阶梯，并与原Q1求解器逐区间交叉核对，不用五个场景插值。

`verify_paper.py` 核查来源、数字宏、图序、PNG重现、A4宽度、字号、目录、引用和字体。其PASS表示图文数据一致性；通信可行性另由结果验证器与三组独立回放证明至采样层面。详见当前 `reports/FIGURE_QC.md`、`reports/consistency.json`；历史日志不可替代本轮证据。

官方工作簿导出入口保持原有 `scripts/export_submission.mjs`，自动表格生成器仍生成最新 `data/workbook_payload.json`。本轮主要交付论文和图件；临时工作簿仅用于与官方模板逐单元格核验。
