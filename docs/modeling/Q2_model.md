# Q2 — 异构无人机多点多架次运输调度

## 1. Problem interpretation

Each transport trip starts from O01, may visit one or more service areas, delivers indivisible boxes, and returns to O01.

The implemented hard constraints are:

- every box is delivered exactly once;
- payload mass and volume limits;
- trip energy <= (1-rho) * usable battery energy;
- medical boxes must be delivered no later than their expected-delivery time;
- first-batch boxes must be delivered no later than their first-batch deadline;
- only the matching A/B/C battery type can be used;
- every battery starts at 100% SOC and must recharge back to 100% before reuse;
- a physical UAV cannot execute overlapping trips;
- a physical battery cannot be simultaneously used or charged by overlapping trips.

Other expected-delivery times are treated as soft targets and measured through weighted tardiness.

## 2. Segment physics inherited from Q1

For every ordered node pair i->j:

1. WGS84 geodesic horizontal distance is used.
2. Cruise altitude = maximum DEM cell elevation touched by the horizontal segment + 50 m.
3. O01 operating altitude is ground elevation; service-area operating altitude is ground elevation + 30 m.
4. Every departure from a service area reclimbs from the 30 m operating altitude.
5. Remaining payload changes after every delivery stop.

Equivalent range:

```text
L_g(q) = L_g^0 - (L_g^0 - L_g^F) * (q / Q_g)^(3/2)
```

Horizontal energy:

```text
E_hor = E_use * d / L_g(q)
```

Climb energy:

```text
E_up = (m_empty + q) * g * h_up / (eta_up * 3.6e6)
```

No additional descent-energy term is added.

## 3. Battery recharge

For end-of-trip SOC s and equivalent full-charge time T_full:

```text
if 0 <= s < 0.90:
    t_chg = T_full * [0.65 * (0.90-s)/0.90 + 0.35]

if 0.90 <= s <= 1:
    t_chg = T_full * 0.35 * (1-s)/0.10
```

A battery becomes available only after this recharge completes.

## 4. Optimization strategy

The current solver is hierarchical rather than one monolithic MILP.

### Stage A — hard-feasible construction

A deadline-aware multi-trip heuristic repeatedly:

1. selects the most urgent remaining hard-deadline box;
2. generates one-to-three-service route candidates near its service area;
3. packs compatible remaining boxes subject to mass, volume and energy;
4. evaluates all currently available physical UAV/battery combinations;
5. schedules a feasible trip and updates UAV and battery availability.

After all hard-deadline boxes are secured, remaining boxes are consolidated with a throughput-oriented rule.

### Stage B — trip-group merge and full re-scheduling

The initial hard-feasible partition is then improved by repeatedly merging two trip groups. After every tentative merge, all trips are re-profiled and re-scheduled from scratch. A merge is retained only if all medical and first-batch hard deadlines remain feasible.

This produces a trade-off frontier between:

- weighted delivery tardiness;
- overall makespan;
- total transport energy;
- number of trips.

## 5. Working balanced solution

The current working balanced point uses **22 trips**.

Metrics:

- hard deadline violations: **0**;
- makespan: **11033.023 s**;
- total transport energy: **79.760597 kWh**;
- weighted tardiness: **327498.249 priority·s**;
- minimum hard-deadline slack: about **1768.65 s**.

The 22-trip point is not claimed to be a mathematically proven global optimum. It is retained because, on the current merge frontier, reducing from 24 to 22 trips leaves makespan unchanged, reduces energy, and only moderately increases weighted tardiness; moving to 21 trips causes a large makespan increase.

## 6. Paper-writing note

The paper should report the full frontier and explain the selected balance point. Avoid presenting the heuristic output as an exact global optimum unless an exact optimization proof is added later.


## Audit implementation update

The canonical physics is now in `src/core/`. Default execution computes all
17–24 frontier points and stores every plan in `Q2_frontier_plans.json`; the
validator replays every saved plan from official data. Numerically tied route
time objectives use explicit comparison tolerances before comparing energy.
All set-based summations are ordered for hash-seed-independent reproduction.
