"""Build and summarise multiple BW stagger timelines for side-by-side comparison."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from engine.bw_timeline_build import build_timeline, timeline_build_kwargs

COMPARE_STAGGER_DEFAULTS: tuple[str, ...] = (
    "feasibility_trains",
    "optimized_trains",
    "tariff_aware_v3",
)

_VALID_STAGGERS = frozenset({
    "uniform",
    "feasibility_trains",
    "optimized_trains",
    "tariff_aware_v3",
    "milp_lite",
})


def compare_fingerprint(schedule_inputs: dict, computed: dict, stagger_models: tuple[str, ...]) -> str:
    kwargs = timeline_build_kwargs(schedule_inputs, computed)
    payload = {**kwargs, "models": list(stagger_models)}
    blob = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _summary_row(stagger: str, tl: dict[str, Any]) -> dict[str, Any]:
    opt = tl.get("optimizer") or {}
    tariff_h = None
    if isinstance(opt.get("tariff_v3"), dict):
        tariff_h = opt["tariff_v3"].get("peak_tariff_filter_h")
    if tariff_h is None:
        tariff_h = opt.get("peak_tariff_filter_h")
    return {
        "stagger_model": stagger,
        "peak_concurrent_bw": tl.get("peak_concurrent_bw"),
        "meets_bw_trains_cap": tl.get("meets_bw_trains_cap"),
        "hours_at_n": tl.get("hours_operating_eq_design_n_h"),
        "hours_at_n_minus_1": tl.get("hours_operating_eq_n_minus_1_h"),
        "peak_tariff_filter_h": tariff_h,
        "method": opt.get("method", "—"),
    }


def build_stagger_comparison(
    schedule_inputs: dict,
    computed: dict,
    stagger_models: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """
    Build timelines for each stagger model (same cycle / horizon / tariff settings).
    """
    models = tuple(
        m for m in (stagger_models or COMPARE_STAGGER_DEFAULTS)
        if m in _VALID_STAGGERS
    )
    if not models:
        models = COMPARE_STAGGER_DEFAULTS

    fp = compare_fingerprint(schedule_inputs, computed, models)
    timelines: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}

    for sm in models:
        try:
            timelines[sm] = build_timeline(schedule_inputs, computed, stagger_model=sm)
        except Exception as exc:
            errors[sm] = str(exc)

    summary = [_summary_row(sm, timelines[sm]) for sm in models if sm in timelines]
    return {
        "enabled": bool(timelines),
        "fingerprint": fp,
        "timelines": timelines,
        "summary": summary,
        "errors": errors,
        "stagger_models": list(models),
        "horizon_days": int(schedule_inputs.get("bw_schedule_horizon_days", 7) or 7),
    }
