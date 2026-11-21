#!/usr/bin/env python3
"""Verify the exact frozen contest submission bytes without rebuilding the paper.

This check is independent of the historical Word/figure packages that are
archived on backup/pre-slim-20261121 rather than shipped on main.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import sys


REPO = Path(__file__).resolve().parents[1]
SUBMISSION = REPO / "submission"

# From submission/CHECKSUMS.txt, checked before the repository was slimmed.
FROZEN_FILES = {
    "D26105580028.pdf": (
        6_022_191,
        "f298eae1213cb1ca2d201154bf3adcd9",
        "28cb0f605f34e2c72fd883d3d1cd3e32e69321d81daf45164b87699e7b74cc3e",
    ),
    "结果提交模板.xlsx": (
        26_216,
        "bf9a96ad1ccce51cd2bfa5c8d056f75c",
        "e5f3707a42dd86124aa9afdb7453a607bcb14b7419ddf0668c5e75bc31081b22",
    ),
    "D26105580028.rar": (
        6_862_274,
        "92d602919d0c6ec744a133dac1918fb4",
        "5e8a09d602a2a882b013fc49265fa330d365d190391422f8c8c7535b09f0f143",
    ),
}


def check_file(name: str, size: int, md5: str, sha256: str) -> bool:
    path = SUBMISSION / name
    # Actions on Windows may use cp1252 when Python prints to stdout.
    display_name = name.encode("ascii", "backslashreplace").decode("ascii")
    if not path.is_file():
        print(f"FAIL missing: submission/{display_name}")
        return False
    if path.stat().st_size != size:
        print(f"FAIL size: {display_name}")
        return False
    h_md5 = hashlib.md5()
    h_sha256 = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h_md5.update(chunk)
            h_sha256.update(chunk)
    if h_md5.hexdigest() != md5 or h_sha256.hexdigest() != sha256:
        print(f"FAIL hash: {display_name}")
        return False
    print(f"PASS exact bytes: {display_name}")
    return True


def main() -> int:
    checks = [
        check_file(name, size, md5, sha256)
        for name, (size, md5, sha256) in FROZEN_FILES.items()
    ]
    if all(checks):
        print("PASS: all three frozen submission artifacts match the recorded bytes")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
