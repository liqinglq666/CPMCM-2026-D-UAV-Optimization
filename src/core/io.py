"""CSV/JSON boundaries: explicit UTF-8, rectangular tables and finite JSON."""

import csv
import json
from pathlib import Path


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(
            reader.fieldnames
        ):
            raise ValueError(f"Missing/duplicate CSV headers: {path}")
        rows = list(reader)
        if any(
            None in row or any(value is None for value in row.values()) for row in rows
        ):
            raise ValueError(f"Nonrectangular CSV: {path}")
        if not rows:
            raise ValueError(f"Empty result CSV: {path}")
        return rows


def write_csv(path, rows, fields=None):
    rows = list(rows)
    if fields is None:
        if not rows:
            raise ValueError(f"Cannot infer CSV fields for empty rows: {path}")
        fields = list(rows[0])
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
