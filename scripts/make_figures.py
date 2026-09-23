# AI-assisted development disclosure
# Tool: ChatGPT
# Model: GPT-5.6 Sol
# Developer: OpenAI
# General-availability release date: 2026-07-09
# The participating team must independently verify all plots and numerical
# outputs before competition submission.

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.core.inputs import load_inputs
from src.core.io import read_csv
from src.config import DEFAULT_DATA_ROOT


def save(fig, out: Path):
    fig.tight_layout()
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def q1_sensitivity(results: Path, out: Path):
    rows = read_csv(results / "q1" / "Q1_sensitivity_summary.csv")
    x = [100 * float(r["返航安全余量"]) for r in rows]
    y = [int(r["最少往返架次数"]) for r in rows]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(x, y, marker="o")
    ax.set_xlabel("Return-energy reserve (%)")
    ax.set_ylabel("Minimum round trips")
    ax.set_title("Q1 Sensitivity of Trip Count to Return Reserve")
    ax.grid(True, alpha=0.25)
    save(fig, out / "Fig_Q1_reserve_sensitivity.png")


def q2_frontier(results: Path, out: Path):
    rows = read_csv(results / "q2" / "Q2_tradeoff_frontier.csv")
    trips = np.array([int(r["trips"]) for r in rows])
    selected = len(read_csv(results / "q2" / "Q2_transport_trips_balanced.csv"))
    tard = np.array([float(r.get("weighted_tardiness", r.get("wt"))) for r in rows])
    energy = np.array([float(r["energy"]) for r in rows])

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(trips, tard, marker="o")
    for x, y in zip(trips, tard):
        ax.annotate(
            str(x),
            (x, y),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=8,
        )
    ax.axvline(selected, linestyle="--", linewidth=1)
    ax.annotate(
        "selected balance point",
        (selected, tard[list(trips).index(selected)]),
        xytext=(10, 18),
        textcoords="offset points",
        fontsize=8,
    )
    ax.set_xlabel("Transport trips")
    ax.set_ylabel("Weighted tardiness (priority·s)")
    ax.set_title("Q2 Trip Count–Timeliness Trade-off")
    ax.grid(True, alpha=0.25)
    save(fig, out / "Fig_Q2_tradeoff_tardiness.png")

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(trips, energy, marker="o")
    for x, y in zip(trips, energy):
        ax.annotate(
            str(x),
            (x, y),
            xytext=(4, 4),
            textcoords="offset points",
            fontsize=8,
        )
    ax.axvline(selected, linestyle="--", linewidth=1)
    ax.annotate(
        "selected balance point",
        (selected, energy[list(trips).index(selected)]),
        xytext=(10, 12),
        textcoords="offset points",
        fontsize=8,
    )
    ax.set_xlabel("Transport trips")
    ax.set_ylabel("Transport energy (kWh)")
    ax.set_title("Q2 Trip Count–Energy Trade-off")
    ax.grid(True, alpha=0.25)
    save(fig, out / "Fig_Q2_tradeoff_energy.png")


def q3_relay_map(results: Path, out: Path, nodes):
    relay = read_csv(results / "q3" / "Q3_relay_sorties.csv")
    fig, ax = plt.subplots(figsize=(7.5, 6))
    sx = [nodes[k][0] for k in nodes if k.startswith("S")]
    sy = [nodes[k][1] for k in nodes if k.startswith("S")]
    ax.scatter(sx, sy, marker="o", label="Service areas")
    ax.scatter(
        [nodes["O01"][0]],
        [nodes["O01"][1]],
        marker="s",
        s=70,
        label="O01",
    )
    for k, (x, y) in nodes.items():
        ax.annotate(
            k,
            (x, y),
            xytext=(3, 3),
            textcoords="offset points",
            fontsize=7,
        )

    rx = [float(r["悬停经度"]) for r in relay]
    ry = [float(r["悬停纬度"]) for r in relay]
    ax.scatter(
        rx,
        ry,
        marker="^",
        s=80,
        label="Relay hover states",
    )
    for r, x, y in zip(relay, rx, ry):
        ax.annotate(
            r["候选点"],
            (x, y),
            xytext=(4, -10),
            textcoords="offset points",
            fontsize=8,
        )
    ax.set_xlabel("Longitude (°)")
    ax.set_ylabel("Latitude (°)")
    ax.set_title("Q3 Service Areas and Selected Relay Hover States")
    ax.legend()
    ax.grid(True, alpha=0.25)
    save(fig, out / "Fig_Q3_relay_locations.png")


def q3_gantt(results: Path, out: Path):
    trips = read_csv(results / "q3" / "Q3_transport_trips.csv")
    relay = read_csv(results / "q3" / "Q3_relay_sorties.csv")
    tasks = []
    for r in trips:
        start = float(r["开始时刻_s"])
        tasks.append(
            (
                r["架次编号"],
                start,
                float(r["返回O01时刻_s"]) - start,
            )
        )
    for r in relay:
        start = float(r["开始时刻_s"])
        tasks.append(
            (
                r["中继架次编号"],
                start,
                float(r["返回O01时刻_s"]) - start,
            )
        )
    tasks.sort(key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(10, 10))
    y = np.arange(len(tasks))
    for yi, task in zip(y, tasks):
        kwargs = {"hatch": "///"} if task[0].startswith("R") else {}
        ax.barh(yi, task[2], left=task[1], **kwargs)
    ax.set_yticks(
        y,
        labels=[t[0] for t in tasks],
        fontsize=7,
    )
    ax.invert_yaxis()
    ax.set_xlabel("Time (s)")
    ax.set_title("Q3 Transport and Relay Schedule Gantt Chart")
    ax.grid(True, axis="x", alpha=0.25)
    save(fig, out / "Fig_Q3_joint_gantt.png")


def q4_gaps(results: Path, out: Path):
    rows = read_csv(results / "q4" / "Q4_resource_summary.csv")
    resources = []
    for r in rows:
        if r["资源"] not in resources:
            resources.append(r["资源"])
    gap2 = [
        int(next(r["缺口"] for r in rows if r["资源"] == res and int(r["K"]) == 2))
        for res in resources
    ]
    gap3 = [
        int(next(r["缺口"] for r in rows if r["资源"] == res and int(r["K"]) == 3))
        for res in resources
    ]
    x = np.arange(len(resources))
    width = 0.38
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(
        x - width / 2,
        gap2,
        width,
        label="K=2",
    )
    ax.bar(
        x + width / 2,
        gap3,
        width,
        label="K=3",
    )
    ax.set_xticks(
        x,
        labels=resources,
        rotation=35,
        ha="right",
    )
    ax.set_ylabel("Shortage units")
    ax.set_title("Q4 Independent-Group Resource Shortages")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.25)
    save(fig, out / "Fig_Q4_resource_gaps.png")


def main():
    parser = argparse.ArgumentParser(
        description="Generate paper-ready figures from result CSVs"
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "results",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "figures",
    )
    parser.add_argument("root", nargs="?", type=Path, default=DEFAULT_DATA_ROOT)
    args = parser.parse_args()
    source_nodes, *_ = load_inputs(args.root)
    nodes = {key: (node.lon, node.lat) for key, node in source_nodes.items()}
    args.out.mkdir(parents=True, exist_ok=True)
    q1_sensitivity(args.results, args.out)
    q2_frontier(args.results, args.out)
    q3_relay_map(args.results, args.out, nodes)
    q3_gantt(args.results, args.out)
    q4_gaps(args.results, args.out)
    print("Figures written to", args.out)


if __name__ == "__main__":
    main()
