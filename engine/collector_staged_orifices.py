"""
Advisory **staged orifice** sizing from the current 1D collector solve.

Uses **frozen** per-hole flows from ``orifice_network`` (same split model as 1A/1B).
Area is repartitioned so ideal jets would share one target velocity on each lateral;
diameters are then **snapped** to **K contiguous manufacturable bands** (constant Ø per band).

Does **not** re-run the lateral distribution solver — rebalancing with true variable
perforation loss is future work. Label outputs ``advisory_only``.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

_WEDGE_HINTS = ("wedge", "slot")


def _f(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _is_wedge_construction(construction: str) -> bool:
    c = str(construction or "").lower()
    return any(h in c for h in _WEDGE_HINTS)


def recommend_staged_orifice_schedule(
    collector_hyd: dict[str, Any] | None,
    *,
    n_groups: int = 2,
    d_step_mm: float = 0.5,
    min_d_mm: float = 3.0,
    max_d_mm: float = 40.0,
) -> dict[str, Any]:
    """
    Build a drill schedule from ``collector_hyd["orifice_network"]``.

    Parameters
    ----------
    n_groups :
        Number of **contiguous** Ø bands per lateral (2–4). Other values → inactive.
    """
    inactive: dict[str, Any] = {
        "active": False,
        "advisory_only": True,
        "method": "equal_jet_velocity_k_band_snap",
        "note": None,
        "n_groups": int(n_groups),
        "groups": [],
        "baseline_orifice_d_mm": 0.0,
        "estimated_velocity_spread_baseline_m_s": None,
        "estimated_velocity_spread_after_snap_m_s": None,
    }

    if not collector_hyd or not isinstance(collector_hyd, dict):
        inactive["note"] = "No collector hydraulics."
        return inactive

    construction = str(collector_hyd.get("lateral_construction") or "")
    if _is_wedge_construction(construction):
        inactive["note"] = (
            "Wedge / slot laterals — staging is **OEM slot layout**, not drilled hole Ø bands. "
            "Use supplier open-area tools."
        )
        return inactive

    net = list(collector_hyd.get("orifice_network") or [])
    if not net:
        inactive["note"] = "No orifice_network — enable distributor inputs."
        return inactive

    n_groups = int(n_groups)
    if n_groups < 2 or n_groups > 4:
        inactive["note"] = "Set **2–4** staged Ø groups to generate a schedule."
        inactive["n_groups"] = n_groups
        return inactive

    d0_mm = _f(collector_hyd.get("lateral_orifice_d_mm"), 0.0)
    if d0_mm <= 0:
        inactive["note"] = "Baseline perforation Ø is zero — set lateral orifice diameter first."
        return inactive

    by_lat: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in net:
        li = int(row.get("lateral_index") or 0)
        if li <= 0:
            continue
        by_lat[li].append(dict(row))

    if not by_lat:
        inactive["note"] = "Orifice network has no lateral_index rows."
        return inactive

    area0_m2 = math.pi * (d0_mm / 1000.0 / 2.0) ** 2
    if area0_m2 <= 0:
        return inactive

    # Baseline velocity spread (from network)
    v_base = [_f(r.get("velocity_m_s")) for r in net if _f(r.get("velocity_m_s")) > 0]
    v_spread_b = None
    if v_base:
        v_spread_b = {"min_m_s": round(min(v_base), 3), "max_m_s": round(max(v_base), 3)}

    groups_out: list[dict[str, Any]] = []
    per_hole_snap: list[dict[str, Any]] = []

    for li in sorted(by_lat.keys()):
        rows = sorted(by_lat[li], key=lambda r: int(r.get("hole_index") or 0))
        n_h = len(rows)
        if n_h < n_groups:
            continue

        q_m3s = [_f(r.get("flow_m3h")) / 3600.0 for r in rows]
        q_tot = sum(q_m3s)
        if q_tot <= 1e-12:
            continue

        n = len(q_m3s)
        a_tot = n * area0_m2
        d_ideal_mm: list[float] = []
        for qh in q_m3s:
            a_j = a_tot * (qh / q_tot)
            d_m = 2.0 * math.sqrt(max(a_j, 1e-12) / math.pi)
            d_ideal_mm.append(d_m * 1000.0)

        step = max(0.1, float(d_step_mm))
        lo_d = max(min_d_mm, min(d_ideal_mm) * 0.85)
        hi_d = min(max_d_mm, max(d_ideal_mm) * 1.15)

        def _snap(x: float) -> float:
            s = round(x / step) * step
            return max(lo_d, min(hi_d, s))

        # K contiguous index bands → one representative diameter per band (mean of ideal in band)
        band_edges = [round(i * n / n_groups) for i in range(n_groups + 1)]
        band_edges[-1] = n
        d_band_assigned: list[float] = [0.0] * n
        for b in range(n_groups):
            i0, i1 = int(band_edges[b]), int(band_edges[b + 1])
            if i1 <= i0:
                continue
            chunk = d_ideal_mm[i0:i1]
            d_rep = _snap(sum(chunk) / len(chunk))
            for ii in range(i0, i1):
                d_band_assigned[ii] = d_rep
            hj0 = int(rows[i0].get("hole_index") or i0 + 1)
            hj1 = int(rows[i1 - 1].get("hole_index") or i1)
            groups_out.append({
                "lateral_index": li,
                "hole_index_from": hj0,
                "hole_index_to": hj1,
                "band_index": b + 1,
                "d_mm_baseline": round(d0_mm, 2),
                "d_mm_ideal_mean_in_band_mm": round(sum(chunk) / len(chunk), 2),
                "d_mm_recommended": round(d_rep, 2),
            })

        for idx, r in enumerate(rows):
            d_mm = d_band_assigned[idx]
            qh = q_m3s[idx]
            a_m2 = math.pi * (d_mm / 1000.0 / 2.0) ** 2
            v_est = qh / a_m2 if a_m2 > 0 else 0.0
            per_hole_snap.append({
                "lateral_index": li,
                "hole_index": int(r.get("hole_index") or idx + 1),
                "flow_m3h": round(_f(r.get("flow_m3h")), 4),
                "d_mm_baseline": round(d0_mm, 2),
                "d_mm_recommended": round(d_mm, 2),
                "velocity_baseline_m_s": round(_f(r.get("velocity_m_s")), 4),
                "velocity_estimated_after_snap_m_s": round(v_est, 4),
            })

    if not groups_out:
        inactive["note"] = "Could not form bands (too few holes per lateral?)."
        return inactive

    v_snap = [_f(x.get("velocity_estimated_after_snap_m_s")) for x in per_hole_snap if x]
    v_spread_a = None
    if v_snap:
        v_spread_a = {"min_m_s": round(min(v_snap), 3), "max_m_s": round(max(v_snap), 3)}

    notes = [
        "Ideal Ø on each lateral assumes **frozen** per-hole split from the 1D model; "
        "equal jet speed with **same total open area** as **n × baseline Ø**.",
        "Snapped schedule uses **contiguous index bands** along each lateral (manufacturing-friendly).",
        "After field drilling, **maldistribution** should be re-checked (this engine does not auto re-solve 1B).",
    ]

    return {
        "active": True,
        "advisory_only": True,
        "method": "equal_jet_velocity_k_band_snap",
        "note": None,
        "n_groups": n_groups,
        "baseline_orifice_d_mm": round(d0_mm, 2),
        "groups": groups_out,
        "per_hole": per_hole_snap,
        "estimated_velocity_spread_baseline_m_s": v_spread_b,
        "estimated_velocity_spread_after_snap_m_s": v_spread_a,
        "notes": notes,
    }
