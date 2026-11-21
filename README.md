# 2026 华为杯｜无人机应急物流与通信协同优化

**无人机应急物资运输与通信协同优化**  
2026 年华为杯中国研究生数学建模竞赛 · 全国二等奖

本仓库提供四个子问题的建模实现、正式提交结果与论文原件。研究围绕地形约束下的安全运输、时限与能耗协同调度、中继通信保障以及分区资源配置展开。

## 研究思路与实现

| 模块 | 核心问题 | 方法与实现 |
| --- | --- | --- |
| Q1 · 安全载荷与分批 | 在地形净空、机型载荷、能耗和返航储备约束下制定运输方案 | 基于 DEM 的航段几何与能量计算、各机型安全载荷求解、货箱分批 |
| Q2 · 运输调度 | 在物资时限、无人机及电池资源约束下组织运输任务 | 组批与路线搜索、资源可行调度、时间—能耗方案比较 |
| Q3 · 通信协同 | 同时满足运输调度和全过程通信保障要求 | 运输/中继协同规划、条件时序优化、离散采样与连续区间数值核验 |
| Q4 · 分区配置 | 固定已接受的 Q3 任务后分析区域独立执行的资源需求 | 服务区组件划分、K=2/3 分区枚举、设备与电池缺口统计 |

共享的地形、飞行、能耗、通信和资源约束实现位于 [`src/core/`](src/core/)；四问求解器分别位于 [`src/q1/`](src/q1/)、[`src/q2/`](src/q2/)、[`src/q3/`](src/q3/) 与 [`src/q4/`](src/q4/)。

## 正式成果

| 文件 | 内容 |
| --- | --- |
| [正式论文 PDF](submission/D26105580028.pdf) | 64 页正式提交版，包含四问的模型、图表和结论 |
| [官方结果工作簿](submission/%E7%BB%93%E6%9E%9C%E6%8F%90%E4%BA%A4%E6%A8%A1%E6%9D%BF.xlsx) | 依据赛事模板填写的六张结果表 |
| [提交附件 RAR](submission/D26105580028.rar) | 比赛正式提交附件 |
| [文件摘要](submission/CHECKSUMS.txt) | 正式文件大小、MD5 与 SHA-256 |

**以 `submission/` 中的 PDF、Excel 和 RAR 为正式提交原件。** 这些文件不在构建或验证步骤中重新生成、覆盖。

### 已接受方案的主要指标

| 问题 | 指标 | 结果 |
| --- | --- | --- |
| Q1 | 运输架次 / 总能耗 | 18 架次 / 59.1304 kWh |
| Q2 | 运输架次 / 物资交付 | 24 架次 / 80 箱按期交付 |
| Q2 | 运输返航完工时间 / 总能耗 | 5903.0382 s / 65.5662 kWh |
| Q3 | 运输 / 中继架次 | 24 / 3 |
| Q3 | 联合完工时间 / 总能耗 | 5931.7347 s / 69.1409 kWh |
| Q4 | K=2 / K=3 的资源缺口总数 | 1 / 3 |

完整数值以 [`results/`](results/) 内的 CSV/JSON 及 [核验摘要](results/validation.json) 为准。Q2/Q3 的候选搜索不构成全局最优性证明；Q3 连续通信核验属于带数值界的可行性检查，不等同于精确算术形式化证明。

## 代码结构

```text
src/
├── core/        地形、航段、能耗、通信、约束与数据结构
├── q1/          安全载荷及运输分批
├── q2/          组批搜索、调度与时间—能耗权衡
├── q3/          运输和中继联合规划
├── q4/          分区与资源需求分析
├── cli.py       命令行调度入口
└── validation.py  结果与约束复核
config/          模型参数和离散热启动
results/         已接受的 Q1–Q4 结果
submission/      参赛论文、结果工作簿与附件原件
tests/           算法单元测试与约束回归测试
```

根目录的 `run_q1.py`—`run_q4.py` 和 `run_all.py` 提供单题和全流程入口。核心模块位于 `src/`，不依赖旧论文制图目录。

## 运行环境与复核

使用 Python 3.12。项目依赖见 `requirements.txt`，开发测试依赖见 `requirements-dev.txt`。

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python scripts/verify_submission_integrity.py
```

算法复算需要完整的竞赛官方原始数据（五份工作簿及 30 米 DEM），按照赛题原文件名解压至 `data/raw/`。原始附件不随本仓库分发。

```bash
# 单题示例：计算结果写入单独目录
python run_q1.py data/raw --out outputs/recomputed/q1
python run_q2.py data/raw --out outputs/recomputed/q2
python run_q3.py data/raw --out outputs/recomputed/q3
python run_q4.py data/raw --q3-dir outputs/recomputed/q3 --out outputs/recomputed/q4

# 全流程重新求解并复核
python run_all.py data/raw --out outputs/recomputed
```

**复算输出始终放在 `outputs/`，不要覆盖 `results/` 中的正式方案。** 不同运行环境和求解预算可能得到不同候选。未提供官方原始附件时，部分依赖真实输入的测试不能执行；应以各项测试的实际通过或跳过记录为准。

## 可复核性

- 已接受方案的主要结果和校验摘要保存在 `results/`；
- `src/validation.py` 对运输、资源与通信约束提供复核逻辑；
- `scripts/verify_submission_integrity.py` 只核对正式 PDF、Excel、RAR 的文件大小与摘要，不修改提交原件；
- 程序中的必要来源与辅助工具说明按赛事规范保留，不影响模型、结果或提交文件的完整性。
