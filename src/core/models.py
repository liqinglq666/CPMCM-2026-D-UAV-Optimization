"""Data types: distances in m, time in s, payload in kg, energy in kWh."""

from dataclasses import dataclass
from typing import Dict, List, Optional
from .numeric import finite, positive


@dataclass(frozen=True)
class Node:
    code: str
    lon: float
    lat: float
    elev: float

    def __post_init__(self):
        finite(self.lon, "longitude", -180, 180)
        finite(self.lat, "latitude", -90, 90)
        finite(self.elev, "elevation")


@dataclass(frozen=True)
class DroneType:
    code: str
    empty_mass: float
    max_payload: float
    max_volume: float
    cruise_speed: float
    range_empty: float
    range_full: float
    energy_use: float
    rho: float
    prep_time: float
    load_time_per_box: float
    handover_base: float
    handover_per_box: float
    climb_speed: float
    descent_speed: float
    eta_up: float
    full_charge: float = 0.0

    def __post_init__(self):
        for name in (
            "empty_mass",
            "max_payload",
            "max_volume",
            "cruise_speed",
            "range_empty",
            "range_full",
            "energy_use",
            "climb_speed",
            "descent_speed",
            "eta_up",
        ):
            positive(getattr(self, name), name)
        if self.range_full > self.range_empty:
            raise ValueError("Full-load range exceeds empty range")
        finite(self.rho, "reserve", 0, 1)
        finite(self.eta_up, "climb efficiency", 0, 1)
        for name in (
            "prep_time",
            "load_time_per_box",
            "handover_base",
            "handover_per_box",
            "full_charge",
        ):
            finite(getattr(self, name), name, 0)


@dataclass(frozen=True)
class Box:
    id: str
    service: str
    kind: str
    mass: float
    volume: float
    first: bool
    first_deadline: Optional[float]
    expected: float
    priority: float
    hard_deadline: Optional[float]

    def __post_init__(self):
        for name in ("mass", "volume", "priority"):
            positive(getattr(self, name), name)
        finite(self.expected, "expected_s", 0)
        if self.hard_deadline is not None:
            finite(self.hard_deadline, "hard_deadline_s", 0)
        if self.first_deadline is not None:
            finite(self.first_deadline, "first_deadline_s", 0)
        if self.first and self.first_deadline is None:
            raise ValueError(f"Missing first-batch deadline: {self.id}")


@dataclass(frozen=True)
class Segment:
    a: str
    b: str
    distance: float
    cruise_alt: float
    climb: float
    descent: float


@dataclass
class Resource:
    id: str
    type: str
    available: float = 0.0


@dataclass
class Trip:
    trip_id: str
    drone_id: str
    type: str
    battery_id: str
    start: float
    stops: List[str]
    boxes_by_stop: Dict[str, List[str]]
    delivery: Dict[str, float]
    end: float
    energy: float
    soc: float
