import importlib
import math
import pytest
from src.core.models import Resource
from src.core.routes import evaluate_route
from src.core.constraints import validate_transport
from src.core.io import read_csv, write_csv
from src.q2.tradeoff import schedule_groups


def fixture_rows(physics, boxes):
    p = evaluate_route(physics, "T", boxes, ["S001", "S002"])
    trip = {
        "架次编号": "T1",
        "机型编号": "T",
        "无人机编号": "U1",
        "电池编号": "BAT1",
        "开始时刻_s": 0.0,
        "访问服务区顺序": "S001->S002",
        "返回O01时刻_s": p.duration,
        "架次能耗_kWh": p.energy,
        "返航SOC_pct": 100 * (1 - p.energy / 4),
        "货箱编号列表": "B1,B2",
    }
    deliveries = [
        {
            "货箱编号": b.id,
            "架次编号": "T1",
            "服务区编号": b.service,
            "交付完成时刻_s": p.delivery[b.id],
            "期望_s": b.expected,
            "硬截止_s": b.hard_deadline,
            "加权延误": b.priority * max(0.0, p.delivery[b.id] - b.expected),
        }
        for b in boxes
    ]
    return [trip], deliveries


def check(trips, deliveries, physics, boxes):
    return validate_transport(
        trips,
        deliveries,
        "q3",
        physics,
        boxes,
        [Resource("U1", "T")],
        [Resource("BAT1", "T")],
    )


def test_recomputation_accepts_valid_schedule(physics, boxes):
    check(*fixture_rows(physics, boxes), physics, boxes)


@pytest.mark.parametrize(
    "key,value",
    [
        ("架次能耗_kWh", 0.01),
        ("返航SOC_pct", 99.0),
        ("返回O01时刻_s", math.nan),
        ("无人机编号", "invented"),
        ("电池编号", "invented"),
        ("访问服务区顺序", "S001"),
        ("货箱编号列表", "B1,B1"),
    ],
)
def test_recomputation_rejects_tampered_trip(physics, boxes, key, value):
    trips, deliveries = fixture_rows(physics, boxes)
    trips[0][key] = value
    with pytest.raises(ValueError):
        check(trips, deliveries, physics, boxes)


@pytest.mark.parametrize(
    "key,value",
    [
        ("硬截止_s", 1e9),
        ("交付完成时刻_s", 1.0),
        ("服务区编号", "S002"),
        ("架次编号", "unknown"),
        ("加权延误", math.nan),
    ],
)
def test_recomputation_rejects_tampered_delivery(physics, boxes, key, value):
    trips, deliveries = fixture_rows(physics, boxes)
    deliveries[0][key] = value
    with pytest.raises(ValueError):
        check(trips, deliveries, physics, boxes)


def test_duplicate_groups_fail(physics, boxes):
    box_map = {b.id: b for b in boxes}
    with pytest.raises(ValueError):
        schedule_groups(
            [{"B1"}, {"B1", "B2"}],
            box_map,
            physics,
            physics.types,
            [Resource("U1", "T")],
            [Resource("BAT1", "T")],
        )


def test_csv_rejects_extra_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("a,b\n1,2,3\n")
    with pytest.raises(ValueError, match="Nonrectangular"):
        read_csv(path)


def test_csv_roundtrip_quotes_and_unicode(tmp_path):
    path = tmp_path / "valid.csv"
    rows = [{"货箱": "B1,B2", "route": "S001->S002"}]
    write_csv(path, rows)
    assert read_csv(path) == rows


@pytest.mark.parametrize(
    "module",
    [
        "run_q1",
        "run_q2",
        "run_q3",
        "run_q4",
        "run_all",
        "scripts.run_q1",
        "scripts.run_q2",
        "scripts.run_q3",
        "scripts.run_q4",
        "scripts.validate_results",
    ],
)
def test_imports_never_parse_cli_or_read_data(module, monkeypatch):
    import sys

    monkeypatch.setattr(sys, "argv", ["pytest", "--invalid-cli-flag"])
    importlib.import_module(module)


def test_run_all_failure_preserves_previous_results(tmp_path, monkeypatch):
    import src.q1.physics_engine
    from src.cli import run_all

    out = tmp_path / "results"
    out.mkdir()
    (out / "validation.json").write_text('{"previous": true}')

    def fail(*args, **kwargs):
        raise RuntimeError("solver failed")

    monkeypatch.setattr(src.q1.physics_engine, "solve_q1", fail)
    with pytest.raises(RuntimeError, match="solver failed"):
        run_all([str(tmp_path / "input"), "--out", str(out)])
    assert (out / "validation.json").read_text() == '{"previous": true}'


def test_resource_comparison_does_not_repair_bad_rows():
    from src.validation import compare_records

    expected = [{"start": 0.0, "end": 10.0, "id": "U1"}]
    actual = [{"start": "0", "end": "9", "id": "U1"}]
    with pytest.raises(ValueError):
        compare_records(actual, expected, "resources")
    assert actual[0]["end"] == "9"
