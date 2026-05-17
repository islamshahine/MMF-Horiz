"""Monte Carlo lite — optional cycle-duration sampling (Tier C1).

Samples α calibration, TSS, capture efficiency, and maldistribution within the same
± spans as ``engine.uncertainty`` (uniform independent draws). Not a substitute for
the deterministic optimistic / expected / conservative envelope.
"""
from __future__ import annotations

import random
from typing import Any

from engine.uncertainty import (
    _DEFAULT_ALPHA_SPAN,
    _DEFAULT_CAPTURE_SPAN,
    _DEFAULT_MAL_SPAN,
    _DEFAULT_TSS_SPAN,
    _run_cycle,
)

_MIN_SAMPLES = 50
_MAX_SAMPLES = 500
_DEFAULT_SAMPLES = 200


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _histogram(vals: list[float], *, n_bins: int = 20) -> dict[str, Any]:
    finite = [v for v in vals if v == v and v < float("inf")]
    if not finite:
        return {"bin_edges_h": [], "counts": []}
    lo, hi = min(finite), max(finite)
    if hi <= lo + 1e-12:
        return {"bin_edges_h": [lo, hi], "counts": [len(finite)]}
    n_bins = max(5, min(40, int(n_bins)))
    width = (hi - lo) / n_bins
    edges = [lo + i * width for i in range(n_bins + 1)]
    counts = [0] * n_bins
    for v in finite:
        idx = min(n_bins - 1, int((v - lo) / width) if width > 0 else 0)
        counts[idx] += 1
    return {"bin_edges_h": [round(e, 4) for e in edges], "counts": counts}


def _n_scenario_flow(load_data: list[tuple[int, int, float]] | None) -> float:
    for x, _n, q in load_data or []:
        if int(x) == 0:
            return float(q)
    if load_data:
        return float(load_data[0][2])
    return 0.0


def build_monte_carlo_cycle_lite(
    inputs: dict[str, Any],
    computed: dict[str, Any],
    *,
    n_samples: int = _DEFAULT_SAMPLES,
    seed: int | None = 42,
    alpha_span: float = _DEFAULT_ALPHA_SPAN,
    tss_span: float = _DEFAULT_TSS_SPAN,
    capture_span: float = _DEFAULT_CAPTURE_SPAN,
    mal_span: float = _DEFAULT_MAL_SPAN,
) -> dict[str, Any]:
    """
    Sample cycle duration [h] at design TSS for the N scenario.

    Returns ``{"enabled": False}`` when inputs are insufficient.
    """
    n = max(_MIN_SAMPLES, min(_MAX_SAMPLES, int(n_samples)))
    q = _n_scenario_flow(computed.get("load_data"))
    layers = inputs.get("layers") or []
    avg_area = float(computed.get("avg_area") or 0.0)
    if q <= 0 or avg_area <= 0 or not layers:
        return {"enabled": False, "reason": "missing_hydraulics"}

    solid_loading = float(
        computed.get("solid_loading_effective_kg_m2")
        or inputs.get("solid_loading")
        or 0.0
    )
    captured_density = float(inputs.get("captured_solids_density") or 1020.0)
    feed_temp = float(inputs.get("feed_temp") or 27.0)
    rho_feed = float(computed.get("rho_feed") or 1000.0)
    dp_trigger = float(inputs.get("dp_trigger_bar") or 1.0)
    alpha_m_kg = float(inputs.get("alpha_specific") or 0.0)
    design_tss = float(inputs.get("tss_avg") or 10.0)
    _acf = max(0.05, min(3.0, float(computed.get("alpha_calibration_factor", 1.0) or 1.0)))
    _cap = max(0.0, min(1.0, float(computed.get("tss_capture_efficiency", 1.0) or 1.0)))
    _mal = max(1.0, float(computed.get("maldistribution_factor", 1.0) or 1.0))
    layer_areas = computed.get("layer_areas_m2")
    if layer_areas is not None and len(layer_areas) != len(layers):
        layer_areas = None

    rng = random.Random(seed)
    _common = dict(
        layers=layers,
        q_filter_m3h=q,
        avg_area_m2=avg_area,
        solid_loading_kg_m2=solid_loading,
        captured_density_kg_m3=captured_density,
        water_temp_c=feed_temp,
        rho_water=rho_feed,
        dp_trigger_bar=dp_trigger,
        alpha_m_kg=alpha_m_kg,
        layer_areas_m2=layer_areas,
    )

    samples: list[float] = []
    for _ in range(n):
        acf_s = rng.uniform(
            max(0.5, _acf * (1.0 - alpha_span)),
            _acf * (1.0 + alpha_span),
        )
        cap_s = rng.uniform(
            max(0.05, _cap * (1.0 - capture_span)),
            min(1.0, _cap * (1.0 + capture_span)),
        )
        tss_s = rng.uniform(
            max(0.1, design_tss * (1.0 - tss_span)),
            design_tss * (1.0 + tss_span),
        )
        mal_s = rng.uniform(_mal, _mal * (1.0 + mal_span))
        h = _run_cycle(
            **_common,
            maldistribution_factor=mal_s,
            alpha_calibration_factor=acf_s,
            tss_capture_efficiency=cap_s,
            design_tss_mg_l=tss_s,
        )
        if h == h and h < float("inf"):
            samples.append(float(h))

    if len(samples) < 10:
        return {"enabled": False, "reason": "too_few_finite_samples"}

    samples.sort()
    det = (computed.get("cycle_uncertainty") or {}).get("N") or {}

    return {
        "enabled": True,
        "method": "monte_carlo_lite_uniform",
        "n_samples_requested": n,
        "n_samples_finite": len(samples),
        "seed": seed,
        "design_tss_mg_l": design_tss,
        "scenario": "N",
        "percentiles_h": {
            "p10": round(_percentile(samples, 10), 2),
            "p50": round(_percentile(samples, 50), 2),
            "p90": round(_percentile(samples, 90), 2),
        },
        "mean_h": round(sum(samples) / len(samples), 2),
        "min_h": round(samples[0], 2),
        "max_h": round(samples[-1], 2),
        "deterministic_envelope_h": {
            "optimistic": det.get("cycle_optimistic_h"),
            "expected": det.get("cycle_expected_h"),
            "conservative": det.get("cycle_conservative_h"),
        },
        "perturbation": {
            "alpha_span": alpha_span,
            "tss_span": tss_span,
            "capture_span": capture_span,
            "mal_span": mal_span,
        },
        "histogram": _histogram(samples),
        "note": (
            "Uniform independent samples on calibration factors — compare to the "
            "deterministic corner envelope; not a statistical confidence interval."
        ),
    }
