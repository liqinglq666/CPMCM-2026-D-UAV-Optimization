"""Recompute a fixed route/relay plan and optimize its timing by linear programming.

The JSON plan contains only discrete decisions (cargo, route, resource order,
relay coordinates). No start time, energy, SOC or communication result is read
from historical outputs. Exactness is conditional on those discrete decisions.
"""

from collections import Counter, defaultdict
import json
import logging
from pathlib import Path

import numpy as np
from scipy.optimize import linprog

from src.config import (
    COMMUNICATION_STEP_S,
    RELAY_GUARD_S,
    Q3_PLAN,
    SECONDS_PER_HOUR,
)
from src.core.inputs import load_inputs, load_relay_inputs, load_communication_inputs
from src.core.energy import charge_time, energy_feasible
from src.core.physics import Physics
from src.core.routes import evaluate_route, route_is_energy_feasible
from src.core.io import write_csv, write_json
from src.core.provenance import save_provenance
from src.core.communication import Communication, sample_states, relay_travel


def prepare_plan(plan, physics, box_map, drones, batteries, relay_inputs, comm, step_s):
    jobs, relays = plan["jobs"], plan["relays"]
    if not jobs or not relays:
        raise ValueError("Empty joint plan")
    for rows in (jobs, relays):
        if len({row["id"] for row in rows}) != len(rows):
            raise ValueError("Duplicate plan job/sortie ID")
    cargo = [box for job in jobs for box in job["boxes"]]
    if Counter(cargo) != Counter(box_map.keys()):
        raise ValueError("Q3 plan must contain every official box exactly once")
    drone_types, battery_types = (
        {r.id: r.type for r in group} for group in (drones, batteries)
    )
    relay_map = {relay["id"]: relay for relay in relays}
    # This fixed-plan LP uses each component once; reuse is verified in the
    # general result validator but requires a different LP topology.
    if len({r["component"] for r in relays}) != len(relays):
        raise ValueError("Fixed-plan LP requires distinct relay components")
    for relay in relays:
        if (
            relay["drone"] not in relay_inputs.drone_ids
            or relay["component"] not in relay_inputs.component_ids
        ):
            raise ValueError("Relay resource outside official inventory")
        lon, lat = relay["lon"], relay["lat"]
        relay["point"] = (
            lon,
            lat,
            physics.terrain.elevation(lon, lat) + relay_inputs.spec.max_hover_agl_m,
        )
        if not comm.link(
            relay["point"], comm.gateway, comm.parameters.backhaul_budget_db
        )[0]:
            raise ValueError(f"Unavailable relay backhaul: {relay['id']}")
        relay["travel"] = relay_travel(physics, relay_inputs.spec, relay["point"])
    for job in jobs:
        if (
            drone_types.get(job["drone"]) != job["type"]
            or battery_types.get(job["battery"]) != job["type"]
        ):
            raise ValueError(f"Transport resource/type mismatch: {job['id']}")
        profile = evaluate_route(
            physics, job["type"], [box_map[b] for b in job["boxes"]], job["route"]
        )
        if not route_is_energy_feasible(profile, physics.types[job["type"]]):
            raise ValueError(f"Transport energy infeasible: {job['id']}")
        relay = relay_map.get(job["relay"])
        if job["relay"] is not None and relay is None:
            raise ValueError(f"Unknown relay sortie: {job['relay']}")
        outages = []
        checked = 0
        for time_s, point in sample_states(profile, physics, step_s):
            checked += 1
            if comm.link(point, comm.gateway, comm.parameters.direct_budget_db)[0]:
                continue
            if (
                relay is None
                or not comm.link(
                    point, relay["point"], comm.parameters.access_budget_db
                )[0]
            ):
                raise ValueError(
                    f"Uncovered communication state: {job['id']} at {time_s:.6f}s"
                )
            outages.append(time_s)
        job.update(
            profile=profile,
            checked_states=checked,
            outage=(min(outages), max(outages)) if outages else None,
        )
    return jobs, relays


def optimize_timing(jobs, relays, box_map, types, relay_spec):
    """LP variables: transport starts, relay service windows, box tardiness, makespan.

    Lexicographic objectives: weighted tardiness, joint makespan, relay service
    duration. Resource order is the explicit order in the selected plan.
    """
    names = [("job", j["id"]) for j in jobs]
    names += [(kind, r["id"]) for r in relays for kind in ("begin", "end")]
    names += [("late", b) for b in sorted(box_map)] + [("makespan", "all")]
    indices = {key: i for i, key in enumerate(names)}
    rows, limits = [], []
    bounds = [(0, None)] * len(names)

    def constraint(terms, limit):
        row = np.zeros(len(names))
        for key, coefficient in terms.items():
            row[indices[key]] += coefficient
        rows.append(row)
        limits.append(limit)

    for job in jobs:
        jid, profile = job["id"], job["profile"]
        constraint({("job", jid): 1, ("makespan", "all"): -1}, -profile.duration)
        for bid, offset in profile.delivery.items():
            box = box_map[bid]
            if box.hard_deadline is not None:
                constraint({("job", jid): 1}, box.hard_deadline - offset)
            constraint({("job", jid): 1, ("late", bid): -1}, box.expected - offset)
        if job["outage"] is not None:
            rid = job["relay"]
            first, last = job["outage"]
            constraint({("begin", rid): 1, ("job", jid): -1}, first - RELAY_GUARD_S)
            constraint({("job", jid): 1, ("end", rid): -1}, -last - RELAY_GUARD_S)
    for key in ("drone", "battery"):
        groups = defaultdict(list)
        for job in jobs:
            groups[job[key]].append(job)
        for group in groups.values():
            for left, right in zip(group, group[1:]):
                occupied = left["profile"].duration
                if key == "battery":
                    drone = types[left["type"]]
                    occupied += charge_time(
                        drone, 1 - left["profile"].energy / drone.energy_use
                    )
                constraint(
                    {("job", left["id"]): 1, ("job", right["id"]): -1}, -occupied
                )
    power = (
        relay_spec.hover_power_kw + relay_spec.communication_power_kw
    ) / SECONDS_PER_HOUR
    for relay in relays:
        rid, travel = relay["id"], relay["travel"]
        bounds[indices["begin", rid]] = (travel["lead"], None)
        constraint({("begin", rid): 1, ("end", rid): -1}, 0)
        max_service = (
            (1 - relay_spec.reserve_fraction) * relay_spec.usable_energy_kwh
            - travel["fixed_energy"]
        ) / power
        constraint({("end", rid): 1, ("begin", rid): -1}, max_service)
        constraint({("end", rid): 1, ("makespan", "all"): -1}, -travel["inbound"])
    by_drone = defaultdict(list)
    for relay in relays:
        by_drone[relay["drone"]].append(relay)
    for group in by_drone.values():
        for left, right in zip(group, group[1:]):
            interval = (
                left["travel"]["inbound"]
                + relay_spec.turnaround_s
                + right["travel"]["lead"]
            )
            constraint({("end", left["id"]): 1, ("begin", right["id"]): -1}, -interval)
    objectives = []
    tardiness = np.zeros(len(names))
    for bid, box in box_map.items():
        tardiness[indices["late", bid]] = box.priority
    objectives.append(tardiness)
    makespan = np.zeros(len(names))
    makespan[indices["makespan", "all"]] = 1
    objectives.append(makespan)
    duration = np.zeros(len(names))
    for relay in relays:
        duration[indices["end", relay["id"]]] = 1
        duration[indices["begin", relay["id"]]] = -1
    objectives.append(duration)
    for objective in objectives:
        result = linprog(
            objective,
            A_ub=np.array(rows),
            b_ub=np.array(limits),
            bounds=bounds,
            method="highs",
        )
        if not result.success:
            raise RuntimeError(f"Joint scheduling LP failed: {result.message}")
        rows.append(objective)
        limits.append(float(result.fun) + 1e-7)
    if np.max(np.array(rows) @ result.x - np.array(limits)) > 1e-5:
        raise RuntimeError("Joint scheduling LP returned an infeasible solution")
    return {key: float(result.x[index]) for key, index in indices.items()}


def solve_q3(root: Path, out_dir: Path, plan_path=Q3_PLAN, step_s=COMMUNICATION_STEP_S):
    nodes, types, drones, batteries, boxes, dem = load_inputs(root)
    box_map = {b.id: b for b in boxes}
    physics = Physics(nodes, types, dem)
    relay_inputs = load_relay_inputs(root)
    communication = Communication(physics, load_communication_inputs(root))
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    jobs, relays = prepare_plan(
        plan, physics, box_map, drones, batteries, relay_inputs, communication, step_s
    )
    times = optimize_timing(jobs, relays, box_map, types, relay_inputs.spec)
    transport_rows, box_rows, comm_rows, relay_rows = [], [], [], []
    for job in jobs:
        jid, profile, drone = job["id"], job["profile"], types[job["type"]]
        start = times["job", jid]
        transport_rows.append(
            {
                "架次编号": jid,
                "无人机编号": job["drone"],
                "机型编号": job["type"],
                "电池编号": job["battery"],
                "开始时刻_s": start,
                "访问服务区顺序": "->".join(job["route"]),
                "返回O01时刻_s": start + profile.duration,
                "架次能耗_kWh": profile.energy,
                "返航SOC_pct": 100 * (1 - profile.energy / drone.energy_use),
                "货箱编号列表": ",".join(sorted(job["boxes"])),
            }
        )
        for bid, offset in sorted(profile.delivery.items()):
            box = box_map[bid]
            box_rows.append(
                {
                    "货箱编号": bid,
                    "架次编号": jid,
                    "服务区编号": box.service,
                    "交付完成时刻_s": start + offset,
                    "期望_s": box.expected,
                    "硬截止_s": box.hard_deadline,
                    "加权延误": box.priority * max(0.0, start + offset - box.expected),
                }
            )
        outage = job["outage"]
        first, last = outage if outage else (profile.phases[0][1], profile.duration)
        comm_rows.append(
            {
                "运输架次编号": jid,
                "通信阶段": "需中继区间" if outage else "全程",
                "开始时刻_s": start + first,
                "结束时刻_s": start + last,
                "保障方式": "中继" if outage else "直连",
                "中继架次编号": job["relay"] if outage else "",
            }
        )
    spec = relay_inputs.spec
    for relay in relays:
        rid, travel = relay["id"], relay["travel"]
        begin, end = times["begin", rid], times["end", rid]
        energy = (
            travel["fixed_energy"]
            + (spec.hover_power_kw + spec.communication_power_kw)
            * (end - begin)
            / SECONDS_PER_HOUR
        )
        if not energy_feasible(energy, spec.usable_energy_kwh, spec.reserve_fraction):
            raise ValueError(f"Relay energy exceeds reserve: {rid}")
        relay_rows.append(
            {
                "中继架次编号": rid,
                "中继无人机编号": relay["drone"],
                "能源组件编号": relay["component"],
                "开始时刻_s": begin - travel["lead"],
                "悬停经度": relay["point"][0],
                "悬停纬度": relay["point"][1],
                "悬停海拔_m": relay["point"][2],
                "建链完成时刻_s": begin,
                "服务结束时刻_s": end,
                "返回O01时刻_s": end + travel["inbound"],
                "架次能耗_kWh": energy,
                "返航SOC_pct": 100 * (1 - energy / spec.usable_energy_kwh),
                "候选点": relay["candidate"],
            }
        )
    from src.core.constraints import (
        validate_transport,
        validate_relays,
        export_resource_check,
    )

    _, resources = validate_transport(
        transport_rows, box_rows, "q3", physics, boxes, drones, batteries
    )
    validate_relays(relay_rows, physics, relay_inputs, communication)
    export_resource_check(out_dir / "Q3_resource_check.csv", resources)
    metrics = {
        "transport_trips": len(jobs),
        "relay_sorties": len(relays),
        "transport_energy_kwh": sum(r["架次能耗_kWh"] for r in transport_rows),
        "relay_energy_kwh": sum(r["架次能耗_kWh"] for r in relay_rows),
        "transport_makespan_s": max(r["返回O01时刻_s"] for r in transport_rows),
        "joint_makespan_s": max(
            r["返回O01时刻_s"] for r in transport_rows + relay_rows
        ),
        "weighted_tardiness": sum(r["加权延误"] for r in box_rows),
        "minimum_hard_slack_s": min(
            box_map[r["货箱编号"]].hard_deadline - r["交付完成时刻_s"]
            for r in box_rows
            if box_map[r["货箱编号"]].hard_deadline is not None
        ),
        "communication_step_s": step_s,
        "checked_states": sum(j["checked_states"] for j in jobs),
        "continuous_time_proof": False,
    }
    for filename, rows in (
        ("Q3_transport_trips.csv", transport_rows),
        ("Q3_box_delivery.csv", box_rows),
        ("Q3_relay_sorties.csv", relay_rows),
        ("Q3_communication.csv", comm_rows),
    ):
        write_csv(out_dir / filename, rows)
    write_json(out_dir / "Q3_metrics.json", metrics)
    logging.getLogger(__name__).info("Q3: %s", metrics)
    save_provenance(root, out_dir)
    return metrics
