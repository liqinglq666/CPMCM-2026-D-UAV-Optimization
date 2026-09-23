# Audit baseline

Upstream commit: `e668347f8c4fdfa60884ddb2154e85f1281c0fd4`.
All 51 tracked files were inventoried, including 20 Python files, model notes,
paper drafts, scripts, tests and CSV outputs. No notebook, CI configuration,
packaging configuration or Excel exporter existed. Official inputs were read
from the supplied D-problem ZIP; originals were not modified.

| Evidence | Before refactor |
|---|---|
| Q1 actual run | 18 trips; 59.13042326715278 kWh; 32776.015748915874 s |
| Q2 actual run | 22 trips; 79.80184619511458 kWh; 11033.023069572366 s; 327498.248877 weighted tardiness |
| Q3 actual run | FAIL: undefined `n` in communication sampling loop |
| Q3 tracked historical CSV | 24 transport trips; 6 relay sorties; 80.8447033281 + 5.9665577761 kWh; joint makespan 13224.358681 s |
| Q4 actual run on historical Q3 CSV | 4 atoms; shortages K=2: 4, K=3: 7 |
| Unit tests | 7 passed, despite broken Q3 CLI |
| Existing result validator | PASS, despite broken resource CSV and without recomputing physics/links |

Historical CSVs, including the malformed Q2 resource-check file, are preserved
verbatim in content under `archive/baseline-e668347/results/` (text fetch may add
an end-of-file newline). They are evidence, not current outputs.

## Before architecture and risk map

- Q1: its own workbook loading, model types, DEM masking, energy and time formulas.
- Q2: second implementation of the same models/loading/formulas; heuristic
  construction followed by merge and complete rescheduling.
- Q3 CLI: executes at import; third physical engine; hardcoded official inputs,
  cached rounded radio coordinates, hand-entered target times and candidate
  altitudes; unused `src/q3/baseline_plan.py` duplicated selected decisions.
- Q4: fixed-Q3 partition enumeration; repeated inventory and charging constants.
- Validation: trusted CSV energy/SOC/deadlines, missed Q2 resources and Q3 link replay.
- Figures: another copy of node coordinates and a hardcoded selected trip count.
- `results/q2/Q2_resource_check.csv`: UAV records had one extra field.
- Default Q2 command generated only 22–24 points, although README claimed 17–24.

Task-to-data mapping: Appendix 2 + transport workbook + nodes + DEM govern all
flight calculations; cargo workbook governs masses/volumes/deadlines; Appendix 3
+ radio workbook + DEM govern link states; relay workbook governs relay energy,
turnaround and inventory; Q4 inherits fixed Q3 missions and communication links.
Wind is not specified by the official model and is not introduced into its results.
