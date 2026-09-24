"""Rules from Appendix 2 and explicit numerical/search choices (SI, kWh)."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data" / "raw"
GRAVITY_MPS2 = 9.80665  # standard gravity, physical constant
JOULES_PER_KWH = 3_600_000.0
SECONDS_PER_HOUR = 3600.0
TERRAIN_CLEARANCE_M = 50.0  # Appendix 2
SERVICE_ALTITUDE_M = 30.0  # Appendix 2
CHARGE_KNEE_SOC = 0.90  # Appendix 2
CHARGE_FAST_FRACTION = 0.65  # Appendix 2
DEM_GRID_TOLERANCE_PIXELS = 1e-9  # conservative boundary snapping, < 1e-7 m
RESERVE_SCENARIOS = (0.10, 0.15, 0.20, 0.25, 0.30)
COMMUNICATION_STEP_S = 1.0  # discrete verification, not continuous proof
RELAY_GUARD_S = 5.0  # explicit conservative scheduling assumption
FEASIBILITY_TOL = 1e-8  # numerical tolerance only
MAX_ROUTE_SERVICES = 5  # factorial enumeration bound, heuristic
BALANCED_TRIPS = 21  # reproducible Pareto target, not a physical constraint
FRONTIER_MIN_TRIPS = 17
TARDINESS_SCALE = 200_000.0  # Q2 heuristic normalization
MAKESPAN_SCALE = 10_000.0
ENERGY_SCALE = 100.0
Q3_PLAN = PROJECT_ROOT / "config" / "q3_plan.json"
