"""
Lifecycle degradation curves — deterministic advisory (media, nozzles, collector).

Sawtooth **condition %** (100 = fresh after replacement, 0 = due) vs project year.
Not a physics-based wear model — links operating stressors to effective replacement interval.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

REPLACEMENT_THRESHOLD_PCT = 35.0
MAX_STRESS_FACTOR = 2.0
DEFAULT_COLLECTOR_INTERVAL_Y = 15.0


def _stress_clamp(stress: float) -> float:
    return max(0.55, min(float(stress), MAX_STRESS_FACTOR))


def degradation_curve(
    horizon_years: int,
    nominal_interval_years: float,
    stress_factor: float,
    *,
    threshold_pct: float = REPLACEMENT_THRESHOLD_PCT,
) -> Tuple[List[dict[str, Any]], float]:
    """
    Annual condition % with sawtooth reset at each effective replacement.

    Returns ``(curve_points, effective_interval_years)``.
    """
    horizon = max(int(horizon_years), 1)
    nominal = max(float(nominal_interval_years), 0.5)
    stress = _stress_clamp(stress_factor)
    eff = nominal / stress
    curve: List[dict[str, Any]] = []
    for y in range(0, horizon + 1):
        age = (y % eff) if eff > 0 else 0.0
        cond = 100.0 * (1.0 - age / eff) if eff > 0 else 100.0
        curve.append({
            "year": y,
            "condition_pct": round(max(0.0, min(100.0, cond)), 1),
            "below_threshold": cond < threshold_pct,
        })
    return curve, round(eff, 2)


def _replacement_years(eff_interval: float, horizon: int) -> List[int]:
    if eff_interval <= 0:
        return []
    yrs: List[int] = []
    t = eff_interval
    while t <= horizon + 1e-6:
        yrs.append(int(round(t)))
        t += eff_interval
    return yrs


def _media_stress(inputs: dict, computed: dict) -> Tuple[float, List[str]]:
    stress = 1.0
    drivers: List[str] = []
    cu = computed.get("cycle_uncertainty") or {}
    n_block = cu.get("N") or cu.get("design") or {}
    if not n_block and isinstance(cu, dict):
        for v in cu.values():
            if isinstance(v, dict) and "cycle_expected_h" in v:
                n_block = v
                break
    cycle_h = float(n_block.get("cycle_expected_h") or 0.0)
    if cycle_h > 0 and cycle_h < 36.0:
        bump = 0.25 * (36.0 - cycle_h) / 36.0
        stress += bump
        drivers.append(f"Short expected cycle ({cycle_h:.0f} h) vs 36 h reference")
    sl = float(computed.get("solid_loading_effective_kg_m2") or inputs.get("solid_loading") or 0)
    if sl > 1.25:
        stress += 0.12 * min((sl - 1.25) / 1.0, 1.0)
        drivers.append(f"Elevated effective solids loading ({sl:.2f} kg/m²)")
    mal = float(computed.get("maldistribution_factor") or 1.0)
    if mal > 1.12:
        stress += 0.08 * min((mal - 1.0) / 0.5, 1.0)
        drivers.append(f"Maldistribution factor {mal:.2f}")
    bw_v = float(inputs.get("bw_velocity") or 0)
    if bw_v > 40.0:
        stress += 0.06 * min((bw_v - 40.0) / 20.0, 1.0)
        drivers.append(f"High design BW rate ({bw_v:.0f} m/h)")
    if not drivers:
        drivers.append("Operating stress near baseline — nominal media interval applies.")
    return stress, drivers


def _nozzle_stress(inputs: dict, computed: dict) -> Tuple[float, List[str]]:
    stress = 1.0
    drivers: List[str] = []
    bw_v = float(inputs.get("bw_velocity") or 0)
    if bw_v > 38.0:
        stress += 0.18 * min((bw_v - 38.0) / 22.0, 1.0)
        drivers.append(f"BW velocity {bw_v:.0f} m/h — nozzle / strainer fatigue")
    cvr = computed.get("collector_velocity_risk") or {}
    sev = str(cvr.get("severity") or cvr.get("overall_severity") or "").lower()
    if sev in ("warning", "critical", "high"):
        stress += 0.15
        drivers.append("Collector velocity risk advisory elevated")
    ud = computed.get("underdrain_system_advisory") or {}
    if str(ud.get("tone", "")).lower() == "warning":
        stress += 0.08
        drivers.append("Underdrain / strainer coherence warning")
    cnp = computed.get("collector_nozzle_plate") or {}
    v_n = float(cnp.get("v_nozzle_m_s") or 0)
    if v_n > 2.5:
        stress += 0.1 * min((v_n - 2.5) / 1.5, 1.0)
        drivers.append(f"Nozzle orifice velocity {v_n:.2f} m/s (screening)")
    if not drivers:
        drivers.append("BW and underdrain screening within typical band.")
    return stress, drivers


def _collector_stress(inputs: dict, computed: dict) -> Tuple[float, List[str]]:
    stress = 1.0
    drivers: List[str] = []
    ch = computed.get("collector_hyd") or {}
    imb = float(ch.get("flow_imbalance_pct") or 0)
    if imb > 12.0:
        stress += 0.2 * min((imb - 12.0) / 25.0, 1.0)
        drivers.append(f"Lateral flow imbalance {imb:.1f} %")
    mal_c = float(ch.get("maldistribution_factor_calc") or 0)
    if mal_c > 1.15:
        stress += 0.1 * min((mal_c - 1.0) / 0.4, 1.0)
        drivers.append(f"Collector maldistribution calc {mal_c:.2f}")
    cvr = computed.get("collector_velocity_risk") or {}
    for key in ("erosion", "plugging", "fines"):
        block = cvr.get(key) if isinstance(cvr.get(key), dict) else {}
        if str(block.get("severity", "")).lower() in ("warning", "critical"):
            stress += 0.06
            drivers.append(f"Velocity risk — {key}")
            break
    staged = computed.get("collector_staged_orifices") or {}
    if staged.get("recommended") and staged.get("n_stages", 0) and int(staged.get("n_stages", 0)) > 2:
        stress += 0.05
        drivers.append("Staged orifice advisory — heterogeneous lateral loading")
    if not drivers:
        drivers.append("Collector 1D screening without major imbalance flags.")
    return stress, drivers


def _component_block(
    label: str,
    nominal_y: float,
    stress: float,
    drivers: List[str],
    horizon: int,
) -> dict[str, Any]:
    curve, eff = degradation_curve(horizon, nominal_y, stress)
    cond_end = curve[-1]["condition_pct"] if curve else 0.0
    return {
        "label": label,
        "nominal_interval_years": round(nominal_y, 2),
        "stress_factor": round(_stress_clamp(stress), 3),
        "effective_interval_years": eff,
        "drivers": drivers,
        "curve": curve,
        "suggested_replacement_years": _replacement_years(eff, horizon),
        "condition_at_horizon_pct": cond_end,
        "below_threshold_at_horizon": cond_end < REPLACEMENT_THRESHOLD_PCT,
    }


def build_lifecycle_degradation(inputs: dict, computed: dict) -> Dict[str, Any]:
    """Advisory degradation bundle for Economics tab and JSON export."""
    horizon = max(int(inputs.get("project_life_years") or inputs.get("design_life_years") or 20), 5)
    media_y = float(
        inputs.get("replacement_interval_media")
        or inputs.get("media_replace_years")
        or 7.0
    )
    noz_y = float(
        inputs.get("replacement_interval_nozzles")
        or inputs.get("nozzle_replace_years")
        or 10.0
    )
    coll_y = float(inputs.get("replacement_interval_collector") or DEFAULT_COLLECTOR_INTERVAL_Y)

    m_stress, m_drv = _media_stress(inputs, computed)
    n_stress, n_drv = _nozzle_stress(inputs, computed)
    c_stress, c_drv = _collector_stress(inputs, computed)

    components = {
        "media": _component_block("Media bed", media_y, m_stress, m_drv, horizon),
        "nozzles": _component_block("Nozzles / underdrain", noz_y, n_stress, n_drv, horizon),
        "collector": _component_block("Feed / BW collector", coll_y, c_stress, c_drv, horizon),
    }

    findings: List[Dict[str, str]] = []
    for key, block in components.items():
        if block["stress_factor"] >= 1.35:
            findings.append({
                "severity": "advisory",
                "topic": f"{block['label']} — accelerated wear",
                "detail": (
                    f"Stress factor **{block['stress_factor']:.2f}×** "
                    f"→ effective interval **{block['effective_interval_years']:.1f} yr** "
                    f"(nominal **{block['nominal_interval_years']:.1f} yr**)."
                ),
            })
        if block["below_threshold_at_horizon"]:
            findings.append({
                "severity": "warning",
                "topic": f"{block['label']} — below threshold at horizon",
                "detail": (
                    f"Condition **{block['condition_at_horizon_pct']:.0f} %** at year **{horizon}** "
                    f"(replacement advisory < **{REPLACEMENT_THRESHOLD_PCT:.0f} %**)."
                ),
            })

    fin = computed.get("econ_financial") or {}
    if fin.get("replacement_schedule"):
        findings.append({
            "severity": "info",
            "topic": "Cash-flow replacements",
            "detail": "Discrete media / nozzle / lining events are in **Lifecycle financial** cash flow — curves here are operating-stress advisory only.",
        })

    tone = "ok"
    if any(f["severity"] == "warning" for f in findings):
        tone = "warning"
    elif findings:
        tone = "advisory"

    return {
        "schema_version": "1.0",
        "horizon_years": horizon,
        "replacement_threshold_pct": REPLACEMENT_THRESHOLD_PCT,
        "components": components,
        "findings": findings,
        "tone": tone,
        "doc_note": "Deterministic sawtooth model — calibrate intervals with site history; not predictive FEA or CFD wear.",
    }
