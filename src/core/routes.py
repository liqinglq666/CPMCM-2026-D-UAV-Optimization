"""One remaining-payload and handover calculation for every multi-stop route."""

from dataclasses import dataclass
from collections import defaultdict
from .energy import energy_feasible


@dataclass(frozen=True)
class RouteProfile:
    duration: float
    energy: float
    delivery: dict
    phases: tuple
    mass: float
    volume: float


def evaluate_route(physics, type_code, boxes, order):
    boxes = sorted(boxes, key=lambda b: b.id)
    order = tuple(order)
    if not boxes or not order:
        raise ValueError("Empty cargo or route")
    if len({b.id for b in boxes}) != len(boxes):
        raise ValueError("Duplicate cargo on route")
    if len(set(order)) != len(order) or set(order) != {b.service for b in boxes}:
        raise ValueError("Route must visit every cargo service exactly once")
    drone = physics.types[type_code]
    mass, volume = sum(b.mass for b in boxes), sum(b.volume for b in boxes)
    if mass > drone.max_payload + 1e-10 or volume > drone.max_volume + 1e-12:
        raise ValueError("Route cargo exceeds mass/volume capacity")
    by_service = defaultdict(list)
    for box in boxes:
        by_service[box.service].append(box)
    time_s = drone.prep_time + drone.load_time_per_box * len(boxes)
    energy, delivery, phases = 0.0, {}, []
    previous = "O01"
    remaining = {b.id: b for b in boxes}
    for dest in (*order, "O01"):
        seg = physics.segment(previous, dest)
        payload = sum(b.mass for b in remaining.values())
        energy += physics.energy(type_code, previous, dest, payload)
        za, zb = physics.operation_altitude(previous), physics.operation_altitude(dest)
        for name, duration, z0, z1 in (
            ("climb", seg.climb / drone.climb_speed, za, seg.cruise_alt),
            (
                "cruise",
                seg.distance / drone.cruise_speed,
                seg.cruise_alt,
                seg.cruise_alt,
            ),
            ("descent", seg.descent / drone.descent_speed, seg.cruise_alt, zb),
        ):
            phases.append(
                (name, time_s, time_s + duration, previous, dest, z0, z1, seg.distance)
            )
            time_s += duration
        if dest != "O01":
            duration = drone.handover_base + drone.handover_per_box * len(
                by_service[dest]
            )
            phases.append(
                ("handover", time_s, time_s + duration, dest, dest, zb, zb, 0.0)
            )
            time_s += duration
            for box in by_service[dest]:
                delivery[box.id] = time_s
                del remaining[box.id]
        previous = dest
    return RouteProfile(time_s, energy, delivery, tuple(phases), mass, volume)


def route_is_energy_feasible(profile, drone):
    return energy_feasible(profile.energy, drone.energy_use, drone.rho)
