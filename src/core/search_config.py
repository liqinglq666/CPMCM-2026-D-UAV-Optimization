"""Validated algorithm parameters, separate from official physical inputs."""

import json
from src.config import PROJECT_ROOT


def load_search_parameters():
    params = json.loads(
        (PROJECT_ROOT / "config/search.json").read_text(encoding="utf-8")
    )
    for name in (
        "seed",
        "q2_iterations",
        "q2_resource_iterations",
        "q2_restart_interval",
        "q3_iterations",
        "q3_restart_interval",
        "q3_target_transport_trips",
        "q3_target_relay_sorties",
        "relay_grid_rows",
        "relay_grid_columns",
        "q3_repair_combination_limit",
    ):
        value = params[name]
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < (0 if name in ("seed", "q2_iterations", "q2_resource_iterations", "q3_iterations") else 1)
        ):
            raise ValueError(f"Invalid search parameter: {name}")
    for name in ("column_iterations", "column_grid_s", "column_mip_seconds",
                 "q2_column_horizon_s", "q3_column_horizon_s"):
        value = params[name]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"Invalid search parameter: {name}")
    from .numeric import positive

    for prefix in ("q2", "q3"):
        if params.get(f"{prefix}_selection_mode", "count") not in ("count", "completion"):
            raise ValueError("Unknown search selection mode")
        if params.get(f"{prefix}_selection_mode") == "completion":
            value = params.get(f"{prefix}_trip_cap")
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError("Invalid completion trip cap")
    if params.get("q3_selection_mode") == "completion":
        value = params.get("q3_relay_cap")
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError("Invalid completion relay cap")
    import math

    for name in ("column_trip_penalty", "column_integer_reduced_cost_limit"):
        if name in params and (isinstance(params[name], bool)
                               or not isinstance(params[name], (int, float))
                               or not math.isfinite(params[name]) or params[name] < 0):
            raise ValueError(f"Invalid search parameter: {name}")
    for name in ("q3_resource_iterations", "q3_resource_seconds", "q3_location_rounds"):
        if name in params and (isinstance(params[name], bool)
                               or not isinstance(params[name], int) or params[name] < 0):
            raise ValueError(f"Invalid search parameter: {name}")
    if params.get("q3_resource_iterations", 0) and not params.get("q3_resource_seconds", 0):
        raise ValueError("Resource search requires a positive time budget")
    for value in params.get("q3_hover_height_fractions", [0.75, 1.0]):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1:
            raise ValueError("Invalid relay height fraction")
    for value in params.get("q3_location_radii_m", [0]):
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not math.isfinite(value) or value < 0):
            raise ValueError("Invalid relay location radius")

    positive(params["relay_local_step_m"], "relay local step")
    factors = params["q3_repair_radius_factors"]
    if not isinstance(factors, list) or not factors:
        raise ValueError("Seed repair radii must be a nonempty list")
    for factor in factors:
        positive(factor, "seed repair radius factor")
    return params
