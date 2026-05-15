"""BW scheduler — phase optimization and multi-day timeline."""

from engine.backwash import filter_bw_timeline_24h, timeline_plant_operating_hours
from engine.bw_scheduler import filters_from_phases, optimize_bw_phases, peak_concurrent_bw


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
