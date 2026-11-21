# -*- coding: utf-8 -*-
"""
Shared communication / relay physics engine for CPMCM 2026 Problem D.

AI-assisted development:
- Tool: ChatGPT
- Model: GPT-5.6 Sol
- Developer: OpenAI

The participating team must independently verify all equations, parameters
and numerical results before competition submission.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Tuple

import numpy as np
from src.core.terrain import Terrain, horizontal_distance
from src.core.numeric import finite, positive
from src.core.energy import (
    climb_energy,
    flight_time,
    two_stage_charge_time as two_stage_charge_time,
)
from src.config import (
    SECONDS_PER_HOUR,
    COMMUNICATION_STEP_S,
    TERRAIN_CLEARANCE_M,
    FEASIBILITY_TOL,
)


@dataclass(frozen=True)
class Radio:
    tx_power_dbm: float
    antenna_gain_dbi: float
    sensitivity_dbm: float

    def __post_init__(self):
        for name, value in vars(self).items():
            finite(value, name)


@dataclass(frozen=True)
class RelaySpec:
    takeoff_mass_kg: float
    cruise_speed_mps: float
    cruise_power_kw: float
    usable_energy_kwh: float
    reserve_fraction: float
    prep_s: float
    link_setup_s: float
    turnaround_s: float
    climb_speed_mps: float
    descent_speed_mps: float
    climb_efficiency: float
    hover_power_kw: float
    communication_power_kw: float
    max_hover_agl_m: float

    def __post_init__(self):
        for name, value in vars(self).items():
            finite(value, name, 0)
        for name in (
            "takeoff_mass_kg",
            "cruise_speed_mps",
            "usable_energy_kwh",
            "climb_speed_mps",
            "descent_speed_mps",
            "climb_efficiency",
        ):
            positive(getattr(self, name), name)
        finite(self.reserve_fraction, "reserve", 0, 1)
        finite(self.climb_efficiency, "climb efficiency", 0, 1)


def bidirectional_loss_threshold(
    a: Radio,
    b: Radio,
    system_loss_db: float,
    fade_margin_db: float,
) -> float:
    """Return the stricter of the two directional path-loss budgets."""
    pth_a = a.sensitivity_dbm + fade_margin_db
    pth_b = b.sensitivity_dbm + fade_margin_db
    ab = (
        a.tx_power_dbm
        + a.antenna_gain_dbi
        + b.antenna_gain_dbi
        - system_loss_db
        - pth_b
    )
    ba = (
        b.tx_power_dbm
        + b.antenna_gain_dbi
        + a.antenna_gain_dbi
        - system_loss_db
        - pth_a
    )
    return min(ab, ba)


def free_space_path_loss(
    frequency_mhz: float,
    distance_km: float,
) -> float:
    positive(frequency_mhz, "frequency_mhz")
    finite(distance_km, "distance_km", 0)
    if distance_km == 0:
        return -math.inf  # coincident endpoints: zero-distance FSPL limit
    d = distance_km
    return 32.45 + 20.0 * math.log10(frequency_mhz) + 20.0 * math.log10(d)


def link_available(
    p1: Tuple[float, float, float],
    p2: Tuple[float, float, float],
    frequency_mhz: float,
    max_path_loss_db: float,
    obstruction_loss_db: float,
    dem_dataset,
    dem: np.ndarray,
):
    """Return (available, total_path_loss_db, obstructed)."""
    horizontal_m = horizontal_distance(p1, p2)
    distance_km = (horizontal_m**2 + (p2[2] - p1[2]) ** 2) ** 0.5 / 1000.0

    fspl = free_space_path_loss(
        frequency_mhz,
        distance_km,
    )

    finite(max_path_loss_db, "link budget")
    finite(obstruction_loss_db, "obstruction loss", 0)
    # Diagnostic loss and obstruction must stay truthful even for unavailable links.
    terrain = (
        dem_dataset
        if isinstance(dem_dataset, Terrain)
        else Terrain(dem, dem_dataset.transform, dem_dataset.nodata)
    )
    obstructed = terrain.obstructed(p1, p2)

    path_loss = fspl + (obstruction_loss_db if obstructed else 0.0)
    return (
        path_loss <= max_path_loss_db,
        path_loss,
        obstructed,
    )


def relay_sortie_energy(
    spec: RelaySpec,
    horizontal_distance_m: float,
    outbound_climb_m: float,
    return_climb_m: float,
    service_duration_s: float,
) -> float:
    """
    Relay energy in kWh:
    two-way horizontal cruise + positive climb work + hover/communication.
    Descent has no extra energy term under the current problem interpretation.
    """
    for name, value in (
        ("horizontal_distance_m", horizontal_distance_m),
        ("outbound_climb_m", outbound_climb_m),
        ("return_climb_m", return_climb_m),
        ("service_duration_s", service_duration_s),
    ):
        finite(value, name, 0)
    cruise_time_s = 2.0 * horizontal_distance_m / spec.cruise_speed_mps
    cruise_energy = spec.cruise_power_kw * cruise_time_s / SECONDS_PER_HOUR
    ascent_energy = climb_energy(
        spec.takeoff_mass_kg, outbound_climb_m + return_climb_m, spec.climb_efficiency
    )
    finite(service_duration_s, "service_duration_s", 0)
    service_energy = (
        (spec.hover_power_kw + spec.communication_power_kw)
        * service_duration_s
        / SECONDS_PER_HOUR
    )
    return cruise_energy + ascent_energy + service_energy


class Communication:
    def __init__(self, physics, parameters):
        self.physics, self.parameters = physics, parameters
        origin = physics.nodes["O01"]
        self.gateway = (origin.lon, origin.lat, origin.elev + parameters.gateway_agl_m)

    def link(self, first, second, budget):
        terrain = self.physics.terrain
        return link_available(
            first,
            second,
            self.parameters.frequency_mhz,
            budget,
            self.parameters.obstruction_loss_db,
            terrain,
            terrain.dem,
        )


def sample_states(profile, physics, step_s=COMMUNICATION_STEP_S):
    """Include both ends of every climb/cruise/descent/handover phase."""
    positive(step_s, "communication step_s")
    for phase, start, end, source, target, z0, z1, _distance in profile.phases:
        count = max(1, math.ceil((end - start) / step_s))
        first, second = physics.nodes[source], physics.nodes[target]
        for index in range(count + 1):
            fraction = index / count
            if phase == "cruise":
                # Same horizontal straight segment as DEM extraction.
                lon = first.lon + (second.lon - first.lon) * fraction
                lat = first.lat + (second.lat - first.lat) * fraction
            else:
                node = second if phase == "descent" else first
                lon, lat = node.lon, node.lat
            yield (
                start + (end - start) * fraction,
                (lon, lat, z0 + (z1 - z0) * fraction),
            )


def relay_travel(physics, spec, point):
    origin = physics.nodes["O01"]
    start = (origin.lon, origin.lat, origin.elev)
    elevation = physics.terrain.elevation(*point[:2])
    agl = point[2] - elevation
    if not 0 <= agl <= spec.max_hover_agl_m + FEASIBILITY_TOL:
        raise ValueError(f"Relay hover AGL out of bounds: {agl}")
    distance = horizontal_distance(start, point)
    # A relay can hover above the terrain-clearance altitude: cruise must also
    # reach its selected hover altitude. This endpoint rule is explicit.
    cruise = max(
        physics.terrain.maximum(start, point) + TERRAIN_CLEARANCE_M, start[2], point[2]
    )
    climb, descent = cruise - start[2], cruise - point[2]
    outbound = flight_time(
        distance,
        climb,
        descent,
        spec.cruise_speed_mps,
        spec.climb_speed_mps,
        spec.descent_speed_mps,
    )
    inbound = flight_time(
        distance,
        descent,
        climb,
        spec.cruise_speed_mps,
        spec.climb_speed_mps,
        spec.descent_speed_mps,
    )
    # The UAV is airborne during link setup, so include hover + radio power.
    energy = relay_sortie_energy(spec, distance, climb, descent, spec.link_setup_s)
    return dict(
        outbound=outbound,
        inbound=inbound,
        lead=spec.prep_s + outbound + spec.link_setup_s,
        fixed_energy=energy,
    )
