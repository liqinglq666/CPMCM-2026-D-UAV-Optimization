"""Derive paper evidence from official inputs and validated outputs.

AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23.
Exact model version/release date: not available in the execution context.
No random experiments; all scenarios are deterministic and conditional.
"""

from pathlib import Path
import argparse
import hashlib
import json
import sys
from dataclasses import asdict

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import DEFAULT_DATA_ROOT
from src.core.inputs import load_inputs, load_relay_inputs, load_communication_inputs
from src.core.physics import Physics
from src.core.energy import leg_energy
from src.core.routes import evaluate_route
from src.core.communication import Communication, sample_states
from src.core.constraints import validate_transport, validate_relays
from src.core.io import read_csv, write_csv, write_json
from src.q1.physics_engine import compute_segments, max_safe_payload


def analyze(data_root, results, out):
    out.mkdir(parents=True, exist_ok=True)
    nodes, types, drones, batteries, boxes, dem = load_inputs(data_root)
    physics = Physics(nodes, types, dem)
    box_map = {b.id: b for b in boxes}
    relay_inputs = load_relay_inputs(data_root)
    radio = load_communication_inputs(data_root)
    comm = Communication(physics, radio)
    q1 = read_csv(results / "q1/Q1_batch_solution.csv")
    q2 = read_csv(results / "q2/Q2_transport_trips_balanced.csv")
    q3 = read_csv(results / "q3/Q3_transport_trips.csv")
    deliveries = read_csv(results / "q3/Q3_box_delivery.csv")
    relays = read_csv(results / "q3/Q3_relay_sorties.csv")
    profiles, _ = validate_transport(
        q3, deliveries, "q3", physics, boxes, drones, batteries
    )
    relay_map = validate_relays(relays, physics, relay_inputs, comm)
    assigned = {
        r["运输架次编号"]: r["中继架次编号"]
        for r in read_csv(results / "q3/Q3_communication.csv")
    }
    backhauls = {
        rid: radio.backhaul_budget_db
        - comm.link(point, comm.gateway, radio.backhaul_budget_db)[1]
        for rid, (point, _begin, _end) in relay_map.items()
    }
    analysis = {
        "assumptions": {
            "wind": "not specified; official planned speed",
            "randomness": "none",
            "confidence_intervals": "not applicable",
            "continuous_time_proof": False,
        },
        "nodes": {k: asdict(v) for k, v in nodes.items()},
        "types": {k: asdict(v) for k, v in types.items()},
        "boxes": [asdict(b) for b in boxes],
        "radio": asdict(radio),
        "relay_spec": asdict(relay_inputs.spec),
        "metrics": {
            q: json.loads(
                (results / q / f"{q.upper()}_metrics.json").read_text(encoding="utf-8")
            )
            for q in ("q1", "q2", "q3")
        },
    }
    # An exact closed-cell terrain profile, independent of graphical sampling.
    segments = compute_segments(nodes, dem)
    critical_service = max(segments, key=lambda k: segments[k].out_up)
    segment = segments[critical_service]
    origin, destination = nodes["O01"], nodes[critical_service]
    rows, cols, begin, end = physics.terrain.cell_intervals(
        (origin.lon, origin.lat), (destination.lon, destination.lat)
    )
    terrain_profile = sorted(
        [
            {
                "begin_m": float(a * segment.distance),
                "end_m": float(b * segment.distance),
                "elevation_m": float(z),
            }
            for a, b, z in zip(begin, end, physics.terrain.values(rows, cols))
        ],
        key=lambda r: (r["begin_m"], r["end_m"]),
    )
    write_csv(out / "terrain_profile.csv", terrain_profile)
    analysis["terrain_example"] = {"service": critical_service, **asdict(segment)}
    energy_components = []
    constraints = []
    for question, trips, soc_field, energy_field in (
        ("q1", q1, "返航SOC（%）", "架次能耗（kWh）"),
        ("q2", q2, "返航SOC（%）", "架次能耗（kWh）"),
        ("q3", q3, "返航SOC_pct", "架次能耗_kWh"),
    ):
        for trip in trips:
            drone = types[trip["机型编号"]]
            cargo = [box_map[k] for k in trip["货箱编号列表"].split(",")]
            profile = evaluate_route(
                physics,
                drone.code,
                cargo,
                [trip["服务区编号"]]
                if question == "q1"
                else trip["访问服务区顺序"].split("->"),
            )
            if not np.isclose(
                profile.energy, float(trip[energy_field]), rtol=0, atol=1e-8
            ):
                raise ValueError("Paper replay disagrees with official result")
            constraints.append(
                {
                    "question": question,
                    "trip": trip["架次编号"],
                    "type": drone.code,
                    "mass_fraction": profile.mass / drone.max_payload,
                    "volume_fraction": profile.volume / drone.max_volume,
                    "energy_fraction": profile.energy
                    / ((1 - drone.rho) * drone.energy_use),
                    "soc_pct": float(trip[soc_field]),
                    "energy_multiplier_limit": (1 - drone.rho)
                    * drone.energy_use
                    / profile.energy,
                }
            )
            if question == "q1":
                for direction, payload, climb in [
                    ("outbound", profile.mass, segments[trip["服务区编号"]].out_up),
                    ("return", 0, segments[trip["服务区编号"]].ret_up),
                ]:
                    _total, horizontal, ascent = leg_energy(
                        drone, segments[trip["服务区编号"]].distance, climb, payload
                    )
                    energy_components.append(
                        {
                            "trip": trip["架次编号"],
                            "service": trip["服务区编号"],
                            "type": drone.code,
                            "direction": direction,
                            "payload_kg": payload,
                            "horizontal_kwh": horizontal,
                            "climb_kwh": ascent,
                        }
                    )
    write_csv(out / "constraint_slacks.csv", constraints)
    write_csv(out / "energy_components.csv", energy_components)
    analysis["fixed_plan_thresholds"] = {
        q: {
            "maximum_common_reserve": min(
                r["soc_pct"] / 100 for r in constraints if r["question"] == q
            ),
            "maximum_energy_multiplier": min(
                r["energy_multiplier_limit"] for r in constraints if r["question"] == q
            ),
        }
        for q in ("q1", "q2", "q3")
    }
    # Reserve response is recomputed by the shared physical engine, not interpolation.
    response = []
    for reserve in np.linspace(0.1, 0.4, 61):
        for sid, seg in segments.items():
            for typ, drone in types.items():
                payload = max_safe_payload(drone, seg, float(reserve))
                response.append(
                    {
                        "reserve": float(reserve),
                        "service": sid,
                        "type": typ,
                        "payload_kg": payload,
                        "reachable": payload is not None,
                        "rated_payload_kg": drone.max_payload,
                        "distance_m": seg.distance,
                    }
                )
    write_csv(out / "payload_reserve.csv", response)
    # Store a modest, explicitly display-only terrain grid for vector contouring.
    lons = np.linspace(
        min(n.lon for n in nodes.values()) - 0.007,
        max(n.lon for n in nodes.values()) + 0.007,
        130,
    )
    lats = np.linspace(
        min(n.lat for n in nodes.values()) - 0.007,
        max(n.lat for n in nodes.values()) + 0.007,
        130,
    )
    heights = [[physics.terrain.elevation(lon, lat) for lon in lons] for lat in lats]
    write_json(
        out / "terrain_map.json",
        {
            "longitude": lons.tolist(),
            "latitude": lats.tolist(),
            "elevation_m": heights,
            "purpose": "display-only sample; all physical/LOS computations traverse original closed DEM cells",
        },
    )
    summaries = []
    for step in (1.0, 0.5):
        states = []
        for tid, (profile, start) in profiles.items():
            rid = assigned[tid]
            for offset, point in sample_states(profile, physics, step):
                time_s = start + offset
                direct = comm.link(point, comm.gateway, radio.direct_budget_db)
                direct_margin = radio.direct_budget_db - direct[1]
                margin, mode = direct_margin, "direct"
                if rid:
                    relay_point, t0, t1 = relay_map[rid]
                    if t0 <= time_s <= t1:
                        access = (
                            radio.access_budget_db
                            - comm.link(point, relay_point, radio.access_budget_db)[1]
                        )
                        relay_margin = min(access, backhauls[rid])
                        if relay_margin > margin:
                            margin, mode = relay_margin, "relay"
                states.append(
                    {
                        "trip": tid,
                        "time_s": time_s,
                        "longitude": point[0],
                        "latitude": point[1],
                        "altitude_m": point[2],
                        "direct_margin_db": direct_margin,
                        "available_margin_db": margin,
                        "best_mode": mode,
                        "direct_obstructed": direct[2],
                    }
                )
        frame = pd.DataFrame(states)
        violations = int((frame.available_margin_db < 0).sum())
        critical = frame.loc[frame.available_margin_db.idxmin()].to_dict()
        summaries.append(
            {
                "step_s": step,
                "checked_states": len(frame),
                "violations": violations,
                "minimum_margin_db": float(frame.available_margin_db.min()),
                "critical_state": critical,
            }
        )
        if step == 1.0:
            frame.to_csv(out / "communication_states.csv", index=False)
        print("Communication:", summaries[-1], flush=True)
        if violations:
            raise ValueError(
                f"Finer paper validation detected {violations} uncovered states at step {step}"
            )
    analysis["sampling_validation"] = summaries
    hard = [
        {
            "box": r["货箱编号"],
            "service": r["服务区编号"],
            "slack_s": box_map[r["货箱编号"]].hard_deadline
            - float(r["交付完成时刻_s"]),
        }
        for r in deliveries
        if box_map[r["货箱编号"]].hard_deadline is not None
    ]
    write_csv(out / "hard_deadline_slacks.csv", hard)
    analysis["hard_deadline_count"] = len(hard)
    analysis["hashes"] = {
        str(p.relative_to(results)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(results.rglob("*"))
        if p.is_file()
    }
    write_json(out / "analysis.json", analysis)
    print("Paper data saved to", out, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--out", type=Path, default=ROOT / "paper/data")
    args = parser.parse_args()
    analyze(args.data, args.results.resolve(), args.out)
