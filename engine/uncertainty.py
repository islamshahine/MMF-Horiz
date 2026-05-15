"""Deterministic cycle-duration envelopes — engineering uncertainty (not statistics).

Uses bounded corner cases on α calibration, TSS, capture efficiency, and maldistribution,
then calls ``filtration_cycle`` (Ruth cake model). No Monte Carlo.
"""
from __future__ import annotations

import math
from typing import Any

from engine.backwash import filtration_cycle

# Default ± spans (fraction of base value)
_DEFAULT_ALPHA_SPAN = 0.15
_DEFAULT_TSS_SPAN = 0.15
_DEFAULT_CAPTURE_SPAN = 0.05
_DEFAULT_MAL_SPAN = 0.10


def _cycle_hours_at_tss(fc: dict, tss_mg_l: float) -> float:
    for row in fc.get("tss_results") or []:
        if abs(float(row["TSS (mg/L)"]) - float(tss_mg_l)) < 1e-6:
            v = float(row["Cycle duration (h)"])
            return v if math.isfinite(v) else float("inf")
    return float("inf")


def _run_cycle(
  *,
  layers: list,
  q_filter_m3h: float,
  avg_area_m2: float,
  solid_loading_kg_m2: float,
  captured_density_kg_m3: float,
  water_temp_c: float,
  rho_water: float,
  dp_trigger_bar: float,
  alpha_m_kg: float,
  layer_areas_m2: list[float] | None,
  maldistribution_factor: float,
  alpha_calibration_factor: float,
  tss_capture_efficiency: float,
  design_tss_mg_l: float,
) -> float:
    fc = filtration_cycle(
        layers=layers,
        q_filter_m3h=q_filter_m3h,
        avg_area_m2=avg_area_m2,
        solid_loading_kg_m2=solid_loading_kg_m2,
        captured_density_kg_m3=captured_density_kg_m3,
        water_temp_c=water_temp_c,
        rho_water=rho_water,
        dp_trigger_bar=dp_trigger_bar,
        alpha_m_kg=alpha_m_kg,
        tss_mg_l_list=[design_tss_mg_l],
        layer_areas_m2=layer_areas_m2,
        maldistribution_factor=maldistribution_factor,
        alpha_calibration_factor=alpha_calibration_factor,
        tss_capture_efficiency=tss_capture_efficiency,
    )
    return _cycle_hours_at_tss(fc, design_tss_mg_l)


def cycle_duration_envelope(
    *,
    layers: list,
    q_filter_m3h: float,
    avg_area_m2: float,
    solid_loading_kg_m2: float,
    captured_density_kg_m3: float,
    water_temp_c: float,
    rho_water: float,
    dp_trigger_bar: float,
    alpha_m_kg: float,
    layer_areas_m2: list[float] | None,
    maldistribution_factor: float,
    alpha_calibration_factor: float,
    tss_capture_efficiency: float,
    design_tss_mg_l: float,
    alpha_span: float = _DEFAULT_ALPHA_SPAN,
    tss_span: float = _DEFAULT_TSS_SPAN,
    capture_span: float = _DEFAULT_CAPTURE_SPAN,
    mal_span: float = _DEFAULT_MAL_SPAN,
) -> dict[str, Any]:
    """Return optimistic / expected / conservative cycle duration [h] at design TSS.

    **Optimistic** — longer run time (favourable): low TSS, low α factor, high capture, no extra mal.
    **Conservative** — shorter run time (stress case): high TSS, high α factor, low capture, extra mal.
  """
    _acf = max(0.05, min(3.0, float(alpha_calibration_factor)))
    _cap = max(0.0, min(1.0, float(tss_capture_efficiency)))
    _mal = max(1.0, float(maldistribution_factor))
    _tss = max(0.1, float(design_tss_mg_l))

    _common = dict(
        layers=layers,
        q_filter_m3h=q_filter_m3h,
        avg_area_m2=avg_area_m2,
        solid_loading_kg_m2=solid_loading_kg_m2,
        captured_density_kg_m3=captured_density_kg_m3,
        water_temp_c=water_temp_c,
        rho_water=rho_water,
        dp_trigger_bar=dp_trigger_bar,
        alpha_m_kg=alpha_m_kg,
        layer_areas_m2=layer_areas_m2,
    )

    expected_h = _run_cycle(
        **_common,
        maldistribution_factor=_mal,
        alpha_calibration_factor=_acf,
        tss_capture_efficiency=_cap,
        design_tss_mg_l=_tss,
    )

    optimistic_h = _run_cycle(
        **_common,
        maldistribution_factor=1.0,
        alpha_calibration_factor=_acf * max(0.5, 1.0 - alpha_span),
        tss_capture_efficiency=min(1.0, _cap * (1.0 + capture_span)),
        design_tss_mg_l=_tss * max(0.5, 1.0 - tss_span),
    )

    conservative_h = _run_cycle(
        **_common,
        maldistribution_factor=_mal * (1.0 + mal_span),
        alpha_calibration_factor=_acf * (1.0 + alpha_span),
        tss_capture_efficiency=max(0.05, _cap * (1.0 - capture_span)),
        design_tss_mg_l=_tss * (1.0 + tss_span),
    )

    finite = [v for v in (optimistic_h, expected_h, conservative_h) if math.isfinite(v)]
    if finite:
        optimistic_h = max(finite)
        conservative_h = min(finite)
        if not math.isfinite(expected_h):
            expected_h = (optimistic_h + conservative_h) / 2.0

    spread_h = (
        optimistic_h - conservative_h
        if math.isfinite(optimistic_h) and math.isfinite(conservative_h)
        else 0.0
    )
    spread_pct = (
        (spread_h / expected_h * 100.0)
        if expected_h > 1e-9 and expected_h < float("inf")
        else 0.0
    )

    if spread_pct >= 50:
        stability = "wide"
        stability_note = (
            "Wide cycle band — operating window sensitive to TSS, cake resistance, "
            "and distribution assumptions; confirm with site data."
        )
    elif spread_pct >= 25:
        stability = "moderate"
        stability_note = (
            "Moderate cycle variability — review peak TSS events and calibration factors."
        )
    else:
        stability = "narrow"
        stability_note = "Narrow cycle band — model inputs are mutually consistent at design TSS."

    return {
        "design_tss_mg_l": _tss,
        "cycle_optimistic_h": round(optimistic_h, 2),
        "cycle_expected_h": round(expected_h, 2),
        "cycle_conservative_h": round(conservative_h, 2),
        "spread_h": round(spread_h, 2),
        "spread_pct": round(spread_pct, 1),
        "stability": stability,
        "stability_note": stability_note,
        "perturbation": {
            "alpha_span": alpha_span,
            "tss_span": tss_span,
            "capture_span": capture_span,
            "mal_span": mal_span,
        },
        "method": "deterministic_corner_cases",
    }


def cycle_uncertainty_by_scenario(
    load_data: list[tuple[int, int, float]],
    *,
    layers: list,
    avg_area_m2: float,
    solid_loading_kg_m2: float,
    captured_density_kg_m3: float,
    water_temp_c: float,
    rho_water: float,
    dp_trigger_bar: float,
    alpha_m_kg: float,
    layer_areas_m2: list[float] | None,
    maldistribution_factor: float,
    alpha_calibration_factor: float,
    tss_capture_efficiency: float,
    design_tss_mg_l: float,
) -> dict[str, dict[str, Any]]:
    """Envelope per redundancy scenario (N, N-1, …). Keys match ``filt_cycles``."""
    out: dict[str, dict[str, Any]] = {}
    for x, _nact, q in load_data:
        sc = "N" if x == 0 else f"N-{x}"
        out[sc] = cycle_duration_envelope(
            layers=layers,
            q_filter_m3h=q,
            avg_area_m2=avg_area_m2,
            solid_loading_kg_m2=solid_loading_kg_m2,
            captured_density_kg_m3=captured_density_kg_m3,
            water_temp_c=water_temp_c,
            rho_water=rho_water,
            dp_trigger_bar=dp_trigger_bar,
            alpha_m_kg=alpha_m_kg,
            layer_areas_m2=layer_areas_m2,
            maldistribution_factor=maldistribution_factor,
            alpha_calibration_factor=alpha_calibration_factor,
            tss_capture_efficiency=tss_capture_efficiency,
            design_tss_mg_l=design_tss_mg_l,
        )
    return out
