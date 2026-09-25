"""Recompute Q2 time/energy alternatives without replacing the fastest output."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import DEFAULT_DATA_ROOT, PROJECT_ROOT
from src.core.inputs import load_inputs
from src.core.physics import Physics
from src.core.io import read_csv
from src.q2.preferences import export_preferences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--plan", type=Path, help="Optional discrete seed; defaults to the current primary Q2 rows")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--q2-dir", type=Path, default=PROJECT_ROOT / "results/q2")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "results/q2")
    args = parser.parse_args()
    (args.out.parent / "validation.json").unlink(missing_ok=True)
    nodes, types, drones, batteries, boxes, dem = load_inputs(args.data)
    if args.plan:
        plan = json.loads(args.plan.read_text(encoding="utf-8"))
    else:
        rows = sorted(read_csv(args.q2_dir / "Q2_transport_trips_balanced.csv"),
                      key=lambda r: (float(r["开始时刻（s）"]), r["无人机编号"]))
        # Only discrete decisions are retained; no historical time or energy
        # is accepted as a solution value by the physical evaluator.
        plan = [dict(id=r["架次编号"], type=r["机型编号"], drone=r["无人机编号"],
                     battery=r["电池编号"], boxes=r["货箱编号列表"].split(","),
                     route=r["访问服务区顺序"].split("->")) for r in rows]
    print(export_preferences(plan, Physics(nodes, types, dem),
                             {b.id: b for b in boxes}, drones, batteries, args.out, seconds=args.seconds))


if __name__ == "__main__":
    main()
