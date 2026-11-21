"""Conservative continuous coverage of affine flight phases on the official DEM.

A fixed radio anchor and a moving endpoint sweep a 3-D triangle. Clip that
triangle against each closed DEM pixel prism, then project the intersection
onto phase time. This encloses every obstructed time, including corner contacts.
WGS84 distance is bounded with a global ellipsoid metric Lipschitz constant.
This is a guarded floating-point certificate, not exact-arithmetic verification.
It does not replace or modify the shared physical model or sampled checks.
"""

import math
import numpy as np

from .terrain import horizontal_distance

PIXEL_PAD = 1e-8
HEIGHT_PAD_M = 1e-6
TIME_PAD = 1e-11
DISTANCE_PAD_M = 1e-6
# Both principal radii of WGS84 curvature are <= a / (1-f).
WGS84_RADIUS_BOUND_M = 6378137.0 / (1 - 1 / 298.257223563)


def _clip(polygon, normal, limit):
    """Clip a convex (u,v) polygon by normal.dot(point) <= limit."""
    if not polygon:
        return []
    output = []
    previous = polygon[-1]
    old = float(np.dot(normal, previous) - limit)
    for point in polygon:
        new = float(np.dot(normal, point) - limit)
        if (old <= 0) != (new <= 0):
            output.append(previous + (point - previous) * (old / (old - new)))
        if new <= 0:
            output.append(point)
        previous, old = point, new
    return output


def merge_intervals(intervals):
    merged = []
    for left, right in sorted(intervals):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
        else:
            merged.append((left, right))
    return merged


def obstruction_intervals(terrain, anchor, first, last):
    """Enclose blocked fractions of a complete affine phase in [0,1]."""
    points = np.array([(*terrain.pixel(*p[:2]), p[2]) for p in (anchor, first, last)])
    low, high = points[:, :2].min(axis=0), points[:, :2].max(axis=0)
    cols = np.arange(max(0, math.floor(low[0] - PIXEL_PAD)),
                     min(terrain.width - 1, math.floor(high[0] + PIXEL_PAD)) + 1)
    rows = np.arange(max(0, math.floor(low[1] - PIXEL_PAD)),
                     min(terrain.height - 1, math.floor(high[1] + PIXEL_PAD)) + 1)
    cc, rr = np.meshgrid(cols, rows)
    cc, rr = cc.ravel(), rr.ravel()
    centers = np.column_stack((cc + .5, rr + .5))
    # Separating-axis filter for triangle/rectangle intersection. It is expanded
    # outwards, and also retains a degenerate projected triangle (vertical phase).
    area = np.linalg.det(points[1:, :2] - points[0, :2])
    sign = 1 if area >= 0 else -1
    keep = np.ones(len(cc), dtype=bool)
    for i in range(3) if abs(area) > 1e-7 else ():
        start, end = points[i, :2], points[(i + 1) % 3, :2]
        edge = end - start
        inward = sign * np.array([-edge[1], edge[0]])
        support = (centers - start) @ inward + (.5 + PIXEL_PAD) * np.abs(inward).sum()
        keep &= support >= -1e-10
    cc, rr = cc[keep], rr[keep]
    heights = terrain.values(rr, cc)
    keep = heights + HEIGHT_PAD_M >= points[:, 2].min()
    anchor_pixel = points[0]
    directions = (points[1:] - anchor_pixel).T
    intervals = []
    for col, row, height in zip(cc[keep], rr[keep], heights[keep]):
        polygon = [np.array([0., 0.]), np.array([1., 0.]), np.array([0., 1.])]
        for axis, lower in ((0, col), (1, row)):
            polygon = _clip(polygon, directions[axis], lower + 1 + PIXEL_PAD - anchor_pixel[axis])
            polygon = _clip(polygon, -directions[axis], anchor_pixel[axis] - lower + PIXEL_PAD)
        polygon = _clip(polygon, directions[2], height + HEIGHT_PAD_M - anchor_pixel[2])
        if not polygon:
            continue
        if any(p.sum() <= 1e-14 for p in polygon):
            return [(0., 1.)]  # The anchor itself touches this closed prism.
        times = [float(p[1] / p.sum()) for p in polygon]
        intervals.append((max(0., min(times) - TIME_PAD), min(1., max(times) + TIME_PAD)))
    return merge_intervals(intervals)


def phase_endpoints(phase, physics):
    name, _begin, _end, source, target, z0, z1, _distance = phase
    if name == "cruise":
        a, b = physics.nodes[source], physics.nodes[target]
    else:
        a = b = physics.nodes[target if name == "descent" else source]
    return (a.lon, a.lat, z0), (b.lon, b.lat, z1)


def distance_upper(anchor, first, last):
    """Product-metric triangle inequality; no projected-distance substitution."""
    middle = tuple((a + b) / 2 for a, b in zip(first, last))
    angular = math.hypot(math.radians(last[0] - first[0]), math.radians(last[1] - first[1]))
    length = math.hypot(WGS84_RADIUS_BOUND_M * angular, last[2] - first[2])
    def distance(point):
        return math.hypot(horizontal_distance(anchor, point), anchor[2] - point[2])
    return min(distance(first) + length, distance(last) + length,
               distance(middle) + length / 2) + DISTANCE_PAD_M


def certify_profile(profile, start, physics, comm, relay=None, *, min_interval_s=1e-5):
    """Cover every phase interior and every boundary using direct/assigned relay.

    relay is (point, begin, end), with the original closed service-window rule.
    A negative exact point replay is a counterexample. An interval that cannot be
    bounded is UNRESOLVED, never silently accepted by finer point sampling.
    """
    from .numeric import positive

    positive(min_interval_s, "minimum interval width")
    if not profile.phases:
        raise ValueError("No physical phases to certify")
    radio = comm.parameters
    links = [(comm.gateway, radio.direct_budget_db, -math.inf, math.inf, math.inf)]
    if relay is not None:
        point, begin, end = relay
        backhaul = radio.backhaul_budget_db - comm.link(point, comm.gateway, radio.backhaul_budget_db)[1]
        links.append((point, radio.access_budget_db, begin, end, backhaul))
    geometric = certified = boundaries = 0
    minimum = math.inf
    witnesses, unresolved, records = [], [], []
    for phase_index, phase in enumerate(profile.phases):
        first, last = phase_endpoints(phase, physics)
        begin, end = start + phase[1], start + phase[2]
        duration = end - begin
        def position(t):
            return tuple(a + (b - a) * t for a, b in zip(first, last))
        blocked = [obstruction_intervals(physics.terrain, anchor, first, last) for anchor, *_ in links]
        cuts = {0., 1.}
        for intervals in blocked:
            cuts.update(t for interval in intervals for t in interval)
        if duration > 0:
            cuts.update((t - begin) / duration for _p, _b, lo, hi, _back in links
                        for t in (lo, hi) if begin < t < end)
        cuts = sorted(cuts)
        geometric += len(cuts) - 1
        def actual_margin(t):
            time, point = begin + duration * t, position(t)
            return max((min(budget - comm.link(point, anchor, budget)[1], backhaul)
                        for anchor, budget, lo, hi, backhaul in links if lo <= time <= hi),
                       default=-math.inf)
        # Actual event instants are checked independently of open-cell statuses.
        for t in cuts:
            margin = actual_margin(t)
            boundaries += 1
            minimum = min(minimum, margin)
            if margin < 0:
                witnesses.append(dict(phase=phase_index, time_s=begin + duration * t,
                                      point=position(t), margin_db=margin, kind="boundary"))
        def enclose(left, right, statuses):
            nonlocal minimum, certified
            middle = (left + right) / 2
            time = begin + duration * middle
            margins = []
            for i, (anchor, budget, lo, hi, backhaul) in enumerate(links):
                if not lo <= time <= hi:
                    continue
                upper = distance_upper(anchor, position(left), position(right))
                loss = 32.45 + 20 * math.log10(radio.frequency_mhz) + 20 * math.log10(upper / 1000)
                if statuses[i]:
                    loss += radio.obstruction_loss_db
                margins.append(min(budget - loss, backhaul))
            margin = max(margins, default=-math.inf)
            if margin >= 0:
                certified += 1
                minimum = min(minimum, margin)
                return
            actual = actual_margin(middle)
            if actual < 0:
                witnesses.append(dict(phase=phase_index, time_s=time, point=position(middle),
                                      margin_db=actual, kind="interior"))
                return
            if duration * (right - left) <= min_interval_s:
                unresolved.append(dict(phase=phase_index, begin_s=begin + duration * left,
                                       end_s=begin + duration * right, margin_bound_db=margin))
                return
            enclose(left, middle, statuses)
            enclose(middle, right, statuses)
        for left, right in zip(cuts, cuts[1:]):
            middle = (left + right) / 2
            statuses = [any(a <= middle <= b for a, b in intervals) for intervals in blocked]
            enclose(left, right, statuses)
        records.append(dict(phase=phase_index, name=phase[0], begin_s=begin, end_s=end,
                            event_fractions=cuts, blocked_fraction_intervals=blocked))
    return dict(status="FAIL" if witnesses else "UNRESOLVED" if unresolved else "PASS",
                phases=len(profile.phases), geometric_intervals=geometric,
                certified_intervals=certified, boundary_checks=boundaries,
                minimum_margin_bound_db=minimum, witnesses=witnesses,
                unresolved_intervals=unresolved, phase_records=records,
                method="closed DEM prism / swept-ray triangle; WGS84 metric bounds",
                formal_exact_arithmetic_proof=False,
                numeric_guards=dict(pixel=PIXEL_PAD, height_m=HEIGHT_PAD_M,
                                    fraction=TIME_PAD, distance_m=DISTANCE_PAD_M))


def certify_profiles(profiles, assignments, relays, physics, comm):
    """Recompute a complete certificate; unknown or duplicate assignments fail."""
    if len(assignments) != len(profiles):
        raise ValueError("Communication assignment count mismatch")
    mapping = {r["运输架次编号"]: r for r in assignments}
    if set(mapping) != set(profiles):
        raise ValueError("Communication assignment IDs mismatch")
    results = {}
    for tid, (profile, start) in profiles.items():
        row = mapping[tid]
        relay = None
        if row["保障方式"] == "中继":
            if row["中继架次编号"] not in relays:
                raise ValueError("Unknown assigned relay")
            relay = relays[row["中继架次编号"]]
        elif row["保障方式"] != "直连":
            raise ValueError("Unknown communication mode")
        results[tid] = certify_profile(profile, start, physics, comm, relay)
    if not results:
        raise ValueError("No trajectories to certify")
    return dict(status="PASS" if all(r["status"] == "PASS" for r in results.values()) else "NOT_CERTIFIED",
                scope="Fixed exported trajectories, assigned relay and official piecewise-constant DEM; guarded floating arithmetic",
                formal_exact_arithmetic_proof=False,
                summary={k: sum(r[k] for r in results.values()) for k in
                         ("phases", "geometric_intervals", "certified_intervals", "boundary_checks")},
                minimum_margin_bound_db=min(r["minimum_margin_bound_db"] for r in results.values()),
                trips=results)
