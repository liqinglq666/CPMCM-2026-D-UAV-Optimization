"""Finite spatial set cover for frozen Q3 routes, independent of relay timing.

This does NOT prove a lower bound over continuous hover space, schedules or
routes. Each fixed transport route must be covered by one selected location;
allowing handovers within a route is a larger problem. Full union-grid points
are used, not just service endpoints. The generated grid is a search parameter.
"""

import argparse
from itertools import product
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from src.config import DEFAULT_DATA_ROOT, PROJECT_ROOT
from src.core.communication import Communication
from src.core.constraints import validate_transport
from src.core.inputs import load_inputs, load_communication_inputs, load_relay_inputs
from src.core.io import read_csv, write_json
from src.core.physics import Physics
from src.core.sampling import sample_audit_states


def diagnose(root, directory, grid=20):
    nodes, types, drones, batteries, boxes, dem = load_inputs(root)
    physics = Physics(nodes, types, dem)
    radio = load_communication_inputs(root)
    communication = Communication(physics, radio)
    relay = load_relay_inputs(root)
    profiles, _ = validate_transport(
        read_csv(directory / "Q3_transport_trips.csv"),
        read_csv(directory / "Q3_box_delivery.csv"), "q3", physics, boxes, drones, batteries,
    )
    direct_cache = {}
    outages = {}
    for tid, (profile, _start) in profiles.items():
        failed = set()
        for _time, point in sample_audit_states(profile, physics):
            if point not in direct_cache:
                direct_cache[point] = communication.link(
                    point, communication.gateway, radio.direct_budget_db,
                )[0]
            if not direct_cache[point]:
                failed.add(point)
        if failed:
            outages[tid] = sorted(failed, key=lambda p: p[2])
    flown = [(float(r["悬停经度"]), float(r["悬停纬度"]), float(r["悬停海拔_m"]))
             for r in read_csv(directory / "Q3_relay_sorties.csv")]
    points = list(flown)
    for lon, lat in product(
        np.linspace(min(n.lon for n in nodes.values()), max(n.lon for n in nodes.values()), grid),
        np.linspace(min(n.lat for n in nodes.values()), max(n.lat for n in nodes.values()), grid),
    ):
        points.append((float(lon), float(lat), physics.terrain.elevation(lon, lat)
                       + relay.spec.max_hover_agl_m))
    valid, coverage = [], []
    for point in sorted(set(points)):
        if not communication.link(point, communication.gateway, radio.backhaul_budget_db)[0]:
            continue
        mask = [all(communication.link(p, point, radio.access_budget_db)[0] for p in states)
                for states in outages.values()]
        if any(mask):
            valid.append(point)
            coverage.append(mask)
    if not outages:
        lower, optimum, chosen, status = 0, 0, [], "no relay required on audit grids"
    else:
        result = milp(
            np.ones(len(valid)), integrality=np.ones(len(valid)), bounds=Bounds(0, 1),
            constraints=LinearConstraint(np.array(coverage, dtype=float).T, 1, np.inf),
            options=dict(time_limit=60, mip_rel_gap=0),
        )
        lower = getattr(result, "mip_dual_bound", None)
        optimum = int(round(result.fun)) if result.status == 0 else None
        chosen = [valid[i] for i, value in enumerate(result.x) if value > 0.5] \
            if result.x is not None else []
        status = result.message
    return dict(
        candidate_count=len(valid), grid_rows=grid, grid_columns=grid,
        fixed_routes_requiring_relay=list(outages), candidate_points=valid,
        route_coverage=coverage, finite_candidate_minimum=optimum,
        finite_candidate_lower_bound=lower, selected_points=chosen, status=status,
        sampling_steps_s=[1.0, 0.5],
        proof_scope="finite points; fixed transport routes; one point per whole route; spatial only",
        continuous_space_lower_bound=False, joint_schedule_certificate=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--q3-dir", type=Path, default=PROJECT_ROOT / "results/q3")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "results/relay_cover.json")
    args = parser.parse_args()
    result = diagnose(args.root, args.q3_dir)
    write_json(args.out, result)
    print({key: result[key] for key in ("candidate_count", "finite_candidate_minimum", "proof_scope")})


if __name__ == "__main__":
    main()
