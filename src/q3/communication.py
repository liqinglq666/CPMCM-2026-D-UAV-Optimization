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
import rasterio
from pyproj import Geod

GEOD = Geod(ellps="WGS84")
G = 9.80665


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
    d = max(distance_km, 1e-9)
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
    """
    DEM line-of-sight check.

    The segment is sampled at approximately half a raster cell in row/column
    coordinates. A terrain cell is treated as blocking when its DEM elevation
    reaches the straight 3-D radio ray.
    """
    inv = ~dem_dataset.transform
    c1, r1 = inv * (p1[0], p1[1])
    c2, r2 = inv * (p2[0], p2[1])
    n = max(2, int(max(abs(r2-r1), abs(c2-c1)) * 2) + 1)

    frac = np.linspace(0.0, 1.0, n)
    rr = np.floor(r1 + (r2-r1) * frac).astype(int)
    cc = np.floor(c1 + (c2-c1) * frac).astype(int)

    valid = (
        (rr >= 0) & (cc >= 0)
        & (rr < dem_dataset.height)
        & (cc < dem_dataset.width)
    )
    rr, cc, frac = rr[valid], cc[valid], frac[valid]
    if len(rr) <= 2:
        return False

    ray_z = p1[2] + (p2[2] - p1[2]) * frac[1:-1]
    terrain_z = dem[rr[1:-1], cc[1:-1]]
    return bool(np.any(terrain_z >= ray_z - 0.1))


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
    _, _, horizontal_m = GEOD.inv(
        p1[0], p1[1], p2[0], p2[1]
    )
    distance_km = (
        horizontal_m**2 + (p2[2]-p1[2])**2
    ) ** 0.5 / 1000.0

    fspl = free_space_path_loss(
        frequency_mhz,
        distance_km,
    )

    # If even free-space loss already exceeds the budget, DEM evaluation
    # cannot restore feasibility.
    obstructed = False
    if fspl <= max_path_loss_db:
        obstructed = _terrain_obstructed_vectorized(
            p1, p2, dem_dataset, dem
        )

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
        * cruise_time_s / 3600.0
    )
    climb_energy = (
        spec.takeoff_mass_kg
        * G
        * (outbound_climb_m + return_climb_m)
        / (spec.climb_efficiency * 3.6e6)
    )
    service_energy = (
        (spec.hover_power_kw + spec.communication_power_kw)
        * service_duration_s / 3600.0
    )
    return (
        cruise_energy
        + climb_energy
        + service_energy
    )


def two_stage_charge_time(
    full_charge_time_s: float,
    soc_fraction: float,
) -> float:
    """Appendix-2 two-stage charging time back to 100% SOC."""
    s = max(0.0, min(1.0, soc_fraction))
    if s < 0.90:
        return full_charge_time_s * (
            0.65 * (0.90 - s) / 0.90
            + 0.35
        )
    return (
        full_charge_time_s
        * 0.35
        * (1.0 - s) / 0.10
    )
