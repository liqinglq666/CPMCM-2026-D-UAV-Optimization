"""Compatibility exports; canonical radio and relay physics live in src.core."""

from src.core.communication import (
    Radio,
    RelaySpec,
    bidirectional_loss_threshold,
    free_space_path_loss,
    link_available,
    relay_sortie_energy,
    two_stage_charge_time,
)

__all__ = [
    "Radio",
    "RelaySpec",
    "bidirectional_loss_threshold",
    "free_space_path_loss",
    "link_available",
    "relay_sortie_energy",
    "two_stage_charge_time",
]
