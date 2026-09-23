# -*- coding: utf-8 -*-
"""
2026 华为杯研究生数学建模竞赛 D 题：Q1 统一物理计算引擎

AI 辅助说明（提交前请按赛事附件4最终核对格式）：
- 工具：ChatGPT
- 模型：GPT-5.6 Sol
- 开发机构：OpenAI
- 模型假设、公式口径、参数与输出应由参赛队独立核验并负责。

核心口径：
1) 航段为两节点水平直线；WGS84 椭球计算水平距离。
2) 计划巡航海拔 = 航段经过的 30 m DEM 像元最高地面高程 + 50 m。
   采用 all_touched=True 栅格化直线，符合“航段所经过 DEM 像元”的字面口径。
3) 等效航程：L(q)=L0-(L0-LF)*(q/Q)^(3/2)。
4) 水平能耗：E_hor=E_use*d/L(q)。
5) 爬升附加能耗：E_up=(m_empty+q)*g*h_up/(eta_up*3.6e6) kWh。
6) 下降附加能耗取 0。
7) 单点往返 O01->Si->O01：去程载荷为该批货箱总质量，返程载荷为 0。
8) 返航安全约束：E_trip <= (1-rho)*E_use。
9) Q1 组批采用词典序目标：架次数最少 -> 总能耗最少 -> 累计作业时间最少。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, List
import pandas as pd
from src.core.models import DroneType, Node, Box
from src.core.inputs import load_inputs
from src.core.physics import Physics
from src.core.energy import equivalent_range as equivalent_range, leg_energy, flight_time
from src.core.numeric import finite
from src.core.io import write_json
from src.config import DEFAULT_RESERVE, RESERVE_SCENARIOS, TERRAIN_CLEARANCE_M

@dataclass(frozen=True)
class SegmentPhysics:
    service: str
    distance: float
    max_dem: float
    cruise_alt: float
    out_up: float
    out_down: float
    ret_up: float
    ret_down: float



def compute_segments(nodes: Dict[str, Node], dem_file: Path):
    physics = Physics(nodes, {}, dem_file)
    segments = {}
    for service in sorted(k for k in nodes if k != "O01"):
        out = physics.segment("O01", service)
        back = physics.segment(service, "O01")
        segments[service] = SegmentPhysics(service, out.distance, out.cruise_alt - TERRAIN_CLEARANCE_M,
            out.cruise_alt, out.climb, out.descent, back.climb, back.descent)
    return segments


def roundtrip_energy(
    drone: DroneType, seg: SegmentPhysics, q: float
) -> float:
    e_out = leg_energy(drone, seg.distance, seg.out_up, q)[0]
    e_back = leg_energy(drone, seg.distance, seg.ret_up, 0.0)[0]
    return e_out + e_back


def roundtrip_time(
    drone: DroneType, seg: SegmentPhysics, n_boxes: int
) -> float:
    t_out = flight_time(seg.distance, seg.out_up, seg.out_down, drone.cruise_speed, drone.climb_speed, drone.descent_speed)
    t_back = flight_time(seg.distance, seg.ret_up, seg.ret_down, drone.cruise_speed, drone.climb_speed, drone.descent_speed)
    t_ops = (
        drone.prep_time
        + n_boxes * drone.load_time_per_box
        + drone.handover_base
        + n_boxes * drone.handover_per_box
    )
    return t_out + t_back + t_ops


def max_safe_payload(
    drone: DroneType, seg: SegmentPhysics, rho: float | None = None
) -> float:
    rho = finite(drone.rho if rho is None else rho, "reserve", 0, 1)
    cap = (1.0 - rho) * drone.energy_use
    if roundtrip_energy(drone, seg, drone.max_payload) <= cap:
        return drone.max_payload
    if roundtrip_energy(drone, seg, 0.0) > cap:
        return None  # explicit unreachable service/type, exported with feasibility status
    lo, hi = 0.0, drone.max_payload
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if roundtrip_energy(drone, seg, mid) <= cap:
            lo = mid
        else:
            hi = mid
    return lo


def feasible_batch(
    drone: DroneType,
    seg: SegmentPhysics,
    batch: List[Box],
    rho: float,
) -> bool:
    if not batch or len({b.id for b in batch}) != len(batch):
        return False
    finite(rho, "reserve", 0, 1)
    mass = sum(b.mass for b in batch)
    volume = sum(b.volume for b in batch)
    if mass > drone.max_payload + 1e-10:
        return False
    if volume > drone.max_volume + 1e-12:
        return False
    return (
        roundtrip_energy(drone, seg, mass)
        <= (1.0 - rho) * drone.energy_use + 1e-10
    )


def optimize_service_q1(
    service: str,
    boxes: List[Box],
    drones: Dict[str, DroneType],
    seg: SegmentPhysics,
    rho: float,
):
    return _optimize_service(service, tuple(boxes), tuple(drones.values()), seg, rho)


@lru_cache(maxsize=128)
def _optimize_service(service, boxes, drone_types, seg, rho):
    drones = {drone.code: drone for drone in drone_types}
    """精确集合划分 DP：词典序 min(架次数, 总能耗, 累计作业时间)。"""
    n = len(boxes)
    full = (1 << n) - 1
    candidates = []

    for mask in range(1, 1 << n):
        batch = [boxes[i] for i in range(n) if (mask >> i) & 1]
        mass = sum(b.mass for b in batch)
        volume = sum(b.volume for b in batch)
        for g in ("A", "B", "C"):
            drone = drones[g]
            if mass > drone.max_payload + 1e-10 or volume > drone.max_volume + 1e-12:
                continue
            e = roundtrip_energy(drone, seg, mass)
            if e > (1-rho)*drone.energy_use + 1e-10:
                continue
            t = roundtrip_time(drone, seg, len(batch))
            soc = 100.0 * (1.0 - e / drone.energy_use)
            candidates.append((mask, g, e, t, mass, volume, soc))

    best_by_mask = {}
    for c in candidates:
        mask, _, e, t, *_ = c
        if mask not in best_by_mask:
            best_by_mask[mask] = c
        elif (e, t) < (
            best_by_mask[mask][2],
            best_by_mask[mask][3],
        ):
            best_by_mask[mask] = c
    candidates = list(best_by_mask.values())

    by_first = {i: [] for i in range(n)}
    for c in candidates:
        mask = c[0]
        for i in range(n):
            if (mask >> i) & 1:
                by_first[i].append(c)

    dp = [None] * (1 << n)
    dp[0] = (0, 0.0, 0.0, [])

    for mask in range(1 << n):
        if dp[mask] is None or mask == full:
            continue
        first = next(i for i in range(n) if not ((mask >> i) & 1))
        for c in by_first[first]:
            cm, _, e, t, *_ = c
            if cm & mask:
                continue
            nm = mask | cm
            cand = (
                dp[mask][0] + 1,
                dp[mask][1] + e,
                dp[mask][2] + t,
                dp[mask][3] + [c],
            )
            if dp[nm] is None or cand[:3] < dp[nm][:3]:
                dp[nm] = cand

    if dp[full] is None:
        raise RuntimeError(
            f"服务区 {service} 在 rho={rho:.2%} 下不存在可行组批"
        )
    return dp[full]


def solve_q1(
    root: Path,
    rho: float = DEFAULT_RESERVE,
    out_dir: Path | None = None,
):
    nodes, drones, _uavs, _batteries, boxes, dem_file = load_inputs(root)
    finite(rho, "reserve", 0, 1)
    segs = compute_segments(nodes, dem_file)
    out_dir = out_dir or root
    out_dir.mkdir(parents=True, exist_ok=True)

    leg_rows = [vars(s) for s in segs.values()]
    pd.DataFrame(leg_rows).to_csv(
        out_dir / "Q1_leg_physics.csv",
        index=False,
        encoding="utf-8-sig",
    )

    load_rows = []
    for sid, seg in segs.items():
        row = {"服务区编号": sid}
        for g in ("A", "B", "C"):
            row[f"{g}型最大安全载荷（kg）"] = max_safe_payload(
                drones[g], seg, rho
            )
            row[f"{g}型空载可达"] = row[f"{g}型最大安全载荷（kg）"] is not None
        load_rows.append(row)

    pd.DataFrame(load_rows).to_csv(
        out_dir / "Q1_max_safe_payload.csv",
        index=False,
        encoding="utf-8-sig",
    )

    by_service: Dict[str, List[Box]] = {}
    for b in boxes:
        by_service.setdefault(b.service, []).append(b)

    result_rows = []
    for sid in sorted(by_service):
        bs = by_service[sid]
        sol = optimize_service_q1(
            sid,
            bs,
            drones,
            segs[sid],
            rho,
        )

        parts = []
        for c in sol[3]:
            mask, _, _, _, _, _, _ = c
            batch = [
                bs[i]
                for i in range(len(bs))
                if (mask >> i) & 1
            ]
            first_n = sum(b.first for b in batch)
            priority_sum = sum(b.priority for b in batch)
            parts.append(
                (first_n, priority_sum, c, batch)
            )

        parts.sort(
            key=lambda x: (-x[0], -x[1], -x[2][4])
        )

        for k, (_, _, c, batch) in enumerate(parts, 1):
            _, g, e, t, mass, volume, soc = c
            result_rows.append(
                {
                    "架次编号": f"Q1-{sid}-{k:02d}",
                    "服务区编号": sid,
                    "机型编号": g,
                    "货箱编号列表": ",".join(
                        b.id for b in batch
                    ),
                    "总质量（kg）": mass,
                    "总体积（m³）": volume,
                    "往返时间（s）": t,
                    "架次能耗（kWh）": e,
                    "返航SOC（%）": soc,
                }
            )

    result_df = pd.DataFrame(result_rows)
    result_df.to_csv(
        out_dir / "Q1_batch_solution.csv",
        index=False,
        encoding="utf-8-sig",
    )

    sens_rows = []
    for rr in RESERVE_SCENARIOS:
        trips = 0
        energy = 0.0
        op_time = 0.0
        split = []

        for sid in sorted(by_service):
            sol = optimize_service_q1(
                sid,
                by_service[sid],
                drones,
                segs[sid],
                rr,
            )
            trips += sol[0]
            energy += sol[1]
            op_time += sol[2]
            if sol[0] > 1:
                split.append(sid)

        sens_rows.append(
            {
                "返航安全余量": rr,
                "最少往返架次数": trips,
                "总运输能耗（kWh）": energy,
                "累计作业时间（s）": op_time,
                "累计作业时间（h）": op_time / 3600.0,
                "需分批服务区": ",".join(split),
            }
        )

    pd.DataFrame(sens_rows).to_csv(
        out_dir / "Q1_sensitivity_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    logging.getLogger(__name__).info("Q1: %s trips, %.6f kWh, %.3f s", len(result_df),
        result_df["架次能耗（kWh）"].sum(), result_df["往返时间（s）"].sum())
    write_json(out_dir / "Q1_metrics.json", {"reserve_fraction": rho, "trips": len(result_df),
        "energy_kwh": float(result_df["架次能耗（kWh）"].sum()),
        "operation_time_s": float(result_df["往返时间（s）"].sum())})
    return result_df
