"""Independent checks that partition sizing inherits Q3 tasks and intervals."""

from collections import Counter
from copy import deepcopy
from pathlib import Path
import json

import pytest

from src.core.io import read_csv
from src.core.inputs import load_inputs, load_relay_inputs
from src.core.energy import two_stage_charge_time
from src.core.constraints import RESULT_TOLERANCE
from src.q4.provenance import check_task_relations, q3_fingerprints


@pytest.mark.parametrize(
    "bad", ["missing_comm", "unknown_relay", "wrong_trip", "duplicate_box"]
)
def test_broken_task_relations_are_not_silently_dropped(bad):
    transport = [{"架次编号": "T", "货箱编号列表": "B"}]
    relay = [{"中继架次编号": "R"}]
    comm = [{"运输架次编号": "T", "保障方式": "中继", "中继架次编号": "R"}]
    boxes = [{"货箱编号": "B", "架次编号": "T"}]
    check_task_relations(transport, relay, comm, boxes)
    if bad == "missing_comm":
        comm.clear()
    elif bad == "unknown_relay":
        comm[0]["中继架次编号"] = "unknown"
    elif bad == "wrong_trip":
        boxes[0]["架次编号"] = "other"
    else:
        boxes.append(deepcopy(boxes[0]))
    with pytest.raises(ValueError):
        check_task_relations(transport, relay, comm, boxes)


@pytest.mark.integration
def test_resource_demands_against_independent_interval_sweep(official_root):
    root = Path(__file__).resolve().parents[1] / "results"
    transport = read_csv(root / "q3/Q3_transport_trips.csv")
    relay = {r["中继架次编号"]: r for r in read_csv(root / "q3/Q3_relay_sorties.csv")}
    relations = {
        r["运输架次编号"]: r["中继架次编号"]
        for r in read_csv(root / "q3/Q3_communication.csv")
        if r["保障方式"] == "中继"
    }
    _nodes, types, _drones, _batteries, boxes, _dem = load_inputs(official_root)
    relay_inputs = load_relay_inputs(official_root)
    configurations = read_csv(root / "q4/Q4_partition_config.csv")

    def count(intervals):
        # Count directly at every interval start, independently of the heap
        # algorithm used by Q4. The same declared numerical tolerance applies.
        return max(
            (
                sum(a <= t and b > t + RESULT_TOLERANCE for a, b in intervals)
                for t, _end in intervals
            ),
            default=0,
        )

    for k in (2, 3):
        seen = []
        for group in (g for g in configurations if int(g["K"]) == k):
            services = set(group["服务区列表"].split(","))
            selected = [
                r for r in transport if set(r["访问服务区顺序"].split("->")) <= services
            ]
            selected_ids = {r["架次编号"] for r in selected}
            cargo = [b for r in selected for b in r["货箱编号列表"].split(",")]
            seen.extend(cargo)
            assert len(cargo) == int(group["货箱数"])
            # Every trip touching a group is wholly inside that group.
            assert all(
                not (services & set(r["访问服务区顺序"].split("->")))
                or r["架次编号"] in selected_ids
                for r in transport
            )
            for code, typ in types.items():
                rows = [r for r in selected if r["机型编号"] == code]
                uav = [
                    (float(r["开始时刻_s"]), float(r["返回O01时刻_s"])) for r in rows
                ]
                battery = [
                    (
                        float(r["开始时刻_s"]),
                        float(r["返回O01时刻_s"])
                        + two_stage_charge_time(
                            typ.full_charge, float(r["返航SOC_pct"]) / 100
                        ),
                    )
                    for r in rows
                ]
                assert int(group[f"{code}型运输无人机数"]) == count(uav)
                assert int(group[f"{code}型电池组数"]) == count(battery)
            rrows = [
                relay[r]
                for r in sorted({relations[t] for t in selected_ids if t in relations})
            ]
            assert len(rrows) == int(group["中继架次"])
            assert int(group["中继无人机数"]) == count(
                [
                    (
                        float(r["开始时刻_s"]),
                        float(r["返回O01时刻_s"]) + relay_inputs.spec.turnaround_s,
                    )
                    for r in rrows
                ]
            )
            assert int(group["中继能源组件数"]) == count(
                [
                    (
                        float(r["开始时刻_s"]),
                        float(r["返回O01时刻_s"])
                        + two_stage_charge_time(
                            relay_inputs.full_charge_s, float(r["返航SOC_pct"]) / 100
                        ),
                    )
                    for r in rrows
                ]
            )
        assert Counter(seen) == Counter(b.id for b in boxes)
    source = root / "q4/Q4_source_manifest.json"
    if source.exists():
        assert json.loads(source.read_text()) == q3_fingerprints(root / "q3")
