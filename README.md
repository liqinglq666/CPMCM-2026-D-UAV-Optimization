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

## Current Q1 baseline

At a 20% return-energy reserve:

- Minimum round trips: **18**
- Total transport energy: **59.1304 kWh**
- Cumulative operation time: **32776.02 s**
- Split-demand service areas: **S001, S002, S003**

These values are working results and must be independently checked by the team before final submission.

## Repository structure

```text
docs/          modeling notes, assumptions, AI-use record
data/          data-placement instructions; raw competition data should stay controlled
src/           reusable model and optimization code
scripts/       executable entry points
results/       intermediate/final numerical results
submission/    official output files prepared for submission
tests/         numerical and physics consistency tests
```

## Reproducibility

Python 3.10+ is recommended. Install dependencies with:

```bash
pip install -r requirements.txt
```

Run Q1 with:

```bash
python scripts/run_q1.py /path/to/D_problem_unpacked --out results/q1
```

## Competition compliance

AI is used only as an auxiliary tool. Modeling assumptions, equations, code, numerical outputs and written conclusions must be independently verified by the participating team. Any external code, literature or AI-assisted program must be cited/declared according to the competition rules.
