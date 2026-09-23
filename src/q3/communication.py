# -*- coding: utf-8 -*-
"""
Q3 communication / relay physics engine for CPMCM 2026 Problem D.

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
from src.core.energy import climb_energy, two_stage_charge_time as two_stage_charge_time
from src.config import SECONDS_PER_HOUR


@dataclass(frozen=True)
class Radio:
    tx_power_dbm: float
    antenna_gain_dbi: float
    sensitivity_dbm: float


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
    return (
        32.45
        + 20.0 * math.log10(frequency_mhz)
        + 20.0 * math.log10(d)
    )


def _terrain_obstructed_vectorized(
    p1: Tuple[float, float, float],
    p2: Tuple[float, float, float],
    dem_dataset,
    dem: np.ndarray,
) -> bool:
    terrain = dem_dataset if isinstance(dem_dataset, Terrain) else Terrain(
        dem, dem_dataset.transform, dem_dataset.nodata)
    return terrain.obstructed(p1, p2)


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
    distance_km = (
        horizontal_m**2 + (p2[2]-p1[2])**2
    ) ** 0.5 / 1000.0

    fspl = free_space_path_loss(
        frequency_mhz,
        distance_km,
    )

    finite(max_path_loss_db, "link budget")
    finite(obstruction_loss_db, "obstruction loss", 0)
    # Diagnostic loss and obstruction must stay truthful even for unavailable links.
    obstructed = _terrain_obstructed_vectorized(p1, p2, dem_dataset, dem)

    path_loss = fspl + (
        obstruction_loss_db if obstructed else 0.0
    )
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
    cruise_time_s = (
        2.0 * horizontal_distance_m
        / spec.cruise_speed_mps
    )
    cruise_energy = (
        spec.cruise_power_kw
        * cruise_time_s / SECONDS_PER_HOUR
    )
    ascent_energy = climb_energy(spec.takeoff_mass_kg, outbound_climb_m + return_climb_m,
                                  spec.climb_efficiency)
    finite(service_duration_s, "service_duration_s", 0)
    service_energy = (
        (spec.hover_power_kw + spec.communication_power_kw)
        * service_duration_s / SECONDS_PER_HOUR
    )
    return (
        cruise_energy
        + ascent_energy
        + service_energy
    )

