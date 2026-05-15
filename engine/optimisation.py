"""Constrained design search over ``compute_all`` — single source of truth.

``evaluate_candidate`` / ``optimise_design`` only call ``engine.compute.compute_all``.
Constraints use **N**-scenario LV, minimum EBCT among filterable layers (soft default
floor = 80 % of ``ebct_threshold``), optional dirty-ΔP cap, BW flow, freeboard, and
steel weight. Pass ``constraints={"ebct_min_min": 5.0}`` or ``{"max_dp_dirty_bar": x}``
to tighten defaults.

This is an **MVP grid ranker**, not a global optimiser (no gradients, no MILP).
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from engine.compute import compute_all
from engine.thresholds import layer_ebct_floor_min, layer_lv_cap_m_h

_REL = 1e-6


def _merge(base: dict, patch: dict) -> dict:
    out = copy.deepcopy(base)
    out.update(patch)
    return out


def _merged_constraints(inputs: dict, constraints: Optional[dict]) -> Dict[str, Any]:
    """Resolve limits. ``max_dp_dirty_bar`` = ``None`` ⇒ skip ΔP check (cake model can exceed trigger)."""
    c: Dict[str, Any] = {
        # Per-layer LV / EBCT checks use ``inputs`` + ``computed["base"]`` in ``constraint_check``.
        "max_dp_dirty_bar": None,
        "max_bw_flow_m3h": 1.0e7,
        "min_freeboard_m": 0.05,
        "max_steel_kg": 1.0e12,
    }
    if constraints:
        c.update(constraints)
    return c


def _lv_n_scenario(computed: dict, scenario: str = "N") -> float:
    fc = computed.get("filt_cycles") or {}
    row = fc.get(scenario) or {}
    return float(row.get("lv_m_h", float("nan")))


def _min_ebct_minutes_n(computed: dict) -> float:
    """Minimum EBCT (min) among non-support layers at **N** scenario flow."""
    load_data = computed.get("load_data") or []
    q_n = None
    for x, _nact, q in load_data:
        if x == 0:
            q_n = float(q)
            break
    if q_n is None or q_n <= 0:
        return float("nan")
    base = computed.get("base") or []
    ebcts: List[float] = []
    for b in base:
        if b.get("is_support"):
            continue
        area = float(b.get("Area", 0.0))
        vol = float(b.get("Vol", 0.0))
        if area <= 0.0:
            continue
        ebct = (vol / q_n) * 60.0
        ebcts.append(ebct)
    return min(ebcts) if ebcts else float("nan")


def constraint_check(
    computed: dict,
    inputs: dict,
    constraints: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Check engineering feasibility against **N**-scenario LV / EBCT and plant caps.

    Returns ``{"feasible": bool, "violations": [...], "details": {...}}``.
    """
    violations: List[str] = []
    details: Dict[str, Any] = {}

    iv = computed.get("input_validation") or {}
    if not iv.get("valid", True):
        violations.append("inputs_failed_validation")
        return {"feasible": False, "violations": violations, "details": details}

    mc = _merged_constraints(inputs, constraints)

    lv = _lv_n_scenario(computed, "N")
    details["lv_n_m_h"] = lv
    avg_a = float(computed.get("avg_area", 0.0) or 0.0)
    if not (lv == lv):  # NaN
        violations.append("lv_missing")
    else:
        base = computed.get("base") or []
        worst_v = float("-inf")
        worst_cap = 0.0
        worst_name = ""
        for b in base:
            if b.get("is_support"):
                continue
            area = float(b.get("Area", 0.0))
            if area <= 1e-12:
                continue
            v_layer = lv * (avg_a / area) if area > 0 else float("nan")
            cap = layer_lv_cap_m_h(b, inputs_fallback=inputs)
            if v_layer > worst_v:
                worst_v = v_layer
                worst_cap = cap
                worst_name = str(b.get("Type", "Media"))
            if v_layer > cap + _REL:
                violations.append("lv_exceeds_threshold")
                details["lv_limiting_layer"] = str(b.get("Type", "Media"))
                details["lv_limiting_m_h"] = round(float(v_layer), 3)
                details["lv_limiting_cap_m_h"] = round(float(cap), 3)
                break
        if worst_v > float("-inf"):
            details["lv_worst_layer"] = worst_name
            details["lv_worst_m_h"] = round(worst_v, 3)
            details["lv_worst_cap_m_h"] = round(worst_cap, 3)

    eb = _min_ebct_minutes_n(computed)
    details["min_ebct_min"] = eb
    if not (eb == eb):
        violations.append("ebct_missing")
    else:
        base = computed.get("base") or []
        load_data = computed.get("load_data") or []
        q_n = None
        for x, _nact, q in load_data:
            if x == 0:
                q_n = float(q)
                break
        if q_n is not None and q_n > 0:
            for b in base:
                if b.get("is_support"):
                    continue
                vol = float(b.get("Vol", 0.0))
                eb_layer = (vol / q_n) * 60.0
                floor = layer_ebct_floor_min(b, inputs_fallback=inputs) * 0.80
                if eb_layer < floor - _REL:
                    violations.append("ebct_below_threshold")
                    break

    dp_cap = mc.get("max_dp_dirty_bar")
    if isinstance(dp_cap, (int, float)):
        bw_dp = computed.get("bw_dp") or {}
        dp_dirty = float(bw_dp.get("dp_dirty_bar", 0.0))
        details["dp_dirty_bar"] = dp_dirty
        if dp_dirty > float(dp_cap) + _REL:
            violations.append("dp_dirty_exceeds_cap")
    else:
        details["dp_dirty_bar"] = float((computed.get("bw_dp") or {}).get("dp_dirty_bar", 0.0))

    bw_hyd = computed.get("bw_hyd") or {}
    q_bw = float(bw_hyd.get("q_bw_m3h", 0.0))
    details["q_bw_m3h"] = q_bw
    if q_bw > mc["max_bw_flow_m3h"] + _REL:
        violations.append("bw_flow_exceeds_cap")

    bw_col = computed.get("bw_col") or {}
    fb = float(bw_col.get("freeboard_m", 0.0))
    details["freeboard_m"] = fb
    if fb < mc["min_freeboard_m"] - _REL:
        violations.append("freeboard_insufficient")

    w_tot = float(computed.get("w_total", 0.0))
    details["steel_kg"] = w_tot
    if w_tot > mc["max_steel_kg"] + _REL:
        violations.append("steel_weight_exceeds_cap")

    return {"feasible": len(violations) == 0, "violations": violations, "details": details}


def evaluate_candidate(
    inputs: dict,
    *,
    constraints: Optional[dict] = None,
    include_computed: bool = False,
) -> Dict[str, Any]:
    """Run ``compute_all`` once and return metrics + ``constraint_check``."""
    computed = compute_all(inputs)
    chk = constraint_check(computed, inputs, constraints)
    econ_c = computed.get("econ_capex") or {}
    econ_o = computed.get("econ_opex") or {}
    econ_g = computed.get("econ_carbon") or {}
    metrics = {
        "total_capex_usd": float(econ_c.get("total_capex_usd", 0.0)),
        "total_opex_usd_yr": float(econ_o.get("total_opex_usd_yr", 0.0)),
        "steel_kg": float(computed.get("w_total", 0.0)),
        "co2_lifecycle_kg": float(econ_g.get("co2_lifecycle_kg", 0.0)),
    }
    summary = {
        "n_filters": inputs.get("n_filters"),
        "nominal_id": inputs.get("nominal_id"),
        "total_length": inputs.get("total_length"),
    }
    out: Dict[str, Any] = {**chk, "metrics": metrics, "summary": summary}
    if include_computed:
        out["computed"] = computed
    return out


_OBJECTIVE_KEYS = {
    "capex": "total_capex_usd",
    "opex": "total_opex_usd_yr",
    "steel": "steel_kg",
    "carbon": "co2_lifecycle_kg",
}


def optimise_design(
    base_inputs: dict,
    candidate_patches: List[dict],
    *,
    objective: str = "capex",
    top_k: int = 5,
    constraints: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Evaluate each ``patch`` merged into ``base_inputs``, keep **feasible** designs,
    sort by ``objective`` ascending, return top ``top_k`` rows.

    ``objective`` ∈ ``{"capex", "opex", "steel", "carbon"}``.
    """
    if objective not in _OBJECTIVE_KEYS:
        raise ValueError(f"objective must be one of {sorted(_OBJECTIVE_KEYS)}")
    mkey = _OBJECTIVE_KEYS[objective]

    rows: List[Dict[str, Any]] = []
    for patch in candidate_patches:
        cand = _merge(base_inputs, patch)
        ev = evaluate_candidate(cand, constraints=constraints, include_computed=False)
        rows.append({"patch": patch, **ev})

    feasible = [r for r in rows if r["feasible"]]
    feasible.sort(key=lambda r: float(r["metrics"][mkey]))
    top = feasible[: max(1, int(top_k))]

    return {
        "objective": objective,
        "top": top,
        "ranked": top,
        "best": top[0] if top else None,
        "all": rows,
        "evaluated": len(rows),
        "feasible_count": len(feasible),
        "n_evaluated": len(rows),
        "n_feasible": len(feasible),
        "pareto_capex_opex": pareto_front_min2(
            feasible, "total_capex_usd", "total_opex_usd_yr",
        ),
    }


def pareto_front_min2(
    feasible_rows: List[Dict[str, Any]],
    key_a: str,
    key_b: str,
) -> List[Dict[str, Any]]:
    """
    Non-dominated subset for two **minimize** metrics on ``row["metrics"]``.

    Row *i* is dominated if another feasible row has both metrics ≤ *i*'s with at least one strict.
    """
    rows = [r for r in feasible_rows if r.get("feasible")]
    if len(rows) < 2:
        return list(rows)

    def mget(r: Dict[str, Any], k: str) -> float:
        return float((r.get("metrics") or {}).get(k, 0.0))

    nd: List[Dict[str, Any]] = []
    for r in rows:
        a, b = mget(r, key_a), mget(r, key_b)
        dominated = False
        for o in rows:
            if o is r:
                continue
            oa, ob = mget(o, key_a), mget(o, key_b)
            if (oa <= a and ob <= b) and (oa < a or ob < b):
                dominated = True
                break
        if not dominated:
            nd.append(r)
    nd.sort(key=
        lambda r: (mget(r, key_a), mget(r, key_b)))
    return nd


__all__ = [
    "constraint_check",
    "evaluate_candidate",
    "optimise_design",
    "pareto_front_min2",
]
