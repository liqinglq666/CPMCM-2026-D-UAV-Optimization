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

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import rasterio
from pyproj import Geod
from rasterio.features import geometry_mask
from shapely.geometry import LineString

G = 9.80665
GEOD = Geod(ellps="WGS84")


def decode_hash_u(text: str) -> str:
    """兼容某些解压环境将中文文件名显示成 #Uxxxx 的情况。"""
    return re.sub(r"#U([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)


def find_file(root: Path, decoded_keyword: str, suffix: str) -> Path:
    candidates = []
    for p in root.rglob(f"*{suffix}"):
        if decoded_keyword in decode_hash_u(p.name):
            candidates.append(p)
    if not candidates:
        raise FileNotFoundError(f"未找到文件：*{decoded_keyword}*{suffix}")
    return candidates[0]


@dataclass(frozen=True)
class DroneType:
    code: str
    empty_mass: float
    max_payload: float
    max_volume: float
    cruise_speed: float
    range_empty: float
    range_full: float
    energy_use: float
    rho: float
    prep_time: float
    load_time_per_box: float
    handover_base: float
    handover_per_box: float
    climb_speed: float
    descent_speed: float
    eta_up: float


@dataclass(frozen=True)
class Node:
    code: str
    lon: float
    lat: float
    elev: float


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


@dataclass(frozen=True)
class Box:
    box_id: str
    service: str
    mass: float
    volume: float
    first_batch: bool
    priority: float


def load_inputs(root: Path):
    node_file = find_file(root, "调度中心与服务区", ".xlsx")
    drone_file = find_file(root, "运输无人机数据", ".xlsx")
    demand_file = find_file(root, "物资需求与配送时限", ".xlsx")
    dem_file = find_file(root, "30米DEM", ".tif")

    node_df = pd.read_excel(node_file, sheet_name="数据", header=None)
    nodes: Dict[str, Node] = {}
    r = node_df.iloc[2]
    nodes[str(r.iloc[0])] = Node(
        str(r.iloc[0]), float(r.iloc[2]), float(r.iloc[3]), float(r.iloc[4])
    )
    for i in range(6, 21):
        r = node_df.iloc[i]
        if pd.notna(r.iloc[0]):
            nodes[str(r.iloc[0])] = Node(
                str(r.iloc[0]), float(r.iloc[2]), float(r.iloc[3]), float(r.iloc[4])
            )

    drone_df = pd.read_excel(drone_file, sheet_name="数据", header=1, nrows=3)
    drones: Dict[str, DroneType] = {}
    for _, r in drone_df.iterrows():
        code = str(r["机型编号"])
        drones[code] = DroneType(
            code=code,
            empty_mass=float(r["含电池空载总质量（kg）"]),
            max_payload=float(r["最大载货质量（kg）"]),
            max_volume=float(r["可用装载体积（m³）"]),
            cruise_speed=float(r["计划巡航速度（m/s）"]),
            range_empty=float(r["空载标准航程（m）"]),
            range_full=float(r["满载标准航程（m）"]),
            energy_use=float(r["电池可用能量（kWh）"]),
            rho=float(r["返航电量下限（%）"]) / 100.0,
            prep_time=float(r["工位固定准备时间（s）"]),
            load_time_per_box=float(r["每箱装载时间（s）"]),
            handover_base=float(r["接收点基础交接时间（s）"]),
            handover_per_box=float(r["每箱增加交接时间（s）"]),
            climb_speed=float(r["最大爬升速度（m/s）"]),
            descent_speed=float(r["最大下降速度（m/s）"]),
            eta_up=float(r["爬升能耗效率"]),
        )

    box_df = pd.read_excel(demand_file, sheet_name="逐箱货箱清单")
    boxes: List[Box] = []
    for _, r in box_df.iterrows():
        boxes.append(
            Box(
                box_id=str(r["货箱编号"]),
                service=str(r["服务区编号"]),
                mass=float(r["单箱质量（kg）"]),
                volume=float(r["单箱体积（m³）"]),
                first_batch=(str(r["是否首批保障"]) == "是"),
                priority=float(r["应急优先系数"]),
            )
        )

    return nodes, drones, boxes, dem_file


def compute_segments(
    nodes: Dict[str, Node], dem_file: Path
) -> Dict[str, SegmentPhysics]:
    o = nodes["O01"]
    out: Dict[str, SegmentPhysics] = {}
    with rasterio.open(dem_file) as ds:
        dem = ds.read(1)
        for sid in sorted(k for k in nodes if k.startswith("S")):
            s = nodes[sid]
            _, _, d = GEOD.inv(o.lon, o.lat, s.lon, s.lat)
            line = LineString([(o.lon, o.lat), (s.lon, s.lat)])
            mask = geometry_mask(
                [line.__geo_interface__],
                out_shape=(ds.height, ds.width),
                transform=ds.transform,
                invert=True,
                all_touched=True,
            )
            max_dem = float(np.max(dem[mask]))
            cruise = max_dem + 50.0
            service_op_alt = s.elev + 30.0
            out[sid] = SegmentPhysics(
                service=sid,
                distance=float(d),
                max_dem=max_dem,
                cruise_alt=cruise,
                out_up=max(0.0, cruise - o.elev),
                out_down=max(0.0, cruise - service_op_alt),
                ret_up=max(0.0, cruise - service_op_alt),
                ret_down=max(0.0, cruise - o.elev),
            )
    return out


def equivalent_range(drone: DroneType, q: float) -> float:
    if not 0.0 <= q <= drone.max_payload + 1e-12:
        raise ValueError(f"载荷 q={q} 超出机型 {drone.code} 范围")
    return drone.range_empty - (
        drone.range_empty - drone.range_full
    ) * (q / drone.max_payload) ** 1.5


def leg_energy(
    drone: DroneType, distance: float, h_up: float, q: float
) -> Tuple[float, float, float]:
    e_hor = drone.energy_use * distance / equivalent_range(drone, q)
    e_up = (drone.empty_mass + q) * G * h_up / (
        drone.eta_up * 3.6e6
    )
    return e_hor + e_up, e_hor, e_up


def roundtrip_energy(
    drone: DroneType, seg: SegmentPhysics, q: float
) -> float:
    e_out = leg_energy(drone, seg.distance, seg.out_up, q)[0]
    e_back = leg_energy(drone, seg.distance, seg.ret_up, 0.0)[0]
    return e_out + e_back


def roundtrip_time(
    drone: DroneType, seg: SegmentPhysics, n_boxes: int
) -> float:
    t_out = (
        seg.out_up / drone.climb_speed
        + seg.distance / drone.cruise_speed
        + seg.out_down / drone.descent_speed
    )
    t_back = (
        seg.ret_up / drone.climb_speed
        + seg.distance / drone.cruise_speed
        + seg.ret_down / drone.descent_speed
    )
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
    rho = drone.rho if rho is None else rho
    cap = (1.0 - rho) * drone.energy_use
    if roundtrip_energy(drone, seg, drone.max_payload) <= cap:
        return drone.max_payload
    if roundtrip_energy(drone, seg, 0.0) > cap:
        return float("nan")
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
            if not feasible_batch(drone, seg, batch, rho):
                continue
            e = roundtrip_energy(drone, seg, mass)
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
    rho: float = 0.20,
    out_dir: Path | None = None,
):
    nodes, drones, boxes, dem_file = load_inputs(root)
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
            first_n = sum(b.first_batch for b in batch)
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
                        b.box_id for b in batch
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
    for rr in (0.10, 0.15, 0.20, 0.25, 0.30):
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

    print(result_df)
    print("\nQ1 totals:")
    print("trips =", len(result_df))
    print(
        "energy_kWh =",
        result_df["架次能耗（kWh）"].sum(),
    )
    print(
        "operation_time_s =",
        result_df["往返时间（s）"].sum(),
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "root",
        type=Path,
        help="D题解压后的根目录",
    )
    parser.add_argument(
        "--rho",
        type=float,
        default=0.20,
        help="返航安全余量，例如0.20",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="输出目录，默认root",
    )
    args = parser.parse_args()
    solve_q1(args.root, args.rho, args.out)
