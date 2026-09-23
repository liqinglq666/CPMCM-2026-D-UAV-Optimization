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
