"""Appendix-2 authoritative energy (kWh), flight (s) and charging rules."""

from src.config import (
    GRAVITY_MPS2,
    JOULES_PER_KWH,
    CHARGE_KNEE_SOC,
    CHARGE_FAST_FRACTION,
    FEASIBILITY_TOL,
)
from .numeric import finite, positive


def equivalent_range(drone, payload_kg: float) -> float:
    payload_kg = finite(payload_kg, "payload_kg", 0)
    if payload_kg > drone.max_payload + 1e-10:
        raise ValueError(f"Payload {payload_kg} exceeds {drone.code} capacity")
    return (
        drone.range_empty
        - (drone.range_empty - drone.range_full)
        * (payload_kg / drone.max_payload) ** 1.5
    )


def climb_energy(mass_kg, climb_m, efficiency):
    finite(mass_kg, "mass_kg", 0)
    finite(climb_m, "climb_m", 0)
    positive(efficiency, "climb efficiency")
    finite(efficiency, "climb efficiency", 0, 1)
    return mass_kg * GRAVITY_MPS2 * climb_m / (efficiency * JOULES_PER_KWH)


def leg_energy(drone, distance: float, h_up: float, q: float):
    finite(distance, "distance_m", 0)
    horizontal = drone.energy_use * distance / equivalent_range(drone, q)
    climb = climb_energy(drone.empty_mass + q, h_up, drone.eta_up)
    return horizontal + climb, horizontal, climb


def flight_time(distance_m, climb_m, descent_m, cruise_mps, climb_mps, descent_mps):
    for name, value in (
        ("distance", distance_m),
        ("climb", climb_m),
        ("descent", descent_m),
    ):
        finite(value, name, 0)
    for value in (cruise_mps, climb_mps, descent_mps):
        positive(value, "speed_mps")
    return climb_m / climb_mps + distance_m / cruise_mps + descent_m / descent_mps


def energy_feasible(energy_kwh, capacity_kwh, reserve):
    finite(energy_kwh, "energy_kwh", 0)
    positive(capacity_kwh, "capacity_kwh")
    finite(reserve, "reserve", 0, 1)
    return energy_kwh <= (1 - reserve) * capacity_kwh + FEASIBILITY_TOL


def two_stage_charge_time(full_charge_time_s: float, soc_fraction: float) -> float:
    finite(full_charge_time_s, "full_charge_time_s", 0)
    s = finite(soc_fraction, "soc_fraction", 0, 1)
    slow = 1 - CHARGE_FAST_FRACTION
    if s < CHARGE_KNEE_SOC:
        return full_charge_time_s * (
            CHARGE_FAST_FRACTION * (CHARGE_KNEE_SOC - s) / CHARGE_KNEE_SOC + slow
        )
    return full_charge_time_s * slow * (1 - s) / (1 - CHARGE_KNEE_SOC)


def charge_time(drone, soc):
    return two_stage_charge_time(drone.full_charge, soc)
