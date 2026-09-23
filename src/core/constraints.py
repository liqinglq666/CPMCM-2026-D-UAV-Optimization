"""Independent schedule constraints, using authoritative input objects."""
from collections import Counter, defaultdict
import math
from .energy import charge_time, energy_feasible, two_stage_charge_time
from .numeric import finite
from .routes import evaluate_route
from .io import write_csv

RESULT_TOLERANCE = 1e-5  # seconds/kWh serialization and LP feasibility tolerance


def close(actual, expected, label):
    actual = finite(actual, label)
    if not math.isclose(actual, expected, abs_tol=RESULT_TOLERANCE, rel_tol=1e-10):
        raise ValueError(f"{label}: reported {actual}, recomputed {expected}")


def check_intervals(intervals, label):
    """Half-open occupancy intervals; track furthest end, including nesting."""
    groups = defaultdict(list)
    for resource, start, end, task in intervals:
        start, end = finite(start, label+" start", 0), finite(end, label+" end", 0)
        if end < start:
            raise ValueError(f"Negative interval: {label}/{task}")
        groups[resource].append((start, end, task))
    for resource, tasks in groups.items():
        latest_end, latest_task = -math.inf, None
        for start, end, task in sorted(tasks):
            if start < latest_end-RESULT_TOLERANCE:
                raise ValueError(f"{label} overlap: {resource}: {latest_task}, {task}")
            if end > latest_end:
                latest_end, latest_task = end, task


def transport_fields(question):
    if question == "q2":
        return {"start": "开始时刻（s）", "end": "返回O01时刻（s）", "energy": "架次能耗（kWh）",
                "soc": "返航SOC（%）", "delivery": "交付完成时刻（s）", "expected": "期望送达时间（s）",
                "hard": "硬截止时间（s）"}
    return {"start": "开始时刻_s", "end": "返回O01时刻_s", "energy": "架次能耗_kWh",
            "soc": "返航SOC_pct", "delivery": "交付完成时刻_s", "expected": "期望_s", "hard": "硬截止_s"}


def validate_transport(trips, deliveries, question, physics, boxes, drones, batteries):
    fields = transport_fields(question)
    box_map = {b.id: b for b in boxes}
    drone_map, battery_map = ({r.id: r.type for r in resources} for resources in (drones, batteries))
    ids = [r["架次编号"] for r in trips]
    if len(set(ids)) != len(ids) or not ids:
        raise ValueError("Empty or duplicate transport trips")
    if Counter(r["货箱编号"] for r in deliveries) != Counter(box_map.keys()):
        raise ValueError("Delivery table does not cover official boxes exactly once")
    delivered = {r["货箱编号"]: r for r in deliveries}
    assigned, drone_intervals, battery_intervals, resources, profiles = [], [], [], [], {}
    for trip in trips:
        tid, typ = trip["架次编号"], trip["机型编号"]
        if drone_map.get(trip["无人机编号"]) != typ or battery_map.get(trip["电池编号"]) != typ or typ not in physics.types:
            raise ValueError(f"Resource inventory/type mismatch: {tid}")
        drone = physics.types[typ]
        start = finite(float(trip[fields["start"]]), "transport start", 0)
        cargo_ids = trip["货箱编号列表"].split(",")
        if any(bid not in box_map for bid in cargo_ids):
            raise ValueError(f"Unknown box in {tid}")
        cargo = [box_map[bid] for bid in cargo_ids]
        profile = evaluate_route(physics, typ, cargo, trip["访问服务区顺序"].split("->"))
        if not energy_feasible(profile.energy, drone.energy_use, drone.rho):
            raise ValueError(f"Battery reserve violated: {tid}")
        close(trip[fields["end"]], start+profile.duration, tid+" return")
        close(trip[fields["energy"]], profile.energy, tid+" energy")
        soc = 1-profile.energy/drone.energy_use
        close(trip[fields["soc"]], 100*soc, tid+" SOC")
        if "货箱数" in trip:
            close(trip["货箱数"], len(cargo), tid+" box count")
        for box in cargo:
            row = delivered[box.id]
            if row["架次编号"] != tid or row["服务区编号"] != box.service:
                raise ValueError(f"Cargo/trip/service mismatch: {box.id}")
            time = start+profile.delivery[box.id]
            close(row[fields["delivery"]], time, box.id+" delivery")
            close(row[fields["expected"]], box.expected, box.id+" expected")
            if box.hard_deadline is None:
                if str(row[fields["hard"]]) not in ("", "None"):
                    raise ValueError(f"Invented hard deadline: {box.id}")
            else:
                close(row[fields["hard"]], box.hard_deadline, box.id+" hard deadline")
                if time > box.hard_deadline+RESULT_TOLERANCE:
                    raise ValueError(f"Hard deadline missed: {box.id}")
            close(row["加权延误"], box.priority*max(0., time-box.expected), box.id+" tardiness")
            if "应急优先系数" in row:
                close(row["应急优先系数"], box.priority, box.id+" priority")
        assigned.extend(cargo_ids)
        end = start+profile.duration
        charge_end = end+charge_time(drone, soc)
        drone_intervals.append((trip["无人机编号"], start, end, tid))
        battery_intervals.append((trip["电池编号"], start, charge_end, tid))
        resources.extend([
            {"架次编号": tid, "资源类型": "无人机", "资源编号": trip["无人机编号"], "机型": typ,
             "任务占用开始（s）": start, "任务占用结束（s）": end, "充电开始（s）": "", "充电结束（s）": "",
             "返航SOC（%）": "", "充电时长（s）": ""},
            {"架次编号": tid, "资源类型": "电池", "资源编号": trip["电池编号"], "机型": typ,
             "任务占用开始（s）": start, "任务占用结束（s）": end, "充电开始（s）": end,
             "充电结束（s）": charge_end, "返航SOC（%）": 100*soc, "充电时长（s）": charge_end-end}])
        profiles[tid] = (profile, start)
    if Counter(assigned) != Counter(box_map.keys()):
        raise ValueError("Transport manifests do not cover official boxes exactly once")
    check_intervals(drone_intervals, "Transport UAV")
    check_intervals(battery_intervals, "Transport battery/charging")
    return profiles, resources


def validate_relays(rows, physics, relay_inputs, communication):
    from src.q3.solver import relay_travel
    spec = relay_inputs.spec
    by_id = {}
    uav_intervals, component_intervals = [], []
    for row in rows:
        rid = row["中继架次编号"]
        if rid in by_id:
            raise ValueError(f"Duplicate relay sortie: {rid}")
        if row["中继无人机编号"] not in relay_inputs.drone_ids or row["能源组件编号"] not in relay_inputs.component_ids:
            raise ValueError(f"Unknown relay resource: {rid}")
        point = tuple(finite(float(row[key]), key) for key in ("悬停经度", "悬停纬度", "悬停海拔_m"))
        travel = relay_travel(physics, spec, point)
        start, begin, end, returned = (finite(float(row[key]), key, 0) for key in
            ("开始时刻_s", "建链完成时刻_s", "服务结束时刻_s", "返回O01时刻_s"))
        if end < begin:
            raise ValueError(f"Negative relay service duration: {rid}")
        close(begin, start+travel["lead"], rid+" setup")
        close(returned, end+travel["inbound"], rid+" return")
        energy = travel["fixed_energy"]+(spec.hover_power_kw+spec.communication_power_kw)*(end-begin)/3600
        if not energy_feasible(energy, spec.usable_energy_kwh, spec.reserve_fraction):
            raise ValueError(f"Relay reserve violated: {rid}")
        close(row["架次能耗_kWh"], energy, rid+" energy")
        soc = 1-energy/spec.usable_energy_kwh
        close(row["返航SOC_pct"], 100*soc, rid+" SOC")
        if not communication.link(point, communication.gateway, communication.parameters.backhaul_budget_db)[0]:
            raise ValueError(f"Unavailable relay backhaul: {rid}")
        uav_intervals.append((row["中继无人机编号"], start, returned+spec.turnaround_s, rid))
        component_intervals.append((row["能源组件编号"], start,
            returned+two_stage_charge_time(relay_inputs.full_charge_s, soc), rid))
        by_id[rid] = (point, begin, end)
    check_intervals(uav_intervals, "Relay UAV/turnaround")
    check_intervals(component_intervals, "Relay component/charging")
    return by_id


def export_resource_check(path, resources):
    write_csv(path, sorted(resources, key=lambda row: (row["资源类型"], row["资源编号"], row["任务占用开始（s）"])))
