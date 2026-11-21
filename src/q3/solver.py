"""Search discrete route/relay plans and optimize conditional timing by LP.

The JSON plan contains only discrete decisions (cargo, route, resource order,
relay coordinates). No start time, energy, SOC or communication result is read
from historical outputs. Exactness is conditional on those discrete decisions.
"""

from collections import defaultdict
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
from src.core.io import write_csv, write_json
from src.core.provenance import save_provenance
from src.core.communication import Communication, sample_states as sample_states
from src.core.sampling import audit_steps


def prepare_plan(plan, physics, box_map, drones, batteries, relay_inputs, comm, step_s):
    """Compatibility entry point: recompute without mutating the caller's plan."""
    from .preparation import PlanPreparer

    return PlanPreparer(
        physics, box_map, drones, batteries, relay_inputs, comm, step_s
    ).prepare(plan)


def optimize_timing(jobs, relays, box_map, types, relay_spec, relay_full_charge_s=None):
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
    by_component = defaultdict(list)
    for relay in relays:
        by_component[relay["component"]].append(relay)
    for group in by_component.values():
        for left, right in zip(group, group[1:]):
            if relay_full_charge_s is None:
                raise ValueError(
                    "Relay component reuse requires official recharge time"
                )
            from src.config import CHARGE_KNEE_SOC, CHARGE_FAST_FRACTION

            rid = left["id"]
            energy_fraction = (
                left["travel"]["fixed_energy"] / relay_spec.usable_energy_kwh
            )
            slope_fraction = power / relay_spec.usable_energy_kwh
            knee = 1 - CHARGE_KNEE_SOC
            regime = left.get("charge_regime", "below_knee_soc")
            if regime == "above_knee_soc":
                # Returned SOC >= 90%; only the slow finishing phase is needed.
                slope = relay_full_charge_s * (1 - CHARGE_FAST_FRACTION) / knee
                intercept = 0.0
                constraint(
                    {("end", rid): slope_fraction, ("begin", rid): -slope_fraction},
                    knee - energy_fraction,
                )
            elif regime == "below_knee_soc":
                slope = relay_full_charge_s * CHARGE_FAST_FRACTION / CHARGE_KNEE_SOC
                intercept = (
                    relay_full_charge_s * (1 - CHARGE_FAST_FRACTION) - slope * knee
                )
                constraint(
                    {("begin", rid): slope_fraction, ("end", rid): -slope_fraction},
                    energy_fraction - knee,
                )
            else:
                raise ValueError("Unknown relay charging branch")
            coefficient = slope * slope_fraction
            interval = (
                left["travel"]["inbound"]
                + right["travel"]["lead"]
                + slope * energy_fraction
                + intercept
            )
            constraint(
                {
                    ("end", rid): 1 + coefficient,
                    ("begin", rid): -coefficient,
                    ("begin", right["id"]): -1,
                },
                -interval,
            )
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


def solve_q3(
    root: Path,
    out_dir: Path,
    plan_path=Q3_PLAN,
    step_s=COMMUNICATION_STEP_S,
    search_parameters=None,
):
    from time import perf_counter
    from src.core.search_config import load_search_parameters
    from .search import search_plan

    started = perf_counter()
    parameters = (
        load_search_parameters() if search_parameters is None else search_parameters
    )
    nodes, types, drones, batteries, boxes, dem = load_inputs(root)
    box_map = {b.id: b for b in boxes}
    physics = Physics(nodes, types, dem)
    relay_inputs = load_relay_inputs(root)
    communication = Communication(physics, load_communication_inputs(root))
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    _selected_plan, selected = search_plan(
        plan,
        physics,
        box_map,
        drones,
        batteries,
        relay_inputs,
        communication,
        step_s,
        parameters,
        out_dir,
    )
    jobs, relays, times = selected["jobs"], selected["relays"], selected["times"]
    transport_rows, box_rows, comm_rows, relay_rows = solution_rows(
        jobs, relays, times, box_map, types, relay_inputs
    )
    from src.core.constraints import (
        validate_transport,
        validate_relays,
        export_resource_check,
    )

    profiles, resources = validate_transport(
        transport_rows, box_rows, "q3", physics, boxes, drones, batteries
    )
    relay_states = validate_relays(relay_rows, physics, relay_inputs, communication)
    from src.validation import validate_communication

    validate_communication(
        profiles, comm_rows, relay_states, physics, communication, step_s
    )
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
        "communication_sampling_steps_s": list(audit_steps(step_s)),
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
    write_json(out_dir / "runtime.json", {"solver_runtime_s": perf_counter() - started})
    save_provenance(root, out_dir)
    return metrics


def solution_rows(jobs, relays, times, box_map, types, relay_inputs):
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
    return transport_rows, box_rows, comm_rows, relay_rows
