"""Relay-window proposals for completion-time search.

The coarse spatial screen only constructs candidates. Accepted schedules still
pass PlanPreparer's full union-grid audit and the physical joint timing LP.
"""

import math

from src.config import RELAY_GUARD_S
from src.core.routes import evaluate_route


def column_geometry(columns, classes, preparer, relays, step=5.0):
    """Cache phase geometry independently of proposed relay service times."""
    if step <= 0:
        raise ValueError("Screening step must be positive")
    points = [preparer.relay(r)[0] for r in relays]
    cache = {}

    def phase_info(code, phase):
        name, start, end, source, target, z0, z1, _distance = phase
        duration = end - start
        count = max(1, math.ceil(duration / step))
        key = code, name, source, target, z0, z1, count
        if key not in cache:
            a, b = preparer.physics.nodes[source], preparer.physics.nodes[target]
            failed, covered = [], [True] * len(points)
            for index in range(count + 1):
                fraction = index / count
                if name == "cruise":
                    point = (a.lon + (b.lon - a.lon) * fraction,
                             a.lat + (b.lat - a.lat) * fraction,
                             z0 + (z1 - z0) * fraction)
                else:
                    node = b if name == "descent" else a
                    point = node.lon, node.lat, z0 + (z1 - z0) * fraction
                if not preparer.link(point, preparer.comm.gateway,
                                     preparer.comm.parameters.direct_budget_db)[0]:
                    failed.append(fraction)
                    for i, relay_point in enumerate(points):
                        if covered[i] and not preparer.link(
                            point, relay_point, preparer.comm.parameters.access_budget_db,
                        )[0]:
                            covered[i] = False
            cache[key] = (min(failed), max(failed), covered) if failed else None
        info = cache[key]
        if info is None:
            return None
        first, last, covered = info
        return (start + max(0, first * duration - step),
                start + min(duration, last * duration + step), covered)

    geometry = []
    for column in columns:
        cargo = [b for i, number in column.counts for b in classes[i][:number]]
        profile = evaluate_route(preparer.physics, column.type, cargo, column.route)
        info = [x for phase in profile.phases
                if (x := phase_info(column.type, phase)) is not None]
        geometry.append(None if not info else (
            min(x[0] for x in info), max(x[1] for x in info),
            tuple(all(x[2][i] for x in info) for i in range(len(points))),
        ))
    return geometry


def service_windows(relays, preparer, horizon, cutoffs):
    """Propose service intervals with explicit return, turnaround and relaunch.

    A cutoff is required for every nonfinal sortie of each physical drone.
    Components must be distinct here; component reuse is handled by the joint
    LP, not approximated by the proposal generator.
    """
    if len({r["component"] for r in relays}) != len(relays):
        raise ValueError("Window proposals require distinct relay components")
    travel = [preparer.relay(r)[1] for r in relays]
    last = {r["drone"]: i for i, r in enumerate(relays)}
    free, windows = {}, []
    for i, relay in enumerate(relays):
        drone = relay["drone"]
        begin = free.get(drone, 0.0) + travel[i]["lead"]
        end = (horizon - travel[i]["inbound"] if last[drone] == i
               else cutoffs[relay["id"]])
        if end < begin:
            raise ValueError("Empty relay service window")
        windows.append((begin, end))
        free[drone] = end + travel[i]["inbound"] + preparer.relay_inputs.spec.turnaround_s
    return windows


def start_windows(columns, geometry, relays, windows, horizon):
    """Intersect communication coverage windows with delivery/return limits."""
    if len(columns) != len(geometry) or len(relays) != len(windows):
        raise ValueError("Mismatched window catalogue")
    modes = []
    for column, info in zip(columns, geometry):
        latest = min(column.latest, horizon - column.duration)
        choices = []
        if info is None:
            if latest >= 0:
                choices.append((0.0, latest, None))
        else:
            first, last, covered = info
            for index, (begin, end) in enumerate(windows):
                if covered[index]:
                    lower = max(0.0, begin - first + RELAY_GUARD_S)
                    upper = min(latest, end - last - RELAY_GUARD_S)
                    if lower <= upper:
                        choices.append((lower, upper, relays[index]["id"]))
        modes.append(choices)
    return modes
