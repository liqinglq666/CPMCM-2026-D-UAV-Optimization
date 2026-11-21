"""Single flight engine shared by Q1, Q2, Q3 and validation."""

from src.config import TERRAIN_CLEARANCE_M, SERVICE_ALTITUDE_M
from .energy import leg_energy, flight_time
from .models import Segment
from .terrain import Terrain, horizontal_distance


class Physics:
    def __init__(self, nodes, types, dem_file):
        self.nodes, self.types = nodes, types
        self.dem_file = dem_file
        self.terrain = Terrain.read(dem_file)
        self._cache = {}

    def operation_altitude(self, code):
        return self.nodes[code].elev + (0 if code == "O01" else SERVICE_ALTITUDE_M)

    def segment(self, a, b):
        key = (a, b)
        if key not in self._cache:
            na, nb = self.nodes[a], self.nodes[b]
            pa, pb = (na.lon, na.lat), (nb.lon, nb.lat)
            za, zb = self.operation_altitude(a), self.operation_altitude(b)
            if a == b:
                self._cache[key] = Segment(a, b, 0.0, za, 0.0, 0.0)
            else:
                cruise = self.terrain.maximum(pa, pb) + TERRAIN_CLEARANCE_M
                if cruise < max(za, zb):
                    raise ValueError(
                        f"Official cruise altitude below operation endpoint: {a}->{b}"
                    )
                self._cache[key] = Segment(
                    a, b, horizontal_distance(pa, pb), cruise, cruise - za, cruise - zb
                )
        return self._cache[key]

    def energy(self, type_code, a, b, payload):
        seg = self.segment(a, b)
        return leg_energy(self.types[type_code], seg.distance, seg.climb, payload)[0]

    def flight_time(self, type_code, a, b):
        t, seg = self.types[type_code], self.segment(a, b)
        return flight_time(
            seg.distance,
            seg.climb,
            seg.descent,
            t.cruise_speed,
            t.climb_speed,
            t.descent_speed,
        )
