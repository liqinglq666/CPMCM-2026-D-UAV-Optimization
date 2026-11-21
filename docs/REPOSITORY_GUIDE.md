# 仓库导航 · 瘦身版（2026-11-21）

这个仓库的 `main` 用于**保留正式比赛提交、模型源码、已接受结果和测试**，历史 Word/PDF 制作包放在只读留存用的 Git 分支中。清理不改变正式数值、PDF 字节或算法结果。

## 正式成果（main）

| 内容 | 入口 |
| --- | --- |
| 64 页唯一正式论文 | [submission/D26105580028.pdf](../submission/D26105580028.pdf) |
| 最终提交 Excel | [submission/结果提交模板.xlsx](../submission/%E7%BB%93%E6%9E%9C%E6%8F%90%E4%BA%A4%E6%A8%A1%E6%9D%BF.xlsx) |
| RAR 正式附件 | [submission/D26105580028.rar](../submission/D26105580028.rar) |
| 最终校验报告和哈希 | [submission/FINAL_SUBMISSION_CHECK.md](../submission/FINAL_SUBMISSION_CHECK.md) · [CHECKSUMS.txt](../submission/CHECKSUMS.txt) |
| 完整算法与输出 | `src/`, `config/`, `results/`, `run_q*.py`, `run_all.py` |
| 运行测试 | `tests/`、`.github/workflows/tests.yml` |
| 独立验证正式提交文件 | `python scripts/verify_submission_integrity.py` |
| 只读冗余/文件体积检查 | `python scripts/check_repo_hygiene.py` |

`archive/` 的历史 baseline 不清理：部分通信回归测试读取 `archive/baseline-2a98f09/`，删除会破坏现有测试的证据来源。

## 已移出 main、但保留在完整备份的目录

备份分支 [backup/pre-slim-20261121](https://github.com/liqinglq666/CPMCM-2026-D-UAV-Optimization/tree/backup/pre-slim-20261121) 固定为瘦身前主分支提交
`c12a898c09995d943707c5c8c2b7cffcd978a1b1`，已核对它与当时 `main` 完全一致。

| 目录 | 当前文件体积（约） | 原有用途 |
| --- | ---: | --- |
| `paper/final/` | 71.9 MiB | 65 页上一版 Word/PDF、成套图形、字体与基线 |
| `paper/final_v2/` | 73.9 MiB | 65 页历史 Word/PDF、27 图的 PDF/SVG/PNG、原 manifest 和图形审计 |
| `paper/figure_data_v2/` | 44.1 MiB | 历史图形的派生数据、同内容别名及回放视图 |

这三套文件的校验清单、内容与原路径均可通过备份分支找回。它们是**历史编辑与可复现资产**，不是唯一正式提交的 64 页 PDF。原始竞赛附件默认未追踪，复绘仍需自己准备完整的官方 D 题数据。

## 如何恢复旧论文与科研图

在自己电脑的仓库中，建议创建临时分支：

```bash
git switch -c restore/legacy-paper
git fetch origin backup/pre-slim-20261121
git restore --source FETCH_HEAD -- paper/final paper/final_v2 paper/figure_data_v2
python paper/final/src/verify_bundle.py
python scripts/figures_v2/verify_bundle.py
```

注意：上面的两个历史 bundle 校验工具可以核对恢复文件的完整性；若原始 D 题附件缺失，只能做其支持的离线检查，不能据此声称执行了全部真实数据复算。恢复命令会把三个目录重新引入当前工作树，**不要把它们作为改动合并回精简版 main**。

要回到整个瘦身前仓库，而非只恢复历史论文目录：

```bash
git fetch origin backup/pre-slim-20261121
git switch -c inspect/pre-slim FETCH_HEAD
```

`main` 的其他程序，包括 `scripts/figures_v2/`，可能仍会引用备份目录；需要运行这些历史论文构建入口时，先按上面的命令恢复材料。

## 自动检查和边界

- 精简版 CI 继续执行 Python Ruff 和 `pytest`；原先两套历史论文包完整性检查不再直接对 `main` 执行，改为验证正式提交的 3 个文件大小、MD5 和 SHA-256。
- 正式算法冻结提交 `bec20f1536458db47bac583c309c7b30637cb67a` 仍可通过 Git 历史访问。`docs/FROZEN_RELEASE.md` 是当时冻结报告；其中原 `freeze/2026-09-25-final` 分支的称呼属于历史记录，当前 GitHub 分支列表不再列出该分支。
- 为了可恢复，备份分支及 Git 提交历史仍保留旧二进制对象。所以**主分支文件变少，不等于 GitHub 仓库实际服务器存储或旧克隆包同步按同样比例下降**。
- 真正清除历史 Git 对象需要在**仓库外部保留独立完整备份**后进行历史重写、协调协作者、强制推送和清理不可达引用；这个步骤不属于本轮无损瘦身，也不应随意执行。

建议执行 `python scripts/verify_submission_integrity.py`，校验三份正式文件是否完全等于终检版。正式附件的内容与原始哈希不应因仓库整理而变化。
