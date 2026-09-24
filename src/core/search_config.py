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
    from .numeric import positive

    positive(params["relay_local_step_m"], "relay local step")
    factors = params["q3_repair_radius_factors"]
    if not isinstance(factors, list) or not factors:
        raise ValueError("Seed repair radii must be a nonempty list")
    for factor in factors:
        positive(factor, "seed repair radius factor")
    return params
