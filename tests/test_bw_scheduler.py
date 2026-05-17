"""BW scheduler — phase optimization and multi-day timeline."""

import pytest

pytestmark = pytest.mark.slow

from engine.backwash import filter_bw_timeline_24h, timeline_plant_operating_hours
from engine.bw_scheduler import (
    build_bw_schedule_assessment,
    filters_from_phases,
    find_peak_bw_windows,
    optimize_bw_phases,
    peak_concurrent_bw,
    peak_concurrent_bw_profile,
)


def test_optimize_lowers_or_matches_feasibility_peak():
    n, tc, bd, k = 16, 8.0, 38 / 60.0, 3
    period = tc + bd
    phases, meta = optimize_bw_phases(
        n,
        period_h=period,
        bw_duration_h=bd,
        bw_trains=k,
        horizon_h=168.0,
    )
    assert meta["peak_optimized"] <= meta["peak_feasibility_spacing"]
    flt = filters_from_phases(n, phases, period_h=period, bw_duration_h=bd, horizon_h=168.0)
    assert peak_concurrent_bw(flt, horizon_h=168.0) == meta["peak_optimized"]


def test_timeline_optimized_trains_7d():
    tl = filter_bw_timeline_24h(
        12,
        t_cycle_h=10.0,
        bw_duration_h=0.5,
        horizon_h=168.0,
        bw_trains=2,
        stagger_model="optimized_trains",
    )
    assert tl["stagger_model"] == "optimized_trains"
    assert tl["horizon_h"] == 168.0
    assert len(tl["filters"]) == 12
    assert "optimizer" in tl
    assert tl["peak_concurrent_bw"] <= tl["optimizer"]["peak_feasibility_spacing"]
    assert "peak_windows" in tl
    assert "meets_bw_trains_cap" in tl


def test_timeline_operating_hours_sum_7d():
    tl = filter_bw_timeline_24h(
        4,
        t_cycle_h=10.0,
        bw_duration_h=0.5,
        horizon_h=168.0,
        stagger_model="uniform",
        bw_trains=None,
    )
    st = timeline_plant_operating_hours(
        tl["filters"],
        horizon_h=168.0,
        n_design_online_total=4,
    )
    total = (
        st["hours_operating_eq_design_n_h"]
        + st["hours_operating_gt_design_n_h"]
        + st["hours_operating_eq_n_minus_1_h"]
        + st["hours_operating_below_n_minus_1_h"]
    )
    assert abs(total - 168.0) < 0.2


def test_peak_profile_and_windows():
    n, tc, bd, k = 8, 6.0, 0.4, 2
    period = tc + bd
    phases, _ = optimize_bw_phases(
        n, period_h=period, bw_duration_h=bd, bw_trains=k, horizon_h=48.0,
    )
    flt = filters_from_phases(n, phases, period_h=period, bw_duration_h=bd, horizon_h=48.0)
    prof = peak_concurrent_bw_profile(flt, horizon_h=48.0)
    assert prof["peak"] >= 1
    wins = find_peak_bw_windows(flt, horizon_h=48.0)
    assert wins
    assert wins[0]["t1_h"] > wins[0]["t0_h"]


def test_stream_aware_optimization():
    phases, meta = optimize_bw_phases(
        12,
        period_h=10.5,
        bw_duration_h=0.5,
        bw_trains=2,
        horizon_h=72.0,
        n_streams=3,
    )
    assert len(phases) == 12
    assert meta.get("stream_aware") is True
    assert len(meta.get("per_stream_peak") or []) == 3


def test_build_bw_schedule_assessment():
    a = build_bw_schedule_assessment(
        8,
        period_h=10.5,
        bw_duration_h=0.5,
        bw_trains=2,
        horizon_h=48.0,
        n_streams=2,
        stagger_model="optimized_trains",
    )
    assert a["peak_concurrent_bw"] >= 0
    assert "advisory_notes" in a
    assert a["stagger_model"] == "optimized_trains"
