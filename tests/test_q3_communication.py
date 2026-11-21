from src.q3.communication import (
    Radio,
    bidirectional_loss_threshold,
    free_space_path_loss,
    two_stage_charge_time,
)


def test_fspl_increases_with_distance() -> None:
    near = free_space_path_loss(2400.0, 1.0)
    far = free_space_path_loss(2400.0, 2.0)
    assert far > near


def test_bidirectional_budget_uses_stricter_direction() -> None:
    a = Radio(20.0, 2.0, -90.0)
    b = Radio(10.0, 4.0, -80.0)
    value = bidirectional_loss_threshold(
        a,
        b,
        system_loss_db=1.0,
        fade_margin_db=10.0,
    )
    ab = 20.0 + 2.0 + 4.0 - 1.0 - (-80.0 + 10.0)
    ba = 10.0 + 4.0 + 2.0 - 1.0 - (-90.0 + 10.0)
    assert value == min(ab, ba)


def test_charge_time_zero_at_full_soc() -> None:
    assert abs(two_stage_charge_time(1800.0, 1.0)) < 1e-12
