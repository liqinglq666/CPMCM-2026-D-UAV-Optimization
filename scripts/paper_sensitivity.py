"""Exact reserve breakpoints for Q1 trip count, without changing its solver.

For each cargo subset retain the largest feasible reserve over official types.
For each exact batch count, a max-min set-partition DP gives the largest reserve
at which any such partition exists. No interpolation of sparse scenarios.
"""

from functools import lru_cache

from src.config import FEASIBILITY_TOL
from src.q1.physics_engine import roundtrip_energy, optimize_service_q1


def partition_reserve_limits(boxes, types, segment):
    n = len(boxes)
    full = (1 << n) - 1
    capacities = {}
    for mask in range(1, full + 1):
        cargo = [b for i, b in enumerate(boxes) if mask & (1 << i)]
        mass, volume = sum(b.mass for b in cargo), sum(b.volume for b in cargo)
        eligible = [
            1 - (roundtrip_energy(g, segment, mass) - FEASIBILITY_TOL) / g.energy_use
            for g in types.values()
            if mass <= g.max_payload + 1e-10 and volume <= g.max_volume + 1e-12
        ]
        if eligible:
            capacities[mask] = max(eligible)

    @lru_cache(None)
    def solve(mask):
        if not mask:
            return {0: 1.0}
        first = mask & -mask
        answer = {}
        sub = mask
        while sub:
            if sub & first and sub in capacities:
                for k, reserve in solve(mask ^ sub).items():
                    value = min(reserve, capacities[sub])
                    answer[k + 1] = max(answer.get(k + 1, -1.0), value)
            sub = (sub - 1) & mask
        return answer

    return solve(full)


def reserve_staircase(boxes, types, segments, low=0.1, high=0.4):
    grouped = {sid: [b for b in boxes if b.service == sid] for sid in segments}
    limits = {
        sid: partition_reserve_limits(bs, types, segments[sid])
        for sid, bs in grouped.items()
    }
    cuts = sorted(
        {low, high} | {r for d in limits.values() for r in d.values() if low < r < high}
    )
    rows = []
    for lo, hi in zip(cuts, cuts[1:]):
        reserve = (lo + hi) / 2
        counts = {
            sid: min((k for k, cap in d.items() if cap >= reserve), default=None)
            for sid, d in limits.items()
        }
        reachable = all(k is not None for k in counts.values())
        trips = sum(counts.values()) if reachable else None
        # Independent check against the unchanged original Q1 implementation.
        if reachable:
            replay = sum(
                optimize_service_q1(sid, grouped[sid], types, segments[sid], reserve)[0]
                for sid in segments
            )
            if replay != trips:
                raise ValueError("Parametric DP disagrees with original Q1 solver")
        if rows and rows[-1]["trips"] == trips:
            rows[-1]["reserve_upper"] = hi
        else:
            rows.append(
                dict(
                    reserve_lower=lo, reserve_upper=hi, trips=trips, reachable=reachable
                )
            )
    return rows, limits
