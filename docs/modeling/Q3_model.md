# Q3 — 运输与通信中继协同优化

## 1. Why Q2 cannot simply be reused

对 Q2 的运输轨迹进行 30 m DEM 视距与链路预算检查后，绝大多数架次存在 G01 直连中断区间。因此 Q3 必须将运输调度和中继资源周转联合考虑，而不能只对 Q2 路线做事后补丁。

## 2. Communication model

For every communication segment:

```text
P_th = P_sens + M
L_max(a->b) = P_t,a + G_t,a + G_r,b - L_sys - P_th,b
L_max,bidir = min(L_max(a->b), L_max(b->a))
FSPL = 32.45 + 20 log10(f_MHz) + 20 log10(D_km)
L_path = FSPL + L_obs * obstruction
```

A link is usable when `L_path <= L_max,bidir`.

Current parameter reduction:

- transport UAV ↔ G01: about **122 dB**;
- transport UAV ↔ relay access: about **116 dB**;
- relay ↔ G01 backhaul: about **126 dB**.

Terrain obstruction is evaluated against the official 30 m DEM. No relay-to-relay multihop is allowed.

## 3. Transport communication state

At every checked transport state:

1. use G01 direct communication when it is available;
2. otherwise use exactly one relay UAV;
3. relay mode is feasible only when both transport→relay access and relay→G01 backhaul are simultaneously available.

The result file reports a conservative relay service window from the first detected direct-loss state to the last detected direct-loss state for each affected trip.

## 4. Relay sortie model

Each relay sortie contains:

```text
O01 preparation
→ outbound climb/cruise/descent
→ link setup
→ hover + communication service
→ return
→ turnaround / component recharge
```

Energy contains:

- two-way cruise power;
- positive climb gravitational work / efficiency;
- hover + communication power during the service window.

The selected hover states use the 300 m AGL upper bound and are retained only when their G01 backhaul is feasible.

## 5. Communication-aware transport redesign

The main cooperation change relative to Q2 is the early western wave.

Instead of preserving the original early `S006→S007→S015` structure, Q3 uses:

- a light `S007` trip;
- a `S007→S006` hard-deadline trip;
- a later dedicated `S015` trip.

This shortens the early western relay requirement and releases the relay UAV early enough to serve the next communication region.

## 6. Current feasible baseline

Current v1 metrics:

- transport trips: **24**;
- relay sorties: **6**;
- hard-deadline violations: **0**;
- transport energy: **80.8447 kWh**;
- relay energy: **5.9585 kWh**;
- total energy: **86.8032 kWh**;
- transport makespan: **12774.32 s**;
- joint makespan: **13223.66 s = 3.67 h**;
- minimum hard-deadline slack: about **178.65 s**.

The solution is a constraint-complete feasible baseline, **not a proof of global optimality**. Its soft weighted tardiness can still be improved if time remains.

## 7. Verification

The current result set verifies:

- all 80 boxes delivered exactly once;
- all medical / first-batch hard deadlines satisfied;
- no overlap of physical transport UAVs;
- no invalid reuse of shared transport batteries before recharge to 100%;
- two relay UAV schedules do not overlap after including turnaround;
- six relay energy components are used once each;
- every sampled direct-failure point has feasible transport↔relay access and relay↔G01 backhaul.

For the final paper, describe the discrete communication verification resolution explicitly rather than claiming an analytic continuous-time proof.
