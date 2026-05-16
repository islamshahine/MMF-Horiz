"""Underdrain system coherence — catalogue, density, strainer (advisory)."""
from __future__ import annotations

from typing import Any, Dict, List

from engine.nozzle_plate_catalogue import (
    DRILLED_DENSITY_TYPICAL_MAX,
    DRILLED_DENSITY_TYPICAL_MIN,
    catalogue_application_warnings,
    get_catalogue_product,
    underdrain_inputs_summary,
    uses_drilled_density_band,
)
from engine.strainer_materials import (
    is_polymer_body_material,
    normalize_strainer_material,
    resolve_strainer_for_catalogue,
    strainer_material_advisory,
    strainer_material_label,
    suggested_strainer_material,
)


def build_underdrain_system_advisory(
    inputs: dict,
    *,
    salinity_ppt: float,
) -> Dict[str, Any]:
    """Cross-check Media nozzle inputs vs strainer alloy vs catalogue."""
    summary = underdrain_inputs_summary(inputs)
    raw_cid = str(inputs.get("nozzle_catalogue_id") or "").strip()
    strainer = normalize_strainer_material(inputs.get("strainer_mat", ""))
    sal_adv = strainer_material_advisory(
        salinity_ppt=float(salinity_ppt),
        strainer_material=strainer,
    )
    findings: List[Dict[str, str]] = list(sal_adv.get("findings") or [])
    recommendations: List[str] = list(sal_adv.get("recommendations") or [])

    cid = summary.get("catalogue_id")
    prod = get_catalogue_product(cid) if cid else None
    findings.extend(catalogue_application_warnings(raw_cid))
    if prod:
        expected = resolve_strainer_for_catalogue(prod, salinity_ppt)
        if normalize_strainer_material(expected) != strainer:
            family = str(prod.get("strainer_body_family", "")).lower()
            if family == "polymer" or is_polymer_body_material(str(prod.get("body_material", ""))):
                findings.append({
                    "severity": "advisory",
                    "topic": "Polymer body vs strainer",
                    "detail": (
                        f"Catalogue **{prod['id']}** expects strainer **{strainer_material_label(expected)}**; "
                        f"you selected **{strainer_material_label(strainer)}**."
                    ),
                })
            else:
                sal_def = strainer_material_label(
                    suggested_strainer_material(salinity_ppt),
                )
                findings.append({
                    "severity": "advisory",
                    "topic": "Metal underdrain vs strainer",
                    "detail": (
                        f"At **{salinity_ppt:.1f} ppt**, default metal strainer is **{sal_def}**; "
                        f"you selected **{strainer_material_label(strainer)}**. "
                        "Metal underdrain products accept **SS316, duplex, or super duplex**."
                    ),
                })

    dens = float(summary.get("np_density_per_m2") or 0.0)
    if uses_drilled_density_band(cid) and (
        dens < DRILLED_DENSITY_TYPICAL_MIN or dens > DRILLED_DENSITY_TYPICAL_MAX
    ):
        findings.append({
            "severity": "advisory",
            "topic": "Hole density",
            "detail": (
                f"Drilled plate target **{dens:.0f} /m²** outside typical "
                f"**{DRILLED_DENSITY_TYPICAL_MIN:.0f}–{DRILLED_DENSITY_TYPICAL_MAX:.0f} /m²** — "
                "Mechanical hole count may clamp unless layout uses brick algorithm."
            ),
        })

    tone = sal_adv.get("tone", "ok")
    if any(f.get("severity") == "warning" for f in findings):
        tone = "warning"
    elif findings and tone == "ok":
        tone = "advisory"

    return {
        **summary,
        "strainer_label": strainer_material_label(strainer),
        "salinity_ppt": float(salinity_ppt),
        "findings": findings,
        "recommendations": recommendations,
        "tone": tone,
    }
