# CPMCM 2026 Problem D — UAV Transportation & Communication Collaborative Optimization

> 2026 “华为杯”中国研究生数学建模竞赛 D 题工作仓库  
> **Competition status: PRIVATE. Do not make public during the competition.**

## Project scope

本仓库用于统一管理 D 题的：

- 题目与数据说明
- 统一物理计算引擎
- Q1 单服务区运输能力与精确组批
- Q2 异构多无人机运输调度
- Q3 运输—通信中继协同优化
- Q4 任务分区与资源配置
- 结果表、敏感性分析与最终提交文件

## Modeling pipeline

```text
Raw data / DEM
      ↓
Unified physics engine
(distance / terrain / altitude / energy / flight time)
      ↓
Q1 payload capacity + exact batching
      ↓
Q2 multi-UAV routing + battery scheduling
      ↓
Q3 relay placement + communication scheduling
      ↓
Q4 partition + resource allocation
      ↓
Official submission workbook + paper
```

## Current status

### Q1 — completed working baseline

At a 20% return-energy reserve:

- Minimum single-service round trips: **18**
- Total transport energy: **59.1304 kWh**
- Cumulative operation time: **32776.02 s**
- Split-demand service areas: **S001, S002, S003**

### Q2 — completed working balanced solution

The current Q2 route/resource search produces a hard-deadline-feasible trade-off frontier.

Working 22-trip balance point:

- Transport trips: **22**
- Hard deadline violations: **0**
- Makespan: **11033.023 s**
- Total transport energy: **79.801846 kWh**
- Weighted tardiness: **327498.249 priority·s**
- Minimum hard-deadline slack: about **1768.65 s**

The Q2 result is a heuristic / trade-off solution, not a claimed proof of global optimality. The full 17–24 trip frontier is stored in `results/q2/Q2_tradeoff_frontier.csv`.

## Repository structure

```text
docs/
  modeling/
    Q1_model.md
    Q2_model.md
  AI_USAGE.md

data/
  raw/
  dem/

src/
  q1/
  q2/

scripts/
  run_q1.py
  run_q2.py

results/
  q1/
  q2/

submission/
tests/
```

## Reproducibility

Python 3.10+ is recommended.

Install dependencies:

```bash
pip install -r requirements.txt
```

Run Q1:

```bash
python scripts/run_q1.py /path/to/D_problem_unpacked --out results/q1
```

Run Q2:

```bash
python scripts/run_q2.py /path/to/D_problem_unpacked --target-trips 22 --out results/q2
```

Q2 output files include:

- `Q2_transport_trips_balanced.csv`
- `Q2_box_delivery_balanced.csv`
- `Q2_tradeoff_frontier.csv`
- `Q2_resource_check.csv`

## Next step

Q3 will inherit the Q2 box groups, route orders, physical UAV/battery schedules and segment timing, then add:

- terrain line-of-sight checking;
- bidirectional link-budget checking;
- direct-link outage intervals;
- relay candidate positions/heights;
- relay UAV / energy-component scheduling.

## Competition compliance

AI is used only as an auxiliary tool. Modeling assumptions, equations, code, numerical outputs and written conclusions must be independently verified by the participating team. Any external code, literature or AI-assisted program actually used must be cited/declared according to the competition rules.
