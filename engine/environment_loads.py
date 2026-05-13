"""
environment_loads.py — Seismic / wind / external painting notes for GA & datasheets.

These are **documentation and order-of-magnitude** helpers, not a substitute
for code-checked structural design (anchors, saddles, local wind on appurtenances).
"""
from __future__ import annotations

from typing import Any

AIR_DENSITY_KG_M3 = 1.25  # ~15 °C, sea level, indicative


def compute_environment_structural(inputs: dict) -> dict[str, Any]:
    """
    Build summary dict from user inputs (SI where applicable).

    Expected keys (optional; defaults applied if missing):
      external_environment, seismic_design_category, seismic_importance_factor,
      spectral_accel_sds, site_class_asce, basic_wind_ms, wind_exposure
    """
    ext_env = str(inputs.get("external_environment") or "Non-marine (industrial / inland)")
    sdc = str(inputs.get("seismic_design_category") or "Not evaluated")
    try:
        ie = float(inputs.get("seismic_importance_factor", 1.0) or 1.0)
    except (TypeError, ValueError):
        ie = 1.0
    try:
        sds = float(inputs.get("spectral_accel_sds", 0.0) or 0.0)
    except (TypeError, ValueError):
        sds = 0.0
    site = str(inputs.get("site_class_asce") or "B")
    try:
        v_ms = float(inputs.get("basic_wind_ms", 0.0) or 0.0)
    except (TypeError, ValueError):
        v_ms = 0.0
    wind_exp = str(inputs.get("wind_exposure") or "C")

    if v_ms > 0:
        q_pa = 0.5 * AIR_DENSITY_KG_M3 * v_ms * v_ms
        q_kpa = q_pa / 1000.0
    else:
        q_pa = 0.0
        q_kpa = 0.0

    if "Marine" in ext_env or "coastal" in ext_env.lower():
        paint_iso = "ISO 12944 — aim C5-M / Im2 (immersion splash zone) or CX per specifier"
        paint_layers = (
            "Typical: Sa 2½ blast → inorganic zinc or epoxy zinc primer → "
            "high-build epoxy or glassflake epoxy barrier → aliphatic polyurethane topcoat."
        )
        ext_note = (
            "Marine/coastal: aggressive external atmosphere — "
            "specify C5-M (or project-specific) system; increased inspection frequency."
        )
    else:
        paint_iso = "ISO 12944 — typically C2–C4 depending on corrosivity category"
        paint_layers = (
            "Typical: Sa 2½ → epoxy zinc-rich or polyamide epoxy primer → "
            "MIO epoxy intermediate → aliphatic PU or acrylic PU finish (colour per ID)."
        )
        ext_note = (
            "Non-marine industrial: standard shop + field coating to owner paint spec; "
            "confirm corrosivity category (C2–C4) for final ISO 12944 system."
        )

    seismic_rows = [
        ["Seismic design category (SDC)", sdc],
        ["Importance factor Ie", f"{ie:g}"],
        ["S_DS (short-period spectral accel., g)", f"{sds:g}" if sds > 0 else "—"],
        ["Site class (ASCE 7)", site],
        [
            "Design basis",
            "Horizontal vessel seismic reactions, anchor bolts, and saddle "
            "local loads shall be by **structural engineer of record** per "
            "IBC / ASCE 7 (or Eurocode 8) for the project jurisdiction.",
        ],
    ]

    wind_rows = [
        ["Basic wind speed V (3-s gust)", f"{v_ms:g} m/s" if v_ms > 0 else "— (not set)"],
        ["Exposure category", wind_exp],
        [
            "Indicative velocity pressure q",
            f"{q_kpa:.3f} kPa  (q = ½ ρ V², ρ = {AIR_DENSITY_KG_M3} kg/m³, **not** ASCE 7 K_z K_d K_zt)",
        ],
        [
            "Design basis",
            "Global wind force on vessel + platforms is a **structural** item; "
            "this value is for orientation only — use project wind map + code load combinations.",
        ],
    ]

    paint_rows = [
        ["Environment", ext_env],
        ["ISO 12944 target", paint_iso],
        ["Typical layer build (indicative)", paint_layers],
        [
            "Internal vs external",
            "Internal protection is set under *Internal protection*; "
            "this section applies **external** steel only.",
        ],
    ]

    return {
        "external_environment": ext_env,
        "seismic_design_category": sdc,
        "seismic_importance_factor": ie,
        "spectral_accel_sds": sds,
        "site_class_asce": site,
        "basic_wind_ms": v_ms,
        "wind_exposure": wind_exp,
        "wind_dynamic_pressure_pa": round(q_pa, 2),
        "wind_dynamic_pressure_kpa": round(q_kpa, 4),
        "external_coating_note": ext_note,
        "paint_system_iso_note": paint_iso,
        "paint_system_layers_note": paint_layers,
        "seismic_table_rows": seismic_rows,
        "wind_table_rows": wind_rows,
        "paint_table_rows": paint_rows,
    }
