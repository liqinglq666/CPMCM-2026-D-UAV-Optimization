# Q4 — 固定 Q3 方案下的任务分区与资源配置

## 1. Fixed decisions inherited from Q3

Q4 does not redesign Q3. The following remain unchanged:

- cargo grouping;
- service-area visit order;
- transport missions;
- relay missions;
- communication-support relation.

If one transport trip visits multiple service areas, those service areas must belong to the same Q4 task group.

## 2. Atomic components

Multi-service Q3 routes induce connected components. The 15 service areas collapse into four indivisible atoms:

1. `{S001,S003,S005,S006,S007,S011,S015}`
2. `{S002,S009,S010,S012,S013,S014}`
3. `{S004}`
4. `{S008}`

Therefore K=2 and K=3 can be solved by exhaustively enumerating partitions of these four atoms.

## 3. Resource requirement per independent group

For each candidate group, fixed Q3 time intervals are replayed.

Transport UAV requirement by type:
- maximum overlap of fixed transport-trip intervals.

Transport battery requirement by type:
- maximum overlap of `trip start → return + recharge-to-100%`.

Relay UAV requirement:
- maximum overlap of `relay start → relay return + turnaround`.

Relay energy-component requirement:
- maximum overlap of `relay start → return + recharge-to-100%`.

When one fixed Q3 relay sortie supports transport trips that would belong to different independent Q4 groups, each independent group needs its own corresponding relay capability because resources cannot cross groups.

## 4. Enumeration objective

The current selection uses a lexicographic criterion:

1. minimize total inventory-shortage units;
2. minimize total independently provisioned resource count;
3. minimize workload coefficient of variation;
4. minimize transport-trip-count imbalance.

This is a modeling choice and should be stated as such in the paper.

## 5. Selected K=2 allocation

- G1: `S001,S003,S004,S005,S006,S007,S011,S015`
- G2: `S002,S008,S009,S010,S012,S013,S014`

Total shortages versus current inventory:

- A-type UAV: 1;
- C-type UAV: 1;
- relay UAV: 2;
- all other resource shortages: 0.

Total shortage units = **4**.

## 6. Selected K=3 allocation

- G1: `S001,S003,S005,S006,S007,S011,S015`
- G2: `S002,S008,S009,S010,S012,S013,S014`
- G3: `S004`

Total shortages:

- A-type UAV: 1;
- B-type UAV: 2;
- C-type UAV: 1;
- A-type battery: 1;
- relay UAV: 2.

Total shortage units = **7**.

Under the stated lexicographic objective, K=2 requires fewer additional resources and has lower workload imbalance than the selected K=3 allocation.


## Audit implementation update

Inventory, recharge and turnaround values now come from the official input
loader and shared energy module. Empty/invalid partitions and negative resource
intervals fail explicitly. Zero-length intervals occupy no resource. The current
recomputed Q3 timing retains the same four service atoms and K=2/K=3 shortage
totals, but resource occupancy and energy must be read from regenerated CSVs.

The independent Q4 entry verifies the official-input fingerprint of its Q3
source before calculation. Concurrent resource counting is shared with the
core constraints module and uses the same 1e-5 s numerical time tolerance as
schedule validation; smaller solver round-off must not invent another resource.
