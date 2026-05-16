"""
Design-to-target search — rank candidates that meet explicit caps.

Uses ``evaluate_candidate`` / ``constraint_check`` from ``optimisation.py`` only;
no second physics path. Targets: dirty ΔP, LCOW, BW flow, optional CAPEX ceiling.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

from engine.optimisation import _merge, constraint_check, evaluate_candidate

_REL = 1e-6

TARGET_KEYS = (
    "max_dp_dirty_bar",
    "max_lcow_usd_m3",
    "max_q_bw_m3h",
    "max_capex_usd",
)


def normalize_targets(targets: Optional[dict]) -> Dict[str, Optional[float]]:
    """Return active targets only (SI). None = not enforced."""
    raw = targets or {}
    out: Dict[str, Optional[float]] = {k: None for k in TARGET_KEYS}
    for key in TARGET_KEYS:
        v = raw.get(key)
        if v is None or v == "":
            continue
        try:
            fv = float(v)
            if fv > 0 or key == "max_dp_dirty_bar":
                out[key] = fv
        except (TypeError, ValueError):
            continue
    return out


def targets_active(targets: Dict[str, Optional[float]]) -> bool:
    return any(v is not None for v in targets.values())


def metrics_from_computed(computed: dict) -> Dict[str, float]:
    econ_c = computed.get("econ_capex") or {}
    econ_b = computed.get("econ_bench") or {}
    bw_dp = computed.get("bw_dp") or {}
    bw_hyd = computed.get("bw_hyd") or {}
    return {
        "dp_dirty_bar": float(bw_dp.get("dp_dirty_bar", 0.0)),
        "lcow_usd_m3": float(econ_b.get("lcow", 0.0)),
        "q_bw_m3h": float(bw_hyd.get("q_bw_m3h", 0.0)),
        "total_capex_usd": float(econ_c.get("total_capex_usd", 0.0)),
        "total_opex_usd_yr": float((computed.get("econ_opex") or {}).get("total_opex_usd_yr", 0.0)),
        "steel_kg": float(computed.get("w_total", 0.0)),
    }


def target_violations(
    metrics: Dict[str, float],
    targets: Dict[str, Optional[float]],
) -> List[str]:
    violations: List[str] = []
    cap = targets.get("max_dp_dirty_bar")
    if cap is not None and metrics.get("dp_dirty_bar", 0.0) > float(cap) + _REL:
        violations.append("target_dp_dirty_exceeded")
    cap = targets.get("max_lcow_usd_m3")
    if cap is not None and metrics.get("lcow_usd_m3", 0.0) > float(cap) + _REL:
        violations.append("target_lcow_exceeded")
    cap = targets.get("max_q_bw_m3h")
    if cap is not None and metrics.get("q_bw_m3h", 0.0) > float(cap) + _REL:
        violations.append("target_q_bw_exceeded")
    cap = targets.get("max_capex_usd")
    if cap is not None and metrics.get("total_capex_usd", 0.0) > float(cap) + _REL:
        violations.append("target_capex_exceeded")
    return violations


def constraints_from_targets(targets: Dict[str, Optional[float]]) -> Dict[str, Any]:
    """Engineering feasibility constraints aligned with active targets."""
    c: Dict[str, Any] = {
        "max_dp_dirty_bar": None,
        "max_bw_flow_m3h": 1.0e7,
    }
    if targets.get("max_dp_dirty_bar") is not None:
        c["max_dp_dirty_bar"] = targets["max_dp_dirty_bar"]
    if targets.get("max_q_bw_m3h") is not None:
        c["max_bw_flow_m3h"] = targets["max_q_bw_m3h"]
    return c


def expand_candidate_patches(
    base_inputs: dict,
    grid_spec: dict,
) -> List[dict]:
    """Cartesian grid over n_filters × optional nominal_id × bw_velocity."""
    nf_list = grid_spec.get("n_filters")
    if not nf_list:
        nf = int(base_inputs.get("n_filters", 6))
        nf_list = list(range(max(4, nf - 3), nf + 4))
    id_list = grid_spec.get("nominal_id") or []
    bw_list = grid_spec.get("bw_velocity") or []
    ids = [float(x) for x in id_list] if id_list else [float(base_inputs.get("nominal_id", 3.0))]
    bws = [float(x) for x in bw_list] if bw_list else [float(base_inputs.get("bw_velocity", 30.0))]
    patches: List[dict] = []
    for nf in nf_list:
        for nid in ids:
            for bw in bws:
                patches.append({
                    "n_filters": int(nf),
                    "nominal_id": nid,
                    "bw_velocity": bw,
                })
    return patches


def evaluate_candidate_targets(
    inputs: dict,
    targets: Dict[str, Optional[float]],
    *,
    constraints: Optional[dict] = None,
) -> Dict[str, Any]:
    """``evaluate_candidate`` plus target metrics / violations (no computed blob)."""
    merged_c = constraints if constraints is not None else constraints_from_targets(targets)
    ev = evaluate_candidate(inputs, constraints=merged_c, include_computed=True)
    comp = ev.pop("computed", {}) or {}
    m = metrics_from_computed(comp)
    ev["metrics"].update({
        "lcow_usd_m3": m["lcow_usd_m3"],
        "dp_dirty_bar": m["dp_dirty_bar"],
        "q_bw_m3h": m["q_bw_m3h"],
    })
    tv = target_violations(m, targets)
    ev["target_violations"] = tv
    ev["meets_targets"] = len(tv) == 0
    ev["target_metrics"] = m
    return ev


def _rank_score(metrics: Dict[str, float], targets: Dict[str, Optional[float]]) -> float:
    """Lower is better — sum normalized slack toward each active cap."""
    score = 0.0
    if targets.get("max_lcow_usd_m3"):
        cap = float(targets["max_lcow_usd_m3"])
        score += metrics.get("lcow_usd_m3", 0.0) / max(cap, 1e-9)
    if targets.get("max_dp_dirty_bar"):
        cap = float(targets["max_dp_dirty_bar"])
        score += metrics.get("dp_dirty_bar", 0.0) / max(cap, 1e-9)
    if targets.get("max_q_bw_m3h"):
        cap = float(targets["max_q_bw_m3h"])
        score += metrics.get("q_bw_m3h", 0.0) / max(cap, 1e-9)
    if targets.get("max_capex_usd"):
        cap = float(targets["max_capex_usd"])
        score += metrics.get("total_capex_usd", 0.0) / max(cap, 1e-9)
    score += metrics.get("total_capex_usd", 0.0) / 1.0e12
    return score


def search_design_targets(
    base_inputs: dict,
    targets: Optional[dict],
    grid_spec: Optional[dict] = None,
    *,
    top_k: int = 5,
) -> Dict[str, Any]:
    """
    Grid search merged patches; return feasible designs that meet all active targets.
    """
    tnorm = normalize_targets(targets)
    if not targets_active(tnorm):
        return {
            "enabled": False,
            "note": "No targets set — enable at least one cap.",
        }

    spec = dict(grid_spec or {})
    patches = expand_candidate_patches(base_inputs, spec)
    merged_c = constraints_from_targets(tnorm)

    rows: List[Dict[str, Any]] = []
    for patch in patches:
        cand = _merge(base_inputs, patch)
        ev = evaluate_candidate_targets(cand, tnorm, constraints=merged_c)
        rows.append({"patch": patch, **ev})

    meeting = [
        r for r in rows
        if r.get("feasible") and r.get("meets_targets")
    ]
    meeting.sort(key=lambda r: _rank_score(r.get("target_metrics") or r.get("metrics") or {}, tnorm))
    top = meeting[: max(1, int(top_k))]

    return {
        "enabled": True,
        "targets": {k: v for k, v in tnorm.items() if v is not None},
        "evaluated": len(rows),
        "feasible_count": sum(1 for r in rows if r.get("feasible")),
        "meets_targets_count": len(meeting),
        "ranked": top,
        "best": top[0] if top else None,
        "all": rows,
        "top_k": int(top_k),
        "assumption_ids": ["ASM-DTARGET-01"],
        "note": (
            "Grid ranker via compute_all only; Apply patches explicitly in UI. "
            "LCOW from econ_bench; dirty ΔP from bw_dp."
        ),
    }


def build_design_targets_summary(
    inputs: dict,
    computed: dict,
    targets: Optional[dict] = None,
) -> Dict[str, Any]:
    """
    Lightweight post-compute snapshot for current design (no grid re-run).
    """
    tnorm = normalize_targets(targets)
    if not targets_active(tnorm):
        return {
            "enabled": False,
            "note": "Set targets in Assessment → Design to target to evaluate.",
        }

    chk = constraint_check(computed, inputs, constraints_from_targets(tnorm))
    m = metrics_from_computed(computed)
    tv = target_violations(m, tnorm)

    return {
        "enabled": True,
        "targets": {k: v for k, v in tnorm.items() if v is not None},
        "baseline": {
            "patch": {},
            "feasible": bool(chk.get("feasible")),
            "engineering_violations": list(chk.get("violations") or []),
            "meets_targets": len(tv) == 0,
            "target_violations": tv,
            "metrics": m,
            "details": chk.get("details") or {},
        },
        "search": None,
        "assumption_ids": ["ASM-DTARGET-01"],
        "note": (
            "Baseline uses current computed bundle. Run search in Assessment for ranked alternatives."
        ),
    }


def targets_from_inputs(inputs: dict) -> Dict[str, Optional[float]]:
    """Optional persisted targets on ``inputs`` (SI)."""
    return normalize_targets({
        "max_dp_dirty_bar": inputs.get("target_max_dp_dirty_bar"),
        "max_lcow_usd_m3": inputs.get("target_max_lcow_usd_m3"),
        "max_q_bw_m3h": inputs.get("target_max_q_bw_m3h"),
        "max_capex_usd": inputs.get("target_max_capex_usd"),
    })
