"""Finite-catalogue column generation followed by an integer interval master.

Pricing scans every allowed grid start of every enumerated sortie. Resource
rows count occupied half-open intervals; battery intervals include full recharge.
The LP certificate applies only to this finite route/time catalogue. Branching
uses generated columns only: its MIP dual bound is NOT a full-catalogue bound.
"""

from collections import Counter
import logging
import math
from time import perf_counter

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, linprog, milp
from scipy.sparse import coo_matrix, eye, hstack


class IntervalMaster:
    def __init__(self, columns, classes, drones, batteries, horizon, step, trip_cap,
                 windows=None, trip_penalty=100.0):
        if horizon <= 0 or step <= 0 or trip_cap < 1:
            raise ValueError("Invalid interval-master horizon, step or trip cap")
        if any(r.available != 0 for r in [*drones, *batteries]):
            raise ValueError("Aggregate master requires initially available resources")
        self.columns, self.classes = columns, classes
        self.horizon, self.step, self.trip_cap = horizon, step, trip_cap
        self.slots = math.ceil(horizon / step)
        self.codes = sorted({c.type for c in columns})
        self.type_count = len(self.codes)
        self.class_count = len(classes)
        self.resource_rows = 2 * self.type_count * self.slots + 1
        self.demand = np.array([len(c) for c in classes])
        inventories = [Counter(r.type for r in specs) for specs in (drones, batteries)]
        self.capacities = np.r_[
            [inventory[code] for inventory in inventories
             for code in self.codes for _ in range(self.slots)], trip_cap,
        ]
        self.type_index = np.array([self.codes.index(c.type) for c in columns])
        self.duration_slots = np.array([math.ceil(c.duration / step) for c in columns])
        self.battery_slots = np.array([
            math.ceil((c.duration + c.charge) / step) for c in columns
        ])
        self.latest = np.array([
            math.floor(min(c.latest, horizon - c.duration) / step) for c in columns
        ])
        if not math.isfinite(trip_penalty) or trip_penalty < 0:
            raise ValueError("Invalid trip penalty")
        self.trip_penalty = trip_penalty
        self.cost = np.array([trip_penalty + c.energy for c in columns])
        self.counts = coo_matrix((
            [number for c in columns for _, number in c.counts],
            ([i for c in columns for i, _ in c.counts],
             [j for j, c in enumerate(columns) for _ in c.counts]),
        ), shape=(self.class_count, len(columns))).tocsc()
        self.allowed = None
        if windows is not None:
            self.allowed = np.zeros((len(columns), self.slots), dtype=bool)
            for index, intervals in enumerate(windows):
                for begin, end in intervals:
                    first = max(0, math.ceil(begin / step))
                    last = min(self.slots - 1, math.floor(end / step))
                    if first <= last:
                        self.allowed[index, first:last + 1] = True
        self.active, self.active_set = [], set()
        self.rows, self.indices, self.values = [], [], []

    def add(self, column, slot):
        if (column, slot) in self.active_set:
            return
        if not 0 <= slot <= self.latest[column] or (
            self.allowed is not None and not self.allowed[column, slot]
        ):
            raise ValueError("Column start outside allowed time window")
        index = len(self.active)
        self.active.append((column, slot))
        self.active_set.add((column, slot))
        for group, number in self.columns[column].counts:
            self.rows.append(group)
            self.indices.append(index)
            self.values.append(number)
        for resource, length in (
            (self.type_index[column], self.duration_slots[column]),
            (self.type_index[column] + self.type_count, self.battery_slots[column]),
        ):
            stop = min(self.slots, slot + length)
            self.rows.extend(self.class_count + resource * self.slots + t
                             for t in range(slot, stop))
            self.indices.extend([index] * (stop - slot))
            self.values.extend([1] * (stop - slot))
        self.rows.append(self.class_count + self.resource_rows - 1)
        self.indices.append(index)
        self.values.append(1)

    def matrix(self):
        return coo_matrix((self.values, (self.rows, self.indices)), shape=(
            self.class_count + self.resource_rows, len(self.active),
        )).tocsc()

    def pricing(self, equality_duals, resource_duals, batch_size):
        """Exact min reduced cost over the finite catalogue; bounded new batch."""
        base = self.cost - self.counts.T @ equality_duals - resource_duals[-1]
        duals = resource_duals[:-1].reshape(2 * self.type_count, self.slots)
        prefix = np.c_[np.zeros(2 * self.type_count), duals.cumsum(axis=1)]
        minimum, offers = math.inf, []
        for slot in range(self.slots):
            valid = self.latest >= slot
            if self.allowed is not None:
                valid &= self.allowed[:, slot]
            indices = np.flatnonzero(valid)
            typ = self.type_index[indices]
            costs = base[indices] - (
                prefix[typ, np.minimum(self.slots, slot + self.duration_slots[indices])]
                - prefix[typ, slot]
            ) - (
                prefix[typ + self.type_count,
                       np.minimum(self.slots, slot + self.battery_slots[indices])]
                - prefix[typ + self.type_count, slot]
            )
            minimum = min(minimum, np.min(costs, initial=math.inf))
            negative = np.flatnonzero(costs < -1e-7)
            # Truncation affects which improving columns are added, never the
            # minimum used for the finite-catalogue dual certificate.
            if len(negative) > 100:
                negative = negative[np.argsort(costs[negative], kind="stable")[:100]]
            offers.extend((float(costs[j]), int(indices[j]), slot) for j in negative
                          if (int(indices[j]), slot) not in self.active_set)
        offers.sort()
        return float(minimum), offers[:batch_size]

    def solve(self, iterations=45, batch_size=1500, time_limit=120, mip_gap=0.005,
              integer_reduced_cost_limit=None):
        started = perf_counter()
        trace, certificate = [], None
        nc, nr = self.class_count, self.resource_rows
        for iteration in range(iterations):
            matrix = self.matrix()
            # Artificial uncovered cargo starts phase I; it may never occur in
            # an accepted integer plan or in a claimed feasible LP optimum.
            objective = np.r_[[self.cost[c] for c, _ in self.active], np.repeat(1e4, nc)]
            result = linprog(
                objective,
                A_eq=hstack([matrix[:nc], eye(nc, format="csc")], format="csc"),
                b_eq=self.demand,
                A_ub=hstack([matrix[nc:], coo_matrix((nr, nc))], format="csc"),
                b_ub=self.capacities, bounds=(0, None), method="highs",
            )
            if not result.success:
                raise RuntimeError(result.message)
            minimum, offers = self.pricing(
                result.eqlin.marginals, result.ineqlin.marginals, batch_size,
            )
            shortage = float(sum(result.x[len(self.active):]))
            # For every allowed column c, rc(c)>=minimum and sum x<=trip_cap.
            # Adding min(0,minimum)*trip_cap is therefore a valid correction
            # even if pricing stops early. This never uses a restricted MIP bound.
            certificate = float(result.fun + min(0, minimum) * self.trip_cap)
            trace.append(dict(iteration=iteration, active_columns=len(self.active),
                              lp_objective=float(result.fun), artificial_cargo=shortage,
                              minimum_reduced_cost=minimum,
                              finite_catalogue_lower_bound=certificate))
            logging.getLogger(__name__).info(
                "Column LP %d: %d variables, shortage %.3g, minimum reduced cost %.3g",
                iteration, len(self.active), shortage, minimum,
            )
            if not offers:
                break
            # Do not leave the last recorded LP referring to a different matrix.
            if iteration + 1 < iterations:
                for _cost, column, slot in offers:
                    self.add(column, slot)
        audit = dict(
            catalogue_sorties=len(self.columns), generated_start_columns=len(self.active),
            horizon_s=self.horizon, grid_step_s=self.step, trip_cap=self.trip_cap,
            objective=f"{self.trip_penalty:g} * trips + energy_kwh; all deliveries on time",
            finite_catalogue_lp_lower_bound=certificate, pricing_trace=trace,
            bound_scope="enumerated sortie catalogue and allowed grid starts only",
            global_continuous_bound=False,
        )
        if not self.active:
            audit.update(status="no_columns", runtime_s=perf_counter() - started)
            return [], audit
        matrix = self.matrix()
        selected = np.arange(len(self.active))
        if integer_reduced_cost_limit is not None:
            if integer_reduced_cost_limit < 0:
                raise ValueError("Negative integer reduced-cost limit")
            selected = np.flatnonzero(result.lower.marginals[:len(self.active)]
                                      <= integer_reduced_cost_limit + 1e-7)
            matrix = matrix[:, selected]
        active = [self.active[i] for i in selected]
        audit.update(integer_start_columns=len(active),
                     integer_reduced_cost_limit=integer_reduced_cost_limit)
        logging.getLogger(__name__).info("Restricted integer master: %d start columns", len(active))
        if not active:
            return [], dict(audit, status="empty_integer_pool", runtime_s=perf_counter() - started)
        integer = milp(
            np.array([self.cost[c] for c, _ in active]),
            integrality=np.ones(len(active)), bounds=Bounds(0, np.inf),
            constraints=LinearConstraint(
                matrix, np.r_[self.demand, np.repeat(-np.inf, nr)],
                np.r_[self.demand, self.capacities],
            ),
            options=dict(time_limit=time_limit, mip_rel_gap=mip_gap),
        )
        audit.update(status=integer.message, runtime_s=perf_counter() - started,
                     restricted_mip_objective=None if integer.fun is None else float(integer.fun),
                     restricted_mip_dual_bound=float(integer.mip_dual_bound)
                     if getattr(integer, "mip_dual_bound", None) is not None else None,
                     restricted_mip_gap=float(integer.mip_gap)
                     if getattr(integer, "mip_gap", None) is not None else None)
        if integer.x is None:
            return [], audit
        rounded = np.rint(integer.x)
        occupied = matrix @ rounded
        if (np.max(np.abs(integer.x - rounded)) > 1e-5
                or np.max(np.abs(occupied[:nc] - self.demand)) > 1e-6
                or np.max(occupied[nc:] - self.capacities) > 1e-6):
            raise ValueError("Integer master solution fails rounded feasibility")
        choices = [(c, slot * self.step, int(rounded[i]))
                   for i, (c, slot) in enumerate(active) if rounded[i] > 0]
        return choices, audit
