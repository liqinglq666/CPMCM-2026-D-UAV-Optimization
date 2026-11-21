"""Fresh physics and union-grid communication checks, without coordinate rounding."""

from functools import lru_cache
from copy import deepcopy

from src.core.discrete import TransportEvaluator
from src.core.communication import relay_travel
from src.core.sampling import sample_audit_states, audit_steps


class PlanPreparer(TransportEvaluator):
    def __init__(
        self, physics, boxes, drones, batteries, relay_inputs, communication, step_s
    ):
        super().__init__(physics, boxes, drones, batteries)
        self.relay_inputs = relay_inputs
        self.comm = communication
        self.step_s = step_s
        self.audit_steps = audit_steps(step_s)
        # Exact argument keys, lifetime limited to this input/DEM generation.
        self.link = lru_cache(maxsize=250000)(communication.link)
        self.outage_cache = {}
        self.access_cache = {}
        self.relay_cache = {}

    def key(self, job):
        return (job["type"], tuple(sorted(job["boxes"])), tuple(job["route"]))

    def outages(self, job):
        key = self.key(job)
        if key not in self.outage_cache:
            states = list(
                sample_audit_states(self.profile(job), self.physics, self.step_s)
            )
            outages = [
                (t, point)
                for t, point in states
                if not self.link(
                    point, self.comm.gateway, self.comm.parameters.direct_budget_db
                )[0]
            ]
            self.outage_cache[key] = len(states), outages
        return self.outage_cache[key]

    def relay(self, relay):
        spec = self.relay_inputs.spec
        lon, lat = relay["lon"], relay["lat"]
        agl = relay.get("agl_m", spec.max_hover_agl_m)
        key = (lon, lat, agl)
        if key not in self.relay_cache:
            point = (lon, lat, self.physics.terrain.elevation(lon, lat) + agl)
            travel = relay_travel(self.physics, spec, point)
            if not self.link(
                point, self.comm.gateway, self.comm.parameters.backhaul_budget_db
            )[0]:
                raise ValueError("Unavailable relay backhaul")
            self.relay_cache[key] = point, travel
        return self.relay_cache[key]

    def covers(self, job, relay):
        point, _travel = self.relay(relay)
        key = (self.key(job), point)
        if key not in self.access_cache:
            _checked, outages = self.outages(job)
            self.access_cache[key] = all(
                self.link(p, point, self.comm.parameters.access_budget_db)[0]
                for _t, p in outages
            )
        return self.access_cache[key]

    def prepare(self, plan):
        plan = deepcopy(plan)
        jobs, relays = plan["jobs"], plan["relays"]
        self.precheck(jobs)
        if len({r["id"] for r in relays}) != len(relays):
            raise ValueError("Duplicate relay IDs")
        relay_map = {r["id"]: r for r in relays}
        for relay in relays:
            if (
                relay["drone"] not in self.relay_inputs.drone_ids
                or relay["component"] not in self.relay_inputs.component_ids
            ):
                raise ValueError("Relay resource outside official inventory")
            relay["point"], relay["travel"] = self.relay(relay)
        for job in jobs:
            rid = job.get("relay")
            if rid is not None and rid not in relay_map:
                raise ValueError("Unknown relay sortie")
            checked, outages = self.outages(job)
            if outages and (rid is None or not self.covers(job, relay_map[rid])):
                raise ValueError(
                    "Uncovered union-grid communication state (1 s + 0.5 s)"
                )
            job.update(
                profile=self.profile(job),
                checked_states=checked,
                outage=(outages[0][0], outages[-1][0]) if outages else None,
            )
        return jobs, relays
