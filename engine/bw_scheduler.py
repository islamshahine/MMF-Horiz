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


def scheduler_dt_h(horizon_h: float, dt_h: float | None = None) -> float:
    """Coarser time step on long horizons — keeps peak scans UI-friendly (~≤400 samples)."""
    if dt_h is not None and float(dt_h) > 0:
        return max(0.01, float(dt_h))
    h = max(1.0, float(horizon_h))
    return max(0.05, min(0.5, h / 400.0))


def peak_concurrent_bw(
    filters: list[dict],
    *,
    horizon_h: float,
    dt_h: float | None = None,
) -> int:
    """Peak count of filters in BW state over ``[0, horizon_h]``."""
    prof = peak_concurrent_bw_profile(filters, horizon_h=horizon_h, dt_h=dt_h)
    return int(prof["peak"])


def peak_concurrent_bw_profile(
    filters: list[dict],
    *,
    horizon_h: float,
    dt_h: float | None = None,
) -> Dict[str, Any]:
    """Peak concurrent BW and time of first peak (scheduling aid)."""
    horizon = float(horizon_h)
    if not filters or horizon <= 0:
        return {"peak": 0, "peak_time_h": 0.0, "samples": []}

    step = scheduler_dt_h(horizon, dt_h)
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
    dt_h: float | None = None,
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


def scheduler_max_passes(horizon_h: float, n_filters: int = 1) -> int:
    """Fewer coordinate-descent passes on long horizons / many filters (UI responsiveness)."""
    h = float(horizon_h)
    n = int(max(1, n_filters))
    if h > 120.0 or (h > 72.0 and n > 12):
        return 1
    if h > 72.0 or n > 12:
        return 2
    if h > 48.0 or n > 8:
        return 3
    return 8


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
    if len(base) > 16:
        return base
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
    max_passes: int | None = None,
    n_streams: int = 1,
) -> tuple[list[float], dict]:
    """
    Phase optimizer — optionally per-stream when ``n_streams`` divides filter count.
    """
    n = int(max(1, n_filters))
    passes = int(max_passes if max_passes is not None else scheduler_max_passes(horizon_h, n))
    ns = max(1, int(n_streams))
    if ns <= 1 or n % ns != 0:
        return _optimize_bw_phases_single(
            n,
            period_h=period_h,
            bw_duration_h=bw_duration_h,
            bw_trains=bw_trains,
            horizon_h=horizon_h,
            max_passes=passes,
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
            max_passes=passes,
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
        "optimizer_passes": passes,
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


# ── B2: tariff-aware scheduler v3 (heuristic — not MILP / DCS) ─────────────────


def hour_of_day(t_h: float) -> float:
    """Clock hour within a 24 h day for multi-day horizons."""
    return float(t_h) % 24.0


def is_in_daily_window(t_h: float, start_h: float, end_h: float) -> bool:
    """True if ``t_h`` falls in ``[start_h, end_h)`` on the clock (wraps midnight)."""
    hod = hour_of_day(t_h)
    s = float(start_h) % 24.0
    e = float(end_h) % 24.0
    if abs(s - e) < 1e-9:
        return False
    if s < e:
        return s <= hod < e
    return hod >= s or hod < e


def tariff_windows_from_inputs(inputs: dict) -> List[Tuple[float, float]]:
    """Peak electricity window(s) on the clock — default 14:00–22:00."""
    custom = inputs.get("bw_peak_tariff_windows")
    if isinstance(custom, list) and custom:
        out: List[Tuple[float, float]] = []
        for w in custom:
            if isinstance(w, dict):
                out.append((float(w["start_h"]), float(w["end_h"])))
            elif isinstance(w, (list, tuple)) and len(w) >= 2:
                out.append((float(w[0]), float(w[1])))
        if out:
            return out
    return [
        (
            float(inputs.get("bw_peak_tariff_start_h", 14.0)),
            float(inputs.get("bw_peak_tariff_end_h", 22.0)),
        ),
    ]


def maintenance_blackouts_from_inputs(
    inputs: dict,
    *,
    horizon_h: float,
) -> List[Tuple[float, float]]:
    """Absolute-hour blackout intervals within ``[0, horizon_h]``."""
    horizon = max(0.0, float(horizon_h))
    out: List[Tuple[float, float]] = []
    for w in inputs.get("bw_maintenance_blackouts") or []:
        if isinstance(w, dict):
            t0 = float(w.get("t0_h", 0))
            t1 = float(w.get("t1_h", 0))
        elif isinstance(w, (list, tuple)) and len(w) >= 2:
            t0, t1 = float(w[0]), float(w[1])
        else:
            continue
        if t1 > t0:
            out.append((max(0.0, t0), min(horizon, t1)))

    if bool(inputs.get("bw_maintenance_blackout_enabled", False)):
        t0 = float(inputs.get("bw_maintenance_blackout_t0_h", 0.0))
        t1 = float(inputs.get("bw_maintenance_blackout_t1_h", 0.0))
        if t1 > t0:
            out.append((max(0.0, t0), min(horizon, t1)))
    return out


def bw_filter_hours_in_peak_tariff(
    filters: list[dict],
    *,
    horizon_h: float,
    peak_windows: List[Tuple[float, float]],
    dt_h: float = 0.05,
) -> float:
    """Σ (concurrent BW filters × Δt) during peak-tariff clock windows — energy proxy."""
    if not filters or not peak_windows:
        return 0.0
    horizon = max(float(horizon_h), 0.0)
    step = max(float(dt_h), 0.01)
    h = 0.0
    t = 0.0
    while t < horizon - 1e-9:
        if any(is_in_daily_window(t, a, b) for a, b in peak_windows):
            h += step * float(_concurrent_bw_at(filters, t))
        t += step
    return h


def bw_hours_overlapping_blackouts(
    filters: list[dict],
    blackouts: List[Tuple[float, float]],
    *,
    dt_h: float = 0.05,
) -> float:
    """Σ filter×hours of BW overlapping maintenance blackouts."""
    if not filters or not blackouts:
        return 0.0
    step = max(float(dt_h), 0.01)
    total = 0.0
    for f in filters:
        for s in f.get("segments") or []:
            if str(s.get("state")) != "bw":
                continue
            t0 = float(s["t0"])
            t1 = float(s["t1"])
            t = t0
            while t < t1 - 1e-9:
                t_mid = t + step * 0.5
                if any(t0_b < t1 and t1_b > t_mid for t0_b, t1_b in blackouts):
                    total += step
                t += step
    return total


def schedule_objective_v3(
    phases: list[float],
    n_filters: int,
    *,
    period_h: float,
    bw_duration_h: float,
    horizon_h: float,
    bw_trains_cap: int,
    peak_tariff_windows: List[Tuple[float, float]],
    tariff_peak_multiplier: float = 1.5,
    maintenance_blackouts: List[Tuple[float, float]],
    w_peak: float = 1000.0,
    w_tariff: float = 2.0,
    w_blackout: float = 50_000.0,
) -> Dict[str, Any]:
    """Scalar objective + diagnostics for tariff-aware phase search."""
    n = int(max(1, n_filters))
    period = max(float(period_h), 1e-9)
    bd = max(float(bw_duration_h), 1e-9)
    horizon = max(float(horizon_h), period)
    flt = filters_from_phases(n, phases, period_h=period, bw_duration_h=bd, horizon_h=horizon)
    peak = int(peak_concurrent_bw(flt, horizon_h=horizon))
    cap = max(1, int(bw_trains_cap))
    cap_excess = max(0, peak - cap)
    peak_tariff_h = bw_filter_hours_in_peak_tariff(
        flt, horizon_h=horizon, peak_windows=peak_tariff_windows,
    )
    off_tariff_h = max(0.0, sum(
        (float(s["t1"]) - float(s["t0"]))
        for f in flt
        for s in (f.get("segments") or [])
        if str(s.get("state")) == "bw"
    ) - peak_tariff_h)
    mult = max(1.0, float(tariff_peak_multiplier))
    tariff_proxy = peak_tariff_h * mult + off_tariff_h
    blackout_h = bw_hours_overlapping_blackouts(flt, maintenance_blackouts)
    score = (
        w_peak * peak
        + w_peak * 10.0 * cap_excess
        + w_tariff * tariff_proxy
        + w_blackout * blackout_h
    )
    return {
        "score": score,
        "peak": peak,
        "cap_excess": cap_excess,
        "peak_tariff_filter_h": round(peak_tariff_h, 2),
        "offpeak_bw_filter_h": round(off_tariff_h, 2),
        "tariff_proxy": round(tariff_proxy, 2),
        "blackout_overlap_h": round(blackout_h, 3),
    }


def _optimize_bw_phases_v3_single(
    n_filters: int,
    *,
    period_h: float,
    bw_duration_h: float,
    bw_trains: int,
    horizon_h: float,
    peak_tariff_windows: List[Tuple[float, float]],
    tariff_peak_multiplier: float,
    maintenance_blackouts: List[Tuple[float, float]],
    max_passes: int = 8,
) -> tuple[list[float], dict]:
    """Coordinate descent minimizing peak + tariff exposure + blackout overlap."""
    n = int(max(1, n_filters))
    period = max(float(period_h), 1e-9)
    bd = max(float(bw_duration_h), 1e-9)
    k = max(1, min(int(bw_trains), n))
    horizon = max(float(horizon_h), period)

    phases = [((i * bd) / float(k)) % period for i in range(n)]
    grid = _candidate_phases(period, bd, k, n)
    if horizon > 48.0 and len(grid) > 12:
        grid = grid[:12]

    def _obj(ph: list[float]) -> Dict[str, Any]:
        return schedule_objective_v3(
            ph,
            n,
            period_h=period,
            bw_duration_h=bd,
            horizon_h=horizon,
            bw_trains_cap=k,
            peak_tariff_windows=peak_tariff_windows,
            tariff_peak_multiplier=tariff_peak_multiplier,
            maintenance_blackouts=maintenance_blackouts,
        )

    best = _obj(phases)
    best_score = float(best["score"])
    passes = 0
    for _ in range(max_passes):
        improved = False
        for i in range(n):
            for cand in grid:
                trial = phases[:]
                trial[i] = cand
                o = _obj(trial)
                if float(o["score"]) < best_score - 1e-6:
                    phases = trial
                    best = o
                    best_score = float(o["score"])
                    improved = True
        for i in range(n):
            for j in range(i + 1, n):
                trial = phases[:]
                trial[i], trial[j] = trial[j], trial[i]
                o = _obj(trial)
                if float(o["score"]) < best_score - 1e-6:
                    phases = trial
                    best = o
                    best_score = float(o["score"])
                    improved = True
        passes += 1
        if not improved:
            break

    feas_phases = [((i * bd) / float(k)) % period for i in range(n)]
    feas = _obj(feas_phases)

    return phases, {
        "peak_optimized": int(best["peak"]),
        "peak_feasibility_spacing": int(feas["peak"]),
        "improvement_filters": max(0, int(feas["peak"]) - int(best["peak"])),
        "optimizer_passes": passes,
        "bw_trains_target": k,
        "meets_bw_trains_cap": int(best["peak"]) <= k,
        "tariff_v3": best,
        "tariff_v3_feasibility": feas,
        "peak_tariff_filter_h": best["peak_tariff_filter_h"],
        "blackout_overlap_h": best["blackout_overlap_h"],
        "tariff_peak_multiplier": float(tariff_peak_multiplier),
        "peak_tariff_windows": [
            {"start_h": a, "end_h": b} for a, b in peak_tariff_windows
        ],
        "maintenance_blackouts": [
            {"t0_h": a, "t1_h": b} for a, b in maintenance_blackouts
        ],
    }


def optimize_bw_phases_v3(
    n_filters: int,
    *,
    period_h: float,
    bw_duration_h: float,
    bw_trains: int,
    horizon_h: float,
    peak_tariff_windows: List[Tuple[float, float]],
    tariff_peak_multiplier: float = 1.5,
    maintenance_blackouts: Optional[List[Tuple[float, float]]] = None,
    max_passes: int | None = None,
    n_streams: int = 1,
) -> tuple[list[float], dict]:
    """Tariff-aware v3 optimizer — per-stream when ``n_streams`` divides filter count."""
    blackouts = list(maintenance_blackouts or [])
    n = int(max(1, n_filters))
    passes = int(max_passes if max_passes is not None else scheduler_max_passes(horizon_h, n))
    ns = max(1, int(n_streams))
    if ns <= 1 or n % ns != 0:
        return _optimize_bw_phases_v3_single(
            n,
            period_h=period_h,
            bw_duration_h=bw_duration_h,
            bw_trains=bw_trains,
            horizon_h=horizon_h,
            peak_tariff_windows=peak_tariff_windows,
            tariff_peak_multiplier=tariff_peak_multiplier,
            maintenance_blackouts=blackouts,
            max_passes=passes,
        )

    period = max(float(period_h), 1e-9)
    bd = max(float(bw_duration_h), 1e-9)
    per = n // ns
    k_stream = max(1, min(int(bw_trains), per))
    phases: list[float] = []
    stream_meta: list[dict] = []
    for _ in range(ns):
        ph, meta = _optimize_bw_phases_v3_single(
            per,
            period_h=period_h,
            bw_duration_h=bw_duration_h,
            bw_trains=k_stream,
            horizon_h=horizon_h,
            peak_tariff_windows=peak_tariff_windows,
            tariff_peak_multiplier=tariff_peak_multiplier,
            maintenance_blackouts=blackouts,
            max_passes=passes,
        )
        phases.extend(ph)
        stream_meta.append(meta)

    flt = filters_from_phases(
        n, phases, period_h=period_h, bw_duration_h=bw_duration_h, horizon_h=horizon_h,
    )
    plant_obj = schedule_objective_v3(
        phases,
        n,
        period_h=period_h,
        bw_duration_h=bw_duration_h,
        horizon_h=horizon_h,
        bw_trains_cap=max(1, min(int(bw_trains), n)),
        peak_tariff_windows=peak_tariff_windows,
        tariff_peak_multiplier=tariff_peak_multiplier,
        maintenance_blackouts=blackouts,
    )
    k_g = max(1, min(int(bw_trains), n))
    feas_phases = [((i * bd) / float(k_g)) % period for i in range(n)]
    feas_obj = schedule_objective_v3(
        feas_phases,
        n,
        period_h=period_h,
        bw_duration_h=bw_duration_h,
        horizon_h=horizon_h,
        bw_trains_cap=k_g,
        peak_tariff_windows=peak_tariff_windows,
        tariff_peak_multiplier=tariff_peak_multiplier,
        maintenance_blackouts=blackouts,
    )
    return phases, {
        "peak_optimized": int(plant_obj["peak"]),
        "peak_feasibility_spacing": int(feas_obj["peak"]),
        "improvement_filters": max(0, int(feas_obj["peak"]) - int(plant_obj["peak"])),
        "optimizer_passes": passes,
        "bw_trains_target": k_g,
        "meets_bw_trains_cap": int(plant_obj["peak"]) <= k_g,
        "stream_aware": True,
        "n_streams": ns,
        "per_stream_meta": stream_meta,
        "tariff_v3": plant_obj,
        "peak_tariff_filter_h": plant_obj["peak_tariff_filter_h"],
        "blackout_overlap_h": plant_obj["blackout_overlap_h"],
        "tariff_peak_multiplier": float(tariff_peak_multiplier),
        "peak_tariff_windows": [
            {"start_h": a, "end_h": b} for a, b in peak_tariff_windows
        ],
        "maintenance_blackouts": [
            {"t0_h": a, "t1_h": b} for a, b in blackouts
        ],
    }


def bw_schedule_advisory_notes_v3(
    *,
    peak: int,
    bw_trains_target: int,
    meets_cap: bool,
    tariff_meta: dict,
    peak_windows: List[Dict[str, float]],
) -> List[str]:
    notes = bw_schedule_advisory_notes(
        peak=peak,
        bw_trains_target=bw_trains_target,
        peak_windows=peak_windows,
        meets_cap=meets_cap,
    )
    pth = float(tariff_meta.get("peak_tariff_filter_h", 0) or 0)
    boh = float(tariff_meta.get("blackout_overlap_h", 0) or 0)
    wins = tariff_meta.get("peak_tariff_windows") or []
    if wins:
        w = wins[0]
        notes.append(
            f"Peak tariff window: **{float(w.get('start_h', 0)):.0f}:00–"
            f"{float(w.get('end_h', 0)):.0f}:00** (×{float(tariff_meta.get('tariff_peak_multiplier', 1.5)):.2f} proxy)."
        )
    notes.append(
        f"BW filter-hours in peak tariff: **{pth:.1f} h** (lower is better for OPEX)."
    )
    if boh > 0.05:
        notes.append(
            f"⚠ **{boh:.2f} h** of BW overlaps maintenance blackout — adjust phases or blackout."
        )
    else:
        notes.append("No BW overlap with maintenance blackout on this horizon.")
    return notes


def build_bw_schedule_assessment_v3(
    n_filters: int,
    *,
    period_h: float,
    bw_duration_h: float,
    bw_trains: int,
    horizon_h: float,
    inputs: dict,
    n_streams: int = 1,
) -> Dict[str, Any]:
    """Tariff-aware schedule assessment (B2)."""
    peak_w = tariff_windows_from_inputs(inputs)
    mult = float(inputs.get("bw_tariff_peak_multiplier") or inputs.get("elec_tariff_peak_multiplier") or 1.5)
    blackouts = maintenance_blackouts_from_inputs(inputs, horizon_h=horizon_h)
    phases, meta = optimize_bw_phases_v3(
        n_filters,
        period_h=period_h,
        bw_duration_h=bw_duration_h,
        bw_trains=bw_trains,
        horizon_h=horizon_h,
        peak_tariff_windows=peak_w,
        tariff_peak_multiplier=mult,
        maintenance_blackouts=blackouts,
        n_streams=n_streams,
    )
    n = int(max(1, n_filters))
    period = max(float(period_h), 1e-9)
    bd = max(float(bw_duration_h), 1e-9)
    horizon = max(float(horizon_h), 0.0)
    k = max(1, min(int(bw_trains), n))
    filters = filters_from_phases(n, phases, period_h=period, bw_duration_h=bd, horizon_h=horizon)
    prof = peak_concurrent_bw_profile(filters, horizon_h=horizon)
    windows = find_peak_bw_windows(filters, horizon_h=horizon)
    peak = int(prof["peak"])
    meets = peak <= k
    notes = bw_schedule_advisory_notes_v3(
        peak=peak,
        bw_trains_target=k,
        meets_cap=meets,
        tariff_meta=meta,
        peak_windows=windows,
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
        "stagger_model": "tariff_aware_v3",
        "horizon_h": round(horizon, 3),
        "tariff_v3": meta.get("tariff_v3") or meta,
    }
