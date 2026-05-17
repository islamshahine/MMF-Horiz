"""Plot-ready series for cycle uncertainty bands (B4 — Filtration charts)."""
from __future__ import annotations

import math
from typing import Any

from engine.backwash import filtration_cycle
from engine.uncertainty import (
    _DEFAULT_ALPHA_SPAN,
    _DEFAULT_CAPTURE_SPAN,
    _DEFAULT_MAL_SPAN,
    _DEFAULT_TSS_SPAN,
)


def _dp_curve_bars(fc: dict) -> tuple[list[float], list[float]]:
    m = [float(r["M (kg/m²)"]) for r in (fc.get("dp_curve") or [])]
    dp = [float(r["ΔP total (bar)"]) for r in (fc.get("dp_curve") or [])]
    return m, dp


def dp_vs_loading_envelope(
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
    """ΔP_total vs M at optimistic / expected / conservative corners (SI)."""
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
        tss_mg_l_list=[_tss],
    )

    corners = {
        "optimistic": dict(
            maldistribution_factor=1.0,
            alpha_calibration_factor=_acf * max(0.5, 1.0 - alpha_span),
            tss_capture_efficiency=min(1.0, _cap * (1.0 + capture_span)),
        ),
        "expected": dict(
            maldistribution_factor=_mal,
            alpha_calibration_factor=_acf,
            tss_capture_efficiency=_cap,
        ),
        "conservative": dict(
            maldistribution_factor=_mal * (1.0 + mal_span),
            alpha_calibration_factor=_acf * (1.0 + alpha_span),
            tss_capture_efficiency=max(0.05, _cap * (1.0 - capture_span)),
        ),
    }

    series: dict[str, list[float]] = {}
    m_ref: list[float] = []
    for label, perturb in corners.items():
        fc = filtration_cycle(**_common, **perturb)
        m, dp = _dp_curve_bars(fc)
        if not m_ref:
            m_ref = m
        series[f"dp_{label}_bar"] = dp

    return {
        "m_kg_m2": m_ref,
        "dp_optimistic_bar": series["dp_optimistic_bar"],
        "dp_expected_bar": series["dp_expected_bar"],
        "dp_conservative_bar": series["dp_conservative_bar"],
        "dp_trigger_bar": float(dp_trigger_bar),
    }


def build_cycle_uncertainty_charts(
    cycle_uncertainty: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    """Aggregate per-scenario envelopes into Filtration chart payloads."""
    if not cycle_uncertainty:
        return {"enabled": False}

    scenarios: list[str] = []
    opt_h: list[float] = []
    exp_h: list[float] = []
    con_h: list[float] = []

    for sc, row in cycle_uncertainty.items():
        if not isinstance(row, dict) or "cycle_expected_h" not in row:
            continue
        scenarios.append(sc)
        opt_h.append(float(row.get("cycle_optimistic_h") or 0))
        exp_h.append(float(row.get("cycle_expected_h") or 0))
        con_h.append(float(row.get("cycle_conservative_h") or 0))

    n_row = cycle_uncertainty.get("N") or {}
    dp_chart = n_row.get("dp_vs_loading_envelope")

    return {
        "enabled": bool(scenarios),
        "scenario_cycle_band": {
            "scenarios": scenarios,
            "cycle_optimistic_h": opt_h,
            "cycle_expected_h": exp_h,
            "cycle_conservative_h": con_h,
        },
        "dp_vs_loading_envelope": dp_chart,
        "design_tss_mg_l": n_row.get("design_tss_mg_l"),
    }
