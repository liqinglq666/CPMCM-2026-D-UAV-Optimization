"""Coupled resource reassignment for a proposed transport priority order.

This is a neighborhood constructor, not a feasibility certificate. Callers
replay the result with their full transport or joint communication evaluator.
"""

from .discrete import clean_jobs
from .energy import charge_time


def rebuild_resources(jobs, evaluator):
    jobs = clean_jobs(jobs)
    drone_free = dict.fromkeys(evaluator.drones, 0.0)
    battery_free = dict.fromkeys(evaluator.batteries, 0.0)
    for job in jobs:
        profile = evaluator.profile(job)
        typ = evaluator.physics.types[job["type"]]
        drones = [d for d, t in evaluator.drones.items() if t == job["type"]]
        batteries = [b for b, t in evaluator.batteries.items() if t == job["type"]]
        if not drones or not batteries:
            raise ValueError("No matching transport inventory")
        drone = min(drones, key=lambda d: (drone_free[d], d))
        battery = min(batteries, key=lambda b: (battery_free[b], b))
        end = max(drone_free[drone], battery_free[battery]) + profile.duration
        job.update(drone=drone, battery=battery)
        drone_free[drone] = end
        battery_free[battery] = end + charge_time(
            typ, 1 - profile.energy / typ.energy_use
        )
    return jobs


def reorder_and_rebuild(jobs, evaluator, rng):
    jobs = clean_jobs(jobs)
    if len(jobs) > 1:
        left, right = rng.sample(range(len(jobs)), 2)
        if rng.random() < 0.5:
            jobs[left], jobs[right] = jobs[right], jobs[left]
        else:
            job = jobs.pop(left)
            jobs.insert(right, job)
    return rebuild_resources(jobs, evaluator)
