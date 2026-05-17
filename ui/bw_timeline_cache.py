"""Fast BW duty-chart rebuild — stagger / tariff / horizon without full ``compute_all``."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import streamlit as st

BW_SCHEDULE_INPUT_KEYS = frozenset({
    "bw_timeline_stagger",
    "bw_schedule_horizon_days",
    "bw_peak_tariff_start_h",
    "bw_peak_tariff_end_h",
    "bw_tariff_peak_multiplier",
    "bw_maintenance_blackout_enabled",
    "bw_maintenance_blackout_t0_h",
    "bw_maintenance_blackout_t1_h",
})

# Never JSON-serialize these for fingerprints (large / redundant).
_FINGERPRINT_SKIP_KEYS = frozenset({
    *BW_SCHEDULE_INPUT_KEYS,
    "nozzle_sched_override",
    "media_presets",
    "mmf_nozzle_sched_user",
})


def inputs_for_compute_cache(inputs: dict) -> dict:
    """Drop schedule-only sidebar keys so stagger changes do not bust the heavy model cache."""
    return {k: v for k, v in inputs.items() if k not in BW_SCHEDULE_INPUT_KEYS}


def _fingerprint_value(v: Any) -> Any:
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, (list, tuple)):
        if len(v) > 64:
            return ("__len__", len(v))
        return [_fingerprint_value(x) for x in v]
    if isinstance(v, dict):
        if len(v) > 64:
            return ("__dict_len__", len(v))
        return {str(k): _fingerprint_value(v[k]) for k in sorted(v.keys(), key=str)[:64]}
    return repr(v)[:120]


def fingerprint_dict(d: dict) -> str:
    """Lightweight hash — skips huge schedule / nozzle payloads."""
    payload = {k: _fingerprint_value(d[k]) for k in sorted(d.keys()) if k not in _FINGERPRINT_SKIP_KEYS}
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()


def core_inputs_fingerprint(inputs: dict) -> str:
    return fingerprint_dict(inputs_for_compute_cache(inputs))


def merge_bw_duty_applied(inputs: dict) -> dict:
    applied = st.session_state.get("_bw_duty_applied")
    if not isinstance(applied, dict) or not applied:
        return inputs
    merged = dict(inputs)
    merged.update(applied)
    return merged


def _timeline_params_from_computed(computed: dict) -> dict[str, Any]:
    from engine.bw_timeline_build import timeline_params_from_computed

    return timeline_params_from_computed(computed)


def minimal_computed_stub(computed: dict) -> dict[str, Any]:
    """Small dict for ``st.cache_data`` — avoids hashing the full ``computed`` tree."""
    p = _timeline_params_from_computed(computed)
    n = max(1, p["n_filters_total"])
    tl = computed.get("bw_timeline") or {}
    filters = tl.get("filters")
    if not filters:
        filters = [{"filter_index": i + 1} for i in range(n)]
    return {
        "streams": max(1, int(computed.get("streams") or 1)),
        "bw_timeline": {
            "filters": filters,
            "t_cycle_h": p["t_cycle_h"],
            "bw_duration_h": p["bw_duration_h"],
            "bw_trains": p["bw_trains"],
            "sim_demand": p.get("sim_demand"),
            "n_design_online_total": int(tl.get("n_design_online_total") or n),
        },
    }


@st.cache_data(show_spinner=False, max_entries=40)
def build_bw_timeline_cached(
    n_filters_total: int,
    t_cycle_h: float,
    bw_duration_h: float,
    horizon_days: int,
    bw_trains: int,
    stagger_model: str,
    sim_demand: float | None,
    n_streams: int,
    peak_tariff_start_h: float,
    peak_tariff_end_h: float,
    tariff_peak_multiplier: float,
    maintenance_blackout_enabled: bool,
    maintenance_blackout_t0_h: float,
    maintenance_blackout_t1_h: float,
    n_design_online_total: int,
) -> dict[str, Any]:
    schedule = {
        "bw_schedule_horizon_days": horizon_days,
        "bw_peak_tariff_start_h": peak_tariff_start_h,
        "bw_peak_tariff_end_h": peak_tariff_end_h,
        "bw_tariff_peak_multiplier": tariff_peak_multiplier,
        "bw_maintenance_blackout_enabled": maintenance_blackout_enabled,
        "bw_maintenance_blackout_t0_h": maintenance_blackout_t0_h,
        "bw_maintenance_blackout_t1_h": maintenance_blackout_t1_h,
    }
    stub = {
        "bw_timeline": {
            "filters": [{}] * max(1, n_filters_total),
            "t_cycle_h": t_cycle_h,
            "bw_duration_h": bw_duration_h,
            "bw_trains": bw_trains,
            "sim_demand": sim_demand,
            "n_design_online_total": n_design_online_total,
        },
        "streams": n_streams,
    }
    from engine.bw_timeline_build import build_timeline

    return build_timeline(schedule, stub, stagger_model=stagger_model)


@st.cache_data(show_spinner="Building stagger comparison…", max_entries=8)
def build_stagger_comparison_cached(
    cache_key: str,
    _schedule_inputs: dict,
    _computed_stub: dict,
    stagger_models: tuple[str, ...],
) -> dict[str, Any]:
    del cache_key
    from engine.bw_stagger_compare import build_stagger_comparison

    return build_stagger_comparison(_schedule_inputs, _computed_stub, stagger_models)


def _repair_bw_timeline_slot(computed: dict) -> None:
    """Undo legacy bug that stored the full ``computed`` dict under ``bw_timeline``."""
    tl = computed.get("bw_timeline")
    if not isinstance(tl, dict):
        return
    if "filt_cycles" in tl and "bw_col" in tl:
        inner = tl.get("bw_timeline")
        computed["bw_timeline"] = inner if isinstance(inner, dict) else {}


def refresh_bw_timeline_in_computed(inputs: dict, computed: dict) -> dict:
    _repair_bw_timeline_slot(computed)
    merged = merge_bw_duty_applied(inputs)
    tl = overlay_bw_timeline(merged, computed)
    if isinstance(st.session_state.get("mmf_last_computed"), dict):
        st.session_state["mmf_last_computed"]["bw_timeline"] = tl
    st.session_state["_bw_duty_dirty"] = False
    return tl


def overlay_bw_timeline(inputs: dict, computed: dict) -> dict:
    from engine.bw_timeline_build import timeline_build_kwargs

    merged = merge_bw_duty_applied(inputs)
    stagger = str(merged.get("bw_timeline_stagger", "feasibility_trains")).strip().lower()
    if stagger not in (
        "uniform", "feasibility_trains", "optimized_trains", "tariff_aware_v3", "milp_lite",
    ):
        stagger = "feasibility_trains"
    kw = timeline_build_kwargs(merged, computed)
    tl = build_bw_timeline_cached(
        kw["n_filters_total"],
        kw["t_cycle_h"],
        kw["bw_duration_h"],
        kw["horizon_days"],
        kw["bw_trains"],
        stagger,
        kw["sim_demand"],
        kw["n_streams"],
        kw["peak_tariff_start_h"],
        kw["peak_tariff_end_h"],
        kw["tariff_peak_multiplier"],
        kw["maintenance_blackout_enabled"],
        kw["maintenance_blackout_t0_h"],
        kw["maintenance_blackout_t1_h"],
        kw["n_design_online_total"],
    )
    computed["bw_timeline"] = tl
    return tl
