# 本程序及代码是在人工智能工具辅助下完成的。
# AI assistance declaration (this entry point and its imported src modules)
# Tool: ChatGPT/Codex.
# Model: GPT-6 Astra (gpt-6-astra).
# Developer: OpenAI.
# Public release date: 2026-09-03.
# Release source: https://developers.openai.com/api/docs/changelog
# Use: code drafting/review, data preparation, scientific plotting, paper editing,
# and consistency checks. Model identity was confirmed by the participants.
# This submission-stage change adds disclosure only; algorithm code is unchanged.
# Original method attribution and seed provenance remain in src and config.

"""Independently enclose continuous coverage from official inputs/exported rows."""

import argparse
import hashlib
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.config import DEFAULT_DATA_ROOT, PROJECT_ROOT
from src.core.communication import Communication
from src.core.continuous_radio import certify_profiles
from src.core.constraints import validate_transport, validate_relays
from src.core.inputs import load_inputs, load_relay_inputs, load_communication_inputs
from src.core.io import read_csv, write_json
from src.core.physics import Physics


def certify(root, directory):
    nodes, types, drones, batteries, boxes, dem = load_inputs(root)
    physics = Physics(nodes, types, dem)
    comm = Communication(physics, load_communication_inputs(root))
    profiles, _ = validate_transport(read_csv(directory / "Q3_transport_trips.csv"),
                                    read_csv(directory / "Q3_box_delivery.csv"),
                                    "q3", physics, boxes, drones, batteries)
    relays = validate_relays(read_csv(directory / "Q3_relay_sorties.csv"), physics,
                             load_relay_inputs(root), comm)
    result = certify_profiles(profiles, read_csv(directory / "Q3_communication.csv"),
                              relays, physics, comm)
    result["source_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sorted(directory.glob("Q3_*.csv"))}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--q3-dir", type=Path, default=PROJECT_ROOT / "results/q3")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "results/continuous_communication.json")
    args = parser.parse_args()
    args.out.unlink(missing_ok=True)
    result = certify(args.data, args.q3_dir)
    write_json(args.out, result)
    if result["status"] != "PASS":
        raise SystemExit("Continuous coverage not certified; inspect witnesses/unresolved intervals")


if __name__ == "__main__":
    main()
