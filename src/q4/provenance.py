"""Bind independent partition sizing to the exact finalized Q3 generation."""

from collections import Counter
import hashlib
from src.core.io import read_csv

Q3_SOURCE_FILES = (
    "Q3_transport_trips.csv",
    "Q3_box_delivery.csv",
    "Q3_relay_sorties.csv",
    "Q3_communication.csv",
    "Q3_resource_check.csv",
    "input_manifest.json",
)


def q3_fingerprints(directory):
    return {
        name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
        for name in Q3_SOURCE_FILES
    }


def check_task_relations(transport, relays, communication, deliveries):
    trip_ids = [r["架次编号"] for r in transport]
    relay_ids = [r["中继架次编号"] for r in relays]
    if len(set(trip_ids)) != len(trip_ids) or len(set(relay_ids)) != len(relay_ids):
        raise ValueError("Q4 received duplicate Q3 task IDs")
    if Counter(r["运输架次编号"] for r in communication) != Counter(trip_ids):
        raise ValueError("Q4 communication relations miss or duplicate Q3 trips")
    for row in communication:
        if row["保障方式"] == "中继":
            if row["中继架次编号"] not in relay_ids:
                raise ValueError("Q4 received unknown Q3 relay relationship")
        elif row["保障方式"] != "直连" or row["中继架次编号"]:
            raise ValueError("Q4 received invalid communication mode")
    cargo = Counter(b for row in transport for b in row["货箱编号列表"].split(","))
    if cargo != Counter(r["货箱编号"] for r in deliveries) or any(
        n != 1 for n in cargo.values()
    ):
        raise ValueError("Q4 cargo relations do not match Q3 transport")
    assigned = {
        b: r["架次编号"] for r in transport for b in r["货箱编号列表"].split(",")
    }
    if any(assigned[r["货箱编号"]] != r["架次编号"] for r in deliveries):
        raise ValueError("Q4 cargo/trip inheritance mismatch")


def read_q3_relations(directory):
    return tuple(
        read_csv(directory / name)
        for name in (
            "Q3_transport_trips.csv",
            "Q3_relay_sorties.csv",
            "Q3_communication.csv",
            "Q3_box_delivery.csv",
        )
    )
