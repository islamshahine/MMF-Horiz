"""Rule-based collector / nozzle / BW distribution intelligence (no CFD)."""
from __future__ import annotations

from typing import Any

# Vessel nozzle schedule screening — water vs air use different velocity norms.
WATER_NOZZLE_SERVICES = frozenset({
    "Feed inlet",
    "Filtrate outlet",
    "Backwash inlet",
    "Backwash outlet",
    "Drain",
    "Sample / instrument",
})
AIR_NOZZLE_SERVICES = frozenset({
    "Air scour",
    "Vent",
})

# Water: erosion / impingement risk in liquid nozzles (typical design ≤ ~2 m/s).
PEAK_NOZZLE_V_WATER_EROSION_M_S = 3.5
# Air: scour lines are normally ~10–20 m/s in pipe — not an erosion criterion like water.
PEAK_NOZZLE_V_AIR_HIGH_M_S = 28.0   # flag only unusually high air pipe velocities
NOZZLE_SPREAD_WARN_PCT = 35.0

_LEGACY_NOZZLE_TOPICS = frozenset({"Nozzle velocity", "Nozzle spread"})


def _velocity_si_m_s(row: dict) -> float | None:
    """Read nozzle pipe velocity from schedule row (engine rows use SI ``Velocity (m/s)``)."""
    for key in ("Velocity (m/s)", "velocity_m_s"):
        if key in row and row[key] is not None:
            try:
                return float(row[key])
            except (TypeError, ValueError):
                pass
    for key in row:
        if isinstance(key, str) and "velocity" in key.lower() and "m/s" in key.lower():
            try:
                return float(row[key])
            except (TypeError, ValueError):
                pass
    return None


def _nozzle_velocities_by_fluid(sched: list) -> tuple[list[float], list[float]]:
    """Split schedule rows into water-side and air-side pipe velocities (m/s)."""
    water_v: list[float] = []
    air_v: list[float] = []
    for row in sched:
        v_raw = _velocity_si_m_s(row)
        if v_raw is None:
            continue
        v = v_raw
        if v <= 0:
            continue
        service = str(row.get("Service", "")).strip()
        if service in AIR_NOZZLE_SERVICES:
            air_v.append(v)
        elif service in WATER_NOZZLE_SERVICES or not service:
            water_v.append(v)
        else:
            water_v.append(v)
    return water_v, air_v


def nozzle_velocities_by_service(sched: list | None) -> dict[str, float]:
    """Per-service pipe velocity (m/s) from §4 vessel nozzle schedule rows."""
    out: dict[str, float] = {}
    for row in sched or []:
        service = str(row.get("Service", "")).strip()
        if not service:
            continue
        v = _velocity_si_m_s(row)
        if v is not None and v > 0:
            out[service] = round(float(v), 2)
    return out


def summarize_nozzle_schedule_velocities(sched: list | None) -> dict[str, float]:
    """Peak water / air nozzle velocities (m/s) from the vessel nozzle schedule."""
    water_v, air_v = _nozzle_velocities_by_fluid(sched or [])
    by_svc = nozzle_velocities_by_service(sched)
    bw_path_water = [
        v for k, v in by_svc.items() if k in ("Backwash inlet", "Backwash outlet")
    ]
    return {
        "peak_nozzle_velocity_water_m_s": round(max(water_v), 2) if water_v else 0.0,
        "peak_nozzle_velocity_air_m_s": round(max(air_v), 2) if air_v else 0.0,
        "peak_bw_path_water_m_s": round(max(bw_path_water), 2) if bw_path_water else 0.0,
        "backwash_inlet_velocity_m_s": by_svc.get("Backwash inlet", 0.0),
        "backwash_outlet_velocity_m_s": by_svc.get("Backwash outlet", 0.0),
        "air_scour_nozzle_velocity_m_s": by_svc.get("Air scour", 0.0),
        "nozzle_velocities_by_service": by_svc,
        "nozzle_spread_water_pct": round(_spread_pct(water_v), 1),
        "nozzle_spread_air_pct": round(_spread_pct(air_v), 1),
    }


def _spread_pct(vels: list[float]) -> float:
    if len(vels) < 2:
        return 0.0
    v_max, v_min = max(vels), min(vels)
    return (v_max - v_min) / max(v_max, 1e-9) * 100.0


def analyse_collector_performance(
    *,
    bw_col: dict | None,
    bw_hyd: dict | None,
    nozzle_sched: list | None,
    air_header_dn_mm: int,
    air_scour_rate_m_h: float,
    nominal_id_m: float,
    collector_velocity_risk: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return findings, recommendations, and a 0–100 performance score."""
    findings: list[dict[str, str]] = []
    recommendations: list[str] = []
    score = 100

    col = bw_col or {}
    hyd = bw_hyd or {}
    sched = nozzle_sched or []

    freeboard_m = float(col.get("freeboard_m", 0.0) or 0.0)
    min_fb = float(col.get("min_freeboard_m", 0.1) or 0.1)
    max_safe = float(col.get("max_safe_bw_m_h", 0.0) or 0.0)
    bw_vel = float(col.get("proposed_bw_m_h", 0.0) or hyd.get("bw_lv_actual_m_h", 0.0) or 0.0)

    if col.get("status", "").startswith("CRITICAL"):
        findings.append({"severity": "critical", "topic": "Media loss", "detail": col.get("status", "")})
        score -= 40
        recommendations.append("Lower BW velocity or raise collector / freeboard before mechanical design freeze.")
    elif col.get("status", "").startswith("WARNING"):
        findings.append({"severity": "warning", "topic": "Freeboard", "detail": col.get("status", "")})
        score -= 20
        recommendations.append("Increase freeboard or reduce bed expansion increment (media / air scour review).")

    if max_safe > 1e-6 and bw_vel > max_safe * 0.95:
        findings.append({
            "severity": "warning",
            "topic": "BW velocity",
            "detail": f"Design BW {bw_vel:.1f} m/h is near max safe {max_safe:.1f} m/h.",
        })
        score -= 15

    if freeboard_m < min_fb * 1.25 and freeboard_m >= min_fb:
        findings.append({
            "severity": "advisory",
            "topic": "Freeboard margin",
            "detail": f"Freeboard {freeboard_m*1000:.0f} mm is only slightly above minimum {min_fb*1000:.0f} mm.",
        })
        score -= 5

    peaks = summarize_nozzle_schedule_velocities(sched)
    water_v, air_v = _nozzle_velocities_by_fluid(sched)
    v_max_water = peaks["peak_nozzle_velocity_water_m_s"]
    v_max_air = peaks["peak_nozzle_velocity_air_m_s"]
    spread_water = peaks["nozzle_spread_water_pct"]
    spread_air = peaks["nozzle_spread_air_pct"]

    if water_v and v_max_water > PEAK_NOZZLE_V_WATER_EROSION_M_S:
        findings.append({
            "severity": "warning",
            "topic": "Nozzle velocity (water)",
            "detail": (
                f"Peak **water** nozzle velocity {v_max_water:.2f} m/s "
                f"(erosion screening ≥ {PEAK_NOZZLE_V_WATER_EROSION_M_S:.1f} m/s) — "
                "check impingement, erosion, and distribution."
            ),
        })
        score -= 10
    if air_v and v_max_air > PEAK_NOZZLE_V_AIR_HIGH_M_S:
        findings.append({
            "severity": "advisory",
            "topic": "Nozzle velocity (air)",
            "detail": (
                f"Peak **air** nozzle velocity {v_max_air:.2f} m/s is high "
                f"(typical air-scour pipe design ~10–20 m/s) — confirm header ΔP and blower, "
                "not liquid-nozzle erosion."
            ),
        })
        score -= 5
    if len(water_v) >= 2 and spread_water > NOZZLE_SPREAD_WARN_PCT:
        findings.append({
            "severity": "advisory",
            "topic": "Nozzle spread (water)",
            "detail": (
                f"Water-side nozzle velocity spread ~{spread_water:.0f}% across services — "
                "verify manifold hydraulics."
            ),
        })
        score -= 8
    if len(air_v) >= 2 and spread_air > NOZZLE_SPREAD_WARN_PCT:
        findings.append({
            "severity": "advisory",
            "topic": "Nozzle spread (air)",
            "detail": (
                f"Air-side nozzle velocity spread ~{spread_air:.0f}% across services — "
                "verify air header / vent sizing."
            ),
        })
        score -= 5

    if air_header_dn_mm < 200 and float(air_scour_rate_m_h) > 45:
        findings.append({
            "severity": "advisory",
            "topic": "Air header",
            "detail": f"DN {air_header_dn_mm} mm with high air scour {air_scour_rate_m_h:.0f} m/h — confirm header ΔP.",
        })
        score -= 5

    if nominal_id_m > 0 and float(col.get("collector_h_m", 0)) / nominal_id_m < 0.12:
        recommendations.append(
            "Collector elevation is low relative to vessel ID — confirm lateral coverage and carryover during air step."
        )

    _vr = collector_velocity_risk or {}
    if _vr.get("active"):
        _pen = max(0, 100 - int(_vr.get("severity_score", 100) or 100))
        score -= min(24, _pen // 2)

    if not recommendations and not findings:
        recommendations.append("Collector height, freeboard, and nozzle schedule are within typical screening limits.")

    score = max(0, min(100, score))
    if score >= 85:
        grade = "Good"
    elif score >= 65:
        grade = "Acceptable"
    else:
        grade = "Review required"

    return {
        "score": score,
        "grade": grade,
        "findings": findings,
        "recommendations": recommendations,
        "method": "rule_based_screening",
        **peaks,
        "nozzle_velocity_limit_water_m_s": PEAK_NOZZLE_V_WATER_EROSION_M_S,
        "nozzle_velocity_limit_air_m_s": PEAK_NOZZLE_V_AIR_HIGH_M_S,
        "nozzle_velocity_note_air": (
            "**Air scour** is a separate **vessel-wall nozzle** (§4 schedule), not the internal "
            "BW collector header/laterals. Typical air pipe ~10–20 m/s — not a water erosion limit."
        ),
        "nozzle_velocity_note_vessel": (
            "Velocities below are **vessel connection** nozzles only (Mechanical §4). "
            "Internal distributor/collector hydraulics are under **Collector hydraulics**."
        ),
    }
