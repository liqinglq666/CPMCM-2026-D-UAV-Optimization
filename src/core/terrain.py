"""Validated WGS84 DEM snapshot; files are closed immediately after loading."""
from dataclasses import dataclass
import math
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from rasterio.windows import Window, transform as window_transform
from pyproj import Geod
from shapely.geometry import LineString, Point
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
        if np.any(~np.isfinite(values)) or (self.nodata is not None and np.any(values == self.nodata)):
            raise ValueError("DEM NoData on required route or radio ray")
        return values

    def elevation(self, lon, lat):
        c, r = self.pixel(lon, lat)
        return float(self.values(int(r), int(c)))

    def maximum(self, a, b):
        ca, ra = self.pixel(*a[:2])
        cb, rb = self.pixel(*b[:2])
        c0, r0 = max(0, int(min(ca, cb)) - 1), max(0, int(min(ra, rb)) - 1)
        c1, r1 = min(self.width, int(max(ca, cb)) + 2), min(self.height, int(max(ra, rb)) + 2)
        shape = Point(a[:2]) if tuple(a[:2]) == tuple(b[:2]) else LineString([a[:2], b[:2]])
        mask = geometry_mask([shape.__geo_interface__], out_shape=(r1-r0, c1-c0),
                             transform=window_transform(Window(c0, r0, c1-c0, r1-r0), self.transform),
                             invert=True, all_touched=True)
        rr, cc = np.nonzero(mask)
        if not len(rr):
            raise ValueError("No DEM cells intersect route")
        return float(np.max(self.values(rr+r0, cc+c0)))

    def obstructed(self, a, b):
        """Visit every raster-cell interval crossed by the straight radio ray.

        Evaluate the lowest ray altitude in each interval. Sub-cell sampling
        may miss a narrow ridge near a pixel corner; boundary traversal does not.
        Endpoints have zero extent and do not create an obstruction by themselves.
        """
        ca, ra = self.pixel(*a[:2])
        cb, rb = self.pixel(*b[:2])
        finite(a[2], "ray elevation")
        finite(b[2], "ray elevation")
        cuts = [np.array([0., 1.])]
        for start, end in ((ca, cb), (ra, rb)):
            if start != end:
                grid = np.arange(math.floor(min(start, end)) + 1, math.ceil(max(start, end)))
                cuts.append((grid - start) / (end - start))
        fractions = np.unique(np.concatenate(cuts))
        mid = (fractions[:-1] + fractions[1:]) / 2
        rr = np.floor(ra + (rb-ra)*mid).astype(int)
        cc = np.floor(ca + (cb-ca)*mid).astype(int)
        terrain = self.values(rr, cc)
        z = a[2] + (b[2]-a[2])*fractions
        return bool(np.any(terrain >= np.minimum(z[:-1], z[1:])))
