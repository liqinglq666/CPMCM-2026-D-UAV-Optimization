"""Content fingerprints bind generated results to the official input versions."""

import hashlib
import json
from .inputs import find_file
from .io import write_json

INPUT_FILES = (
    ("调度中心与服务区", ".xlsx"),
    ("运输无人机数据", ".xlsx"),
    ("物资需求与配送时限", ".xlsx"),
    ("中继无人机数据", ".xlsx"),
    ("通信链路参数", ".xlsx"),
    ("30米DEM", ".tif"),
)


def input_fingerprints(root):
    return {
        name + suffix: hashlib.sha256(
            find_file(root, name, suffix).read_bytes()
        ).hexdigest()
        for name, suffix in INPUT_FILES
    }


def save_provenance(root, out):
    write_json(out / "input_manifest.json", input_fingerprints(root))


def check_provenance(root, results):
    expected = input_fingerprints(root)
    for question in ("q1", "q2", "q3", "q4"):
        actual = json.loads(
            (results / question / "input_manifest.json").read_text(encoding="utf-8")
        )
        if actual != expected:
            raise ValueError(
                f"Stale {question.upper()} results: official input hashes differ"
            )
    return expected
