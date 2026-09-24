"""Generate LaTeX tables, numerical macros and the official-workbook payload.
AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
"""

from pathlib import Path
import json
import hashlib
import csv
import sys
import pandas as pd
from paper_data import load_analysis

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.config import (
    MAX_ROUTE_SERVICES,
    TARDINESS_SCALE,
    MAKESPAN_SCALE,
    ENERGY_SCALE,
    RELAY_GUARD_S,
)
from src.q4.partition import canonical_partitions

DATA = ROOT / "paper/data"
RESULTS = ROOT / "results"
TABLES = ROOT / "paper/tables"
TABLES.mkdir(parents=True, exist_ok=True)
a = load_analysis(ROOT)
q1 = pd.read_csv(RESULTS / "q1/Q1_batch_solution.csv")
q2 = pd.read_csv(RESULTS / "q2/Q2_transport_trips_balanced.csv")
q3 = pd.read_csv(RESULTS / "q3/Q3_transport_trips.csv")
relay = pd.read_csv(RESULTS / "q3/Q3_relay_sorties.csv")
payload = pd.read_csv(RESULTS / "q1/Q1_max_safe_payload.csv")
frontier = pd.read_csv(RESULTS / "q2/Q2_tradeoff_frontier.csv")
sensitivity = pd.read_csv(RESULTS / "q1/Q1_sensitivity_summary.csv")
partition = pd.read_csv(RESULTS / "q4/Q4_partition_config.csv")
resources = pd.read_csv(RESULTS / "q4/Q4_resource_summary.csv")
c = pd.read_csv(DATA / "constraint_slacks.csv")
m = a["metrics"]
validation = json.loads((RESULTS / "validation.json").read_text(encoding="utf-8"))
atom_count = validation["q4"]["atomic_groups"]
capacity_scenarios = pd.read_csv(DATA / "payload_reserve.csv")
search_parameters = json.loads((ROOT / "config/search.json").read_text())
reserve_stairs = pd.read_csv(DATA / "reserve_staircase.csv")
replay = json.loads((RESULTS / "communication_replay.json").read_text(encoding="utf-8"))
quarter = next(r for r in replay["sampling"] if r["step_s"] == 0.25)
before_repair = json.loads(
    (ROOT / "archive/baseline-2a98f09/results/q3/Q3_metrics.json").read_text()
)
q1_utilization = (
    c[c.question == "q1"][["mass_fraction", "volume_fraction", "energy_fraction"]]
    .idxmax(axis=1)
    .value_counts()
)
macros = {
    "MassTightBatches": str(q1_utilization.get("mass_fraction", 0)),
    "VolumeTightBatches": str(q1_utilization.get("volume_fraction", 0)),
    "EnergyTightBatches": str(q1_utilization.get("energy_fraction", 0)),
    "NumBoxes": str(len(a["boxes"])),
    "NumServices": str(len(a["nodes"]) - 1),
    "QOneTrips": str(m["q1"]["trips"]),
    "QOneEnergy": f"{m['q1']['energy_kwh']:.3f}",
    "QOneTime": f"{m['q1']['operation_time_s']:.3f}",
    "QOneHours": f"{m['q1']['operation_time_s'] / 3600:.3f}",
    "QTwoTrips": str(m["q2"]["trips"]),
    "QTwoEnergy": f"{m['q2']['energy']:.3f}",
    "QTwoTime": f"{m['q2']['makespan']:.3f}",
    "QTwoHours": f"{m['q2']['makespan'] / 3600:.3f}",
    "QTwoLate": f"{m['q2']['weighted_tardiness']:.3f}",
    "QThreeTrips": str(m["q3"]["transport_trips"]),
    "RelayTrips": str(m["q3"]["relay_sorties"]),
    "QThreeTransportEnergy": f"{m['q3']['transport_energy_kwh']:.3f}",
    "RelayEnergy": f"{m['q3']['relay_energy_kwh']:.3f}",
    "JointEnergy": f"{m['q3']['transport_energy_kwh'] + m['q3']['relay_energy_kwh']:.3f}",
    "JointTime": f"{m['q3']['joint_makespan_s']:.3f}",
    "JointHours": f"{m['q3']['joint_makespan_s'] / 3600:.3f}",
    "QThreeTransportTime": f"{m['q3']['transport_makespan_s']:.3f}",
    "QThreeLate": f"{m['q3']['weighted_tardiness']:.3f}",
    "HardSlack": f"{m['q3']['minimum_hard_slack_s']:.3f}",
    "HardBoxes": str(a["hard_deadline_count"]),
    "StatesOne": str(a["sampling_validation"][0]["checked_states"]),
    "StatesHalf": str(a["sampling_validation"][1]["checked_states"]),
    "MarginOne": f"{a['sampling_validation'][0]['minimum_margin_db']:.3f}",
    "MarginHalf": f"{a['sampling_validation'][1]['minimum_margin_db']:.3f}",
    "StatesQuarter": str(quarter["checked_states"]),
    "MarginQuarter": f"{quarter['minimum_margin_db']:.3f}",
    "ViolationsQuarter": str(quarter["violations"]),
    "RepairLateReduction": f"{100 * (1 - m['q3']['weighted_tardiness'] / before_repair['weighted_tardiness']):.2f}",
    "RepairEnergyReduction": f"{100 * (1 - (m['q3']['transport_energy_kwh'] + m['q3']['relay_energy_kwh']) / (before_repair['transport_energy_kwh'] + before_repair['relay_energy_kwh'])):.2f}",
    "RepairTimeIncrease": f"{m['q3']['joint_makespan_s'] - before_repair['joint_makespan_s']:.2f}",
    "ViolationsHalf": str(a["sampling_validation"][1]["violations"]),
    "CriticalTripHalf": a["sampling_validation"][1]["critical_state"]["trip"],
    "CriticalTimeHalf": f"{a['sampling_validation'][1]['critical_state']['time_s']:.3f}",
    "ParetoCount": str(len(pd.read_csv(RESULTS / "q2/Q2_pareto_frontier.csv"))),
    "SearchSeed": str(search_parameters["seed"]),
    "QTwoIterations": str(search_parameters["q2_iterations"]),
    "QThreeIterations": str(search_parameters["q3_iterations"]),
    "ReserveTripBreak": f"{reserve_stairs.iloc[0].reserve_upper * 100:.2f}",
    "ReserveReachabilityLimit": f"{reserve_stairs[~reserve_stairs.reachable].reserve_lower.min() * 100:.2f}",
    "MinSoc": f"{c[c.question == 'q3'].soc_pct.min():.2f}",
    "QOneReserveLimit": f"{100 * a['fixed_plan_thresholds']['q1']['maximum_common_reserve']:.2f}",
    "QThreeEnergyTolerance": f"{100 * (a['fixed_plan_thresholds']['q3']['maximum_energy_multiplier'] - 1):.2f}",
    "QTwoEnergyTolerance": f"{100 * (a['fixed_plan_thresholds']['q2']['maximum_energy_multiplier'] - 1):.2f}",
    "GapTwo": str(resources[resources.K == 2]["缺口"].sum()),
    "GapThree": str(resources[resources.K == 3]["缺口"].sum()),
    "EnergyIncrease": f"{100 * ((m['q3']['transport_energy_kwh'] + m['q3']['relay_energy_kwh']) / m['q2']['energy'] - 1):.2f}",
    "TimeIncrease": f"{100 * (m['q3']['joint_makespan_s'] / m['q2']['makespan'] - 1):.2f}",
    "CMinPayload": f"{payload['C型最大安全载荷（kg）'].min():.2f}",
    "BMinPayload": f"{payload['B型最大安全载荷（kg）'].min():.2f}",
    "CRestricted": str(
        (payload["C型最大安全载荷（kg）"] < a["types"]["C"]["max_payload"] - 1e-8).sum()
    ),
    "CandidateCount": str(len(frontier)),
    "CandidateMaxTrips": str(int(frontier.trips.max())),
    "CandidateMinTrips": str(int(frontier.trips.min())),
    "AtomicGroups": str(atom_count),
    "PartitionsTwo": str(sum(1 for _ in canonical_partitions(atom_count, 2))),
    "PartitionsThree": str(sum(1 for _ in canonical_partitions(atom_count, 3))),
    "ReserveGridCount": str(capacity_scenarios.reserve.nunique()),
    "CapacityCaseCount": str(len(capacity_scenarios)),
    "BatchScenarioCount": str(len(sensitivity)),
    "MaxRouteServices": str(MAX_ROUTE_SERVICES),
    "MergeLateScale": f"{TARDINESS_SCALE:g}",
    "MergeTimeScale": f"{MAKESPAN_SCALE:g}",
    "MergeEnergyScale": f"{ENERGY_SCALE:g}",
    "RelayGuard": f"{RELAY_GUARD_S:g}",
}
(TABLES / "numbers.tex").write_text(
    "% Auto-generated; never edit numbers here.\n"
    + "".join("\\newcommand{\\" + k + "}{" + v + "}\n" for k, v in macros.items()),
    encoding="utf-8",
)
(DATA / "paper_numbers.json").write_text(
    json.dumps(macros, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)


def table(name, headers, rows, align=None):
    # Numeric rounding is presentation-only; full-precision CSVs remain authoritative.
    s = (
        "\\begin{tabular}{"
        + (align or "l" + "r" * (len(headers) - 1))
        + "}\n\\toprule\n"
    )
    s += " & ".join(headers) + r" \\" + "\n\\midrule\n"
    for row in rows:
        s += " & ".join(str(v) for v in row) + r" \\" + "\n"
    s += "\\bottomrule\n\\end{tabular}\n"
    long_names = {
        "payloads",
        "q1_batches",
        "q2_schedule",
        "q3_schedule",
        "relay_schedule",
        "relay_positions",
        "frontier",
    }
    if name not in long_names:
        (TABLES / f"{name}.tex").write_text(s, encoding="utf-8")
        return
    header = " & ".join(headers) + r" \\" + "\n"
    long_s = r"\begin{longtable}{" + (align or "l" + "r" * (len(headers) - 1)) + "}\n"
    long_s += r"\caption{\resultcaption}\label{\resultlabel}\\" + "\n"
    long_s += "\\toprule\n" + header + "\\midrule\n\\endfirsthead\n"
    long_s += "\\toprule\n" + header + "\\midrule\n\\endhead\n\\bottomrule\n\\endfoot\n"
    long_s += "".join(
        " & ".join(str(v) for v in row) + (r" \\*" if i < 2 else r" \\") + "\n"
        for i, row in enumerate(rows)
    )
    long_s += "\\end{longtable}\n"
    (TABLES / f"{name}_long.tex").write_text(long_s, encoding="utf-8")


table(
    "drone_parameters",
    [
        "机型",
        "$Q_g$ / kg",
        "$V_g$ / m$^3$",
        "$E_g$ / kWh",
        "$v_g^c$ / m s$^{-1}$",
        "$L_g^0/L_g^F$ / km",
    ],
    [
        [
            g,
            f"{t['max_payload']:g}",
            f"{t['max_volume']:.3f}",
            f"{t['energy_use']:.1f}",
            f"{t['cruise_speed']:g}",
            f"{t['range_empty'] / 1000:g}/{t['range_full'] / 1000:g}",
        ]
        for g, t in a["types"].items()
    ],
)
table(
    "payloads",
    ["服务区", "A 型 / kg", "B 型 / kg", "C 型 / kg"],
    [
        [r["服务区编号"]]
        + [f"{r[f'{g}型最大安全载荷（kg）']:.2f}" for g in ["A", "B", "C"]]
        for _, r in payload.iterrows()
    ],
)
table(
    "summary",
    ["方案", "运输架次", "中继架次", "总能耗 / kWh", "时间 / s"],
    [
        ["Q1", macros["QOneTrips"], "--", macros["QOneEnergy"], macros["QOneTime"]],
        ["Q2", macros["QTwoTrips"], "--", macros["QTwoEnergy"], macros["QTwoTime"]],
        [
            "Q3",
            macros["QThreeTrips"],
            macros["RelayTrips"],
            macros["JointEnergy"],
            macros["JointTime"],
        ],
    ],
)
table(
    "frontier",
    ["架次", "能耗 / kWh", "完工 / s", "加权延误 / 系数·s"],
    [
        [
            int(r.trips),
            f"{r.energy:.3f}",
            f"{r.makespan:.1f}",
            f"{r.weighted_tardiness:.1f}",
        ]
        for r in frontier.itertuples()
    ],
)
table(
    "q2_selection",
    ["架次", "能耗 / kWh", "完工 / s", "加权延误 / 系数·s"],
    [
        [
            int(r.trips),
            f"{r.energy:.3f}",
            f"{r.makespan:.1f}",
            f"{r.weighted_tardiness:.1f}",
        ]
        for r in frontier[abs(frontier.trips - m["q2"]["trips"]) <= 1].itertuples()
    ],
)
table(
    "sensitivity",
    ["储备 / \\%", "架次", "能耗 / kWh", "累计作业 / s"],
    [
        [
            f"{r['返航安全余量'] * 100:.0f}",
            int(r["最少往返架次数"]),
            f"{r['总运输能耗（kWh）']:.3f}",
            f"{r['累计作业时间（s）']:.1f}",
        ]
        for _, r in sensitivity.iterrows()
    ],
)
table(
    "sampling",
    ["步长 / s", "状态数", "未覆盖状态数", "最小余量 / dB"],
    [
        [
            f"{r['step_s']:.1f}",
            r["checked_states"],
            r["violations"],
            f"{r['minimum_margin_db']:.6f}",
        ]
        for r in a["sampling_validation"]
    ],
)
table(
    "q1_batches",
    ["架次", "机型", "箱数", "质量 / kg", "能耗 / kWh", "SOC / \\%"],
    [
        [
            r["架次编号"].replace("Q1-", ""),
            r["机型编号"],
            len(r["货箱编号列表"].split(",")),
            f"{r['总质量（kg）']:.0f}",
            f"{r['架次能耗（kWh）']:.3f}",
            f"{r['返航SOC（%）']:.2f}",
        ]
        for _, r in q1.iterrows()
    ],
    align="llrrrr",
)
for question, frame, sf, ef, eng in [
    ("q2", q2, "开始时刻（s）", "返回O01时刻（s）", "架次能耗（kWh）"),
    ("q3", q3, "开始时刻_s", "返回O01时刻_s", "架次能耗_kWh"),
]:
    table(
        question + "_schedule",
        ["架次", "无人机", "电池", "开始 / s", "返回 / s", "能耗 / kWh"],
        [
            [
                r["架次编号"].replace(question.upper() + "-", ""),
                r["无人机编号"],
                r["电池编号"].replace("-BAT-", "-"),
                f"{r[sf]:.1f}",
                f"{r[ef]:.1f}",
                f"{r[eng]:.3f}",
            ]
            for _, r in frame.iterrows()
        ],
        align="lllrrr",
    )
table(
    "relay_schedule",
    ["架次", "开始 / s", "建链 / s", "服务结束 / s", "返航 / s", "能耗 / kWh"],
    [
        [r["中继架次编号"]]
        + [
            f"{r[k]:.1f}"
            for k in ["开始时刻_s", "建链完成时刻_s", "服务结束时刻_s", "返回O01时刻_s"]
        ]
        + [f"{r['架次能耗_kWh']:.3f}"]
        for _, r in relay.iterrows()
    ],
)
table(
    "relay_positions",
    ["架次", "经度 / °E", "纬度 / °N", "海拔 / m", "SOC / \\%"],
    [
        [
            r["中继架次编号"],
            f"{r['悬停经度']:.7f}",
            f"{r['悬停纬度']:.7f}",
            f"{r['悬停海拔_m']:.3f}",
            f"{r['返航SOC_pct']:.2f}",
        ]
        for _, r in relay.iterrows()
    ],
)
labels = {
    "A_uav": "A 型无人机",
    "B_uav": "B 型无人机",
    "C_uav": "C 型无人机",
    "A_bat": "A 型电池",
    "B_bat": "B 型电池",
    "C_bat": "C 型电池",
    "relay_uav": "中继无人机",
    "relay_comp": "中继能源组件",
}
table(
    "resource_gaps",
    ["资源", "库存", "$K=2$ 需求", "缺口", "$K=3$ 需求", "缺口"],
    [
        [
            labels[key],
            int(g["现有库存"].iloc[0]),
            int(g[g.K == 2]["分组独立执行总需求"].iloc[0]),
            int(g[g.K == 2]["缺口"].iloc[0]),
            int(g[g.K == 3]["分组独立执行总需求"].iloc[0]),
            int(g[g.K == 3]["缺口"].iloc[0]),
        ]
        for key, g in resources.groupby("资源", sort=False)
    ],
)
# Official template sheets, unchanged headers/order, plus necessary Q3 transport supplements.
sheets = []


def sheet(name, frame, headers=None, add=False):
    headers = headers or list(frame.columns)
    values = frame.astype(object).where(pd.notna(frame), None).values.tolist()
    numeric = [
        i
        for i, c in enumerate(frame.columns)
        if pd.api.types.is_numeric_dtype(frame[c])
    ]
    widths = [
        max(
            15,
            min(
                50,
                max(
                    [len(str(v[i])) for v in values if v[i] is not None]
                    + [len(headers[i])]
                )
                * 1.15,
            ),
        )
        if i not in numeric
        else 19
        for i in range(len(headers))
    ]
    formats = {
        str(i): (
            "0"
            if "数" in headers[i] or headers[i].startswith("K")
            else (
                "0.0000000" if "经度" in headers[i] or "纬度" in headers[i] else "0.000"
            )
        )
        for i in numeric
    }
    sheets.append(
        dict(
            name=name,
            headers=headers,
            values=values,
            add=add,
            numeric_columns=numeric,
            widths=widths,
            formats=formats,
        )
    )


sheet("Q1_单点组批", q1)
sheet("Q2_运输架次", q2.iloc[:, :8])
sheet(
    "Q2_逐箱交付", pd.read_csv(RESULTS / "q2/Q2_box_delivery_balanced.csv").iloc[:, :4]
)
sheet(
    "Q3_中继架次",
    relay.iloc[:, :11],
    [
        "中继架次编号",
        "中继无人机编号",
        "能源组件编号",
        "开始时刻（s）",
        "悬停经度（°）",
        "悬停纬度（°）",
        "悬停海拔（m）",
        "建链完成时刻（s）",
        "服务结束时刻（s）",
        "返回O01时刻（s）",
        "架次能耗（kWh）",
    ],
)
sheet(
    "Q3_通信保障",
    pd.read_csv(RESULTS / "q3/Q3_communication.csv"),
    [
        "运输架次编号",
        "通信阶段",
        "开始时刻（s）",
        "结束时刻（s）",
        "保障方式",
        "中继架次编号",
    ],
)
sheet("Q4_分区配置", partition.iloc[:, :11], ["K（2或3）", *partition.columns[1:11]])
sheet("Q3_运输架次", q3, add=True)
sheet("Q3_逐箱交付", pd.read_csv(RESULTS / "q3/Q3_box_delivery.csv"), add=True)
(DATA / "workbook_payload.json").write_text(
    json.dumps({"sheets": sheets}, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
contracts = json.loads(
    (ROOT / "paper/figure_contracts.json").read_text(encoding="utf-8")
)
with (ROOT / "paper/figure_manifest.csv").open(
    "w", newline="", encoding="utf-8"
) as stream:
    writer = csv.DictWriter(
        stream,
        lineterminator="\n",
        fieldnames=[
            "figure_id",
            "core_claim",
            "source_data",
            "script",
            "output",
            "section",
            "data_sha256",
        ],
    )
    writer.writeheader()
    for contract in contracts:
        writer.writerow(
            {k: contract[k] for k in ("figure_id", "core_claim", "script", "section")}
            | {
                "source_data": ";".join(contract["source_data"]),
                "output": ";".join(
                    "outputs/figures/" + contract["figure_id"] + "." + e
                    for e in contract["export_formats"]
                ),
                "data_sha256": json.dumps(
                    {
                        source: hashlib.sha256((ROOT / source).read_bytes()).hexdigest()
                        for source in contract["source_data"]
                    },
                    sort_keys=True,
                ),
            }
        )
print(
    "Generated",
    len(macros),
    "number macros, tables, workbook payload and figure manifest",
)
