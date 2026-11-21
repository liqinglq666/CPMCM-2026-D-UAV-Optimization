import shutil
import pytest
from src.core.inputs import (
    load_inputs,
    find_file,
    load_relay_inputs,
    load_communication_inputs,
    positive_integer,
)
from src.core.physics import Physics
from src.core.routes import evaluate_route
from src.core.numeric import lexicographic_less
from src.q1.physics_engine import compute_segments, roundtrip_energy, roundtrip_time
from src.q3.communication import relay_sortie_energy


def test_tie_breaker_ignores_summation_noise():
    assert lexicographic_less(
        (0.0, 0.0, 1000.0 + 1e-12, 4.0),
        (0.0, 0.0, 1000.0, 5.0),
        (1e-8, 1e-6, 1e-8, 1e-10),
    )


@pytest.mark.parametrize("count", [0, -1, 3.5, float("nan"), float("inf")])
def test_fractional_inventory_is_not_truncated(count):
    with pytest.raises(ValueError):
        positive_integer(count, "inventory")


@pytest.mark.integration
def test_official_parameters_and_shared_single_stop_engine(official_root):
    nodes, types, drones, batteries, boxes, dem = load_inputs(official_root)
    radio = load_communication_inputs(official_root)
    assert (
        radio.direct_budget_db,
        radio.access_budget_db,
        radio.backhaul_budget_db,
    ) == (122.0, 116.0, 126.0)
    physics = Physics(nodes, types, dem)
    segments = compute_segments(nodes, dem)
    for service, seg in segments.items():
        box = next(b for b in boxes if b.service == service)
        for code, drone in types.items():
            route = evaluate_route(physics, code, [box], [service])
            assert route.energy == pytest.approx(
                roundtrip_energy(drone, seg, box.mass), abs=1e-10
            )
            assert route.duration == pytest.approx(
                roundtrip_time(drone, seg, 1), abs=1e-9
            )
    # Appendix 2 fixes planned speeds; no wind data or correction is introduced.
    assert types["A"].cruise_speed == 12.0
    assert types["B"].cruise_speed == types["C"].cruise_speed == 15.0


@pytest.mark.integration
def test_relay_setup_energy_and_negative_leg(official_root):
    spec = load_relay_inputs(official_root).spec
    difference = relay_sortie_energy(
        spec, 100.0, 50.0, 40.0, 60.0 + spec.link_setup_s
    ) - relay_sortie_energy(spec, 100.0, 50.0, 40.0, 60.0)
    assert difference == pytest.approx(
        (spec.hover_power_kw + spec.communication_power_kw) * spec.link_setup_s / 3600.0
    )
    with pytest.raises(ValueError):
        relay_sortie_energy(spec, 100.0, -10.0, 50.0, 60.0)


@pytest.mark.integration
def test_modified_official_mass_and_inventory_are_read(tmp_path, official_root):
    import openpyxl

    for keyword in ("调度中心与服务区", "运输无人机数据", "物资需求与配送时限"):
        shutil.copy2(find_file(official_root, keyword), tmp_path)
    # Loader only locates the DEM; this test does not open it.
    (tmp_path / "30米DEM.tif").write_bytes(b"placeholder")
    demand = find_file(tmp_path, "物资需求与配送时限")
    book = openpyxl.load_workbook(demand)
    book["逐箱货箱清单"]["D2"] = 3.5
    book.save(demand)
    assert load_inputs(tmp_path)[4][0].mass == 3.5
    transport = find_file(tmp_path, "运输无人机数据")
    book = openpyxl.load_workbook(transport)
    book["数据"]["B20"] = 6.5
    book.save(transport)
    with pytest.raises(ValueError, match="integer"):
        load_inputs(tmp_path)


def test_ambiguous_inputs_fail(tmp_path):
    (tmp_path / "a数据.xlsx").touch()
    (tmp_path / "b数据.xlsx").touch()
    with pytest.raises(ValueError, match="Ambiguous"):
        find_file(tmp_path, "数据")
