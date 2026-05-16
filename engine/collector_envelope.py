"""Deterministic BW-flow sweeps on the 1D collector model (optioneering, not CFD)."""

from __future__ import annotations

from typing import Any

from engine.collector_hydraulics import compute_collector_hydraulics, distribution_solver_converged


def build_collector_bw_flow_envelope(
    *,
    compute_kwargs: dict[str, Any],
    reference_q_bw_m3h: float,
    q_low_frac: float = 0.55,
    q_high_frac: float = 1.15,
    n_points: int = 7,
    imbalance_feasible_max_pct: float = 55.0,
) -> dict[str, Any]:
    """
    Re-run ``compute_collector_hydraulics`` at several **total** BW flow rates
    (same geometry, header mode, fluids).

    Returns SI arrays suitable for charts. **Advisory only** — uses the same
    screening 1D physics as the design point (no enrichment / advisories per row).
    """
    inactive: dict[str, Any] = {
        "active": False,
        "method": "deterministic_q_bw_sweep_1d",
        "advisory_only": True,
        "note": "Reference BW flow is zero or sweep disabled — no envelope.",
        "reference_q_bw_m3h": 0.0,
        "q_bw_m3h": [],
        "q_fraction_of_design": [],
        "flow_imbalance_pct": [],
        "header_velocity_max_m_s": [],
        "orifice_velocity_max_m_s": [],
        "orifice_velocity_min_m_s": [],
        "maldistribution_factor_calc": [],
        "distribution_converged": [],
        "feasible": [],
        "sweep_rows": [],
    }

    q_ref = float(reference_q_bw_m3h)
    if q_ref <= 1e-9:
        return inactive

    n_points = max(3, min(25, int(n_points)))
    lo = max(0.05, min(0.98, float(q_low_frac)))
    hi = max(lo + 0.02, min(1.80, float(q_high_frac)))

    qs_set: list[float] = []
    for i in range(n_points):
        frac = lo + (hi - lo) * (i / max(1, n_points - 1))
        qs_set.append(round(q_ref * frac, 6))
    qs_set.append(round(q_ref, 6))
    qs = sorted({q for q in qs_set if q > 1e-9})

    rows: list[dict[str, Any]] = []
    kw = {k: v for k, v in compute_kwargs.items() if k != "q_bw_m3h"}

    for q in qs:
        ch = compute_collector_hydraulics(q_bw_m3h=q, **kw)
        profile = ch.get("profile") or []
        if not profile:
            rows.append({
                "q_bw_m3h": round(q, 4),
                "q_fraction_of_design": round(q / q_ref, 4) if q_ref > 0 else 0.0,
                "flow_imbalance_pct": None,
                "header_velocity_max_m_s": None,
                "orifice_velocity_max_m_s": None,
                "orifice_velocity_min_m_s": None,
                "maldistribution_factor_calc": None,
                "distribution_converged": False,
                "feasible": False,
            })
            continue

        conv = distribution_solver_converged(ch)
        imb = float(ch.get("flow_imbalance_pct") or 0.0)
        mal = float(ch.get("maldistribution_factor_calc") or 1.0)
        hv = float(ch.get("header_velocity_max_m_s") or 0.0)
        ov_max = float(ch.get("orifice_velocity_max_m_s") or 0.0)
        ov_min = float(ch.get("orifice_velocity_min_m_s") or 0.0)
        feasible = conv and imb <= float(imbalance_feasible_max_pct)
        rows.append({
            "q_bw_m3h": round(q, 4),
            "q_fraction_of_design": round(q / q_ref, 4) if q_ref > 0 else 0.0,
            "flow_imbalance_pct": round(imb, 3),
            "header_velocity_max_m_s": round(hv, 4),
            "orifice_velocity_max_m_s": round(ov_max, 4),
            "orifice_velocity_min_m_s": round(ov_min, 4),
            "maldistribution_factor_calc": round(mal, 4),
            "distribution_converged": bool(conv),
            "feasible": bool(feasible),
        })

    def _col(key: str) -> list[Any]:
        return [r.get(key) for r in rows]

    return {
        "active": True,
        "method": "deterministic_q_bw_sweep_1d",
        "advisory_only": True,
        "note": (
            "Each point is an independent 1D manifold solve at the stated **total** filter BW flow. "
            f"Feasible = converged distribution and imbalance ≤ **{imbalance_feasible_max_pct:.0f}%** (screening)."
        ),
        "reference_q_bw_m3h": round(q_ref, 4),
        "q_bw_m3h": [r["q_bw_m3h"] for r in rows],
        "q_fraction_of_design": [r["q_fraction_of_design"] for r in rows],
        "flow_imbalance_pct": _col("flow_imbalance_pct"),
        "header_velocity_max_m_s": _col("header_velocity_max_m_s"),
        "orifice_velocity_max_m_s": _col("orifice_velocity_max_m_s"),
        "orifice_velocity_min_m_s": _col("orifice_velocity_min_m_s"),
        "maldistribution_factor_calc": _col("maldistribution_factor_calc"),
        "distribution_converged": _col("distribution_converged"),
        "feasible": _col("feasible"),
        "sweep_rows": rows,
        "imbalance_feasible_max_pct": float(imbalance_feasible_max_pct),
        "sweep_params": {
            "q_low_frac": lo,
            "q_high_frac": hi,
            "n_points": n_points,
        },
    }
