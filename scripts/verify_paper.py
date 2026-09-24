"""Check result-to-manuscript/workbook consistency without editing spreadsheets.

AI assistance: ChatGPT/Codex, OpenAI, 2026-09-23; exact model/release unavailable.
"""

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

from openpyxl import load_workbook
from paper_data import load_analysis
from pdf_quality import audit_pdf
from PIL import Image
from pypdf import PdfReader

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
    candidates = records("results/q2/Q2_tradeoff_frontier.csv")
    q4_resources = records("results/q4/Q4_resource_summary.csv")
    expected_numbers.update(
        CandidateCount=str(len(candidates)),
        CandidateMaxTrips=str(max(int(r["trips"]) for r in candidates)),
        CandidateMinTrips=str(min(int(r["trips"]) for r in candidates)),
        GapTwo=str(sum(int(r["缺口"]) for r in q4_resources if r["K"] == "2")),
        GapThree=str(sum(int(r["缺口"]) for r in q4_resources if r["K"] == "3")),
    )
    replay = json.loads((ROOT / "results/communication_replay.json").read_text())
    assert replay["source_sha256"] == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((ROOT / "results/q3").glob("Q3_*.csv"))
    }
    quarter = next(r for r in replay["sampling"] if r["step_s"] == 0.25)
    expected_numbers.update(
        StatesQuarter=str(quarter["checked_states"]),
        MarginQuarter=f"{quarter['minimum_margin_db']:.3f}",
        ViolationsQuarter=str(quarter["violations"]),
    )
    for diagnostic in analysis["sampling_validation"]:
        extra = next(
            r for r in replay["sampling"] if r["step_s"] == diagnostic["step_s"]
        )
        for key in ("checked_states", "violations", "minimum_margin_db"):
            assert extra[key] == diagnostic[key]
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
    manifest = {r["figure_id"]: r for r in records("paper/figure_manifest.csv")}
    assert set(manifest) == {c["figure_id"] for c in figures}
    for contract in figures:
        declared = json.loads(manifest[contract["figure_id"]]["data_sha256"])
        assert set(declared) == set(contract["source_data"])
        assert all(
            hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
            for name, digest in declared.items()
        )
        assert (ROOT / contract["script"]).is_file()
        assert all((ROOT / source).is_file() for source in contract["source_data"])
        stem = ROOT / "outputs/figures" / contract["figure_id"]
        assert len(PdfReader(stem.with_suffix(".pdf")).pages) == 1
        with Image.open(stem.with_suffix(".png")) as im:
            assert min(im.info["dpi"]) >= 299.9
            im.verify()
        svg = stem.with_suffix(".svg").read_text(encoding="utf-8")
        assert "<svg" in svg
        # A native DEM is raster data; only map backgrounds may embed images.
        if contract["figure_id"] not in {"fig02_task_map", "fig08_communication_map"}:
            assert "<image" not in svg
        qa = json.loads(
            (ROOT / "outputs/figure-qa" / (contract["figure_id"] + ".json")).read_text()
        )
        assert math.isclose(qa["width_mm"], 160, abs_tol=1e-7)
        assert qa["minimum_text_pt"] >= 7.5 and not qa["canvas_clipped_text"]

    for filename, summary in zip(
        ["communication_states.csv", "communication_states_05s.csv"],
        analysis["sampling_validation"],
    ):
        states = records("paper/data/" + filename)
        assert len(states) == summary["checked_states"]
        critical = min(states, key=lambda r: float(r["available_margin_db"]))
        assert float(critical["available_margin_db"]) == summary["minimum_margin_db"]
        assert float(critical["time_s"]) == summary["critical_state"]["time_s"]
        assert critical["trip"] == summary["critical_state"]["trip"]
        assert (
            sum(float(r["available_margin_db"]) < 0 for r in states)
            == summary["violations"]
        )
    paper = PdfReader(ROOT / "outputs/paper/main.pdf")
    font_audit = audit_pdf(ROOT / "outputs/paper/main.pdf")
    pages = [p.extract_text() for p in paper.pages]
    assert all(text.strip().endswith(str(i)) for i, text in enumerate(pages, 1))
    text = re.sub(r"\s+", "", "".join(pages))
    assert "??" not in text
    toc_source = (ROOT / "outputs/paper/main.toc").read_text(encoding="utf-8")
    toc_entries = re.findall(
        r"\\contentsline \{(?:sub)?section\}.*?\}\{(\d+)\}\{([^}]+)\}", toc_source
    )
    assert len(toc_entries) > 10, "Missing automatic table of contents"
    for page_number, destination in toc_entries:
        assert destination in paper.named_destinations
        assert paper.get_destination_page_number(
            paper.named_destinations[destination]
        ) + 1 == int(page_number)
    assert "目录" in pages[1]
    toc_pages = range(1, int(toc_entries[0][0]) - 1)

    def annotation_count(page):
        return len(page["/Annots"]) if "/Annots" in page else 0

    toc_links = sum(annotation_count(paper.pages[i]) for i in toc_pages)
    assert toc_links >= len(toc_entries), "TOC links missing"
    compatibility = PdfReader(ROOT / "outputs/paper/main-compatible.pdf")
    assert len(compatibility.pages) == len(paper.pages)
    assert all(
        annotation_count(compatibility.pages[i]) == annotation_count(paper.pages[i])
        for i in toc_pages
    )

    # Inspect the included manuscript, not orphan .tex files left by a reorder.
    main_source = (ROOT / "paper/main.tex").read_text(encoding="utf-8")
    section_paths = re.findall(r"\\input\{(sections/[^}]+)\}", main_source)
    assert len(section_paths) == len(set(section_paths)), "Duplicate section inclusion"
    included = [ROOT / "paper" / (name + ".tex") for name in section_paths]
    assert set(included) == set((ROOT / "paper/sections").glob("*.tex")), (
        "Orphan/missing section"
    )
    sources = [path.read_text(encoding="utf-8") for path in included]
    source = "\n".join(sources)
    section_number = 0
    figure_sections = {}
    for content in sources:
        section_number += len(re.findall(r"\\section\{", content))
        for figure_id in re.findall(r"\\paperfig\{([^}]+)\}", content):
            assert figure_id not in figure_sections, "Duplicate figure inclusion"
            figure_sections[figure_id] = str(section_number)
    assert figure_sections == {c["figure_id"]: c["section"] for c in figures}, (
        "Stale figure section contract"
    )
    assert list(figure_sections) == [c["figure_id"] for c in figures], (
        "Stale figure order"
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
    assert list(dict.fromkeys(citations)) == re.findall(
        r"\\bibitem\{([^}]+)\}", references
    ), "References must follow first citation order"

    result = {
        "status": "PASS",
        "status_scope": "artifact consistency, not a certificate of communication feasibility",
        "refined_communication_passed": analysis["refined_communication_passed"],
        "sampling_violations": [
            r["violations"] for r in analysis["sampling_validation"]
        ],
        "source_result_files": len(analysis["hashes"]),
        "workbook_sheets": len(payload["sheets"]),
        "workbook_cells_compared": cells,
        "preserved_official_sheets": 6,
        "added_transport_detail_sheets": 2,
        "independent_aggregates": expected_numbers,
        "generated_number_macros": len(numbers),
        "used_macros_found_in_pdf": len(used),
        "figures": len(figures),
        "figure_sections": figure_sections,
        "included_sections": section_paths,
        "figure_files": len(figures) * 3,
        "pdf_pages": len(paper.pages),
        "toc_entries_checked": len(toc_entries),
        "toc_links": toc_links,
        "pdf_font_audit": font_audit,
        "reference_entries": len(set(citations)),
        "citation_occurrences": len(citations),
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
