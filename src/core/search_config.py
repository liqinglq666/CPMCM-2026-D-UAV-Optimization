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
        "q2_restart_interval",
        "q3_iterations",
        "q3_restart_interval",
        "relay_grid_rows",
        "relay_grid_columns",
    ):
        value = params[name]
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < (0 if name in ("seed", "q2_iterations", "q3_iterations") else 1)
        ):
            raise ValueError(f"Invalid search parameter: {name}")
    from .numeric import positive

    positive(params["relay_local_step_m"], "relay local step")
    return params
