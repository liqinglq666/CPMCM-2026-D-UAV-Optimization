"""Count-compressed sortie columns and interval-graph resource reconstruction.

Cargo classes are interchangeable only for the all-on-time subproblem. The
column catalogue exhausts one/two-stop patterns, not unrestricted routes.
Neither that restriction nor a time grid supplies a global continuous bound.
"""

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations, permutations, product
import heapq

from src.core.energy import charge_time
from src.core.routes import evaluate_route, route_is_energy_feasible


@dataclass(frozen=True)
class SortieColumn:
    type: str
    counts: tuple
    route: tuple
    duration: float
    energy: float
    charge: float
    latest: float


def cargo_classes(boxes):
    groups = defaultdict(list)
    for box in boxes:
        # All expected dates are enforced in this subproblem. First-batch and
        # medical deadlines remain enforced even if earlier than expectation.
        due = min(box.expected, box.expected if box.hard_deadline is None else box.hard_deadline)
        key = (box.service, box.kind, box.mass, box.volume, box.expected,
               box.priority, due)
        groups[key].append(box)
    return [sorted(groups[k], key=lambda b: b.id) for k in sorted(groups)]


def enumerate_columns(physics, classes, max_stops=2):
    """Enumerate every count pattern and visit order within max_stops."""
    services = sorted({group[0].service for group in classes})
    subsets = {}
    for service in services:
        indices = [i for i, group in enumerate(classes) if group[0].service == service]
        patterns = []
        for counts in product(*(range(len(classes[i]) + 1) for i in indices)):
            if not any(counts):
                continue
            cargo = [b for i, number in zip(indices, counts) for b in classes[i][:number]]
            patterns.append((
                tuple((i, number) for i, number in zip(indices, counts) if number),
                cargo, sum(b.mass for b in cargo), sum(b.volume for b in cargo),
            ))
        subsets[service] = patterns
    columns = []
    for size in range(1, min(max_stops, len(services)) + 1):
        for stops in combinations(services, size):
            for patterns in product(*(subsets[s] for s in stops)):
                mass, volume = sum(p[2] for p in patterns), sum(p[3] for p in patterns)
                eligible = [t for t in physics.types.values()
                            if mass <= t.max_payload + 1e-10
                            and volume <= t.max_volume + 1e-12]
                if not eligible:
                    continue
                counts = tuple(x for pat in patterns for x in pat[0])
                cargo = [b for pat in patterns for b in pat[1]]
                for drone in eligible:
                    for route in permutations(stops):
                        profile = evaluate_route(physics, drone.code, cargo, route)
                        if not route_is_energy_feasible(profile, drone):
                            continue
                        latest = min(
                            min(b.expected, b.expected if b.hard_deadline is None else b.hard_deadline)
                            - profile.delivery[b.id] for b in cargo
                        )
                        if latest < 0:
                            continue
                        columns.append(SortieColumn(
                            drone.code, counts, route, profile.duration, profile.energy,
                            charge_time(drone, 1 - profile.energy / drone.energy_use), latest,
                        ))
    return columns


def color_intervals(intervals, resources):
    """Optimal coloring of half-open intervals using interchangeable resources.

    Each input is (task_index, start, end). Earliest-finish reuse is possible iff
    the interval clique number fits the inventory. Exact endpoints are used;
    a shortage is rejected rather than hidden by rounding an overlap away.
    """
    available = [(r.available, r.id) for r in resources]
    heapq.heapify(available)
    assignment = {}
    for index, start, end in sorted(intervals, key=lambda item: (item[1], item[0])):
        if end < start or start < 0:
            raise ValueError("Invalid resource interval")
        if not available or available[0][0] > start + 1e-8:
            raise ValueError("Interval peak exceeds resource inventory")
        _free, resource = heapq.heappop(available)
        assignment[index] = resource
        heapq.heappush(available, (end, resource))
    return assignment


def reconstruct(columns, choices, classes, drones, batteries):
    """Expand integer count decisions into unique boxes and resource IDs."""
    pending = [list(group) for group in classes]
    jobs, intervals, battery_intervals = [], defaultdict(list), defaultdict(list)
    for col_index, start, copies in sorted(choices, key=lambda x: (x[1], x[0])):
        if copies < 0 or int(copies) != copies:
            raise ValueError("Noninteger column multiplicity")
        col = columns[col_index]
        for _ in range(copies):
            cargo = []
            for group, number in col.counts:
                if len(pending[group]) < number:
                    raise ValueError("Column demand overcovered")
                cargo.extend(b.id for b in pending[group][:number])
                del pending[group][:number]
            index = len(jobs)
            jobs.append(dict(id=f"column-{index:03d}", type=col.type,
                             route=list(col.route), boxes=sorted(cargo), start=start))
            intervals[col.type].append((index, start, start + col.duration))
            battery_intervals[col.type].append((index, start, start + col.duration + col.charge))
    if any(pending):
        raise ValueError("Column demand undercovered")
    for kind, specs, occupancy in (("drone", drones, intervals),
                                   ("battery", batteries, battery_intervals)):
        for code, group in occupancy.items():
            assigned = color_intervals(group, [r for r in specs if r.type == code])
            for index, resource in assigned.items():
                jobs[index][kind] = resource
    return jobs
