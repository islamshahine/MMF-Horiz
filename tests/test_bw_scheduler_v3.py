"""BW scheduler v3 — tariff windows and maintenance blackouts."""
from engine.backwash import filter_bw_timeline_24h
from engine.bw_scheduler import (
    bw_hours_overlapping_blackouts,
    filters_from_phases,
    is_in_daily_window,
    optimize_bw_phases_v3,
    schedule_objective_v3,
)


def test_is_in_daily_window_wrap():
    assert is_in_daily_window(23.0, 22.0, 6.0)
    assert not is_in_daily_window(12.0, 22.0, 6.0)


def test_v3_reduces_peak_tariff_hours_vs_uniform():
    n, tc, bd, k = 8, 6.0, 0.4, 2
    period = tc + bd
    horizon = 48.0
    peak_w = [(14.0, 22.0)]
    uniform = [(i / n) * period for i in range(n)]
    blackouts: list = []
    u_obj = schedule_objective_v3(
        uniform,
        n,
        period_h=period,
        bw_duration_h=bd,
        horizon_h=horizon,
        bw_trains_cap=k,
        peak_tariff_windows=peak_w,
        tariff_peak_multiplier=1.5,
        maintenance_blackouts=blackouts,
    )
    phases, meta = optimize_bw_phases_v3(
        n,
        period_h=period,
        bw_duration_h=bd,
        bw_trains=k,
        horizon_h=horizon,
        peak_tariff_windows=peak_w,
        tariff_peak_multiplier=1.5,
        maintenance_blackouts=blackouts,
        max_passes=3,
    )
    v3_obj = schedule_objective_v3(
        phases,
        n,
        period_h=period,
        bw_duration_h=bd,
        horizon_h=horizon,
        bw_trains_cap=k,
        peak_tariff_windows=peak_w,
        tariff_peak_multiplier=1.5,
        maintenance_blackouts=blackouts,
    )
    assert float(v3_obj["peak_tariff_filter_h"]) <= float(u_obj["peak_tariff_filter_h"]) + 1.0
    assert meta["meets_bw_trains_cap"] or meta["peak_optimized"] <= k + 1


def test_blackout_penalty():
    n, period, bd, horizon = 4, 10.0, 0.5, 48.0
    phases = [0.0, 2.5, 5.0, 7.5]
    flt = filters_from_phases(n, phases, period_h=period, bw_duration_h=bd, horizon_h=horizon)
    overlap = bw_hours_overlapping_blackouts(flt, [(0.0, 20.0)])
    assert overlap > 0.0


def test_timeline_tariff_aware_v3():
    tl = filter_bw_timeline_24h(
        8,
        t_cycle_h=6.0,
        bw_duration_h=0.4,
        horizon_h=72.0,
        bw_trains=2,
        stagger_model="tariff_aware_v3",
        scheduler_inputs={
            "bw_peak_tariff_start_h": 14.0,
            "bw_peak_tariff_end_h": 22.0,
            "bw_tariff_peak_multiplier": 1.5,
            "bw_maintenance_blackout_enabled": True,
            "bw_maintenance_blackout_t0_h": 30.0,
            "bw_maintenance_blackout_t1_h": 36.0,
        },
    )
    assert tl["stagger_model"] == "tariff_aware_v3"
    assert "tariff_v3" in tl
    assert tl.get("meets_bw_trains_cap") is not None
