# Benchmark review against Huaweibei-cool — 2026-09-23
> 历史工作资料：本文件未随本轮代码审计重写。当前数值和验证边界请以 `results/`、`docs/modeling/` 与 `docs/audit/REFACTOR_REPORT.md` 为准；不得直接把本文旧数值当作本轮输出。

Reference repository reviewed: `siyunhao2025-beep/Huaweibei-cool`.

This note records transferable writing/validation ideas only. The benchmark repository is **not** treated as a scientific source for this D-problem model, and no model text/result is copied into the paper.

## Materials reviewed

- `modules/abstract.md`
- `modules/validation.md`
- `modules/innovation.md`
- `playbooks/optimization/00_overview.md`
- `playbooks/optimization/动态规划与离散调度.md`
- `playbooks/spatial-graph/最短路径与VRP.md`
- `playbooks/spatial-graph/空间布局与覆盖优化.md`
- `docs/SCORING_RUBRIC.md`
- `assets/checklists/优秀论文自检表.md`

## Gaps identified in our previous paper

1. The four questions were explained clearly, but the cross-question dependency was not visible enough at the beginning.
2. Q2 had a selected 22-trip point but did not quantitatively explain the discrete trade-off elbow.
3. Q2 resource constraints were implemented in code but not sufficiently formalized in the paper.
4. Q3 communication feasibility was reported, but the reason transport had to be restructured rather than simply adding relays was not quantified.
5. Q4 said “exact enumeration” without reporting the complete search size.
6. Validation evidence was scattered across sections instead of being summarized as one evidence chain.
7. Innovation statements were method-oriented rather than “problem observation → technical change → quantified evidence”.

## Changes implemented in paper v4.2

### Abstract

Each question now reports:
- task/method;
- quantitative result;
- validation/boundary;
- evidence-backed contribution.

### Framework

Added a new four-layer framework figure:
Q1 capability → Q2 transport/resource scheduling → Q3 communication-constrained restructuring → Q4 independent partition/resource configuration.

### Q2

Added explicit variables:
- `x_rb`: box-to-trip assignment;
- `y_ra`: physical UAV-to-trip assignment;
- `z_re`: battery-to-trip assignment;
- `s_r`: trip start time.

Added hard constraints for:
- unique box delivery;
- mass/volume/energy;
- physical-UAV non-overlap;
- battery occupancy through recharge-to-100%;
- medical/first-batch deadlines.

Quantified the selected balance point:
- 24 → 22 trips: energy **−3.37%**, weighted tardiness **+7.77%**, makespan unchanged;
- 22 → 21 trips: makespan **+20.03%**, while energy and tardiness do not improve together.

### Q3

Added the core necessity evidence:
- only 3 of 24 final transport trips are direct-link throughout;
- **21/24 = 87.5%** require relay support for at least one interval;
- overlapping loss windows + only two relay UAVs create concurrency conflicts, so communication cannot be treated as a post-hoc add-on.

Final one-second audit metrics:
- transport trips 24;
- relay sorties 6;
- hard-deadline violations 0;
- joint energy **86.811261 kWh**;
- joint makespan **13224.359 s**;
- minimum hard-deadline slack **178.649 s**.

### Q4

Made exactness explicit:
- four indivisible atoms;
- `S(4,2)=7`;
- `S(4,3)=6`;
- total **13** unlabeled candidate partitions, all exhaustively replayed.

### Validation

Added a consolidated validation table matching evidence type to conclusion risk:
- Q1: reserve sensitivity + exact DP;
- Q2: trade-off frontier + resource timing audit;
- Q3: ≤1 s communication audit + relay/energy resource audit;
- Q4: exhaustive fixed-Q3 enumeration.

### Innovation

Rewritten as evidence-backed changes rather than algorithm names:
1. unified physical engine across all questions;
2. UAV–battery dual-resource occupancy;
3. communication constraints driving transport restructuring;
4. coupled service partition reduced to exact atom enumeration.

## Wording boundary

Continue to use:
- Q1: exact solution under stated lexicographic objective;
- Q2: balanced feasible / trade-off solution;
- Q3: communication-aware feasible collaborative baseline;
- Q4: exact enumeration conditional on fixed Q3 and stated objective.

Do not call Q2/Q3 globally optimal.

