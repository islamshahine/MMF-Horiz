"""Lateral construction types, water-service material guidance, and screening rules."""
from __future__ import annotations

from typing import Any

LATERAL_CONSTRUCTION_OPTIONS: tuple[str, ...] = (
    "Drilled perforated pipe",
    "Wedge wire screen",
    "Coated carbon steel (drilled)",
)

# Drilled-pipe materials (perforation % / ligament governs).
DRILLED_LATERAL_MATERIALS: tuple[str, ...] = (
    "PVC",
    "CPVC / PP",
    "Stainless steel",
    "Custom",
)

# Screen assemblies — do not use drilled-hole ligament rules.
WEDGE_LATERAL_MATERIALS: tuple[str, ...] = (
    "Wedge wire — SS316L",
    "Wedge wire — Duplex / Super Duplex",
    "Wedge wire — Titanium",
    "Wedge wire — OEM profile",
)

COATED_CS_MATERIALS: tuple[str, ...] = (
    "CS + epoxy lining",
    "CS + ceramic / glass-flake",
    "CS + rubber lining",
)

WEDGE_OPEN_AREA_TYPICAL_PCT = "20–60%"
WEDGE_OPEN_AREA_SCREEN_MAX = 0.60
WEDGE_OPEN_AREA_DEFAULT = 0.35

_HYDRAULIC_FACTORS: dict[str, dict[str, float]] = {
    "Drilled perforated pipe": {
        "discharge_cd": 0.62,
        "target_slot_orifice_v_m_s": 2.5,
        "headloss_factor": 1.0,
    },
    "Wedge wire screen": {
        "discharge_cd": 0.78,
        "target_slot_orifice_v_m_s": 1.8,
        "headloss_factor": 0.85,
    },
    "Coated carbon steel (drilled)": {
        "discharge_cd": 0.60,
        "target_slot_orifice_v_m_s": 2.5,
        "headloss_factor": 1.05,
    },
}


def is_wedge_wire_construction(lateral_construction: str) -> bool:
    return str(lateral_construction or "").strip().lower().startswith("wedge wire")


def is_drilled_construction(lateral_construction: str) -> bool:
    key = str(lateral_construction or "").strip()
    return key in ("Drilled perforated pipe", "Coated carbon steel (drilled)")


def water_service_class(salinity_ppt: float) -> str:
    s = max(0.0, float(salinity_ppt))
    if s <= 1.0:
        return "fresh"
    if s <= 15.0:
        return "brackish"
    return "seawater"


def hydraulic_factors_for_lateral(lateral_construction: str) -> dict[str, float]:
    key = str(lateral_construction or "Drilled perforated pipe").strip()
    return dict(_HYDRAULIC_FACTORS.get(key, _HYDRAULIC_FACTORS["Drilled perforated pipe"]))


def materials_for_construction(lateral_construction: str) -> tuple[str, ...]:
    key = str(lateral_construction or "").strip()
    if is_wedge_wire_construction(key):
        return WEDGE_LATERAL_MATERIALS
    if key == "Coated carbon steel (drilled)":
        return COATED_CS_MATERIALS
    return DRILLED_LATERAL_MATERIALS


def water_service_material_guidance(
    *,
    salinity_ppt: float,
    lateral_construction: str,
    lateral_material: str,
) -> dict[str, Any]:
    """Corrosion / alloy recommendations from feed water salinity and lateral type."""
    svc = water_service_class(salinity_ppt)
    mat = str(lateral_material or "")
    findings: list[dict[str, str]] = []
    recommendations: list[str] = []

    if svc == "seawater":
        if "304" in mat or mat == "Stainless steel":
            findings.append({
                "severity": "warning",
                "topic": "Seawater metallurgy",
                "detail": (
                    "Standard **304 / generic SS** is generally **not** suitable for long-term "
                    "seawater underdrain service (chloride pitting, crevice, MIC, weld attack)."
                ),
            })
            recommendations.append(
                "Seawater: prefer **Duplex / Super Duplex**, **titanium wedge wire**, or "
                "**FRP/HDPE/PP** laterals — confirm with corrosion engineer."
            )
        if is_drilled_construction(lateral_construction) and "PVC" in mat:
            findings.append({
                "severity": "advisory",
                "topic": "Seawater + PVC",
                "detail": "PVC laterals in seawater — verify temperature, UV, and support; often limited to smaller units.",
            })
        if lateral_construction == "Coated carbon steel (drilled)":
            recommendations.append(
                "Coated CS in seawater: audit **holidays**, **weld edges**, **air-scour abrasion**, "
                "and repair strategy — ceramic/epoxy/rubber each have different limits."
            )
    elif svc == "brackish":
        recommendations.append(
            "Brackish service: **316L SS** drilled laterals are often acceptable; "
            "confirm chlorides and stagnation. Wedge wire duplex assemblies used in SWRO pre-treatment."
        )
    else:
        recommendations.append(
            "Fresh water: broader material choice — still verify chlorine, temperature, and BW air scour fatigue."
        )

    if is_wedge_wire_construction(lateral_construction):
        recommendations.append(
            "Wedge wire: govern with **collapse**, **rod spacing**, **slot width**, **weld integrity**, "
            "**ΔP / fatigue**, and **abrasion** — not drilled-hole ligament %."
        )

    return {
        "water_service": svc,
        "salinity_ppt": round(float(salinity_ppt), 2),
        "findings": findings,
        "recommendations": recommendations,
    }


def wedge_wire_screening(
    *,
    lateral_dn_mm: float,
    lateral_length_m: float,
    open_area_fraction: float,
    slot_width_mm: float = 0.0,
    bw_head_mwc: float = 15.0,
    lateral_material: str = "Wedge wire — OEM profile",
    user_open_area_fraction: float = 0.0,
) -> dict[str, Any]:
    """
    Screen wedge-wire laterals — open area % is informational; collapse / OEM limits govern.
    """
    oa_user = float(user_open_area_fraction) if user_open_area_fraction > 0 else WEDGE_OPEN_AREA_DEFAULT
    oa = max(0.05, min(WEDGE_OPEN_AREA_SCREEN_MAX, float(open_area_fraction) if open_area_fraction > 0 else oa_user))
    cap = WEDGE_OPEN_AREA_SCREEN_MAX
    findings: list[dict[str, str]] = []

    if oa > 0.50:
        findings.append({
            "severity": "advisory",
            "topic": "Wedge wire open area",
            "detail": (
                f"Slot open area **{oa * 100:.0f}%** is high — confirm **collapse strength** and "
                "**support geometry** with OEM data (typical 20–60%)."
            ),
        })
    if bw_head_mwc > 20.0:
        findings.append({
            "severity": "warning",
            "topic": "Collapse / ΔP",
            "detail": (
                f"BW head **{bw_head_mwc:.0f} m** — verify screen **collapse** rating and "
                "**longitudinal rod** capacity at max differential."
            ),
        })
    if slot_width_mm <= 0:
        findings.append({
            "severity": "advisory",
            "topic": "Slot width",
            "detail": "Enter slot width (mm) when known — affects clogging, media retention, and entrance loss.",
        })

    return {
        "lateral_construction": "Wedge wire screen",
        "lateral_material": lateral_material,
        "screening_model": "wedge_wire",
        "open_area_fraction": round(oa, 4),
        "open_area_fraction_pct": round(oa * 100.0, 2),
        "open_area_limit_pct": round(cap * 100.0, 1),
        "open_area_range_pct": WEDGE_OPEN_AREA_TYPICAL_PCT,
        "open_area_max_fraction": cap,
        "limit_source": "Wedge wire OEM / collapse — not drilled ligament rule",
        "structural_ok": oa <= cap + 1e-6,
        "n_perforations_max_structural": 0,
        "ligament_mm": 0.0,
        "ligament_min_mm": 0.0,
        "ligament_check_applies": False,
        "perforation_pitch_check_applies": False,
        "findings": findings,
        "hydraulic_note": (
            "Wedge wire: lower entrance velocity, better distribution, lower headloss vs discrete holes — "
            "use OEM Cd and slot area in detailed design."
        ),
    }


def coated_cs_screening(
    *,
    lateral_material: str,
    open_area_fraction_pct: float,
) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    findings.append({
        "severity": "advisory",
        "topic": "Coated carbon steel",
        "detail": (
            f"**{lateral_material}** — review coating **holidays**, **weld burn-back**, "
            "**media abrasion**, and **air scour fatigue**; repair strategy required at specification."
        ),
    })
    if open_area_fraction_pct > 20.0:
        findings.append({
            "severity": "advisory",
            "topic": "Coating at perforations",
            "detail": "High open area on drilled CS — perforation edges are high risk for holiday / undercut corrosion.",
        })
    return findings
