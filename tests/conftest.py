from pathlib import Path
import os
import numpy as np
import pytest
from rasterio.transform import from_origin
from src.core.models import DroneType, Node, Box
from src.core.terrain import Terrain
from src.core.physics import Physics


@pytest.fixture
def drone():
    return DroneType(
        "T",
        10.0,
        20.0,
        1.0,
        10.0,
        10000.0,
        6000.0,
        4.0,
        0.2,
        10.0,
        2.0,
        3.0,
        1.0,
        2.0,
        2.0,
        0.72,
        1800.0,
    )


@pytest.fixture
def terrain():
    return Terrain(np.zeros((12, 12)), from_origin(0, 12, 1, 1))


@pytest.fixture
def physics(drone, tmp_path):
    import rasterio

    path = tmp_path / "dem.tif"
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=20,
        height=20,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(109, 24, 0.001, 0.001),
    ) as ds:
        ds.write(np.zeros((20, 20), dtype="float32"), 1)
    nodes = {
        "O01": Node("O01", 109.0015, 23.9985, 0),
        "S001": Node("S001", 109.0045, 23.9985, 0),
        "S002": Node("S002", 109.0085, 23.9985, 0),
    }
    return Physics(nodes, {"T": drone}, path)


@pytest.fixture
def boxes():
    return [
        Box("B1", "S001", "医疗物资", 3.0, 0.01, True, 1000.0, 1000.0, 2.0, 1000.0),
        Box("B2", "S002", "食品", 4.0, 0.02, False, None, 1500.0, 1.0, None),
    ]


@pytest.fixture
def official_root():
    path = Path(
        os.environ.get(
            "UAV_DATA_ROOT", Path(__file__).resolve().parents[1] / "data" / "raw"
        )
    )
    if not list(path.rglob("*.tif")):
        pytest.skip("Official-data integration requires UAV_DATA_ROOT or data/raw")
    return path
