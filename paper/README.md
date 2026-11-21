# 论文入口

**唯一正式提交版本**：[64 页 PDF](../submission/D26105580028.pdf)，详见 [正式论文说明](FINAL_PAPER.md) 及 [提交终检报告](../submission/FINAL_SUBMISSION_CHECK.md)。

2026-11-21 为精简 `main` 的工作树，历史论文编辑资产已从主分支移至
[backup/pre-slim-20261121](https://github.com/liqinglq666/CPMCM-2026-D-UAV-Optimization/tree/backup/pre-slim-20261121)：

- `paper/final/`：上版 65 页论文、Word、图件、字体、校验日志。
- `paper/final_v2/`：历史 65 页论文与 27 幅科研图，包含所有 SVG/PDF/PNG、图级数据和 checksum/manifest。
- `paper/figure_data_v2/`：制图中间数据和别名。

这三套旧文件**没有发生科学内容上的删改**；备份仍按原有目录路径保存。在 `main` 运行旧构建脚本之前，需要先恢复这些目录，方法见 [恢复与清理指南](../docs/REPOSITORY_GUIDE.md)。

主分支仍保留 `paper/main.tex`、`paper/sections/`、`paper/data/`、`paper/fonts/` 等体积较小的历史研究/LaTeX 来源文件，以及 `src/`、`results/` 和正式提交流程。旧 LaTeX 路线不能替代已正式提交的 64 页 PDF。

正式比赛 PDF、Excel 和 RAR 可运行 `python scripts/verify_submission_integrity.py` 直接验证完整字节摘要；此检查无需原始 DEM 数据，也不需要历史论文 Word/图包。
