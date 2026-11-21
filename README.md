# 2026 年“华为杯”全国研究生数学建模竞赛 · D 题

**获奖：全国二等奖**  
**研究主题：无人机应急物资运输与通信协同优化**

本仓库同时保留**正式提交成果、Q1–Q4 最终方案与完整核心算法源码**。历史搜索轨迹、旧论文版本、重复计算档案与中间图表不放在主分支。

## 正式提交成果

| 文件 | 用途 |
| --- | --- |
| [最终论文 PDF](submission/D26105580028.pdf) | 唯一正式 64 页论文，包含四问的完整分析及图表 |
| [官方结果 Excel](submission/%E7%BB%93%E6%9E%9C%E6%8F%90%E4%BA%A4%E6%A8%A1%E6%9D%BF.xlsx) | 6 张正式结果表 |
| [正式 RAR 附件](submission/D26105580028.rar) | 比赛提交时包含的程序及材料 |
| [校验清单](submission/CHECKSUMS.txt) | PDF、Excel、RAR 的原始字节哈希 |

## 算法代码在哪里？

算法已恢复在 **[src/](src/)**，不是历史计算文件：

| 问题 | 主要代码 | 模型重点 |
| --- | --- | --- |
| Q1 安全载荷与分批 | [src/q1/physics_engine.py](src/q1/physics_engine.py) | 地形与能量计算、返航储备、精确分批 |
| Q2 运输调度优化 | [src/q2/](src/q2/) | 路线与组批搜索、资源占用、列生成、时间和能耗偏好 |
| Q3 中继通信协同 | [src/q3/](src/q3/) | 联合时序、通信可行性、连续区间校验、资源安排 |
| Q4 分区与配置 | [src/q4/partition.py](src/q4/partition.py) | 固定正式 Q3 任务后的分区枚举和资源需求 |

共享物理模型在 [src/core/](src/core/)；输入校验和系统约束在 [src/validation.py](src/validation.py)；
可复现参数及离散热启动在 [config/](config/)，单题及全流程入口在根目录 `run_q1.py`、`run_q2.py`、`run_q3.py`、`run_q4.py`、`run_all.py`。

## 已冻结的最终结果

| 问题 | 正式结果 |
| --- | --- |
| Q1 | 18 架次，59.1304 kWh |
| Q2 | 24 架次，80 箱按期交付；5903.0382 s，65.5662 kWh |
| Q3 | 24 运输 + 3 中继架次；5931.7347 s，69.1409 kWh |
| Q4 | K=2 资源缺口 1 项；K=3 资源缺口 3 项 |

最终结果表格见 [results/q1/](results/q1/)、[results/q2/](results/q2/)、[results/q3/](results/q3/)、[results/q4/](results/q4/)；指标摘要见 [results/validation.json](results/validation.json)。
不将有限搜索结果表述为原问题的全局最优证明，通信连续检查是数值证书而非精确算术证明。

## 运行与验证

需要 Python 3.11/3.12 及完整**官方 D 题原始附件**（5 份工作簿和 30 米 DEM），将官方 ZIP 解压到 `data/raw/` 并保持原始名称和目录结构。仓库不上传官方原始数据。

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/verify_submission_integrity.py
```

单题及全流程求解入口：

```bash
python run_q1.py /path/to/official_D --out outputs/recomputed/q1
python run_q2.py /path/to/official_D --out outputs/recomputed/q2
python run_q3.py /path/to/official_D --out outputs/recomputed/q3
python run_q4.py /path/to/official_D --q3-dir outputs/recomputed/q3 --out outputs/recomputed/q4
python run_all.py /path/to/official_D --out outputs/recomputed
```

**请把新运行结果写入独立的 `outputs/`，不要覆盖 `results/` 内的正式参赛方案。** Q2/Q3 的限时搜索受硬件、随机种子和求解预算影响，新运行可能出现其他可行候选；重新运行不代表原比赛结果会改变。

## 本仓库的清理范围

- **保留**：核心算法和支持代码、配置、可运行入口、必要测试、最终 CSV/JSON、正式论文 PDF/Excel/RAR。
- **不展示**：`archive/` 的历史基线、旧论文 Word/PDF 及制图中间文件、过去的搜索轨迹、历史审计报告。
- 论文及最终附件均保持提交时的原字节；可运行 `python scripts/verify_submission_integrity.py` 核对。

