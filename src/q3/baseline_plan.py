# -*- coding: utf-8 -*-
"""Communication-aware Q3 feasible baseline decisions.

This module records the selected relay states and wave assignment used by
results/q3. It intentionally does not claim global optimality.
"""

from __future__ import annotations

# (longitude, latitude, hover altitude MSL)
RELAY_CANDIDATES = {
    "G02_01": (109.1968578, 23.0152097, 631.6434021),
    "G02_02": (109.1968578, 23.0332097, 683.4054260),
    "G03_02": (109.2148578, 23.0332097, 552.0204163),
    "G04_04": (109.2328578, 23.0692097, 564.9332581),
    "G06_01": (109.2688578, 23.0152097, 642.9300842),
    "G07_04": (109.2868578, 23.0692097, 882.3285522),
}

# The key Q2->Q3 cooperation change:
# split / reorder early western missions to release the western relay earlier.
TRANSPORT_REDESIGN = {
    "Q3-003": {
        "type": "B",
        "route": ["S007"],
        "boxes": ["S007-WAT-01"],
    },
    "Q3-004": {
        "type": "B",
        "route": ["S007", "S006"],
        "boxes": [
            "S007-MED-01",
            "S006-MED-01",
            "S006-WAT-01",
        ],
    },
    "Q3-023": {
        "type": "A",
        "route": ["S015"],
        "boxes": ["S015-MED-01", "S015-WAT-01"],
    },
}

RELAY_WAVES = [
    {
        "relay_sortie": "R01-01",
        "relay_uav": "R01",
        "component": "R-BAT-01",
        "candidate": "G02_01",
        "transport_trips": ["Q3-003", "Q3-004"],
    },
    {
        "relay_sortie": "R01-02",
        "relay_uav": "R01",
        "component": "R-BAT-02",
        "candidate": "G03_02",
        "transport_trips": ["Q3-001", "Q3-002"],
    },
    {
        "relay_sortie": "R01-03",
        "relay_uav": "R01",
        "component": "R-BAT-03",
        "candidate": "G02_02",
        "transport_trips": [
            "Q3-011", "Q3-014", "Q3-021",
            "Q3-022", "Q3-023",
        ],
    },
    {
        "relay_sortie": "R02-01",
        "relay_uav": "R02",
        "component": "R-BAT-04",
        "candidate": "G06_01",
        "transport_trips": [
            "Q3-005", "Q3-006", "Q3-007", "Q3-012",
        ],
    },
    {
        "relay_sortie": "R02-02",
        "relay_uav": "R02",
        "component": "R-BAT-05",
        "candidate": "G04_04",
        "transport_trips": [
            "Q3-010", "Q3-013", "Q3-015A",
            "Q3-015B", "Q3-017", "Q3-018", "Q3-020",
        ],
    },
    {
        "relay_sortie": "R02-03",
        "relay_uav": "R02",
        "component": "R-BAT-06",
        "candidate": "G07_04",
        "transport_trips": ["Q3-016"],
    },
]
