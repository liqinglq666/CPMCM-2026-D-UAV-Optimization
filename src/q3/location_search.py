"""Height-aware relay refinement with a coarse screen and full acceptance."""

from pyproj import Geod

from .search import build_plan, evaluate


def refine_locations(plan, result, preparer, drones, batteries, params):
    best_plan, best = plan, result
    geod, trace = Geod(ellps="WGS84"), []
    for round_index in range(params.get("q3_location_rounds", 0)):
        for index in reversed(range(len(best_plan["relays"]))):
            relay = best_plan["relays"][index]
            jobs = [j for j in best_plan["jobs"] if j.get("relay") == relay["id"]]
            candidates = {}
            for radius in params["q3_location_radii_m"]:
                for azimuth in range(0, 360, 45):
                    lon, lat, _az = geod.fwd(relay["lon"], relay["lat"], azimuth, radius)
                    for fraction in params["q3_hover_height_fractions"]:
                        agl = fraction * preparer.relay_inputs.spec.max_hover_agl_m
                        proposal = dict(relay, lon=lon, lat=lat, agl_m=agl,
                                        candidate="completion-height-grid")
                        try:
                            point, travel = preparer.relay(proposal)
                            if not all(all(preparer.link(
                                p, point, preparer.comm.parameters.access_budget_db,
                            )[0] for _time, p in preparer.outages(job)[1][::15]) for job in jobs):
                                continue
                        except ValueError:
                            continue
                        candidates[lon, lat, agl] = (travel["lead"] + travel["inbound"], proposal)
            accepted = 0
            for _cost, relay_proposal in sorted(candidates.values(), key=lambda pair: pair[0])[:30]:
                if not all(preparer.covers(job, relay_proposal) for job in jobs):
                    continue
                proposal = build_plan(best_plan)
                proposal["relays"][index] = relay_proposal
                try:
                    checked = evaluate(proposal, preparer, drones, batteries)
                except (ValueError, RuntimeError):
                    continue
                if checked["objective"][2:5] < best["objective"][2:5]:
                    best_plan, best = proposal, checked
                    accepted += 1
            trace.append(dict(round=round_index, relay=relay["id"],
                              coarse_candidates=len(candidates), accepted=accepted,
                              objective=best["objective"]))
    return best_plan, best, dict(
        trace=trace, screen="Every 15th union-grid outage point; proposal only",
        acceptance_steps_s=list(preparer.audit_steps), global_continuous_bound=False,
    )
