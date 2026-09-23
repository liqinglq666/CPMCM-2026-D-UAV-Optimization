# Q1 — 单服务区运输能力与精确组批

## 1. Purpose

Q1 establishes the common physical-computation layer used by later questions.

For each service area and each transport-UAV type, compute:

- horizontal distance;
- terrain-constrained cruise altitude;
- climb/descent height;
- energy consumption;
- round-trip time;
- maximum safe payload.

Then partition indivisible cargo boxes into feasible batches.

## 2. Unified physics assumptions

### Horizontal distance

Use WGS84 geodesic distance between node coordinates.

### Terrain clearance

For a horizontal segment, identify all intersected 30 m DEM cells.

```text
cruise altitude = maximum intersected DEM elevation + 50 m
```

### Payload-dependent equivalent range

```text
L(q) = L0 - (L0 - LF) * (q / Q)^(3/2)
```

### Horizontal energy

```text
E_hor = E_use * d / L(q)
```

### Climb energy

```text
E_up = (m_empty + q) * g * h_up / (eta_up * 3.6e6)
```

### Descent

No additional descent-energy term is added under the current interpretation of the problem statement.

### Return reserve

A trip is feasible only if:

```text
E_trip <= (1 - rho) * E_use
```

where rho is the required return-energy reserve.

## 3. Batch feasibility

Each batch must satisfy simultaneously:

- payload-mass capacity;
- payload-volume capacity;
- energy feasibility under the return reserve.

Cargo boxes are indivisible.

## 4. Optimization objective

Lexicographic objective:

1. minimize number of trips;
2. minimize total energy;
3. minimize cumulative operation time.

An exact subset-partition dynamic program is used for each service area.

## 5. Baseline working result

At rho = 20%:

- minimum trips = 18;
- total transport energy = 59.1304 kWh;
- cumulative operation time = 32776.02 s;
- S001, S002, S003 require multiple batches.

These are working results and should be cross-checked before final submission.


## Audit implementation update

Q1 uses the shared input, DEM, energy and flight-time implementations in
`src/core/`. A type unable to make an empty round trip is represented explicitly
as unreachable rather than an unexplained NaN. NoData and outside-DEM paths fail
explicitly. The standalone validator recomputes leg physics, safe payloads, cargo
coverage and every reported reserve-sensitivity point.
