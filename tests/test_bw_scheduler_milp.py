"""BW scheduler MILP lite (C5) — discrete phase ILP and timeline integration."""
from engine.backwash import filter_bw_timeline_24h
from engine.bw_scheduler import optimize_bw_phases_v3, schedule_objective_v3
from engine.bw_scheduler_milp import build_bw_schedule_assessment_milp, optimize_bw_phases_milp


def _sched_inputs():
    return {
        "bw_peak_tariff_start_h": 14.0,
        "bw_peak_tariff_end_h": 22.0,
        "bw_tariff_peak_multiplier": 1.5,
        "bw_maintenance_blackout_start_h": 0.0,
        "bw_maintenance_blackout_end_h": 0.0,
    }


def test_milp_returns_phases_and_meta():
    n, tc, bd, k = 6, 6.0, 0.4, 2
    period = tc + bd
    phases, meta = optimize_bw_phases_milp(
        n,
        period_h=period,
        bw_duration_h=bd,
        bw_trains=k,
        horizon_h=48.0,
        peak_tariff_windows=[(14.0, 22.0)],
        maintenance_blackouts=[],
    )
    assert len(phases) == n
    assert meta.get("method") in (
        "milp_discrete_slots",
        "fallback_v3_no_pulp",
        "fallback_v3_milp_Not Solved",
    ) or str(meta.get("method", "")).startswith("fallback_v3")


def test_milp_not_worse_than_uniform_tariff_objective_when_solved():
    n, tc, bd, k = 8, 6.0, 0.4, 2
    period = tc + bd
    horizon = 48.0
    peak_w = [(14.0, 22.0)]
    uniform = [(i / n) * period for i in range(n)]
    u_obj = schedule_objective_v3(
        uniform,
        n,
        period_h=period,
        bw_duration_h=bd,
        horizon_h=horizon,
        bw_trains_cap=k,
        peak_tariff_windows=peak_w,
        tariff_peak_multiplier=1.5,
        maintenance_blackouts=[],
    )
    phases, meta = optimize_bw_phases_milp(
        n,
        period_h=period,
        bw_duration_h=bd,
        bw_trains=k,
        horizon_h=horizon,
        peak_tariff_windows=peak_w,
        maintenance_blackouts=[],
    )
    m_obj = schedule_objective_v3(
        phases,
        n,
        period_h=period,
        bw_duration_h=bd,
        horizon_h=horizon,
        bw_trains_cap=k,
        peak_tariff_windows=peak_w,
        tariff_peak_multiplier=1.5,
        maintenance_blackouts=[],
    )
    if meta.get("method") == "milp_discrete_slots":
        assert float(m_obj["peak_tariff_filter_h"]) <= float(u_obj["peak_tariff_filter_h"]) + 2.0


def test_build_bw_schedule_assessment_milp_shape():
    n, tc, bd, k = 4, 5.0, 0.35, 2
    period = tc + bd
    assess = build_bw_schedule_assessment_milp(
        n,
        period_h=period,
        bw_duration_h=bd,
        bw_trains=k,
        horizon_h=24.0,
        inputs=_sched_inputs(),
    )
    assert assess["stagger_model"] == "milp_lite"
    assert len(assess["filters"]) == n
    assert "peak_concurrent_bw" in assess
    assert assess.get("optimizer")


def test_timeline_milp_lite_integration():
    tl = filter_bw_timeline_24h(
        6,
        t_cycle_h=6.0,
        bw_duration_h=0.4,
        horizon_h=48.0,
        bw_trains=2,
        stagger_model="milp_lite",
        scheduler_inputs=_sched_inputs(),
    )
    assert tl["stagger_model"] == "milp_lite"
    assert tl["peak_concurrent_bw"] >= 1
    assert len(tl["filters"]) == 6


def test_milp_fallback_no_pulp(monkeypatch):
    """When PuLP is missing, optimizer delegates to v3."""
    import builtins

    _real = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pulp":
            raise ImportError("mock no pulp")
        return _real(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)
    n, tc, bd, k = 4, 6.0, 0.4, 2
    period = tc + bd
    phases, meta = optimize_bw_phases_milp(
        n,
        period_h=period,
        bw_duration_h=bd,
        bw_trains=k,
        horizon_h=24.0,
    )
    assert meta.get("method") == "fallback_v3_no_pulp"
    assert len(phases) == n
