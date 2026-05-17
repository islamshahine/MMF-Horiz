"""Build BW duty timeline dict (no Streamlit)."""
from __future__ import annotations

from typing import Any


def timeline_params_from_computed(computed: dict) -> dict[str, Any]:
    tl = computed.get("bw_timeline") or {}
    return {
        "n_filters_total": len(tl.get("filters") or []),
        "t_cycle_h": float(tl.get("t_cycle_h") or 24.0),
        "bw_duration_h": float(tl.get("bw_duration_h") or 0.05),
        "bw_trains": int(tl.get("bw_trains") or 1),
        "sim_demand": tl.get("sim_demand"),
        "n_streams": max(1, int(computed.get("streams") or 1)),
    }


def timeline_build_kwargs(schedule_inputs: dict, computed: dict) -> dict[str, Any]:
    """Scalars for one timeline build (schedule_inputs = duty/tariff fields)."""
    params = timeline_params_from_computed(computed)
    n_total = params["n_filters_total"]
    if n_total < 1:
        n_total = max(
            1,
            int(schedule_inputs.get("streams", 1) or 1)
            * int(schedule_inputs.get("n_filters", 1) or 1),
        )
    sd = params.get("sim_demand")
    sim_f = float(sd) if sd is not None else None
    n_des = int((computed.get("bw_timeline") or {}).get("n_design_online_total") or n_total)
    return {
        "n_filters_total": n_total,
        "t_cycle_h": params["t_cycle_h"],
        "bw_duration_h": params["bw_duration_h"],
        "horizon_days": int(schedule_inputs.get("bw_schedule_horizon_days", 7) or 7),
        "bw_trains": params["bw_trains"],
        "sim_demand": sim_f,
        "n_streams": params["n_streams"],
        "peak_tariff_start_h": float(schedule_inputs.get("bw_peak_tariff_start_h", 14.0) or 14.0),
        "peak_tariff_end_h": float(schedule_inputs.get("bw_peak_tariff_end_h", 22.0) or 22.0),
        "tariff_peak_multiplier": float(schedule_inputs.get("bw_tariff_peak_multiplier", 1.5) or 1.5),
        "maintenance_blackout_enabled": bool(
            schedule_inputs.get("bw_maintenance_blackout_enabled", False)
        ),
        "maintenance_blackout_t0_h": float(
            schedule_inputs.get("bw_maintenance_blackout_t0_h", 0.0) or 0.0
        ),
        "maintenance_blackout_t1_h": float(
            schedule_inputs.get("bw_maintenance_blackout_t1_h", 0.0) or 0.0
        ),
        "n_design_online_total": n_des,
    }


def build_timeline(
    schedule_inputs: dict,
    computed: dict,
    *,
    stagger_model: str,
) -> dict[str, Any]:
    from engine.backwash import filter_bw_timeline_24h, timeline_plant_operating_hours

    kw = timeline_build_kwargs(schedule_inputs, computed)
    horizon_days = int(max(1, min(14, kw["horizon_days"])))
    horizon_h = float(horizon_days * 24)
    sched_in = {
        "bw_peak_tariff_start_h": kw["peak_tariff_start_h"],
        "bw_peak_tariff_end_h": kw["peak_tariff_end_h"],
        "bw_tariff_peak_multiplier": kw["tariff_peak_multiplier"],
        "bw_maintenance_blackout_enabled": kw["maintenance_blackout_enabled"],
        "bw_maintenance_blackout_t0_h": kw["maintenance_blackout_t0_h"],
        "bw_maintenance_blackout_t1_h": kw["maintenance_blackout_t1_h"],
    }
    tl = filter_bw_timeline_24h(
        n_filters_total=max(1, int(kw["n_filters_total"])),
        t_cycle_h=float(kw["t_cycle_h"]),
        bw_duration_h=float(kw["bw_duration_h"]),
        horizon_h=horizon_h,
        bw_trains=max(1, int(kw["bw_trains"])),
        stagger_model=str(stagger_model),
        sim_demand=kw["sim_demand"],
        n_streams=max(1, int(kw["n_streams"])),
        scheduler_inputs=sched_in,
    )
    tl["horizon_days"] = horizon_days
    n_des = max(1, int(kw["n_design_online_total"]))
    tl_stats = timeline_plant_operating_hours(
        tl.get("filters") or [],
        horizon_h=float(tl.get("horizon_h", horizon_h)),
        n_design_online_total=n_des,
    )
    return {**tl, **tl_stats}
