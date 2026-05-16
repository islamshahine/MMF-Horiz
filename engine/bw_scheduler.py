"""
BW train scheduler — scheduling aid (heuristic, not MILP / DCS).

Minimises peak concurrent backwash over a multi-hour horizon by adjusting
per-filter BW phase offsets while keeping the fixed filtration cycle period.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Tuple


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


def _concurrent_bw_at(
    filters: list[dict],
    t_h: float,
) -> int:
    c = 0
    for f in filters:
        for s in f["segments"]:
            if s["state"] == "bw" and float(s["t0"]) <= t_h < float(s["t1"]):
                c += 1
                break
    return c


def peak_concurrent_bw(
    filters: list[dict],
    *,
    horizon_h: float,
    dt_h: float = 0.05,
) -> int:
    """Peak count of filters in BW state over ``[0, horizon_h]``."""
    prof = peak_concurrent_bw_profile(filters, horizon_h=horizon_h, dt_h=dt_h)
    return int(prof["peak"])


def peak_concurrent_bw_profile(
    filters: list[dict],
    *,
    horizon_h: float,
    dt_h: float = 0.05,
) -> Dict[str, Any]:
    """Peak concurrent BW and time of first peak (scheduling aid)."""
    horizon = float(horizon_h)
    if not filters or horizon <= 0:
        return {"peak": 0, "peak_time_h": 0.0, "samples": []}

    step = max(float(dt_h), 0.01)
    peak = 0
    peak_t = 0.0
    samples: List[Tuple[float, int]] = []
    t = 0.0
    while t < horizon - 1e-9:
        c = _concurrent_bw_at(filters, t)
        samples.append((round(t, 3), c))
        if c > peak:
            peak = c
            peak_t = t
        t += step
    return {
        "peak": int(peak),
        "peak_time_h": round(peak_t, 3),
        "samples": samples,
    }


def find_peak_bw_windows(
    filters: list[dict],
    *,
    horizon_h: float,
    dt_h: float = 0.05,
    max_windows: int = 3,
) -> List[Dict[str, float]]:
    """Contiguous intervals where concurrent BW equals the horizon peak."""
    prof = peak_concurrent_bw_profile(filters, horizon_h=horizon_h, dt_h=dt_h)
    target = int(prof["peak"])
    if target < 1:
        return []

    windows: List[Dict[str, float]] = []
    in_win = False
    t0 = 0.0
    for t, c in prof["samples"]:
        if c >= target:
            if not in_win:
                in_win = True
                t0 = t
        elif in_win:
            windows.append({"t0_h": round(t0, 3), "t1_h": round(t, 3), "peak": float(target)})
            in_win = False
            if len(windows) >= max_windows:
                break
    if in_win and len(windows) < max_windows:
        windows.append({
            "t0_h": round(t0, 3),
            "t1_h": round(float(horizon_h), 3),
            "peak": float(target),
        })
    return windows[:max_windows]


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
    base = sorted(cands)
    for a in range(len(base)):
        for b in range(a + 1, len(base)):
            cands.add(((base[a] + base[b]) / 2.0) % period)
    return sorted(cands)


def _optimize_bw_phases_single(
    n_filters: int,
    *,
    period_h: float,
    bw_duration_h: float,
    bw_trains: int,
    horizon_h: float,
    max_passes: int = 8,
) -> tuple[list[float], dict]:
    """
    Coordinate descent + pairwise swaps on per-filter phases (scheduling aid).

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
        for i in range(n):
            for j in range(i + 1, n):
                trial = phases[:]
                trial[i], trial[j] = trial[j], trial[i]
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
        "meets_bw_trains_cap": best_peak <= k,
    }


def optimize_bw_phases(
    n_filters: int,
    *,
    period_h: float,
    bw_duration_h: float,
    bw_trains: int,
    horizon_h: float,
    max_passes: int = 8,
    n_streams: int = 1,
) -> tuple[list[float], dict]:
    """
    Phase optimizer — optionally per-stream when ``n_streams`` divides filter count.
    """
    n = int(max(1, n_filters))
    ns = max(1, int(n_streams))
    if ns <= 1 or n % ns != 0:
        return _optimize_bw_phases_single(
            n,
            period_h=period_h,
            bw_duration_h=bw_duration_h,
            bw_trains=bw_trains,
            horizon_h=horizon_h,
            max_passes=max_passes,
        )

    period = max(float(period_h), 1e-9)
    bd = max(float(bw_duration_h), 1e-9)
    per = n // ns
    k_stream = max(1, min(int(bw_trains), per))
    phases: list[float] = []
    stream_peaks: list[int] = []
    for _s in range(ns):
        ph, meta = _optimize_bw_phases_single(
            per,
            period_h=period_h,
            bw_duration_h=bw_duration_h,
            bw_trains=k_stream,
            horizon_h=horizon_h,
            max_passes=max_passes,
        )
        phases.extend(ph)
        stream_peaks.append(int(meta["peak_optimized"]))

    flt = filters_from_phases(
        n, phases, period_h=period_h, bw_duration_h=bw_duration_h, horizon_h=horizon_h,
    )
    plant_peak = peak_concurrent_bw(flt, horizon_h=horizon_h)
    k_g = max(1, min(int(bw_trains), n))
    feas_phases = [((i * bd) / float(k_g)) % period for i in range(n)]
    feas_peak = peak_concurrent_bw(
        filters_from_phases(
            n, feas_phases, period_h=period_h, bw_duration_h=bw_duration_h, horizon_h=horizon_h,
        ),
        horizon_h=horizon_h,
    )
    k_tgt = max(1, min(int(bw_trains), n))
    return phases, {
        "peak_optimized": plant_peak,
        "peak_feasibility_spacing": feas_peak,
        "improvement_filters": max(0, feas_peak - plant_peak),
        "optimizer_passes": max_passes,
        "bw_trains_target": k_tgt,
        "meets_bw_trains_cap": plant_peak <= k_tgt,
        "stream_aware": True,
        "n_streams": ns,
        "per_stream_peak": stream_peaks,
    }


def bw_schedule_advisory_notes(
    *,
    peak: int,
    bw_trains_target: int,
    peak_windows: List[Dict[str, float]],
    meets_cap: bool,
    stream_aware: bool = False,
) -> List[str]:
    """Short ops-facing notes (scheduling aid only)."""
    notes: List[str] = []
    if not meets_cap and peak > bw_trains_target:
        notes.append(
            f"Peak **{peak}** filters in BW exceeds rated **{bw_trains_target}** train(s) — "
            "add BW capacity, lengthen cycle, or stagger more filters."
        )
    elif meets_cap:
        notes.append(
            f"Peak concurrent BW **{peak}** is within the **{bw_trains_target}**-train schematic cap "
            "on this horizon."
        )
    if peak_windows:
        _w = peak_windows[0]
        notes.append(
            f"First peak overlap window: **{_w['t0_h']:.1f}–{_w['t1_h']:.1f} h** "
            f"({int(_w['peak'])} filters in BW)."
        )
    if stream_aware:
        notes.append(
            "Phases optimised **per stream** then combined — typical for multi-train MMF plants."
        )
    return notes


def build_bw_schedule_assessment(
    n_filters: int,
    *,
    period_h: float,
    bw_duration_h: float,
    bw_trains: int,
    horizon_h: float,
    n_streams: int = 1,
    stagger_model: str = "optimized_trains",
) -> Dict[str, Any]:
    """Structured scheduler output for UI / tests (heuristic scheduling aid)."""
    n = int(max(1, n_filters))
    period = max(float(period_h), 1e-9)
    bd = max(float(bw_duration_h), 1e-9)
    horizon = max(float(horizon_h), 0.0)
    k = max(1, min(int(bw_trains), n))
    sm = str(stagger_model or "feasibility_trains").strip().lower()

    if sm == "optimized_trains":
        phases, meta = optimize_bw_phases(
            n,
            period_h=period,
            bw_duration_h=bd,
            bw_trains=k,
            horizon_h=horizon,
            n_streams=n_streams,
        )
    elif sm == "uniform":
        phases = [(i / float(n)) * period for i in range(n)]
        meta = {"peak_optimized": None, "bw_trains_target": k}
    else:
        phases = [((i * bd) / float(k)) % period for i in range(n)]
        meta = {"peak_optimized": None, "bw_trains_target": k}

    filters = filters_from_phases(n, phases, period_h=period, bw_duration_h=bd, horizon_h=horizon)
    prof = peak_concurrent_bw_profile(filters, horizon_h=horizon)
    windows = find_peak_bw_windows(filters, horizon_h=horizon)
    peak = int(prof["peak"])
    meets = peak <= k
    notes = bw_schedule_advisory_notes(
        peak=peak,
        bw_trains_target=k,
        peak_windows=windows,
        meets_cap=meets,
        stream_aware=bool(meta.get("stream_aware")),
    )
    return {
        "filters": filters,
        "phases_h": [round(float(p) % period, 4) for p in phases],
        "peak_concurrent_bw": peak,
        "peak_time_h": prof["peak_time_h"],
        "peak_windows": windows,
        "meets_bw_trains_cap": meets,
        "bw_trains_target": k,
        "optimizer": meta,
        "advisory_notes": notes,
        "stagger_model": sm,
        "horizon_h": round(horizon, 3),
    }


def phi_fn_from_phases(phases: list[float], period_h: float) -> Callable[[int], float]:
    period = max(float(period_h), 1e-9)
    ph = list(phases)

    def _phi(i: int) -> float:
        if i < len(ph):
            return float(ph[i]) % period
        return 0.0

    return _phi
