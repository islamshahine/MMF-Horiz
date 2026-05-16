"""
Strainer nozzle materials — weight catalogue and salinity-based alloy guidance.

Mechanical weights only; corrosion acceptance is the owner's corrosion engineer.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from engine.collector_lateral_types import water_service_class

# Unit weight per strainer nozzle body (kg) — internals / economics
STRAINER_WEIGHT_KG: Dict[str, float] = {
    "Super_duplex_2507": 0.36,
    "Super_duplex_PREN42": 0.36,
    "Duplex_2205": 0.34,
    "HDPE": 0.08,
    "PP": 0.06,
    "SS316": 0.35,
}

STRAINER_MATERIAL_ORDER: tuple[str, ...] = (
    "Super_duplex_2507",
    "Super_duplex_PREN42",
    "Duplex_2205",
    "HDPE",
    "PP",
    "SS316",
)

STRAINER_MATERIAL_LABELS: Dict[str, str] = {
    "Super_duplex_2507": "Super duplex 2507 (PREN > 40) — seawater",
    "Super_duplex_PREN42": "Super duplex — PREN > 42 (conservative EPC)",
    "Duplex_2205": "Duplex 2205 (PREN ~35)",
    "HDPE": "HDPE — polymer",
    "PP": "PP — polymer",
    "SS316": "SS316 / 316L — legacy (not high chloride)",
}

STRAINER_PREN_TYPICAL: Dict[str, Optional[int]] = {
    "Super_duplex_2507": 42,
    "Super_duplex_PREN42": 43,
    "Duplex_2205": 35,
    "HDPE": None,
    "PP": None,
    "SS316": 24,
}

_ALIASES: Dict[str, str] = {
    "SS 316L": "SS316",
    "SS316L": "SS316",
    "316L": "SS316",
    "SS316": "SS316",
    "2507": "Super_duplex_2507",
    "2205": "Duplex_2205",
}


def normalize_strainer_material(material: str) -> str:
    """Map legacy / shorthand names to registry keys."""
    key = str(material or "").strip()
    if key in STRAINER_WEIGHT_KG:
        return key
    return _ALIASES.get(key, key)


def strainer_material_label(material: str) -> str:
    k = normalize_strainer_material(material)
    return STRAINER_MATERIAL_LABELS.get(k, k.replace("_", " "))


def suggested_strainer_material(salinity_ppt: float) -> str:
    """Default metal strainer alloy from feed salinity (no polymer bodies)."""
    svc = water_service_class(salinity_ppt)
    if svc == "seawater":
        return "Super_duplex_2507"
    if svc == "brackish":
        return "Duplex_2205"
    return "SS316"


def is_polymer_body_material(body_material: str) -> bool:
    b = str(body_material or "").upper()
    return "PP" in b or "HDPE" in b or "POLYPROPYLENE" in b or "POLYETHYLENE" in b


def resolve_strainer_for_catalogue(
    product: dict[str, Any] | None,
    salinity_ppt: float,
) -> str:
    """
    Strainer default: **salinity wins** for metal underdrains (SS / duplex / super duplex);
    **body material wins** for polymer (PP / HDPE).
    """
    if not product:
        return suggested_strainer_material(salinity_ppt)

    family = str(product.get("strainer_body_family", "")).lower()
    if family == "polymer" or is_polymer_body_material(str(product.get("body_material", ""))):
        body = str(product.get("body_material", "")).upper()
        fixed = product.get("strainer_material_fixed")
        if fixed:
            return normalize_strainer_material(str(fixed))
        if "HDPE" in body:
            return "HDPE"
        if "PP" in body:
            return "PP"
        return "PP"

    if family == "metal" or str(product.get("type", "")).lower() in (
        "drilled", "slotted",
    ):
        return suggested_strainer_material(salinity_ppt)

    legacy = product.get("strainer_material_suggested")
    if legacy:
        return normalize_strainer_material(str(legacy))
    return suggested_strainer_material(salinity_ppt)


def catalogue_strainer_hint(product: dict[str, Any] | None, salinity_ppt: float) -> str:
    """Short label for catalogue table / captions."""
    if not product:
        return "By feed salinity"
    if str(product.get("strainer_body_family", "")).lower() == "polymer":
        return strainer_material_label(resolve_strainer_for_catalogue(product, salinity_ppt))
    opts = product.get("strainer_material_options")
    if opts:
        return "SS / Duplex / Super duplex (default by salinity)"
    return strainer_material_label(resolve_strainer_for_catalogue(product, salinity_ppt))


def strainer_material_advisory(
    *,
    salinity_ppt: float,
    strainer_material: str,
) -> Dict[str, Any]:
    """
    Alloy guidance for strainer nozzles (screwed into nozzle plate).

    Advisory only — not a materials specification.
    """
    mat = normalize_strainer_material(strainer_material)
    svc = water_service_class(salinity_ppt)
    pren = STRAINER_PREN_TYPICAL.get(mat)
    findings: List[Dict[str, str]] = []
    recommendations: List[str] = []
    suggested = suggested_strainer_material(salinity_ppt)

    if svc == "seawater":
        if mat == "SS316":
            findings.append({
                "severity": "warning",
                "topic": "High chloride — SS316",
                "detail": (
                    "**SS316 / 316L** is generally **not acceptable** for long-term seawater "
                    "strainer service (pitting, crevice at plate threads, under-deposit attack)."
                ),
            })
        if mat == "Duplex_2205":
            findings.append({
                "severity": "advisory",
                "topic": "PREN vs client spec",
                "detail": (
                    "**Duplex 2205** (typical PREN ~35) may **not** satisfy owner specs requiring "
                    "**PREN > 40** or **> 42** — confirm with corrosion engineer."
                ),
            })
        if mat in ("PP", "HDPE"):
            findings.append({
                "severity": "advisory",
                "topic": "Polymer strainers in seawater",
                "detail": (
                    "**PP / HDPE** can be suitable when the underdrain is fully polymer and "
                    "mechanical design (threaded insert, ΔP, temperature, BW) is proven."
                ),
            })
        if mat == "Super_duplex_2507":
            recommendations.append(
                "Super duplex **2507** is a common default for SWRO strainers (typical PREN > 40)."
            )
        if mat == "Super_duplex_PREN42":
            recommendations.append(
                "PREN > 42 grade (e.g. **2507**, **Zeron 100**) — aligns with conservative EPC schedules."
            )
        if mat != suggested:
            recommendations.append(
                f"For **{salinity_ppt:.1f} ppt** feed, suggested selection: "
                f"**{strainer_material_label(suggested)}**."
            )
    elif svc == "brackish":
        if mat == "SS316":
            recommendations.append(
                "Brackish: **316L** strainers are often used — confirm chlorides, stagnation, and chlorination."
            )
        if mat in ("Super_duplex_2507", "Super_duplex_PREN42"):
            recommendations.append(
                "Super duplex is conservative for brackish — acceptable if client mandates duplex family."
            )
    else:
        if mat in ("Super_duplex_2507", "Super_duplex_PREN42", "Duplex_2205"):
            recommendations.append(
                "Fresh water: super duplex / duplex is usually not required on cost grounds unless specified."
            )

    tone = "ok"
    if any(f.get("severity") == "warning" for f in findings):
        tone = "warning"
    elif findings or recommendations:
        tone = "advisory"

    return {
        "material": mat,
        "material_label": strainer_material_label(mat),
        "water_service": svc,
        "salinity_ppt": round(float(salinity_ppt), 2),
        "pren_typical": pren,
        "suggested_material": suggested,
        "suggested_label": strainer_material_label(suggested),
        "findings": findings,
        "recommendations": recommendations,
        "tone": tone,
    }
