"""Check result-to-manuscript/workbook consistency without editing spreadsheets.

AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
"""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

from openpyxl import load_workbook
from PIL import Image
from pypdf import PdfReader

from paper_data import load_analysis
from pdf_quality import audit_pdf

ROOT = Path(__file__).resolve().parents[1]


def verify(workbook: Path, template: Path, rebuild_figures: bool = False):
    if sys.flags.optimize:
        raise RuntimeError(
            "Run verification without Python -O; all assertions must execute"
        )
    analysis = load_analysis(ROOT)
    numbers = json.loads(
        (ROOT / "paper/data/paper_numbers.json").read_text(encoding="utf-8")
    )
    payload = json.loads(
        (ROOT / "paper/data/workbook_payload.json").read_text(encoding="utf-8")
    )
    book = load_workbook(workbook, data_only=False, read_only=False)
    original = load_workbook(template, read_only=True)
    cells = 0
    for sheet in payload["sheets"]:
        actual = book[sheet["name"]]
        if not sheet["add"]:
            old_header = [c.value for c in next(original[sheet["name"]].iter_rows())]
            assert [c.value for c in next(actual.iter_rows())] == old_header
        assert actual.max_row >= len(sheet["values"]) + 1
        # The untouched template can retain formatted empty rows below the data.
        assert all(
            all(cell.value is None for cell in row)
            for row in actual.iter_rows(min_row=len(sheet["values"]) + 2)
        )
        for row_index, row in enumerate(sheet["values"], 2):
            for column_index, expected in enumerate(row, 1):
                value = actual.cell(row_index, column_index).value
                if isinstance(expected, (int, float)):
                    assert math.isfinite(expected)
                    assert isinstance(value, (int, float))
                    assert math.isclose(value, expected, rel_tol=1e-12, abs_tol=1e-10)
                else:
                    assert (value or None) == (expected or None), (
                        sheet["name"],
                        row_index,
                        column_index,
                    )
                cells += 1
    assert book.sheetnames == [s["name"] for s in payload["sheets"]]
    book.close()
    original.close()

    def records(path):
        with (ROOT / path).open(encoding="utf-8-sig", newline="") as stream:
            return list(csv.DictReader(stream))

    q1 = records("results/q1/Q1_batch_solution.csv")
    q2 = records("results/q2/Q2_transport_trips_balanced.csv")
    q3 = records("results/q3/Q3_transport_trips.csv")
    relays = records("results/q3/Q3_relay_sorties.csv")
    # Independent aggregation of the row-level results, not a metrics JSON copy.
    expected_numbers = {
        "QOneTrips": str(len(q1)),
        "QTwoTrips": str(len(q2)),
        "QThreeTrips": str(len(q3)),
        "RelayTrips": str(len(relays)),
        "QOneEnergy": f"{sum(float(r['架次能耗（kWh）']) for r in q1):.3f}",
        "QOneTime": f"{sum(float(r['往返时间（s）']) for r in q1):.3f}",
        "QTwoEnergy": f"{sum(float(r['架次能耗（kWh）']) for r in q2):.3f}",
        "QTwoTime": f"{max(float(r['返回O01时刻（s）']) for r in q2):.3f}",
        "JointEnergy": f"{sum(float(r['架次能耗_kWh']) for r in q3 + relays):.3f}",
        "JointTime": f"{max(float(r['返回O01时刻_s']) for r in q3 + relays):.3f}",
        "MinSoc": f"{min(float(r['返航SOC_pct']) for r in q3):.2f}",
    }
    assert all(numbers[key] == value for key, value in expected_numbers.items())
    for rows in (q1, q2, q3):
        cargo = [item for r in rows for item in r["货箱编号列表"].split(",")]
        assert len(cargo) == len(set(cargo)) == len(analysis["boxes"])

    figures = json.loads(
        (ROOT / "paper/figure_contracts.json").read_text(encoding="utf-8")
    )
    reproduced = None
    if rebuild_figures:
        before = {
            c["figure_id"]: hashlib.sha256(
                (ROOT / "outputs/figures" / (c["figure_id"] + ".png")).read_bytes()
            ).hexdigest()
            for c in figures
        }
        for contract in figures:
            subprocess.run(
                [sys.executable, str(ROOT / contract["script"])], cwd=ROOT, check=True
            )
        after = {
            c["figure_id"]: hashlib.sha256(
                (ROOT / "outputs/figures" / (c["figure_id"] + ".png")).read_bytes()
            ).hexdigest()
            for c in figures
        }
        assert before == after, "Identical input produced different figure pixels"
        reproduced = after
    for contract in figures:
        assert (ROOT / contract["script"]).is_file()
        assert all((ROOT / source).is_file() for source in contract["source_data"])
        stem = ROOT / "outputs/figures" / contract["figure_id"]
        assert len(PdfReader(stem.with_suffix(".pdf")).pages) == 1
        with Image.open(stem.with_suffix(".png")) as im:
            assert min(im.info["dpi"]) >= 299.9
            im.verify()
        svg = stem.with_suffix(".svg").read_text(encoding="utf-8")
        assert "<svg" in svg and "<image" not in svg  # no raster screenshots

    paper = PdfReader(ROOT / "outputs/paper/main.pdf")
    font_audit = audit_pdf(ROOT / "outputs/paper/main.pdf")
    pages = [p.extract_text() for p in paper.pages]
    assert all(text.strip().endswith(str(i)) for i, text in enumerate(pages, 1))
    text = re.sub(r"\s+", "", "".join(pages))
    assert "??" not in text
    source = "\n".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "paper/sections").glob("*.tex")
    )
    used = set(re.findall(r"\\(" + "|".join(numbers) + r")\b", source))
    assert all(numbers[key] in text for key in used), [
        key for key in used if numbers[key] not in text
    ]
    macro_source = (ROOT / "paper/tables/numbers.tex").read_text(encoding="utf-8")
    assert all(
        (chr(92) + "newcommand{" + chr(92) + key + "}{" + value + "}") in macro_source
        for key, value in numbers.items()
    )
    log = (ROOT / "outputs/paper/main.log").read_text(encoding="utf-8")
    assert not re.search(r"Overfull|undefined|Missing character", log)
    citations = re.findall(r"\\cite\{([^}]+)\}", source)
    references = (ROOT / "paper/references.tex").read_text(encoding="utf-8")
    assert set(citations) == set(re.findall(r"\\bibitem\{([^}]+)\}", references))

    result = {
        "status": "PASS",
        "source_result_files": len(analysis["hashes"]),
        "workbook_sheets": len(payload["sheets"]),
        "workbook_cells_compared": cells,
        "preserved_official_sheets": 6,
        "added_transport_detail_sheets": 2,
        "independent_aggregates": expected_numbers,
        "generated_number_macros": len(numbers),
        "used_macros_found_in_pdf": len(used),
        "figures": len(figures),
        "figure_files": len(figures) * 3,
        "pdf_pages": len(paper.pages),
        "pdf_font_audit": font_audit,
        "reference_entries": len(citations),
        "reproduced_png_sha256": reproduced,
        "pdf_sha256": hashlib.sha256(
            (ROOT / "outputs/paper/main.pdf").read_bytes()
        ).hexdigest(),
        "workbook_sha256": hashlib.sha256(workbook.read_bytes()).hexdigest(),
        "interpretation": "Deterministic official model; sampled communication is not a continuous certificate.",
    }
    out = ROOT / "paper/reports"
    out.mkdir(exist_ok=True)
    (out / "consistency.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--rebuild-figures", action="store_true")
    args = parser.parse_args()
    verify(args.workbook, args.template, args.rebuild_figures)
