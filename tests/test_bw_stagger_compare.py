"""Stagger comparison cache — multi-model duty timelines."""
from engine.bw_stagger_compare import build_stagger_comparison, compare_fingerprint
from engine.bw_timeline_build import build_timeline


def _stub_computed(n: int = 4, *, streams: int = 1):
    period = 13.7
    return {
        "streams": streams,
        "bw_timeline": {
            "filters": [{"filter_index": i + 1, "segments": []} for i in range(n)],
            "t_cycle_h": 12.0,
            "bw_duration_h": 0.63,
            "period_h": period,
            "bw_trains": 2,
            "sim_demand": 0.5,
            "horizon_h": 48.0,
            "n_design_online_total": n,
        },
    }


def _schedule():
    return {
        "bw_schedule_horizon_days": 2,
        "bw_peak_tariff_start_h": 14.0,
        "bw_peak_tariff_end_h": 22.0,
        "bw_tariff_peak_multiplier": 1.5,
        "bw_maintenance_blackout_enabled": False,
        "bw_maintenance_blackout_t0_h": 0.0,
        "bw_maintenance_blackout_t1_h": 0.0,
    }


def test_build_stagger_comparison_two_models():
    sched = _schedule()
    comp = _stub_computed(4)
    out = build_stagger_comparison(
        sched, comp, ("feasibility_trains", "uniform"),
    )
    assert out["enabled"]
    assert "feasibility_trains" in out["timelines"]
    assert "uniform" in out["timelines"]
    assert len(out["summary"]) == 2
    assert out["timelines"]["feasibility_trains"]["stagger_model"] == "feasibility_trains"


def test_compare_fingerprint_stable():
    sched = _schedule()
    comp = _stub_computed(4)
    a = compare_fingerprint(sched, comp, ("feasibility_trains", "uniform"))
    b = compare_fingerprint(sched, comp, ("feasibility_trains", "uniform"))
    assert a == b


def test_build_timeline_feasibility_fast():
    tl = build_timeline(_schedule(), _stub_computed(4), stagger_model="feasibility_trains")
    assert tl["peak_concurrent_bw"] >= 1
    assert len(tl["filters"]) == 4
