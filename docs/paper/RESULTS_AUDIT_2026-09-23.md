# Q1–Q4 Results Audit — 2026-09-23

This file freezes the currently verified numerical baseline used for paper drafting.
If any model or result CSV changes, rerun `scripts/validate_results.py` and regenerate this audit.

## Q1 — exact single-service batching

At 20% return-energy reserve:

- minimum round trips: **18**;
- total transport energy: **59.130423 kWh**;
- cumulative operation time: **32776.016 s = 9.10445 h**;
- split service areas: **S001, S002, S003**.

Reserve sensitivity:

| reserve | trips | energy (kWh) | cumulative time (h) |
|---:|---:|---:|---:|
| 10% | 18 | 59.1304 | 9.1044 |
| 15% | 18 | 59.1304 | 9.1044 |
| 20% | 18 | 59.1304 | 9.1044 |
| 25% | 19 | 61.0725 | 9.6016 |
| 30% | 20 | 67.2266 | 10.1628 |

Q1 uses exact subset-partition dynamic programming for each service area.

## Q2 — balanced transport schedule

Selected working point on the trip-count trade-off frontier:

- transport trips: **22**;
- hard-deadline violations: **0**;
- makespan: **11033.023 s**;
- total transport energy: **79.801846 kWh**;
- weighted tardiness: **327498.249 priority·s**.

This is a heuristic / trade-off solution, not a proof of global optimality.

## Q3 — communication-aware collaborative baseline

Verified feasible baseline:

- transport trips: **24**;
- relay sorties: **6**;
- all 80 boxes delivered exactly once;
- hard-deadline violations: **0**;
- transport energy: **80.844703 kWh**;
- relay energy: **5.958528 kWh**;
- joint energy: **86.803232 kWh**;
- transport makespan: **12774.325 s**;
- joint makespan: **13223.665 s = 3.67324 h**;
- weighted tardiness: **756674.615 priority·s**;
- minimum hard-deadline slack: **178.649 s**.

Relative to the selected Q2 point:

- transport trips: +2;
- joint energy: about **+8.77%**;
- joint makespan: about **+19.86%**.

Interpretation: these are the current costs of adding continuous communication feasibility under the two-relay resource restriction.

### Q3 validation completed

The current result set has been rechecked for:

- physical transport-UAV non-overlap;
- type-specific shared transport-battery non-overlap including recharge-to-100% time;
- 80-box uniqueness and completeness;
- medical / first-batch hard deadlines;
- relay-UAV non-overlap including 300 s turnaround;
- six distinct relay-energy components;
- relay communication windows lying inside the corresponding established-link / service windows;
- sampled direct-failure states having feasible transport↔relay and relay↔G01 links in the Q3 solver.

Important limitation: communication continuity is verified on the solver's finite temporal / DEM sampling resolution; do not call it an analytic continuous-time proof.

## Q4 — fixed-Q3 partition enumeration

Q3 multi-service transport relations yield four indivisible atoms:

1. `S001,S003,S005,S006,S007,S011,S015`
2. `S002,S009,S010,S012,S013,S014`
3. `S004`
4. `S008`

All unlabeled K=2 and K=3 partitions of these atoms are exhaustively enumerated under the fixed Q3 missions and timing.

Lexicographic objective:

1. minimum total resource-shortage units;
2. minimum total independently provisioned resource count;
3. minimum workload coefficient of variation;
4. minimum transport-trip imbalance.

Selected totals:

- **K=2 shortage = 4 units**
- **K=3 shortage = 7 units**

Selected K=2 shortages:
- A-type UAV: 1;
- C-type UAV: 1;
- relay UAV: 2.

Selected K=3 shortages:
- A-type UAV: 1;
- B-type UAV: 2;
- C-type UAV: 1;
- A-type battery: 1;
- relay UAV: 2.

Q4 enumeration is exact **conditional on the fixed Q3 plan and the stated objective**.

## Language to use in the paper

Safe wording:

- Q1: “exact optimal batching under the stated Q1 lexicographic objective”.
- Q2: “balanced feasible solution / trade-off solution”.
- Q3: “communication-aware feasible collaborative baseline”.
- Q4: “exact partition enumeration conditional on fixed Q3 decisions”.

Avoid:

- “Q2 global optimum”;
- “Q3 global optimum”;
- “continuous communication proven for all real-valued time”;
- “K=2 is universally optimal” without the stated Q4 objective and fixed-Q3 condition.
