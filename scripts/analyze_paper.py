"""Derive paper evidence from official inputs and validated outputs.

AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23.
Exact model version/release date: not available in the execution context.
No random experiments; all scenarios are deterministic and conditional.
"""

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import DEFAULT_DATA_ROOT
from src.core.communication import Communication, sample_states
from src.core.constraints import validate_relays, validate_transport
from src.core.energy import leg_energy
from src.core.inputs import load_communication_inputs, load_inputs, load_relay_inputs
from src.core.io import read_csv, write_csv, write_json
from src.core.physics import Physics
from src.core.routes import evaluate_route
from src.q1.physics_engine import compute_segments, max_safe_payload
from paper_sensitivity import reserve_staircase


def analyze(data_root, results, out, allow_diagnostic_failures=False):
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
            "randomness": "Q2/Q3 fixed-seed search; diagnostics have no random steps",
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
    from diagnose_transport_load import diagnose

    analysis["q2_workload_bound"] = diagnose(data_root, results / "q2")
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
    stairs, reserve_limits = reserve_staircase(boxes, types, segments)
    write_csv(out / "reserve_staircase.csv", stairs)
    analysis["reserve_partition_limits"] = reserve_limits
    # Native DEM pixel centres in the task extent; no graphical resampling.
    terrain = physics.terrain
    west = min(n.lon for n in nodes.values()) - 0.007
    east = max(n.lon for n in nodes.values()) + 0.007
    south = min(n.lat for n in nodes.values()) - 0.007
    north = max(n.lat for n in nodes.values()) + 0.007
    c0, r0 = terrain.pixel(west, north)
    c1, r1 = terrain.pixel(east, south)
    cols = np.arange(int(c0), int(c1) + 1)
    rows = np.arange(int(r0), int(r1) + 1)
    lons = [float((terrain.transform * (c + 0.5, 0))[0]) for c in cols]
    lats = [float((terrain.transform * (0, r + 0.5))[1]) for r in rows]
    heights = terrain.values(rows[:, None], cols[None, :])
    write_json(
        out / "terrain_map.json",
        {
            "longitude": lons,
            "latitude": lats,
            "elevation_m": heights.tolist(),
            "purpose": "native DEM pixel centres; contours are display only",
            "crs": "EPSG:4326",
            "resampled": False,
            "grid_step_degrees": [terrain.transform.a, terrain.transform.e],
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
        filename = (
            "communication_states.csv"
            if step == 1.0
            else "communication_states_05s.csv"
        )
        frame.to_csv(out / filename, index=False)
        print("Communication:", summaries[-1], flush=True)
        if violations and not allow_diagnostic_failures:
            raise ValueError(
                f"Finer paper validation detected {violations} uncovered states at step {step}"
            )
    analysis["sampling_validation"] = summaries
    critical = summaries[-1]["critical_state"]
    rid = assigned[critical["trip"]]
    counterexample = {
        "state": critical,
        "assigned_relay": rid,
        "direct_margin_db": critical["direct_margin_db"],
        "refined_check_passed": summaries[-1]["violations"] == 0,
    }
    if rid:
        relay_point, begin, end = relay_map[rid]
        point = tuple(critical[k] for k in ("longitude", "latitude", "altitude_m"))
        access = comm.link(point, relay_point, radio.access_budget_db)
        counterexample.update(
            relay_active=begin <= critical["time_s"] <= end,
            access_margin_db=radio.access_budget_db - access[1],
            access_obstructed=bool(access[2]),
            backhaul_margin_db=backhauls[rid],
        )
    write_json(out / "communication_critical_state.json", counterexample)
    analysis["refined_communication_passed"] = not any(
        s["violations"] for s in summaries
    )
    analysis["diagnostic_failures_exported"] = bool(allow_diagnostic_failures)
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
    diagnostic_names = [
        "terrain_profile.csv",
        "energy_components.csv",
        "constraint_slacks.csv",
        "payload_reserve.csv",
        "terrain_map.json",
        "communication_states.csv",
        "communication_states_05s.csv",
        "hard_deadline_slacks.csv",
        "reserve_staircase.csv",
        "communication_critical_state.json",
    ]
    analysis["diagnostic_hashes"] = {
        name: hashlib.sha256((out / name).read_bytes()).hexdigest()
        for name in diagnostic_names
    }
    write_json(out / "analysis.json", analysis)
    print("Paper data saved to", out, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--results", type=Path, default=ROOT / "results")
    parser.add_argument("--out", type=Path, default=ROOT / "paper/data")
    parser.add_argument(
        "--allow-diagnostic-failures",
        action="store_true",
        help="Export failed diagnostic evidence for honest reporting; never declares feasibility",
    )
    args = parser.parse_args()
    analyze(args.data, args.results.resolve(), args.out, args.allow_diagnostic_failures)
