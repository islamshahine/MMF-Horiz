"""BW phase MILP lite (C5) — discrete ILP for peak / tariff / blackout objective.

Uses PuLP + CBC when available; falls back to ``optimize_bw_phases_v3`` otherwise.
Not plant DCS — scheduling aid only.
"""
from __future__ import annotations

from typing import Any, List, Tuple

from engine.bw_scheduler import (
    filters_from_phases,
    maintenance_blackouts_from_inputs,
    optimize_bw_phases_v3,
    peak_concurrent_bw,
    schedule_objective_v3,
    tariff_windows_from_inputs,
)

_MAX_FILTERS = 24
_MAX_SLOTS = 12
_MAX_TIME_SAMPLES = 32
_CBC_TIME_LIMIT_S = 8


def _adapt_time_samples(horizon_h: float) -> List[float]:
    """Coarser grid on long horizons — keeps ILP constraints bounded."""
    horizon = max(0.0, float(horizon_h))
    n = min(_MAX_TIME_SAMPLES, max(12, int(horizon / 2.0) + 1))
    if n < 2:
        return [0.0]
    return [i * horizon / (n - 1) for i in range(n)]


def _filter_in_bw_at_slot(
    n: int,
    slot_m: int,
    n_slots: int,
    *,
    period_h: float,
    bw_duration_h: float,
    t_h: float,
) -> bool:
    period = max(float(period_h), 1e-9)
    bd = max(float(bw_duration_h), 1e-9)
    phi = (float(slot_m) / max(1, n_slots)) * period
    t = float(t_h)
    k = round((t - phi) / period)
    for kk in (k - 1, k, k + 1):
        start = phi + kk * period
        if start <= t < start + bd:
            return True
    return False


def _slot_tariff_blackout(
    n_slots: int,
    *,
    period_h: float,
    bw_duration_h: float,
    horizon_h: float,
    peak_tariff_windows: List[Tuple[float, float]],
    maintenance_blackouts: List[Tuple[float, float]],
) -> tuple[list[float], list[float]]:
    """Per-slot tariff / blackout hours (identical for every filter)."""
    from engine.bw_scheduler import bw_filter_hours_in_peak_tariff, bw_hours_overlapping_blackouts

    tariff: list[float] = []
    blackout: list[float] = []
    for m in range(n_slots):
        phi = (m / n_slots) * period_h
        flt_one = filters_from_phases(
            1, [phi], period_h=period_h, bw_duration_h=bw_duration_h, horizon_h=horizon_h,
        )
        tariff.append(
            bw_filter_hours_in_peak_tariff(
                flt_one, horizon_h=horizon_h, peak_windows=peak_tariff_windows,
            )
        )
        blackout.append(bw_hours_overlapping_blackouts(flt_one, maintenance_blackouts))
    return tariff, blackout


def _build_coefficients(
    n: int,
    n_slots: int,
    *,
    period_h: float,
    bw_duration_h: float,
    horizon_h: float,
    peak_tariff_windows: List[Tuple[float, float]],
    maintenance_blackouts: List[Tuple[float, float]],
) -> tuple[list[float], list[list[list[float]]], list[float], list[float]]:
    """Time samples; concurrent[t][i][m]; tariff[m]; blackout[m]."""
    times = _adapt_time_samples(horizon_h)
    concurrent: list[list[list[float]]] = []
    for t in times:
        plane: list[list[float]] = []
        for i in range(n):
            row = [
                1.0
                if _filter_in_bw_at_slot(
                    n, m, n_slots, period_h=period_h, bw_duration_h=bw_duration_h, t_h=t,
                )
                else 0.0
                for m in range(n_slots)
            ]
            plane.append(row)
        concurrent.append(plane)

    tariff, blackout = _slot_tariff_blackout(
        n_slots,
        period_h=period_h,
        bw_duration_h=bw_duration_h,
        horizon_h=horizon_h,
        peak_tariff_windows=peak_tariff_windows,
        maintenance_blackouts=maintenance_blackouts,
    )
    return times, concurrent, tariff, blackout


def optimize_bw_phases_milp(
    n_filters: int,
    *,
    period_h: float,
    bw_duration_h: float,
    bw_trains: int,
    horizon_h: float,
    peak_tariff_windows: List[Tuple[float, float]] | None = None,
    tariff_peak_multiplier: float = 1.5,
    maintenance_blackouts: List[Tuple[float, float]] | None = None,
    n_slots: int | None = None,
    w_peak: float = 1000.0,
    w_tariff: float = 2.0,
    w_blackout: float = 50_000.0,
) -> tuple[list[float], dict[str, Any]]:
    """
    Assign each filter to a discrete phase slot minimizing ILP objective.
    Falls back to v3 if PuLP missing or problem too large.
    """
    n = int(max(1, min(int(n_filters), _MAX_FILTERS)))
    period = max(float(period_h), 1e-9)
    bd = max(float(bw_duration_h), 1e-9)
    horizon = max(float(horizon_h), period)
    peak_w = list(peak_tariff_windows or [(14.0, 22.0)])
    blackouts = list(maintenance_blackouts or [])
    m_slots = max(4, min(int(n_slots or min(n, _MAX_SLOTS)), _MAX_SLOTS))

    # Long horizons: v3 heuristic is fast enough; MILP CBC can freeze the UI on multi-day charts.
    if horizon > 48.0:
        ph, meta = optimize_bw_phases_v3(
            n, period_h=period, bw_duration_h=bd, bw_trains=bw_trains, horizon_h=horizon,
            peak_tariff_windows=peak_w, tariff_peak_multiplier=tariff_peak_multiplier,
            maintenance_blackouts=blackouts,
        )
        meta["method"] = "fallback_v3_horizon_gt_48h"
        return ph, meta

    if n > _MAX_FILTERS:
        return optimize_bw_phases_v3(
            n, period_h=period, bw_duration_h=bd, bw_trains=bw_trains, horizon_h=horizon,
            peak_tariff_windows=peak_w, tariff_peak_multiplier=tariff_peak_multiplier,
            maintenance_blackouts=blackouts,
        )

    try:
        import pulp
    except ImportError:
        ph, meta = optimize_bw_phases_v3(
            n, period_h=period, bw_duration_h=bd, bw_trains=bw_trains, horizon_h=horizon,
            peak_tariff_windows=peak_w, tariff_peak_multiplier=tariff_peak_multiplier,
            maintenance_blackouts=blackouts,
        )
        meta["method"] = "fallback_v3_no_pulp"
        return ph, meta

    times, conc, tariff, blackout = _build_coefficients(
        n, m_slots, period_h=period, bw_duration_h=bd, horizon_h=horizon,
        peak_tariff_windows=peak_w, maintenance_blackouts=blackouts,
    )

    prob = pulp.LpProblem("aquasight_bw_milp", pulp.LpMinimize)
    x = pulp.LpVariable.dicts(
        "x",
        ((i, m) for i in range(n) for m in range(m_slots)),
        cat=pulp.LpBinary,
    )
    peak_var = pulp.LpVariable("peak_concurrent", lowBound=0, cat=pulp.LpInteger)

    for i in range(n):
        prob += pulp.lpSum(x[i, m] for m in range(m_slots)) == 1

    for t_idx in range(len(times)):
        plane = conc[t_idx]
        prob += peak_var >= pulp.lpSum(
            plane[i][m] * x[i, m] for i in range(n) for m in range(m_slots)
        )

    mult = max(1.0, float(tariff_peak_multiplier))
    prob += (
        w_peak * peak_var
        + w_tariff * mult * pulp.lpSum(tariff[m] * x[i, m] for i in range(n) for m in range(m_slots))
        + w_blackout * pulp.lpSum(blackout[m] * x[i, m] for i in range(n) for m in range(m_slots))
    )

    prob.solve(
        pulp.PULP_CBC_CMD(msg=False, timeLimit=_CBC_TIME_LIMIT_S, threads=0),
    )
    status = pulp.LpStatus.get(prob.status, "?")
    if status not in ("Optimal", "Not Solved"):
        ph, meta = optimize_bw_phases_v3(
            n, period_h=period, bw_duration_h=bd, bw_trains=bw_trains, horizon_h=horizon,
            peak_tariff_windows=peak_w, tariff_peak_multiplier=tariff_peak_multiplier,
            maintenance_blackouts=blackouts,
        )
        meta["method"] = f"fallback_v3_milp_{status}"
        return ph, meta

    phases: list[float] = []
    for i in range(n):
        chosen = 0
        for m in range(m_slots):
            if pulp.value(x[i, m]) and pulp.value(x[i, m]) > 0.5:
                chosen = m
                break
        phases.append((chosen / m_slots) * period)

    flt = filters_from_phases(n, phases, period_h=period, bw_duration_h=bd, horizon_h=horizon)
    obj = schedule_objective_v3(
        phases, n, period_h=period, bw_duration_h=bd, horizon_h=horizon,
        bw_trains_cap=bw_trains, peak_tariff_windows=peak_w,
        tariff_peak_multiplier=mult, maintenance_blackouts=blackouts,
    )
    meta = {
        "method": "milp_discrete_slots",
        "solver_status": status,
        "n_slots": m_slots,
        "n_time_samples": len(times),
        "peak_optimized": int(peak_concurrent_bw(flt, horizon_h=horizon)),
        "milp_objective": round(float(pulp.value(prob.objective) or 0), 2),
        "tariff_v3": obj,
        "peak_tariff_filter_h": obj.get("peak_tariff_filter_h"),
        "blackout_overlap_h": obj.get("blackout_overlap_h"),
    }
    return phases, meta


def build_bw_schedule_assessment_milp(
    n_filters: int,
    *,
    period_h: float,
    bw_duration_h: float,
    bw_trains: int,
    horizon_h: float,
    inputs: dict,
    n_streams: int = 1,
) -> dict[str, Any]:
    """MILP schedule assessment — mirrors v3 assessment shape."""
    from engine.bw_scheduler import (
        bw_schedule_advisory_notes_v3,
        find_peak_bw_windows,
        peak_concurrent_bw_profile,
    )

    peak_w = tariff_windows_from_inputs(inputs)
    mult = float(inputs.get("bw_tariff_peak_multiplier") or 1.5)
    blackouts = maintenance_blackouts_from_inputs(inputs, horizon_h=horizon_h)
    phases, meta = optimize_bw_phases_milp(
        n_filters,
        period_h=period_h,
        bw_duration_h=bw_duration_h,
        bw_trains=bw_trains,
        horizon_h=horizon_h,
        peak_tariff_windows=peak_w,
        tariff_peak_multiplier=mult,
        maintenance_blackouts=blackouts,
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
    if meta.get("method", "").startswith("milp"):
        notes.insert(
            0,
            f"MILP lite ({meta.get('solver_status', '—')}): discrete phase slots — "
            "not DCS/MES integration.",
        )
    elif "fallback" in str(meta.get("method", "")):
        notes.insert(0, "MILP unavailable — fell back to tariff-aware v3 heuristic.")
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
        "stagger_model": "milp_lite",
        "horizon_h": round(horizon, 3),
        "tariff_v3": meta.get("tariff_v3") or meta,
    }
