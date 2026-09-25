"""Independent, uncached radio replay from official inputs and exported schedules.

The extra 0.25 s grid is an out-of-search diagnostic, not continuous proof.
--allow-violations is only for retaining a failing historical counterexample.
"""

import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import DEFAULT_DATA_ROOT, PROJECT_ROOT
from src.core.communication import Communication, sample_states
from src.core.constraints import validate_transport, validate_relays
from src.core.inputs import load_inputs, load_relay_inputs, load_communication_inputs
from src.core.io import read_csv, write_json
from src.core.physics import Physics


def replay(root, directory, steps):
    nodes, types, drones, batteries, boxes, dem = load_inputs(root)
    physics = Physics(nodes, types, dem)
    radio = load_communication_inputs(root)
    comm = Communication(physics, radio)
    profiles, _resources = validate_transport(
        read_csv(directory / "Q3_transport_trips.csv"),
        read_csv(directory / "Q3_box_delivery.csv"),
        "q3",
        physics,
        boxes,
        drones,
        batteries,
    )
    relays = validate_relays(
        read_csv(directory / "Q3_relay_sorties.csv"),
        physics,
        load_relay_inputs(root),
        comm,
    )
    assigned = {
        r["运输架次编号"]: r["中继架次编号"]
        for r in read_csv(directory / "Q3_communication.csv")
    }
    backhaul = {
        rid: radio.backhaul_budget_db
        - comm.link(point, comm.gateway, radio.backhaul_budget_db)[1]
        for rid, (point, _begin, _end) in relays.items()
    }
    summaries = []
    for step in steps:
        count, violations, critical = 0, [], None
        for tid, (profile, start) in profiles.items():
            rid = assigned[tid]
            for offset, point in sample_states(profile, physics, step):
                count += 1
                time = start + offset
                direct = (
                    radio.direct_budget_db
                    - comm.link(point, comm.gateway, radio.direct_budget_db)[1]
                )
                margin = direct
                if rid:
                    relay_point, begin, end = relays[rid]
                    if begin <= time <= end:
                        access = (
                            radio.access_budget_db
                            - comm.link(point, relay_point, radio.access_budget_db)[1]
                        )
                        margin = max(margin, min(access, backhaul[rid]))
                state = dict(
                    trip=tid, time_s=time, point=point, available_margin_db=margin
                )
                if critical is None or margin < critical["available_margin_db"]:
                    critical = state
                if margin < 0:
                    violations.append(state)
        summary = dict(
            step_s=step,
            checked_states=count,
            violations=len(violations),
            minimum_margin_db=critical["available_margin_db"],
            critical_state=critical,
            uncovered_states=violations,
        )
        print(summary, flush=True)
        summaries.append(summary)
    return dict(
        sampling=summaries,
        continuous_time_proof=False,
        source_sha256={
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.glob("Q3_*.csv"))
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--q3-dir", type=Path, default=PROJECT_ROOT / "results/q3")
    parser.add_argument("--steps", type=float, nargs="+", default=[1.0, 0.5, 0.25])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-violations", action="store_true")
    args = parser.parse_args()
    args.out.unlink(missing_ok=True)
    result = replay(args.data, args.q3_dir, args.steps)
    write_json(args.out, result)
    if any(r["violations"] for r in result["sampling"]) and not args.allow_violations:
        raise SystemExit(
            "Communication replay failed; evidence saved, no feasibility claim"
        )


if __name__ == "__main__":
    main()
