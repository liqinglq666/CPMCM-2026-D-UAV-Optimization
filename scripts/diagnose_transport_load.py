"""Necessary fleet workload bounds for the current fixed Q2 route/type plan.

This is NOT a lower bound for the unrestricted routing and cargo problem.
Ignoring recharge and deadlines only relaxes the fixed-profile schedule.
"""

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import DEFAULT_DATA_ROOT
from src.core.inputs import load_inputs
from src.core.physics import Physics
from src.core.routes import evaluate_route
from src.core.io import read_csv, write_json


def diagnose(data_root, result_dir):
    nodes, types, drones, _batteries, boxes, dem = load_inputs(data_root)
    physics = Physics(nodes, types, dem)
    box_map = {box.id: box for box in boxes}
    inventory = Counter(drone.type for drone in drones)
    totals = defaultdict(float)
    rows = read_csv(result_dir / "Q2_transport_trips_balanced.csv")
    for row in rows:
        profile = evaluate_route(
            physics, row["机型编号"],
            [box_map[bid] for bid in row["货箱编号列表"].split(",")],
            row["访问服务区顺序"].split("->"),
        )
        totals[row["机型编号"]] += profile.duration
    bounds = [
        dict(type=typ, workload_s=duration, drones=inventory[typ],
             lower_bound_s=duration / inventory[typ])
        for typ, duration in sorted(totals.items())
    ]
    bound = max(item["lower_bound_s"] for item in bounds)
    makespan = max(float(row["返回O01时刻（s）"]) for row in rows)
    return dict(
        scope="fixed cargo groups, route orders and types only; not global",
        formula="max_type(sum(profile.duration) / available_drones)",
        fleet_bounds=bounds, lower_bound_s=bound, makespan_s=makespan,
        maximum_rescheduling_gain_s=makespan - bound,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--results", type=Path, default=ROOT / "results/q2")
    parser.add_argument("--out", type=Path, default=ROOT / "results/q2_workload_bound.json")
    args = parser.parse_args()
    write_json(args.out, diagnose(args.root, args.results))
