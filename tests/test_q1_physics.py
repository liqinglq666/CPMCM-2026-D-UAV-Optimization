from src.q1.physics_engine import DroneType, equivalent_range, leg_energy


def _drone() -> DroneType:
    return DroneType(
        code="T",
        empty_mass=10.0,
        max_payload=20.0,
        max_volume=1.0,
        cruise_speed=10.0,
        range_empty=10000.0,
        range_full=6000.0,
        energy_use=4.0,
        rho=0.20,
        prep_time=0.0,
        load_time_per_box=0.0,
        handover_base=0.0,
        handover_per_box=0.0,
        climb_speed=2.0,
        descent_speed=2.0,
        eta_up=0.72,
    )


def test_equivalent_range_endpoints() -> None:
    d = _drone()
    assert abs(equivalent_range(d, 0.0) - d.range_empty) < 1e-9
    assert abs(equivalent_range(d, d.max_payload) - d.range_full) < 1e-9


def test_loaded_horizontal_energy_exceeds_empty() -> None:
    d = _drone()
    empty = leg_energy(d, distance=1000.0, h_up=0.0, q=0.0)[0]
    loaded = leg_energy(d, distance=1000.0, h_up=0.0, q=20.0)[0]
    assert loaded > empty
