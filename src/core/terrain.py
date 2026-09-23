"""Validated WGS84 DEM snapshot; files are closed immediately after loading."""

from dataclasses import dataclass
import math
import numpy as np
import rasterio
from pyproj import Geod
from src.config import DEM_GRID_TOLERANCE_PIXELS
from .numeric import finite

GEOD = Geod(ellps="WGS84")


def horizontal_distance(a, b):
    for p in (a, b):
        finite(p[0], "longitude", -180, 180)
        finite(p[1], "latitude", -90, 90)
    return float(GEOD.inv(a[0], a[1], b[0], b[1])[2])


@dataclass
class Terrain:
    dem: np.ndarray
    transform: object
    nodata: float | None = None

    @classmethod
    def read(cls, path):
        with rasterio.open(path) as ds:
            if ds.crs is None or ds.crs.to_epsg() != 4326:
                raise ValueError("Official DEM must have EPSG:4326 coordinates")
            array = ds.read(1, masked=True).astype(float).filled(np.nan)
            return cls(array, ds.transform, ds.nodata)

    @property
    def width(self):
        return self.dem.shape[1]

    @property
    def height(self):
        return self.dem.shape[0]

    @property
    def shape(self):
        return self.dem.shape

    def pixel(self, lon, lat):
        finite(lon, "longitude", -180, 180)
        finite(lat, "latitude", -90, 90)
        col, row = ~self.transform * (lon, lat)
        if not (0 <= row < self.height and 0 <= col < self.width):
            raise ValueError(f"Point outside DEM: {(lon, lat)}")
        return col, row

    def values(self, rows, cols):
        values = self.dem[rows, cols]
        if np.any(~np.isfinite(values)) or (
            self.nodata is not None and np.any(values == self.nodata)
        ):
            raise ValueError("DEM NoData on required route or radio ray")
        return values

    def elevation(self, lon, lat):
        c, r = self.pixel(lon, lat)
        return float(self.values(int(r), int(c)))

    def maximum(self, a, b):
        rows, cols, _begin, _end = self.cell_intervals(a, b)
        return float(np.max(self.values(rows, cols)))

    def cell_intervals(self, a, b):
        """Closed pixel intersections, including both sides of edges and corners.

        The DEM is piecewise constant on pixel footprints. At a boundary the
        larger adjacent height is conservative; traversal direction must not
        change the result. Zero-duration intervals retain corner contacts.
        """
        ca, ra = self.pixel(*a[:2])
        cb, rb = self.pixel(*b[:2])
        cuts = [np.array([0.0, 1.0])]
        for start, end in ((ca, cb), (ra, rb)):
            if start != end:
                grid = np.arange(
                    math.floor(min(start, end)) + 1, math.ceil(max(start, end))
                )
                cuts.append((grid - start) / (end - start))
        fractions = np.unique(np.concatenate(cuts))
        begin = np.concatenate((fractions[:-1], fractions))
        end = np.concatenate((fractions[1:], fractions))
        mid = (begin + end) / 2
        columns = ca + (cb - ca) * mid
        rows = ra + (rb - ra) * mid

        def adjacent(values):
            nearest = np.rint(values)
            on_edge = np.abs(values - nearest) <= DEM_GRID_TOLERANCE_PIXELS
            values = np.where(on_edge, nearest, values)
            return np.floor(values).astype(int), on_edge

        cc, column_edge = adjacent(columns)
        rr, row_edge = adjacent(rows)
        pieces = []
        for dr, dc in ((0, 0), (-1, 0), (0, -1), (-1, -1)):
            r, c = rr + dr, cc + dc
            valid = (r >= 0) & (r < self.height) & (c >= 0) & (c < self.width)
            if dr:
                valid &= row_edge
            if dc:
                valid &= column_edge
            pieces.append((r[valid], c[valid], begin[valid], end[valid]))
        return tuple(np.concatenate(parts) for parts in zip(*pieces))

    def obstructed(self, a, b):
        """Test the lowest ray altitude on each closed pixel intersection."""
        finite(a[2], "ray elevation")
        finite(b[2], "ray elevation")
        rows, cols, begin, end = self.cell_intervals(a, b)
        terrain = self.values(rows, cols)
        z_begin = a[2] + (b[2] - a[2]) * begin
        z_end = a[2] + (b[2] - a[2]) * end
        return bool(np.any(terrain >= np.minimum(z_begin, z_end)))
