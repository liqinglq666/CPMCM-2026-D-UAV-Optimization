"""Discrete transport moves shared by Q2 and Q3; all physics stays in routes.

A plan is an ordered list of jobs. This order induces the precedence on each
physical resource, but does not prevent unrelated resources running in parallel.
No times or objective values are part of the discrete state.
"""

from collections import Counter
from copy import deepcopy
import hashlib
import json

from .energy import charge_time
from .routes import evaluate_route, route_is_energy_feasible
from .numeric import lexicographic_less
from src.config import MAX_ROUTE_SERVICES

JOB_KEYS = ("id", "type", "drone", "battery", "boxes", "route", "relay")
TRANSPORT_MOVES = (
    "relocate",
    "swap",
    "merge",
    "split",
    "destroy_repair",
    "route_order",
    "type",
    "drone",
    "battery",
    "resource_order",
)
OBJECTIVE_TOLERANCES = (1e-5, 0, 1e-6, 1e-9)


def service_components(routes):
    """Connected service sets induced by indivisible multi-stop routes."""
    routes = [tuple(route) for route in routes]
    services = sorted({service for route in routes for service in route})
    parent = {service: service for service in services}

    def find(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left, right):
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    for route in routes:
        for left, right in zip(route, route[1:]):
            union(left, right)
    components = {}
    for service in services:
        components.setdefault(find(service), []).append(service)
    return sorted(components.values(), key=lambda values: (-len(values), values))


def clean_jobs(jobs):
    return [{k: deepcopy(j[k]) for k in JOB_KEYS if k in j} for j in jobs]


def fingerprint(plan):
    encoded = json.dumps(plan, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def q2_objective(result):
    return (
        result["weighted_tardiness"],
        result["trips"],
        result["makespan"],
        result["energy"],
    )


def improves(candidate, incumbent, tolerances=OBJECTIVE_TOLERANCES):
    return lexicographic_less(candidate, incumbent, tolerances)


def dominates(left, right, tolerances=OBJECTIVE_TOLERANCES):
    return all(a <= b + t for a, b, t in zip(left, right, tolerances)) and any(
        a < b - t for a, b, t in zip(left, right, tolerances)
    )


class TransportEvaluator:
    """Cache only freshly evaluated profiles, scoped to one immutable input set."""

    def __init__(self, physics, boxes, drones, batteries):
        self.physics = physics
        self.boxes = boxes
        self.drones = {r.id: r.type for r in drones}
        self.batteries = {r.id: r.type for r in batteries}
        self.profiles = {}

    def profile(self, job):
        key = (job["type"], tuple(sorted(job["boxes"])), tuple(job["route"]))
        if key not in self.profiles:
            p = evaluate_route(
                self.physics, job["type"], [self.boxes[b] for b in key[1]], key[2]
            )
            if not route_is_energy_feasible(p, self.physics.types[job["type"]]):
                raise ValueError("Transport reserve violated")
            self.profiles[key] = p
        return self.profiles[key]

    def precheck(self, jobs):
        if not jobs or len({j["id"] for j in jobs}) != len(jobs):
            raise ValueError("Empty or duplicate transport jobs")
        if Counter(b for j in jobs for b in j["boxes"]) != Counter(self.boxes.keys()):
            raise ValueError("Cargo must be delivered exactly once")
        for job in jobs:
            if (
                self.drones.get(job["drone"]) != job["type"]
                or self.batteries.get(job["battery"]) != job["type"]
            ):
                raise ValueError("Transport resource/type mismatch")
            p = self.profile(job)
            if any(
                p.delivery[b] > self.boxes[b].hard_deadline + 1e-7
                for b in job["boxes"]
                if self.boxes[b].hard_deadline is not None
            ):
                raise ValueError("Route cannot meet a hard deadline even at time zero")

    def schedule(self, jobs):
        """Exact earliest starts for fixed routes, assignments and resource order.

        All transport objectives are nondecreasing in start times. Longest-path
        propagation in the induced acyclic precedence graph therefore attains
        their common minimum for this discrete state, without an LP.
        """
        self.precheck(jobs)
        uav_free = dict.fromkeys(self.drones, 0.0)
        battery_free = dict.fromkeys(self.batteries, 0.0)
        scheduled = []
        tardiness = 0.0
        for index, job in enumerate(jobs):
            p = self.profile(job)
            typ = self.physics.types[job["type"]]
            start = max(uav_free[job["drone"]], battery_free[job["battery"]])
            delivery = {b: start + t for b, t in p.delivery.items()}
            if any(
                delivery[b] > self.boxes[b].hard_deadline + 1e-7
                for b in job["boxes"]
                if self.boxes[b].hard_deadline is not None
            ):
                raise ValueError("Hard deadline violated")
            tardiness += sum(
                self.boxes[b].priority * max(0.0, t - self.boxes[b].expected)
                for b, t in delivery.items()
            )
            end = start + p.duration
            soc = 1 - p.energy / typ.energy_use
            uav_free[job["drone"]] = end
            battery_free[job["battery"]] = end + charge_time(typ, soc)
            scheduled.append(
                dict(
                    job=job,
                    profile=p,
                    start=start,
                    end=end,
                    delivery=delivery,
                    soc=100 * soc,
                    group=index,
                )
            )
        return dict(
            jobs=scheduled,
            hard_violations=0,
            weighted_tardiness=tardiness,
            trips=len(jobs),
            makespan=max(j["end"] for j in scheduled),
            energy=sum(j["profile"].energy for j in scheduled),
        )

    def repair_job(self, job, rng):
        """Retain route order, remove empty stops, insert new stops by distance."""
        services = {self.boxes[b].service for b in job["boxes"]}
        if not services or len(services) > MAX_ROUTE_SERVICES:
            raise ValueError("Outside the bounded route neighborhood")
        route = [s for s in job["route"] if s in services]
        for service in sorted(services - set(route)):

            def distance(i):
                trial = ["O01"] + route[:i] + [service] + route[i:] + ["O01"]
                return sum(
                    self.physics.segment(a, b).distance
                    for a, b in zip(trial, trial[1:])
                )

            route.insert(min(range(len(route) + 1), key=distance), service)
        job["route"] = route
        job["boxes"] = sorted(job["boxes"])
        alternatives = [t for t in sorted(self.physics.types) if t != job["type"]]
        rng.shuffle(alternatives)
        for typ in [job["type"]] + alternatives:
            ds = sorted(d for d, t in self.drones.items() if t == typ)
            bs = sorted(b for b, t in self.batteries.items() if t == typ)
            if not ds or not bs:
                continue
            trial = dict(job, type=typ)
            try:
                self.profile(trial)
            except ValueError:
                continue
            job["type"] = typ
            if job["drone"] not in ds:
                job["drone"] = rng.choice(ds)
            if job["battery"] not in bs:
                job["battery"] = rng.choice(bs)
            return
        raise ValueError("No feasible type for cargo/route")


def transport_neighbor(jobs, operator, rng, evaluator, iteration):
    """One bounded neighborhood move; infeasible proposals are rejected upstream."""
    jobs = clean_jobs(jobs)
    if operator not in TRANSPORT_MOVES:
        raise ValueError(f"Unknown transport move: {operator}")
    i = rng.randrange(len(jobs))
    job = jobs[i]
    if operator in ("relocate", "swap", "merge", "destroy_repair"):
        if len(jobs) < 2:
            raise ValueError("Move requires two jobs")
        j = rng.choice([k for k in range(len(jobs)) if k != i])
        other = jobs[j]
        if operator == "relocate":
            box = rng.choice(job["boxes"])
            job["boxes"].remove(box)
            other["boxes"].append(box)
        elif operator == "swap":
            a, b = rng.randrange(len(job["boxes"])), rng.randrange(len(other["boxes"]))
            job["boxes"][a], other["boxes"][b] = other["boxes"][b], job["boxes"][a]
        elif operator == "merge":
            job["boxes"] += other["boxes"]
            other["boxes"] = []
        else:
            pool = sorted(job["boxes"] + other["boxes"])
            rng.shuffle(pool)
            cut = rng.randrange(1, len(pool))
            job["boxes"], other["boxes"] = pool[:cut], pool[cut:]
        for changed in (job, other):
            if changed["boxes"]:
                evaluator.repair_job(changed, rng)
        jobs = [j for j in jobs if j["boxes"]]
    elif operator == "split":
        if len(job["boxes"]) < 2:
            raise ValueError("Cannot split singleton")
        pool = sorted(job["boxes"])
        rng.shuffle(pool)
        cut = rng.randrange(1, len(pool))
        new = deepcopy(job)
        new["id"] = f"split-{iteration}-{job['id']}"
        job["boxes"], new["boxes"] = pool[:cut], pool[cut:]
        for changed in (job, new):
            evaluator.repair_job(changed, rng)
        new["drone"] = rng.choice(
            sorted(d for d, t in evaluator.drones.items() if t == new["type"])
        )
        new["battery"] = rng.choice(
            sorted(b for b, t in evaluator.batteries.items() if t == new["type"])
        )
        jobs.insert(rng.randrange(len(jobs) + 1), new)
    elif operator == "route_order":
        if len(job["route"]) < 2:
            raise ValueError("No alternate visit order")
        a, b = rng.sample(range(len(job["route"])), 2)
        job["route"][a], job["route"][b] = job["route"][b], job["route"][a]
    elif operator == "type":
        choices = [
            t
            for t in sorted(evaluator.physics.types)
            if t != job["type"]
            and t in evaluator.drones.values()
            and t in evaluator.batteries.values()
        ]
        if not choices:
            raise ValueError("No alternate type")
        job["type"] = rng.choice(choices)
        # An explicitly selected type must be evaluated, not silently reverted.
        evaluator.profile(job)
        job["drone"] = rng.choice(
            sorted(d for d, t in evaluator.drones.items() if t == job["type"])
        )
        job["battery"] = rng.choice(
            sorted(b for b, t in evaluator.batteries.items() if t == job["type"])
        )
    elif operator in ("drone", "battery"):
        resources = evaluator.drones if operator == "drone" else evaluator.batteries
        choices = sorted(
            r for r, t in resources.items() if t == job["type"] and r != job[operator]
        )
        if not choices:
            raise ValueError("No alternate resource")
        job[operator] = rng.choice(choices)
    else:
        jobs.pop(i)
        jobs.insert(rng.randrange(len(jobs) + 1), job)
    return jobs
