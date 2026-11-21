# 2026 华为杯｜无人机应急运输优化

2026 年华为杯中国研究生数学建模竞赛，全国二等奖。

项目主要研究复杂地形下的无人机应急物资配送。除了运输任务本身，还需要考虑电池和机队调度、通信中继，以及多个服务区域独立执行任务时的资源配置。仓库保留了算法实现、最终结果和正式提交的论文。

## 主要工作

- **Q1｜安全载荷与分批**：根据 30 m DEM 计算航线地形净空和飞行能耗，确定不同机型的安全载荷，并安排货箱分批运输。代码见 [`src/q1/`](src/q1/)。
- **Q2｜运输调度**：联合处理货箱分组、访问顺序、无人机及电池分配，在满足配送时限的前提下比较任务完成时间与能耗。代码见 [`src/q2/`](src/q2/)。
- **Q3｜通信保障**：在运输计划中加入中继无人机，协调运输与通信时序，并检查飞行过程中的链路可用性。代码见 [`src/q3/`](src/q3/)。
- **Q4｜分区配置**：以确定的运输和中继任务为基础，比较两区和三区方案的资源需求。代码见 [`src/q4/`](src/q4/)。

地形、能耗、通信和资源约束使用 [`src/core/`](src/core/) 中的公共模块。

## 最终结果

| 模块 | 结果 |
| --- | --- |
| Q1 | 18 架次，总能耗 59.1304 kWh |
| Q2 | 24 架次，80 箱按期送达；完工时间 5903.0382 s，总能耗 65.5662 kWh |
| Q3 | 24 架运输机次、3 架中继机次；完工时间 5931.7347 s，总能耗 69.1409 kWh |
| Q4 | 两区方案资源缺口 1 项，三区方案资源缺口 3 项 |

以上为比赛提交时采用的方案。详细表格见 [`results/`](results/)，论文中的建模假设、约束及结果分析以 [正式论文](submission/D26105580028.pdf) 为准。Q2、Q3 采用有限搜索与数值校验，不主张已经证明全局最优。

## 仓库内容

```text
src/          Q1–Q4 求解器及共享计算模块
config/       参数设置和初始方案
results/      最终结果（CSV、JSON）
submission/   正式论文、结果工作簿和提交附件
tests/        算法与约束测试
run_all.py    全流程运行入口
run_q1.py ... run_q4.py    各题运行入口
```

正式提交文件：
[论文 PDF](submission/D26105580028.pdf) ·
[结果 Excel](submission/%E7%BB%93%E6%9E%9C%E6%8F%90%E4%BA%A4%E6%A8%A1%E6%9D%BF.xlsx) ·
[提交附件 RAR](submission/D26105580028.rar)

## 运行

使用 Python 3.12。需要先准备竞赛官方原始数据（五份工作簿和 30 m DEM），按原有文件名放入 `data/raw/`；数据不包含在仓库中。

```bash
python -m pip install -r requirements-dev.txt

# 单题运行
python run_q1.py data/raw --out outputs/q1
python run_q2.py data/raw --out outputs/q2
python run_q3.py data/raw --out outputs/q3
python run_q4.py data/raw --q3-dir results/q3 --out outputs/q4

# 全流程求解和验证
python run_all.py data/raw --out outputs/recomputed

# 测试与正式附件校验
python -m pytest -q
python scripts/verify_submission_integrity.py
```

重新计算的结果建议写到 `outputs/`，不要覆盖 `results/` 中的正式参赛数据。求解过程涉及搜索和数值优化，运行环境或计算预算不同，候选方案可能有所差异。
