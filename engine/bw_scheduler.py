"""
BW train scheduler — scheduling aid (heuristic, not MILP / DCS).

Minimises peak concurrent backwash over a multi-hour horizon by adjusting
per-filter BW phase offsets while keeping the fixed filtration cycle period.
"""
from __future__ import annotations

import math
from typing import Callable


def filters_from_phases(
    n_filters: int,
    phases: list[float],
    *,
    period_h: float,
    bw_duration_h: float,
    horizon_h: float,
) -> list[dict]:
    """Build operate/BW segment lists per filter from phase offsets (hours)."""
    n_int = int(max(0, n_filters))
    period = max(float(period_h), 1e-9)
    bd = max(float(bw_duration_h), 1e-9)
    horizon = max(float(horizon_h), 0.0)
    if n_int < 1:
        return []

    ph = list(phases[:n_int])
    while len(ph) < n_int:
        ph.append(0.0)

    filters: list[dict] = []
    for i in range(n_int):
        phi = float(ph[i]) % period
        bws: list[tuple[float, float]] = []
        k_lo = int(math.floor((0.0 - phi - bd) / period)) - 1
        k_hi = int(math.ceil((horizon - phi) / period)) + 2
        for k in range(k_lo, k_hi + 1):
            start = phi + k * period
            t0 = max(0.0, start)
            t1 = min(horizon, start + bd)
            if t0 + 1e-9 < t1:
                bws.append((t0, t1))
        bws.sort()
        merged: list[tuple[float, float]] = []
        for a, b in bws:
            if merged and a <= merged[-1][1] + 1e-9:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))

        segs: list[dict[str, float | str]] = []
        cursor = 0.0
        for a, b in merged:
            if cursor + 1e-9 < a:
                segs.append({"state": "operate", "t0": cursor, "t1": a})
            segs.append({"state": "bw", "t0": a, "t1": b})
            cursor = b
        if cursor + 1e-9 < horizon:
            segs.append({"state": "operate", "t0": cursor, "t1": horizon})
        filters.append({"filter_index": i + 1, "segments": segs, "phase_h": round(phi, 4)})
    return filters


def peak_concurrent_bw(
    filters: list[dict],
    *,
    horizon_h: float,
    dt_h: float = 0.05,
) -> int:
    """Peak count of filters in BW state over ``[0, horizon_h]``."""
    horizon = float(horizon_h)
    if not filters or horizon <= 0:
        return 0
    peak = 0.0
    t = 0.0
    while t < horizon - 1e-9:
        c = 0
        for f in filters:
            for s in f["segments"]:
                if s["state"] == "bw" and float(s["t0"]) <= t < float(s["t1"]):
                    c += 1
                    break
        peak = max(peak, float(c))
        t += dt_h
    return int(round(peak))


def _candidate_phases(period_h: float, bw_duration_h: float, bw_trains: int, n_filters: int) -> list[float]:
    period = max(float(period_h), 1e-9)
    bd = max(float(bw_duration_h), 1e-9)
    k = max(1, int(bw_trains))
    n = max(1, int(n_filters))
    cands: set[float] = set()
    for j in range(k):
        cands.add((j * bd / float(k)) % period)
    for j in range(n):
        cands.add((j * period / float(n)) % period)
    for j in range(max(n, k * 2)):
        cands.add((j * bd / float(k)) % period)
    return sorted(cands)


def optimize_bw_phases(
    n_filters: int,
    *,
    period_h: float,
    bw_duration_h: float,
    bw_trains: int,
    horizon_h: float,
    max_passes: int = 8,
) -> tuple[list[float], dict]:
    """
    Coordinate descent on per-filter phases (scheduling aid).

    Starts from feasibility-train spacing ``i·Δt_bw/K``; tries alternative
  phases on a discrete grid to lower peak concurrent BW.
    """
    n = int(max(1, n_filters))
    period = max(float(period_h), 1e-9)
    bd = max(float(bw_duration_h), 1e-9)
    k = max(1, min(int(bw_trains), n))
    horizon = max(float(horizon_h), period)

    phases = [((i * bd) / float(k)) % period for i in range(n)]
    grid = _candidate_phases(period, bd, k, n)

    def _peak(ph: list[float]) -> int:
        flt = filters_from_phases(n, ph, period_h=period, bw_duration_h=bd, horizon_h=horizon)
        return peak_concurrent_bw(flt, horizon_h=horizon)

    best_peak = _peak(phases)
    passes = 0
    for _ in range(max_passes):
        improved = False
        for i in range(n):
            for cand in grid:
                trial = phases[:]
                trial[i] = cand
                p = _peak(trial)
                if p < best_peak:
                    phases = trial
                    best_peak = p
                    improved = True
        passes += 1
        if not improved:
            break

    feas_phases = [((i * bd) / float(k)) % period for i in range(n)]
    feas_peak = _peak(feas_phases)

    return phases, {
        "peak_optimized": best_peak,
        "peak_feasibility_spacing": feas_peak,
        "improvement_filters": max(0, feas_peak - best_peak),
        "optimizer_passes": passes,
        "bw_trains_target": k,
    }


def phi_fn_from_phases(phases: list[float], period_h: float) -> Callable[[int], float]:
    period = max(float(period_h), 1e-9)
    ph = list(phases)

    def _phi(i: int) -> float:
        if i < len(ph):
            return float(ph[i]) % period
        return 0.0

    return _phi
