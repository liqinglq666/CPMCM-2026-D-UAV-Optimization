"""Recompute all result tables from official inputs; CSV self-consistency is insufficient."""

from collections import Counter
import json
from pathlib import Path
import tempfile
from src.config import (
    COMMUNICATION_STEP_S,
    RELAY_GUARD_S,
    RESERVE_SCENARIOS,
    SECONDS_PER_HOUR,
)
from src.core.inputs import load_inputs, load_relay_inputs, load_communication_inputs
from src.core.io import read_csv, write_json
from src.core.physics import Physics
from src.core.provenance import check_provenance
from src.core.constraints import (
    close,
    validate_transport,
    validate_relays,
    RESULT_TOLERANCE,
)
from src.q1.physics_engine import (
    compute_segments,
    max_safe_payload,
    feasible_batch,
    roundtrip_energy,
    roundtrip_time,
    optimize_service_q1,
)
from src.core.communication import Communication
from src.core.sampling import sample_audit_states, audit_steps
from src.q4.partition import solve_partitions


def compare_records(actual, expected, label):
    if len(actual) != len(expected):
        raise ValueError(label + ": row count mismatch")
    for left, right in zip(actual, expected):
        if set(left) != set(right):
            raise ValueError(label + ": columns differ")
        for key, value in right.items():
            if isinstance(value, (int, float)):
                close(left[key], value, label + " " + key)
            elif str(left[key]) != ("" if value is None else str(value)):
                raise ValueError(label + ": field mismatch: " + key)


def validate_q1(directory, nodes, types, boxes, dem):
    rows = read_csv(directory / "Q1_batch_solution.csv")
    box_map = {b.id: b for b in boxes}
    metrics = json.loads((directory / "Q1_metrics.json").read_text(encoding="utf-8"))
    rho = metrics["reserve_fraction"]
    expected_reserves = {
        code: drone.rho if rho is None else rho for code, drone in types.items()
    }
    if metrics["reserve_by_type"] != expected_reserves:
        raise ValueError("Q1 per-type reserve metadata mismatch")
    segs = compute_segments(nodes, dem)
    covered, trip_ids = [], []
    for row in rows:
        service, typ = row["服务区编号"], row["机型编号"]
        bids = row["货箱编号列表"].split(",")
        cargo = [box_map[bid] for bid in bids]
        if any(b.service != service for b in cargo):
            raise ValueError("Q1 batch crosses service areas")
        if not feasible_batch(types[typ], segs[service], cargo, rho):
            raise ValueError("Q1 infeasible batch")
        mass, volume = sum(b.mass for b in cargo), sum(b.volume for b in cargo)
        energy = roundtrip_energy(types[typ], segs[service], mass)
        close(row["总质量（kg）"], mass, "Q1 mass")
        close(row["总体积（m³）"], volume, "Q1 volume")
        close(row["架次能耗（kWh）"], energy, "Q1 energy")
        close(
            row["往返时间（s）"],
            roundtrip_time(types[typ], segs[service], len(cargo)),
            "Q1 time",
        )
        close(row["返航SOC（%）"], 100 * (1 - energy / types[typ].energy_use), "Q1 SOC")
        covered.extend(bids)
        trip_ids.append(row["架次编号"])
    if Counter(covered) != Counter(box_map.keys()) or len(set(trip_ids)) != len(rows):
        raise ValueError("Q1 duplicated or missing boxes/trips")
    payloads = read_csv(directory / "Q1_max_safe_payload.csv")
    if Counter(r["服务区编号"] for r in payloads) != Counter(segs.keys()):
        raise ValueError("Q1 safe-payload service coverage mismatch")
    for row in payloads:
        for typ in types:
            expected = max_safe_payload(types[typ], segs[row["服务区编号"]], rho)
            value = row[f"{typ}型最大安全载荷（kg）"]
            if expected is None:
                if value != "" or row[f"{typ}型空载可达"] != "False":
                    raise ValueError("Q1 unreachable service must be explicit")
            else:
                close(value, expected, "Q1 safe payload")
                if row[f"{typ}型空载可达"] != "True":
                    raise ValueError("Q1 reachable service marked unreachable")
    for key, actual in (
        ("trips", len(rows)),
        ("energy_kwh", sum(float(r["架次能耗（kWh）"]) for r in rows)),
        ("operation_time_s", sum(float(r["往返时间（s）"]) for r in rows)),
    ):
        close(metrics[key], actual, "Q1 metrics " + key)
    compare_records(
        read_csv(directory / "Q1_leg_physics.csv"),
        [vars(seg) for seg in segs.values()],
        "Q1 leg physics",
    )
    sensitivity = read_csv(directory / "Q1_sensitivity_summary.csv")
    if len(sensitivity) != len(RESERVE_SCENARIOS):
        raise ValueError("Q1 sensitivity scenarios missing")
    for row, reserve in zip(sensitivity, RESERVE_SCENARIOS):
        close(row["返航安全余量"], reserve, "reserve scenario")
        solutions = {
            service: optimize_service_q1(
                service, [b for b in boxes if b.service == service], types, seg, reserve
            )
            for service, seg in segs.items()
            if any(b.service == service for b in boxes)
        }
        close(
            row["最少往返架次数"],
            sum(s[0] for s in solutions.values()),
            "sensitivity trips",
        )
        close(
            row["总运输能耗（kWh）"],
            sum(s[1] for s in solutions.values()),
            "sensitivity energy",
        )
        time = sum(s[2] for s in solutions.values())
        close(row["累计作业时间（s）"], time, "sensitivity seconds")
        close(row["累计作业时间（h）"], time / SECONDS_PER_HOUR, "sensitivity hours")
        if row["需分批服务区"] != ",".join(
            sid for sid, sol in solutions.items() if sol[0] > 1
        ):
            raise ValueError("Q1 sensitivity split-service mismatch")
    return metrics


def validate_communication(profiles, comm_rows, relays, physics, communication, step_s):
    if Counter(row["运输架次编号"] for row in comm_rows) != Counter(profiles.keys()):
        raise ValueError("Communication table duplicates/misses transport trips")
    checked = 0
    for row in comm_rows:
        tid = row["运输架次编号"]
        profile, start = profiles[tid]
        mode, rid = row["保障方式"], row["中继架次编号"]
        if mode not in ("直连", "中继"):
            raise ValueError("Unknown communication mode")
        if row["通信阶段"] != ("需中继区间" if mode == "中继" else "全程"):
            raise ValueError("Communication phase disagrees with coverage mode")
        if mode == "中继" and rid not in relays:
            raise ValueError("Unknown relay in communication table")
        if mode == "直连" and rid:
            raise ValueError("Direct link row must not reference a relay")
        outages = []
        for offset, point in sample_audit_states(profile, physics, step_s):
            checked += 1
            if communication.link(
                point, communication.gateway, communication.parameters.direct_budget_db
            )[0]:
                continue
            outages.append(start + offset)
            if mode != "中继":
                raise ValueError(f"False direct-link claim: {tid}")
            relay_point, begin, end = relays[rid]
            if not begin - RESULT_TOLERANCE <= start + offset <= end + RESULT_TOLERANCE:
                raise ValueError(f"Relay unavailable at transport state: {tid}")
            if not communication.link(
                point, relay_point, communication.parameters.access_budget_db
            )[0]:
                raise ValueError(f"Uncovered transport state: {tid}")
        if outages:
            first, last = min(outages), max(outages)
            _point, begin, end = relays[rid]
            if (
                begin > first - RELAY_GUARD_S + RESULT_TOLERANCE
                or end < last + RELAY_GUARD_S - RESULT_TOLERANCE
            ):
                raise ValueError(f"Relay guard window missing: {tid}")
        else:
            if mode != "直连":
                raise ValueError(f"Spurious relay outage claim: {tid}")
            first, last = start + profile.phases[0][1], start + profile.duration
        close(row["开始时刻_s"], first, tid + " communication start")
        close(row["结束时刻_s"], last, tid + " communication end")
    return checked


def validate_frontier(
    directory,
    physics,
    boxes,
    drones,
    batteries,
    selected_trips=None,
    selected_deliveries=None,
):
    rows = read_csv(directory / "Q2_tradeoff_frontier.csv")
    plans = json.loads(
        (directory / "Q2_frontier_plans.json").read_text(encoding="utf-8")
    )
    if Counter(row["trips"] for row in rows) != Counter(plans.keys()):
        raise ValueError("Q2 frontier does not match saved plans")
    for row in rows:
        plan = plans[row["trips"]]
        validate_q2_plan(row, plan, physics, boxes, drones, batteries)
    if selected_trips is not None:
        selected = plans.get(str(len(selected_trips)))
        if selected is None:
            raise ValueError("Selected Q2 plan is missing from the frontier")
        compare_records(selected_trips, selected["trips"], "Q2 selected frontier trips")
        compare_records(
            selected_deliveries,
            selected["deliveries"],
            "Q2 selected frontier deliveries",
        )


def validate_q2_plan(row, plan, physics, boxes, drones, batteries):
    profiles, _resources = validate_transport(
        plan["trips"], plan["deliveries"], "q2", physics, boxes, drones, batteries
    )
    for key, expected in (
        ("trips", len(profiles)),
        ("energy", sum(profile.energy for profile, _ in profiles.values())),
        (
            "makespan",
            max(start + profile.duration for profile, start in profiles.values()),
        ),
        ("weighted_tardiness", sum(float(r["加权延误"]) for r in plan["deliveries"])),
        ("hard_violations", 0),
    ):
        close(row[key], expected, "frontier " + key)


def validate_pareto(directory, physics, boxes, drones, batteries):
    from src.core.discrete import dominates

    rows = read_csv(directory / "Q2_pareto_frontier.csv")
    plans = json.loads((directory / "Q2_pareto_plans.json").read_text(encoding="utf-8"))
    if Counter(r["plan_id"] for r in rows) != Counter(plans.keys()):
        raise ValueError("Pareto frontier/plan IDs mismatch")
    objectives = []
    for row in rows:
        validate_q2_plan(row, plans[row["plan_id"]], physics, boxes, drones, batteries)
        objectives.append(
            tuple(
                float(row[k])
                for k in ("weighted_tardiness", "trips", "makespan", "energy")
            )
        )
    if any(
        dominates(a, b)
        for i, a in enumerate(objectives)
        for j, b in enumerate(objectives)
        if i != j
    ):
        raise ValueError("Pareto archive contains a dominated solution")
    return len(rows)


def validate_q3_metrics(metrics, summary, trips, relay_rows, deliveries, boxes, step_s):
    for key, expected in (
        ("transport_trips", len(trips)),
        ("relay_sorties", len(relay_rows)),
        ("transport_energy_kwh", summary["energy_kwh"]),
        ("relay_energy_kwh", summary["relay_energy_kwh"]),
        ("transport_makespan_s", summary["makespan_s"]),
        ("joint_makespan_s", summary["joint_makespan_s"]),
        (
            "weighted_tardiness",
            sum(float(row["加权延误"]) for row in deliveries),
        ),
        ("checked_states", summary["checked_states"]),
        ("communication_step_s", step_s),
        (
            "minimum_hard_slack_s",
            min(
                box.hard_deadline - float(row["交付完成时刻_s"])
                for box in boxes
                if box.hard_deadline is not None
                for row in deliveries
                if row["货箱编号"] == box.id
            ),
        ),
    ):
        close(metrics[key], expected, "Q3 metric " + key)
    if metrics["continuous_time_proof"] is not False:
        raise ValueError("Sampled communication cannot certify continuous time")
    if metrics.get("communication_sampling_steps_s") != list(audit_steps(step_s)):
        raise ValueError("Q3 metrics omit a required communication sampling grid")


def validate_results(root: Path, results: Path, step_s=COMMUNICATION_STEP_S):
    # A failed revalidation must never leave an earlier success certificate.
    (results / "validation.json").unlink(missing_ok=True)
    fingerprints = check_provenance(root, results)
    nodes, types, drones, batteries, boxes, dem = load_inputs(root)
    physics = Physics(nodes, types, dem)
    summary = {"q1": validate_q1(results / "q1", nodes, types, boxes, dem)}
    for question, trip_file, delivery_file in (
        ("q2", "Q2_transport_trips_balanced.csv", "Q2_box_delivery_balanced.csv"),
        ("q3", "Q3_transport_trips.csv", "Q3_box_delivery.csv"),
    ):
        trips = read_csv(results / question / trip_file)
        deliveries = read_csv(results / question / delivery_file)
        profiles, resources = validate_transport(
            trips, deliveries, question, physics, boxes, drones, batteries
        )
        resource_rows = read_csv(
            results / question / f"{question.upper()}_resource_check.csv"
        )
        expected_resources = sorted(
            resources,
            key=lambda row: (
                row["资源类型"],
                row["资源编号"],
                row["任务占用开始（s）"],
            ),
        )
        compare_records(resource_rows, expected_resources, question + " resource check")
        summary[question] = {
            "trips": len(trips),
            "boxes": len(deliveries),
            "energy_kwh": sum(p.energy for p, _ in profiles.values()),
            "makespan_s": max(start + p.duration for p, start in profiles.values()),
        }
        metrics = json.loads(
            (results / question / f"{question.upper()}_metrics.json").read_text(
                encoding="utf-8"
            )
        )
        if question == "q2":
            validate_frontier(
                results / question, physics, boxes, drones, batteries, trips, deliveries
            )
            if (results / question / "Q2_search_summary.json").exists():
                summary[question]["pareto_points"] = validate_pareto(
                    results / question, physics, boxes, drones, batteries
                )
            for key, expected in (
                ("trips", len(trips)),
                ("energy", summary[question]["energy_kwh"]),
                ("makespan", summary[question]["makespan_s"]),
                (
                    "weighted_tardiness",
                    sum(float(row["加权延误"]) for row in deliveries),
                ),
                ("hard_violations", 0),
            ):
                close(metrics[key], expected, "Q2 metric " + key)
        if question == "q3":
            relay_inputs = load_relay_inputs(root)
            communication = Communication(physics, load_communication_inputs(root))
            relay_rows = read_csv(results / question / "Q3_relay_sorties.csv")
            relays = validate_relays(relay_rows, physics, relay_inputs, communication)
            summary[question]["checked_states"] = validate_communication(
                profiles,
                read_csv(results / question / "Q3_communication.csv"),
                relays,
                physics,
                communication,
                step_s,
            )
            summary[question]["relay_energy_kwh"] = sum(
                float(r["架次能耗_kWh"]) for r in relay_rows
            )
            summary[question]["joint_makespan_s"] = max(
                summary[question]["makespan_s"],
                max(float(r["返回O01时刻_s"]) for r in relay_rows),
            )
            validate_q3_metrics(
                metrics, summary[question], trips, relay_rows, deliveries, boxes, step_s
            )
    if (results / "q3/Q3_search_summary.json").exists():
        from src.q4.provenance import q3_fingerprints

        inherited = json.loads(
            (results / "q4/Q4_source_manifest.json").read_text(encoding="utf-8")
        )
        if inherited != q3_fingerprints(results / "q3"):
            raise ValueError("Q4 does not inherit the finalized Q3 generation")
    with tempfile.TemporaryDirectory(prefix="uav-q4-validation-") as directory:
        expected = solve_partitions(results / "q3", Path(directory), root)
        for filename in ("Q4_partition_config.csv", "Q4_resource_summary.csv"):
            calculated, actual = (
                read_csv(Path(directory) / filename),
                read_csv(results / "q4" / filename),
            )
            if len(calculated) != len(actual):
                raise ValueError(f"Q4 result row count mismatch: {filename}")
            for left, right in zip(calculated, actual):
                if left.keys() != right.keys():
                    raise ValueError(f"Q4 column mismatch: {filename}")
                for key in left:
                    if left[key] == right[key]:
                        continue
                    try:
                        target = float(left[key])
                    except ValueError:
                        raise ValueError(
                            f"Q4 result mismatch: {filename}/{key}"
                        ) from None
                    close(right[key], target, "Q4 " + key)
        summary["q4"] = {
            "atomic_groups": len(expected["atoms"]),
            "shortages": {
                str(k): sum(r["缺口"] for r in expected["resource_rows"] if r["K"] == k)
                for k in (2, 3)
            },
        }
    summary["input_sha256"] = fingerprints
    summary["communication_step_s"] = step_s
    summary["communication_sampling_steps_s"] = list(audit_steps(step_s))
    summary["continuous_time_proof"] = False
    write_json(results / "validation.json", summary)
    return summary
