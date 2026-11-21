# 仓库导航与清理边界

2026-11-21 整理。本文是文件入口及维护约定，不改变比赛的模型、数据、论文或验收结论。

## 从哪里开始

| 任务 | 唯一优先入口 | 说明 |
| --- | --- | --- |
| 查看正式参赛论文 | [submission/D26105580028.pdf](../submission/D26105580028.pdf) | 唯一正式提交的 64 页 PDF；不要用历史 65 页版本替代 |
| 查看提交材料与核验 | [submission/FINAL_SUBMISSION_CHECK.md](../submission/FINAL_SUBMISSION_CHECK.md) | PDF、官方结果工作簿、RAR 与摘要、上传说明 |
| 了解正式模型及复算 | [README.md](../README.md) / `src/` / `config/` / `results/` | 运行入口是根目录的 `run_q1.py` 至 `run_q4.py` 与 `run_all.py` |
| 校验结果 | `python -m pytest -q` 和 `python scripts/validate_results.py` | 后者需要对应的官方原始输入；缺失时不能宣称完成全量核验 |
| 了解冻结算法 | [docs/FROZEN_RELEASE.md](FROZEN_RELEASE.md) | 冻结分支 `freeze/2026-09-25-final` 不移动 |
| 编辑、复绘历史 65 页论文 | [paper/final_v2/README.md](../paper/final_v2/README.md) | 27 图、Word、历史 PDF、逐图来源和哈希；不是正式提交 PDF |
| 查看更早论文 | [paper/README.md](../paper/README.md) | `paper/final/`、历史 LaTeX 都是可追溯旧版本 |
| 检查仓库重复与大文件 | `python scripts/check_repo_hygiene.py` | 只读取本地 Git 已跟踪文件，不修改或删除任何内容 |

## 清理检查结论

2026-11-21 检查 `main` 工作树：987 个文件、当前文件内容共 231,600,550 字节（约 221 MiB）；`paper/` 609 个文件、约 191 MiB，`archive/` 117 个文件、约 14 MiB。这里是当前树的文件体积，不是 Git 提交历史占用或远端仓库结算体积。

**看起来重复，并不等于可以删除。** 例如 `paper/figure_data_v2/` 与 `paper/final_v2/figures/` 中相同的 `fig_*_data.json`，以及 `q2_fig*_data.json` 的别名，属于已记录的历史图形包。其文件路径与摘要包含在 `paper/final_v2/manifest.json` 中；删除或改写会使 `scripts/figures_v2/verify_bundle.py` 的完整性验证失败。字体、历史 Word/PDF、审计记录与版本备份也可能参与复现及证据链。

### 维护原则

1. **保留** `submission/`、`src/`、`config/`、`results/`、`data/`、`archive/`、`paper/final/`、`paper/final_v2/` 和已存在的正式审计记录；未经逐条核对不删除、不移动。
2. **禁止动冻结版本**：不覆盖比赛正式 PDF/Excel/RAR，不修改模型或已核实数值，不重新计算后悄悄替换既有结果，不移动 `freeze/2026-09-25-final`。
3. **避免新增噪声**：本地缓存、编辑器交换文件、Office 锁文件、构建目录和新生成的临时产物遵守 `.gitignore`；官方大体积原始输入留在 `data/raw/`，不随意提交。
4. **先查证，再精简**：用 `scripts/check_repo_hygiene.py` 复核重复文件，定位引用、manifest 哈希与复现脚本；确有可删除候选时，在独立分支验证，再审查合并。
5. **体积说明**：普通 Git 删除提交不会移除历史版本中的大文件。若需要真正缩减克隆历史体积，涉及历史改写及其他协作者，必须单独评估，不应作为日常“清理”自动执行。

## 本次安全整理范围

只改文档导航、`.gitignore` 和新增只读审查脚本。不删除已有资料，不修改冻结校验清单，不提交重新计算的数据。后续若决定精简历史成果，应先标定保留的正式版与完整性验证范围，经过检查再另行提交。
