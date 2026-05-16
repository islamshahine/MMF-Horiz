"""
One-at-a-time **driver decomposition** for filtration cycle uncertainty (2A extension).

Complements ``uncertainty.cycle_duration_envelope`` — does not replace corner-case
optimistic / expected / conservative bands used by economics.
"""
from __future__ import annotations

import math
from typing import Any

from engine.uncertainty import _run_cycle

_DRIVER_SPECS: list[dict[str, Any]] = [
    {
        "id": "design_tss",
        "label": "Feed TSS (design)",
        "optimistic_key": "design_tss_mg_l",
        "conservative_key": "design_tss_mg_l",
    },
    {
        "id": "alpha_calibration",
        "label": "α calibration factor",
        "optimistic_key": "alpha_calibration_factor",
        "conservative_key": "alpha_calibration_factor",
    },
    {
        "id": "tss_capture",
        "label": "TSS capture efficiency",
        "optimistic_key": "tss_capture_efficiency",
        "conservative_key": "tss_capture_efficiency",
    },
    {
        "id": "maldistribution",
        "label": "Maldistribution factor",
        "optimistic_key": "maldistribution_factor",
        "conservative_key": "maldistribution_factor",
    },
]


def _corner_values(
    *,
    alpha_calibration_factor: float,
    tss_capture_efficiency: float,
    maldistribution_factor: float,
    design_tss_mg_l: float,
    alpha_span: float,
    tss_span: float,
    capture_span: float,
    mal_span: float,
) -> tuple[dict[str, float], dict[str, float]]:
    """Per-parameter values at optimistic vs conservative corners (matches uncertainty.py)."""
    _acf = max(0.05, min(3.0, float(alpha_calibration_factor)))
    _cap = max(0.0, min(1.0, float(tss_capture_efficiency)))
    _mal = max(1.0, float(maldistribution_factor))
    _tss = max(0.1, float(design_tss_mg_l))

    optimistic = {
        "maldistribution_factor": 1.0,
        "alpha_calibration_factor": _acf * max(0.5, 1.0 - alpha_span),
        "tss_capture_efficiency": min(1.0, _cap * (1.0 + capture_span)),
        "design_tss_mg_l": _tss * max(0.5, 1.0 - tss_span),
    }
    conservative = {
        "maldistribution_factor": _mal * (1.0 + mal_span),
        "alpha_calibration_factor": _acf * (1.0 + alpha_span),
        "tss_capture_efficiency": max(0.05, _cap * (1.0 - capture_span)),
        "design_tss_mg_l": _tss * (1.0 + tss_span),
    }
    return optimistic, conservative


def _narrative_for_driver(
    label: str,
    expected_h: float,
    optimistic_only_h: float,
    conservative_only_h: float,
    span_note: str,
) -> str:
    if not math.isfinite(expected_h) or expected_h <= 0:
        return f"**{label}** — cycle not finite at design TSS; check cake / trigger inputs."

    d_opt = optimistic_only_h - expected_h
    d_con = conservative_only_h - expected_h
    parts = [f"**{label}** ({span_note})"]
    if math.isfinite(d_opt) and abs(d_opt) >= 0.05:
        parts.append(
            f"optimistic corner alone **{'+' if d_opt >= 0 else ''}{d_opt:.2f} h** vs expected"
        )
    if math.isfinite(d_con) and abs(d_con) >= 0.05:
        parts.append(
            f"conservative corner alone **{'+' if d_con >= 0 else ''}{d_con:.2f} h** vs expected"
        )
    swing = (
        optimistic_only_h - conservative_only_h
        if math.isfinite(optimistic_only_h) and math.isfinite(conservative_only_h)
        else 0.0
    )
    if abs(swing) >= 0.05:
        parts.append(f"one-at-a-time swing **{swing:.2f} h**")
    if len(parts) == 1:
        parts.append("minor effect on cycle at current spans")
    return " · ".join(parts) + "."


def decompose_cycle_drivers(
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
    expected_h: float,
    alpha_span: float = 0.15,
    tss_span: float = 0.15,
    capture_span: float = 0.05,
    mal_span: float = 0.10,
) -> dict[str, Any]:
    """
    One-at-a-time perturbation: each driver moved to its corner while others stay at expected.

    Returns table rows, ranked narratives, and plot-ready arrays for a tornado-style chart.
    """
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
    expected_kw = dict(
        **_common,
        maldistribution_factor=max(1.0, float(maldistribution_factor)),
        alpha_calibration_factor=max(0.05, min(3.0, float(alpha_calibration_factor))),
        tss_capture_efficiency=max(0.0, min(1.0, float(tss_capture_efficiency))),
        design_tss_mg_l=max(0.1, float(design_tss_mg_l)),
    )

    opt_corners, con_corners = _corner_values(
        alpha_calibration_factor=expected_kw["alpha_calibration_factor"],
        tss_capture_efficiency=expected_kw["tss_capture_efficiency"],
        maldistribution_factor=expected_kw["maldistribution_factor"],
        design_tss_mg_l=expected_kw["design_tss_mg_l"],
        alpha_span=alpha_span,
        tss_span=tss_span,
        capture_span=capture_span,
        mal_span=mal_span,
    )

    span_notes = {
        "design_tss": f"±{tss_span * 100:.0f}% on design TSS",
        "alpha_calibration": f"±{alpha_span * 100:.0f}% on α calibration",
        "tss_capture": f"±{capture_span * 100:.0f}% on capture efficiency",
        "maldistribution": f"+{mal_span * 100:.0f}% on maldistribution (conservative only)",
    }

    rows: list[dict[str, Any]] = []
    for spec in _DRIVER_SPECS:
        did = str(spec["id"])
        o_key = str(spec["optimistic_key"])
        kw_opt = dict(expected_kw)
        kw_opt[o_key] = opt_corners[o_key]
        kw_con = dict(expected_kw)
        kw_con[o_key] = con_corners[o_key]

        h_opt = _run_cycle(**kw_opt)
        h_con = _run_cycle(**kw_con)
        swing = (
            h_opt - h_con
            if math.isfinite(h_opt) and math.isfinite(h_con)
            else 0.0
        )
        d_opt = h_opt - expected_h if math.isfinite(h_opt) and math.isfinite(expected_h) else 0.0
        d_con = h_con - expected_h if math.isfinite(h_con) and math.isfinite(expected_h) else 0.0

        rows.append({
            "driver_id": did,
            "driver": spec["label"],
            "cycle_optimistic_only_h": round(h_opt, 2) if math.isfinite(h_opt) else None,
            "cycle_conservative_only_h": round(h_con, 2) if math.isfinite(h_con) else None,
            "delta_optimistic_h": round(d_opt, 2) if math.isfinite(d_opt) else None,
            "delta_conservative_h": round(d_con, 2) if math.isfinite(d_con) else None,
            "swing_h": round(swing, 2) if math.isfinite(swing) else None,
            "rank_metric": abs(swing) if math.isfinite(swing) else 0.0,
        })

    rows.sort(key=lambda r: float(r.get("rank_metric") or 0.0), reverse=True)

    narratives = [
        _narrative_for_driver(
            str(r["driver"]),
            expected_h,
            float(r["cycle_optimistic_only_h"] or 0),
            float(r["cycle_conservative_only_h"] or 0),
            span_notes.get(str(r["driver_id"]), ""),
        )
        for r in rows
    ]

    labels = [str(r["driver"]) for r in rows]
    plot = {
        "driver_ids": [str(r["driver_id"]) for r in rows],
        "driver_labels": labels,
        "expected_h": round(expected_h, 2) if math.isfinite(expected_h) else None,
        "delta_optimistic_h": [r["delta_optimistic_h"] for r in rows],
        "delta_conservative_h": [r["delta_conservative_h"] for r in rows],
        "swing_h": [r["swing_h"] for r in rows],
        "cycle_optimistic_only_h": [r["cycle_optimistic_only_h"] for r in rows],
        "cycle_conservative_only_h": [r["cycle_conservative_only_h"] for r in rows],
    }

    dominant = rows[0]["driver"] if rows else "—"
    dom_swing = float(rows[0].get("swing_h") or 0.0) if rows else 0.0
    summary = (
        f"Largest one-at-a-time driver at design TSS: **{dominant}** "
        f"(swing ≈ **{dom_swing:.2f} h**). "
        "Corner-case band in the parent envelope may differ — drivers interact."
    )

    return {
        "method": "one_at_a_time_corner_perturbation",
        "drivers": rows,
        "narratives": narratives,
        "summary": summary,
        "plot": plot,
        "perturbation": {
            "alpha_span": alpha_span,
            "tss_span": tss_span,
            "capture_span": capture_span,
            "mal_span": mal_span,
        },
    }
