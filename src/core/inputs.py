"""Official workbook schema. All questions read source values here."""
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Dict, List, Optional
import pandas as pd
from .models import Node, DroneType, Resource, Box
from .numeric import positive, finite


def decode_hash_u(text):
    return re.sub(r"#U([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)


def find_file(root: Path, keyword: str, suffix: str = ".xlsx") -> Path:
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"Official data directory not found: {root}")
    paths = sorted(p for p in root.rglob("*" + suffix)
                   if keyword in decode_hash_u(p.name) and not p.name.startswith("~$"))
    if not paths:
        raise FileNotFoundError(f"Missing official file: {keyword}{suffix} under {root}")
    if len(paths) != 1:
        raise ValueError(f"Ambiguous official input {keyword}: {paths}")
    return paths[0]


def load_inputs(root: Path):
    node_file = find_file(root, "调度中心与服务区")
    node_df = pd.read_excel(node_file, sheet_name="数据", header=None)
    nodes: Dict[str, Node] = {}
    for i in [2] + list(range(6, 21)):
        r = node_df.iloc[i]
        nodes[str(r.iloc[0])] = Node(
            str(r.iloc[0]),
            float(r.iloc[2]),
            float(r.iloc[3]),
            float(r.iloc[4]),
        )

    drone_file = find_file(root, "运输无人机数据")
    d = pd.read_excel(drone_file, sheet_name="数据", header=None)
    header = list(d.iloc[1])
    types: Dict[str, DroneType] = {}
    for i in range(2, 5):
        r = dict(zip(header, d.iloc[i]))
        code = str(r["机型编号"])
        types[code] = DroneType(
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
            full_charge=0.0,
        )

    for i in range(19, 22):
        code = str(d.iloc[i, 0])
        old = types[code]
        types[code] = DroneType(
            **{**old.__dict__, "full_charge": float(d.iloc[i, 2])}
        )

    drones: List[Resource] = []
    for i in range(8, 16):
        if pd.notna(d.iloc[i, 0]):
            drones.append(
                Resource(str(d.iloc[i, 0]), str(d.iloc[i, 1]), 0.0)
            )

    batteries: List[Resource] = []
    counts = {str(d.iloc[i, 0]): int(d.iloc[i, 1]) for i in range(19, 22)}
    for code, count in counts.items():
        for j in range(1, count + 1):
            batteries.append(Resource(f"{code}-BAT-{j:02d}", code, 0.0))

    demand_file = find_file(root, "物资需求与配送时限")
    box_df = pd.read_excel(demand_file, sheet_name="逐箱货箱清单")
    boxes: List[Box] = []
    for _, r in box_df.iterrows():
        kind = str(r["物资类型"])
        first = str(r["是否首批保障"]) == "是"
        first_deadline = (
            None
            if pd.isna(r["首批截止时间（s）"])
            else float(r["首批截止时间（s）"])
        )
        expected = float(r["期望送达时间（s）"])

        hard_deadline: Optional[float]
        hard_deadline = expected if kind == "医疗物资" else None
        if first and first_deadline is not None:
            hard_deadline = (
                first_deadline
                if hard_deadline is None
                else min(hard_deadline, first_deadline)
            )

        boxes.append(
            Box(
                id=str(r["货箱编号"]),
                service=str(r["服务区编号"]),
                kind=kind,
                mass=float(r["单箱质量（kg）"]),
                volume=float(r["单箱体积（m³）"]),
                first=first,
                first_deadline=first_deadline,
                expected=expected,
                priority=float(r["应急优先系数"]),
                hard_deadline=hard_deadline,
            )
        )

    dem_file = find_file(root, "30米DEM", ".tif")
    if len({b.id for b in boxes}) != len(boxes):
        raise ValueError("Duplicate cargo IDs")
    if not boxes or not drones or not batteries:
        raise ValueError("Empty cargo or resource inventory")
    for box in boxes:
        if box.service not in nodes or box.service == "O01":
            raise ValueError(f"Unknown cargo service: {box.service}")
    for resources in (drones, batteries):
        if len({r.id for r in resources}) != len(resources):
            raise ValueError("Duplicate resource IDs")
        if any(r.type not in types for r in resources):
            raise ValueError("Unknown resource type")
    if any(float(d.iloc[i, 17]) != 0 for i in range(2, 5)):
        raise ValueError("Nonzero descent energy is unsupported by Appendix-2 model")
    return nodes, types, drones, batteries, boxes, dem_file


@dataclass(frozen=True)
class RelayInputs:
    spec: object
    drone_ids: tuple
    component_ids: tuple
    full_charge_s: float


@dataclass(frozen=True)
class CommunicationInputs:
    frequency_mhz: float
    obstruction_loss_db: float
    gateway_agl_m: float
    direct_budget_db: float
    access_budget_db: float
    backhaul_budget_db: float


def load_relay_inputs(root):
    from src.q3.communication import RelaySpec
    df = pd.read_excel(find_file(root, "中继无人机数据"), sheet_name="数据", header=None)
    row = dict(zip(df.iloc[1], df.iloc[2]))
    fields = {
        "takeoff_mass_kg": "计划起飞总质量（kg）", "cruise_speed_mps": "计划巡航速度（m/s）",
        "cruise_power_kw": "巡航功率（kW）", "usable_energy_kwh": "能源组件可用能量（kWh）",
        "prep_s": "工位固定准备时间（s）", "link_setup_s": "建链时间（s）",
        "turnaround_s": "架次周转时间（s）", "climb_speed_mps": "最大爬升速度（m/s）",
        "descent_speed_mps": "最大下降速度（m/s）", "climb_efficiency": "爬升能耗效率",
        "hover_power_kw": "悬停功率（kW）", "communication_power_kw": "通信附加功率（kW）",
        "max_hover_agl_m": "最大悬停离地高度（m）"}
    values = {key: positive(float(row[col]), key) for key, col in fields.items()}
    values["reserve_fraction"] = finite(float(row["返航电量下限（%）"]) / 100, "relay reserve", 0, 1)
    if float(row["下降能耗效率"]) != 0:
        raise ValueError("Nonzero relay descent energy is unsupported")
    spec = RelaySpec(**values)
    drones = tuple(str(df.iloc[i, 0]) for i in (6, 7))
    count = int(df.iloc[11, 1])
    if count <= 0 or count != float(df.iloc[11, 1]):
        raise ValueError("Invalid relay component count")
    components = tuple(f"R-BAT-{i:02d}" for i in range(1, count + 1))
    return RelayInputs(spec, drones, components, positive(float(df.iloc[11, 2]), "relay full charge"))


def load_communication_inputs(root):
    from src.q3.communication import Radio, bidirectional_loss_threshold
    df = pd.read_excel(find_file(root, "通信链路参数"), sheet_name="数据", header=None)
    params = {(str(r.iloc[0]), str(r.iloc[1])): float(r.iloc[4])
              for _, r in df.iloc[2:].iterrows() if pd.notna(r.iloc[4])}
    def value(category, name):
        return finite(params[category, name], name)
    sensitivity = value("接收参数", "接收灵敏度（dBm）")
    fade = value("接收参数", "衰落裕量（dB）")
    loss = value("传播参数", "系统损耗（dB）")
    def radio(kind):
        return Radio(value(kind, "发射功率（dBm）"), value(kind, "天线增益（dBi）"), sensitivity)
    gateway = radio("固定网关 G01")
    transport = radio("运输无人机")
    def budget(a, b):
        return bidirectional_loss_threshold(a, b, loss, fade)
    return CommunicationInputs(
        positive(value("传播参数", "载波频率（MHz）"), "frequency"),
        finite(value("传播参数", "地形遮挡附加损耗（dB）"), "obstruction loss", 0),
        finite(value("固定网关 G01", "天线离地高度（m）"), "gateway AGL", 0),
        budget(transport, gateway), budget(transport, radio("中继接入端")),
        budget(radio("中继回传端"), gateway))
