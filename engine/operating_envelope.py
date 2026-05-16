"""
Operating envelope map — LV × EBCT feasibility grid (screening / advisory).

Classifies hypothetical (LV, EBCT) pairs against per-layer thresholds, overlays
redundancy scenario operating points from ``load_data`` + ``base``.
"""
from __future__ import annotations

import math
from typing import Any, List, Optional

from engine.compute import ebct_severity_classify, lv_severity_classify
from engine.thresholds import layer_ebct_floor_min, layer_lv_cap_m_h

_SEV_RANK = {"": 0, None: 0, "advisory": 1, "warning": 2, "critical": 3}
_REGION_BY_RANK = {0: "stable", 1: "marginal", 2: "elevated", 3: "critical"}
_RANK_BY_REGION = {v: k for k, v in _REGION_BY_RANK.items()}


def _cell_worst_rank(
    lv_m_h: float,
    ebct_min: float,
    base: List[dict],
    *,
    inputs_fallback: Optional[dict] = None,
) -> int:
    """Worst severity rank across non-support layers at hypothetical (LV, EBCT)."""
    worst = 0
    for b in base:
        if not isinstance(b, dict) or b.get("is_support"):
            continue
        cap = layer_lv_cap_m_h(b, inputs_fallback=inputs_fallback)
        floor = layer_ebct_floor_min(b, inputs_fallback=inputs_fallback)
        for sev in (
            lv_severity_classify(float(lv_m_h), cap),
            ebct_severity_classify(float(ebct_min), floor),
        ):
            worst = max(worst, _SEV_RANK.get(sev, 0))
    return worst


def _rank_to_region(rank: int) -> str:
    return _REGION_BY_RANK.get(int(rank), "stable")


def _scenario_label(x: int) -> str:
    return "N" if x == 0 else f"N-{x}"


def _operating_point_at_q(
    q_m3h: float,
    base: List[dict],
    avg_area_m2: float,
    *,
    inputs_fallback: Optional[dict] = None,
) -> Optional[dict[str, Any]]:
    if q_m3h <= 1e-9 or avg_area_m2 <= 1e-9:
        return None
    lv = q_m3h / avg_area_m2
    ebct_min = float("inf")
    worst_layer = ""
    for b in base:
        if not isinstance(b, dict) or b.get("is_support"):
            continue
        area = float(b.get("Area", 0.0) or 0.0)
        vol = float(b.get("Vol", 0.0) or 0.0)
        if area <= 1e-12:
            continue
        e = (vol / q_m3h) * 60.0
        if e < ebct_min:
            ebct_min = e
            worst_layer = str(b.get("Layer") or b.get("name") or "")
    if not math.isfinite(ebct_min):
        return None
    rank = _cell_worst_rank(lv, ebct_min, base, inputs_fallback=inputs_fallback)
    return {
        "lv_m_h": round(lv, 4),
        "ebct_min_min": round(ebct_min, 4),
        "region": _rank_to_region(rank),
        "severity_rank": rank,
        "worst_layer": worst_layer,
        "q_m3h": round(q_m3h, 4),
    }


def build_operating_envelope(
    inputs: dict,
    computed: dict,
    *,
    n_lv: int = 28,
    n_ebct: int = 28,
) -> dict[str, Any]:
    """
    Build ``computed["operating_envelope"]`` — SI throughout.

    Grid uses plant LV (q / avg_area) vs bottleneck EBCT (min over layers at that q).
  Hypothetical grid cells test LV and EBCT independently against layer thresholds.
    """
    base = computed.get("base") or []
    load_data = computed.get("load_data") or []
    avg_area = float(computed.get("avg_area") or 0.0)
    redundancy = int(inputs.get("redundancy") or 0)

    if not base or avg_area <= 1e-9:
        return {
            "enabled": False,
            "note": "No media geometry — operating envelope map not available.",
        }

    caps: List[float] = []
    floors: List[float] = []
    for b in base:
        if not isinstance(b, dict) or b.get("is_support"):
            continue
        caps.append(layer_lv_cap_m_h(b, inputs_fallback=inputs))
        floors.append(layer_ebct_floor_min(b, inputs_fallback=inputs))

    if not caps or not floors:
        return {
            "enabled": False,
            "note": "No non-support layers — envelope map skipped.",
        }

    lv_cap = max(caps)
    ebct_floor = min(floors)

    scenario_points: List[dict[str, Any]] = []
    lv_ops: List[float] = []
    ebct_ops: List[float] = []
    for x, _nact, q in load_data:
        pt = _operating_point_at_q(
            float(q), base, avg_area, inputs_fallback=inputs
        )
        if pt is None:
            scenario_points.append({
                "scenario": _scenario_label(int(x)),
                "lv_m_h": None,
                "ebct_min_min": None,
                "region": "not_evaluated",
                "severity_rank": -1,
                "q_m3h": float(q),
            })
            continue
        pt["scenario"] = _scenario_label(int(x))
        scenario_points.append(pt)
        lv_ops.append(pt["lv_m_h"])
        ebct_ops.append(pt["ebct_min_min"])

    lv_hi = max(lv_cap * 1.25, max(lv_ops) * 1.15 if lv_ops else lv_cap * 1.1, lv_cap)
    lv_lo = 0.0
    ebct_hi = max(
        ebct_floor * 2.5,
        max(ebct_ops) * 1.25 if ebct_ops else ebct_floor * 2.0,
        ebct_floor * 1.5,
    )
    ebct_lo = max(0.0, ebct_floor * 0.35)

    n_lv = max(int(n_lv), 8)
    n_ebct = max(int(n_ebct), 8)
    lv_axis = [lv_lo + (lv_hi - lv_lo) * i / (n_lv - 1) for i in range(n_lv)]
    ebct_axis = [ebct_lo + (ebct_hi - ebct_lo) * j / (n_ebct - 1) for j in range(n_ebct)]

    region_matrix: List[List[str]] = []
    rank_matrix: List[List[int]] = []
    for eb in ebct_axis:
        row_r: List[str] = []
        row_k: List[int] = []
        for lv in lv_axis:
            rk = _cell_worst_rank(lv, eb, base, inputs_fallback=inputs)
            row_r.append(_rank_to_region(rk))
            row_k.append(rk)
        region_matrix.append(row_r)
        rank_matrix.append(row_k)

    return {
        "enabled": True,
        "method": "lv_ebct_grid_v1",
        "lv_axis_m_h": [round(v, 4) for v in lv_axis],
        "ebct_axis_min": [round(v, 4) for v in ebct_axis],
        "region_matrix": region_matrix,
        "severity_rank_matrix": rank_matrix,
        "lv_cap_reference_m_h": round(lv_cap, 4),
        "ebct_floor_reference_min": round(ebct_floor, 4),
        "scenario_points": scenario_points,
        "redundancy": redundancy,
        "n_scenarios": len(scenario_points),
        "assumption_ids": ["ASM-ENV-01"],
        "note": (
            "2D screening map: plant LV (q/avg chordal area) vs minimum layer EBCT at that flow. "
            "Grid cells test LV and EBCT against per-layer thresholds independently — not a coupled "
            "RTD model. Scenario markers use actual load_data flows."
        ),
    }
