"""Prevent mixing newly solved results with stale paper metrics and figures."""

import hashlib
import json

import pytest

from scripts.paper_data import load_analysis


@pytest.mark.parametrize("mutation", ["changed", "missing", "no_manifest"])
def test_paper_rejects_stale_or_missing_results(tmp_path, mutation):
    source = tmp_path / "results/q3/metrics.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"energy": 1}', encoding="utf-8")
    analysis = {
        "hashes": {"q3/metrics.json": hashlib.sha256(source.read_bytes()).hexdigest()}
    }
    data = tmp_path / "paper/data/analysis.json"
    data.parent.mkdir(parents=True)
    diagnostic = data.parent / "communication_states_05s.csv"
    diagnostic.write_text("time_s,available_margin_db\n1,0.12\n", encoding="utf-8")
    analysis["diagnostic_hashes"] = {
        diagnostic.name: hashlib.sha256(diagnostic.read_bytes()).hexdigest()
    }
    data.write_text(json.dumps(analysis), encoding="utf-8")
    assert load_analysis(tmp_path) == analysis
    if mutation == "changed":
        source.write_text('{"energy": 2}', encoding="utf-8")
    elif mutation == "missing":
        source.unlink()
    else:
        data.write_text('{"hashes": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="[Ss]tale|[Mm]issing"):
        load_analysis(tmp_path)


@pytest.mark.parametrize("mutation", ["changed", "missing", "no_manifest"])
def test_paper_rejects_stale_or_missing_diagnostics(tmp_path, mutation):
    result = tmp_path / "results/metrics.json"
    result.parent.mkdir(parents=True)
    result.write_text("{}")
    data = tmp_path / "paper/data"
    data.mkdir(parents=True)
    diagnostic = data / "communication_states_05s.csv"
    diagnostic.write_text("time_s,available_margin_db\n1,0.12\n")
    analysis = {
        "hashes": {"metrics.json": hashlib.sha256(result.read_bytes()).hexdigest()},
        "diagnostic_hashes": {
            diagnostic.name: hashlib.sha256(diagnostic.read_bytes()).hexdigest()
        },
    }
    manifest = data / "analysis.json"
    manifest.write_text(json.dumps(analysis))
    assert load_analysis(tmp_path) == analysis
    if mutation == "changed":
        diagnostic.write_text("time_s,available_margin_db\n1,12\n")
    elif mutation == "missing":
        diagnostic.unlink()
    else:
        analysis.pop("diagnostic_hashes")
        manifest.write_text(json.dumps(analysis))
    with pytest.raises(ValueError, match="[Ss]tale|[Mm]issing"):
        load_analysis(tmp_path)
