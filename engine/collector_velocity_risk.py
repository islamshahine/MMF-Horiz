"""Advisory velocity screening for internal BW collector (1D model outputs only).

Erosion, plugging, and fines narratives are **heuristic** — not wear-rate physics.
Thresholds are aligned with ``collector_hydraulics`` screening flags where possible.
"""
from __future__ import annotations

import math
from typing import Any

# Keep in sync with collector_hydraulics intent (header warning ≈ 3 m/s).
HEADER_V_ADVISORY_M_S = 2.0
HEADER_V_WARNING_M_S = 3.0

# Drilled perforation nominal ceiling before strong advisory (m/s, liquid).
ORIFICE_V_WARNING_DRILLED_M_S = 5.0
ORIFICE_V_CRITICAL_M_S = 8.0

# Lateral riser / pipe axial velocity (not orifice jet).
LATERAL_V_ADVISORY_M_S = 2.5
LATERAL_V_WARNING_M_S = 3.5

IMBALANCE_SAND_ADVISORY_PCT = 22.0
SPREAD_PLUGGING_RATIO = 2.5


def _f(x: Any, default: float = 0.0) -> float:
    try:
        v = float(x)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _max_profile_row(
    profile: list[dict[str, Any]], key: str
) -> tuple[float, dict[str, Any] | None]:
    best = 0.0
    best_row: dict[str, Any] | None = None
    for row in profile:
        v = _f(row.get(key))
        if v > best:
            best = v
            best_row = row
    return best, best_row


def analyse_collector_velocity_risk(
    collector_hyd: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Post-process ``computed["collector_hyd"]`` velocities for UI / traceability.

    Returns SI velocities only; all narrative keys are advisory.
    """
    empty: dict[str, Any] = {
        "method": "advisory_velocity_screening_1d",
        "advisory_only": True,
        "active": False,
        "note": "No collector hydraulics — enable distributor inputs to populate profile.",
        "severity_score": 100,
        "grade": "—",
        "header_velocity_max_m_s": 0.0,
        "lateral_velocity_max_m_s": 0.0,
        "orifice_velocity_max_m_s": 0.0,
        "orifice_velocity_min_m_s": 0.0,
        "flow_imbalance_pct": 0.0,
        "orifice_velocity_ratio": None,
        "hotspots": [],
        "findings": [],
        "plugging_hint": None,
        "sand_carryover_hint": None,
        "limits_reference_si": {
            "header_advisory_m_s": HEADER_V_ADVISORY_M_S,
            "header_warning_m_s": HEADER_V_WARNING_M_S,
            "lateral_advisory_m_s": LATERAL_V_ADVISORY_M_S,
            "lateral_warning_m_s": LATERAL_V_WARNING_M_S,
            "orifice_warning_drilled_m_s": ORIFICE_V_WARNING_DRILLED_M_S,
        },
    }

    if not collector_hyd or not isinstance(collector_hyd, dict):
        return empty

    profile = collector_hyd.get("profile") or []
    if not profile:
        out = dict(empty)
        out["note"] = "Collector hydraulics has no profile[] — check inputs / BW flow."
        return out

    h_max, h_row = _max_profile_row(profile, "header_velocity_m_s")
    lat_max, lat_row = _max_profile_row(profile, "lateral_velocity_m_s")
    orf_max, orf_row = _max_profile_row(profile, "orifice_velocity_m_s")

    orf_min = _f(collector_hyd.get("orifice_velocity_min_m_s"))
    if orf_min <= 0 and profile:
        vmins = [_f(r.get("orifice_velocity_m_s")) for r in profile if _f(r.get("orifice_velocity_m_s")) > 1e-9]
        orf_min = min(vmins) if vmins else 0.0

    imb = _f(collector_hyd.get("flow_imbalance_pct"))
    target_v = _f(collector_hyd.get("target_opening_velocity_m_s"), 1.0)
    construction = str(collector_hyd.get("lateral_construction") or "")
    is_wedge = "wedge" in construction.lower()

    orifice_warn = target_v * 1.4 if is_wedge else max(ORIFICE_V_WARNING_DRILLED_M_S, target_v * 1.35)

    ratio = None
    if orf_max > 1e-9 and orf_min > 1e-9:
        ratio = orf_max / orf_min

    findings: list[dict[str, str]] = []
    hotspots: list[dict[str, Any]] = []

    def _hot(zone: str, *, m_s: float, detail: str, row: dict[str, Any] | None, severity: str) -> None:
        li = int(row.get("lateral_index", 0)) if row else 0
        st = _f(row.get("station_m")) if row else 0.0
        hotspots.append({
            "zone": zone,
            "severity": severity,
            "velocity_m_s": round(m_s, 4),
            "lateral_index": li,
            "station_m": round(st, 4) if st else None,
            "detail": detail,
        })

    # Header
    h_sev = "ok"
    if h_max >= HEADER_V_WARNING_M_S:
        h_sev = "warning"
        findings.append({
            "severity": "warning",
            "topic": "Internal header velocity",
            "detail": (
                f"Peak header velocity **{h_max:.2f} m/s** reaches the 1A screening limit "
                f"({HEADER_V_WARNING_M_S:.1f} m/s) — larger header ID or fewer laterals may help."
            ),
        })
        _hot("header", m_s=h_max, detail="Peak along header ladder", row=h_row, severity="warning")
    elif h_max >= HEADER_V_ADVISORY_M_S:
        h_sev = "advisory"
        findings.append({
            "severity": "advisory",
            "topic": "Internal header velocity",
            "detail": (
                f"Header velocity up to **{h_max:.2f} m/s** (advisory **≥ {HEADER_V_ADVISORY_M_S:.1f} m/s**) — "
                "confirm acceptable for material and internals supplier practice."
            ),
        })
        _hot("header", m_s=h_max, detail="Elevated header run", row=h_row, severity="advisory")

    # Lateral pipe
    lat_sev = "ok"
    if lat_max >= LATERAL_V_WARNING_M_S:
        lat_sev = "warning"
        findings.append({
            "severity": "warning",
            "topic": "Internal lateral velocity",
            "detail": (
                f"Peak lateral pipe velocity **{lat_max:.2f} m/s** exceeds **{LATERAL_V_WARNING_M_S:.1f} m/s** "
                "heuristic — verify pressure drop and erosion on the riser, not only orifices."
            ),
        })
        _hot("lateral_pipe", m_s=lat_max, detail="Lateral trunk / riser", row=lat_row, severity="warning")
    elif lat_max >= LATERAL_V_ADVISORY_M_S:
        lat_sev = "advisory"
        findings.append({
            "severity": "advisory",
            "topic": "Internal lateral velocity",
            "detail": (
                f"Lateral pipe velocity up to **{lat_max:.2f} m/s** — watch coupling to orifice jet targets."
            ),
        })
        _hot("lateral_pipe", m_s=lat_max, detail="Lateral trunk", row=lat_row, severity="advisory")

    # Orifice / slot
    o_sev = "ok"
    if orf_max >= ORIFICE_V_CRITICAL_M_S and not is_wedge:
        o_sev = "warning"
        findings.append({
            "severity": "warning",
            "topic": "Orifice velocity",
            "detail": (
                f"Peak orifice jet **{orf_max:.2f} m/s** exceeds **{ORIFICE_V_CRITICAL_M_S:.0f} m/s** "
                "bracket — review drilling pattern, open area, and supplier limits."
            ),
        })
    elif orf_max >= orifice_warn:
        o_sev = "warning" if orf_max >= ORIFICE_V_WARNING_DRILLED_M_S or orf_max >= target_v * 1.5 else "advisory"
        findings.append({
            "severity": o_sev,
            "topic": "Orifice / slot velocity",
            "detail": (
                f"Opening velocity up to **{orf_max:.2f} m/s** vs target **{target_v:.2f} m/s** "
                f"({'wedge / slot' if is_wedge else 'drilled'} model). "
                "Check erosion screens and distribution assumptions."
            ),
        })
    elif orf_max >= target_v * 1.12:
        o_sev = "advisory"
        findings.append({
            "severity": "advisory",
            "topic": "Orifice / slot velocity",
            "detail": (
                f"Opening velocity marginally above target (**{orf_max:.2f}** vs **{target_v:.2f} m/s**)."
            ),
        })

    if o_sev != "ok":
        _hot(
            "orifice",
            m_s=orf_max,
            detail="Peak opening / slot jet",
            row=orf_row,
            severity=o_sev,
        )

    plugging_hint = None
    if ratio is not None and ratio >= SPREAD_PLUGGING_RATIO and len(profile) >= 2:
        plugging_hint = (
            f"Orifice velocity ratio max/min ≈ **{ratio:.1f}** — **fines may accumulate in low‑velocity holes** "
            "(advisory; validate with operating experience)."
        )
        findings.append({
            "severity": "advisory",
            "topic": "Orifice velocity spread",
            "detail": plugging_hint,
        })

    sand_carryover_hint = None
    if imb >= IMBALANCE_SAND_ADVISORY_PCT and orf_max >= target_v * 1.15:
        sand_carryover_hint = (
            "**High lateral imbalance** with **strong terminal jets** can increase carryover risk during BW "
            "(advisory screening only)."
        )
        findings.append({
            "severity": "advisory",
            "topic": "Fines / carryover (screening)",
            "detail": sand_carryover_hint,
        })

    # Hole-level hotspots from orifice_network (top jets)
    net = list(collector_hyd.get("orifice_network") or [])
    if net:
        sorted_holes = sorted(net, key=lambda r: _f(r.get("velocity_m_s")), reverse=True)
        for r in sorted_holes[:5]:
            v = _f(r.get("velocity_m_s"))
            if v <= 0:
                continue
            hotspots.append({
                "zone": "orifice_hole",
                "severity": "advisory" if v < orifice_warn else "warning",
                "velocity_m_s": round(v, 4),
                "lateral_index": int(r.get("lateral_index") or 0),
                "hole_index": int(r.get("hole_index") or 0),
                "station_m": r.get("station_m"),
                "y_along_lateral_m": r.get("y_along_lateral_m"),
                "detail": "Per-hole jet from 1B network",
            })

    # Score 0–100 (100 = no concerns)
    score = 100
    for f in findings:
        sev = f.get("severity", "advisory")
        if sev == "critical":
            score -= 28
        elif sev == "warning":
            score -= 14
        else:
            score -= 6
    score = max(0, min(100, score))
    if score >= 85:
        grade = "Low concern"
    elif score >= 65:
        grade = "Review"
    else:
        grade = "Elevated (advisory)"

    return {
        "method": "advisory_velocity_screening_1d",
        "advisory_only": True,
        "active": True,
        "note": None,
        "severity_score": score,
        "grade": grade,
        "header_velocity_max_m_s": round(h_max, 4),
        "lateral_velocity_max_m_s": round(lat_max, 4),
        "orifice_velocity_max_m_s": round(orf_max, 4),
        "orifice_velocity_min_m_s": round(orf_min, 4) if orf_min > 0 else 0.0,
        "flow_imbalance_pct": round(imb, 2),
        "orifice_velocity_ratio": round(ratio, 3) if ratio is not None else None,
        "hotspots": hotspots[:12],
        "findings": findings,
        "plugging_hint": plugging_hint,
        "sand_carryover_hint": sand_carryover_hint,
        "limits_reference_si": {
            "header_advisory_m_s": HEADER_V_ADVISORY_M_S,
            "header_warning_m_s": HEADER_V_WARNING_M_S,
            "lateral_advisory_m_s": LATERAL_V_ADVISORY_M_S,
            "lateral_warning_m_s": LATERAL_V_WARNING_M_S,
            "orifice_warning_drilled_m_s": ORIFICE_V_WARNING_DRILLED_M_S,
            "orifice_warn_used_m_s": round(orifice_warn, 3),
        },
        "severity_peaks": {
            "header": h_sev,
            "lateral_pipe": lat_sev,
            "orifice": o_sev,
        },
    }
