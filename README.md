# CPMCM 2026 Problem D — UAV Transportation & Communication Collaborative Optimization

> 2026 “华为杯”中国研究生数学建模竞赛 D 题工作仓库  
> **Competition status: PRIVATE. Do not make public during the competition.**

## Scope

本仓库统一管理 D 题：

- Q1 单服务区运输能力、最大安全载荷与精确组批
- Q2 异构运输无人机、多架次、多点配送与共享电池调度
- Q3 30 m DEM 通信视距、链路预算与运输—中继协同调度
- Q4 固定 Q3 任务关系下的 K=2 / K=3 分区资源配置
- 结果 CSV、模型说明、AI 使用记录与最终提交工作区

## Modeling pipeline

```text
Official data / 30 m DEM
        ↓
Unified flight physics
(distance / terrain / altitude / energy / time)
        ↓
Q1 exact batching
        ↓
Q2 transport scheduling + battery resources
        ↓
Q3 direct-link check + relay collaborative scheduling
        ↓
Q4 indivisible service atoms + exact K=2/K=3 enumeration
        ↓
Official workbook / paper / attachment package
```

## Current working results

### Q1

20% return-energy reserve:

- Minimum single-service round trips: **18**
- Total transport energy: **59.1304 kWh**
- Cumulative operation time: **32776.02 s**
- Split service areas: **S001, S002, S003**

Sensitivity shows the trip count remains 18 from 10% to 20% reserve, rises to 19 at 25%, and 20 at 30%.

### Q2

Current balanced hard-deadline-feasible point:

- Transport trips: **22**
- Hard-deadline violations: **0**
- Makespan: **11033.023 s**
- Total transport energy: **79.801846 kWh**
- Weighted tardiness: **327498.249 priority·s**

The full 17–24 trip trade-off frontier is stored under `results/q2/`.

### Q3

Communication-aware feasible joint baseline:

- Transport trips: **24**
- Relay sorties: **6**
- Hard-deadline violations: **0**
- Transport energy: **80.844703 kWh**
- Relay energy: **5.958528 kWh**
- Joint energy: **86.803232 kWh**
- Transport makespan: **12774.325 s**
- Joint makespan: **13223.665 s ≈ 3.67 h**
- Minimum hard-deadline slack: **≈178.65 s**

The communication model uses 2.4 GHz FSPL, DEM obstruction checking and bidirectional link-budget thresholds. The current Q3 is a verified feasible collaborative baseline, not a proof of global optimality.

### Q4

Q3 multi-service routes induce four indivisible service atoms. K=2 and K=3 partitions are exhaustively enumerated.

Current lexicographic objective:

1. minimum total inventory shortage;
2. minimum independently provisioned resource scale;
3. minimum workload coefficient of variation;
4. minimum transport-trip imbalance.

Selected resource-shortage totals:

- **K=2: 4 shortage units**
- **K=3: 7 shortage units**

Under this stated resource-first objective, K=2 places less pressure on existing inventory.

## Repository structure

```text
docs/
  AI_USAGE.md
  modeling/
    Q1_model.md
    Q2_model.md
    Q3_model.md
    Q4_model.md

data/
  raw/            # official raw data kept local by default
  dem/            # official DEM kept local by default

src/
  q1/
  q2/
  q3/
  q4/

scripts/
  run_q1.py
  run_q2.py
  run_q3.py
  run_q4.py

results/
  q1/
  q2/
  q3/
  q4/

submission/
tests/
```

## Reproducibility

Python 3.10+ recommended.

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

Run Q3:

```bash
python scripts/run_q3.py /path/to/D_problem_unpacked --q2-dir results/q2 --out results/q3
```

Run Q4:

```bash
python scripts/run_q4.py --q3-dir results/q3 --out results/q4
```

Validate the complete result set:

```bash
python scripts/validate_results.py --results results
```

Regenerate paper figures after any result change:

```bash
python scripts/make_figures.py --results results --out figures
```

The figure generator currently creates Q1 reserve-sensitivity, Q2 timeliness/energy trade-off, Q3 relay-location and joint Gantt figures, and the Q4 resource-shortage comparison.

## Important modeling language

Q1 contains an exact subset-partition step for each single service area.

Q2 and Q3 are heuristic / trade-off / collaborative feasible solutions. Do **not** describe them as globally optimal unless an exact optimality proof is added later.

Q4 is exact enumeration **conditional on the fixed Q3 decisions and the stated lexicographic resource objective**.

## Competition compliance

AI is used only as an auxiliary tool. Modeling assumptions, equations, code, numerical outputs and written conclusions must be independently verified by the participating team. External code, literature and AI-assisted code actually used must be cited or declared according to the official competition rules.

Do not make this repository public during the competition.
