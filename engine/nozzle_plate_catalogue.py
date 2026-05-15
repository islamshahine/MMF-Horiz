"""
Underdrain / nozzle-plate product catalogue (screening references).

Not vendor-certified submittals — use for bore, Cd, and density starting points only.
"""
from __future__ import annotations

from typing import Any

# Representative products for MMF underdrain screening (SI stored).
NOZZLE_PLATE_CATALOGUE: list[dict[str, Any]] = [
    {
        "id": "generic_drilled_50",
        "vendor": "Generic",
        "product": "Drilled PE / SS plate — 50 mm bore",
        "type": "drilled",
        "bore_mm": 50.0,
        "slot_width_mm": 0.0,
        "open_area_pct_typical": 4.5,
        "discharge_cd": 0.62,
        "max_velocity_m_s": 2.0,
        "density_per_m2_typical": 45.0,
        "notes": "Common legacy MMF drilled plate; verify with fabricator drawing.",
    },
    {
        "id": "generic_drilled_38",
        "vendor": "Generic",
        "product": "Drilled plate — 38 mm bore",
        "type": "drilled",
        "bore_mm": 38.0,
        "slot_width_mm": 0.0,
        "open_area_pct_typical": 3.2,
        "discharge_cd": 0.62,
        "max_velocity_m_s": 2.2,
        "density_per_m2_typical": 55.0,
        "notes": "Tighter hole count for same plate area vs 50 mm.",
    },
    {
        "id": "johnson_slot_0.25mm",
        "vendor": "Johnson Screens (style)",
        "product": "Wedge-wire slot — 0.25 mm slot",
        "type": "slotted",
        "bore_mm": 0.0,
        "slot_width_mm": 0.25,
        "open_area_pct_typical": 6.0,
        "discharge_cd": 0.70,
        "max_velocity_m_s": 1.5,
        "density_per_m2_typical": 80.0,
        "notes": "Use slot width as hydraulic opening; confirm open area % with supplier.",
    },
    {
        "id": "johnson_slot_0.5mm",
        "vendor": "Johnson Screens (style)",
        "product": "Wedge-wire slot — 0.50 mm slot",
        "type": "slotted",
        "bore_mm": 0.0,
        "slot_width_mm": 0.50,
        "open_area_pct_typical": 8.0,
        "discharge_cd": 0.70,
        "max_velocity_m_s": 1.8,
        "density_per_m2_typical": 70.0,
        "notes": "Finer slot — higher density typical on plate.",
    },
    {
        "id": "hansen_aquaflow_2mm",
        "vendor": "Hansen (style)",
        "product": "Aquaflow-type slotted insert — 2.0 mm slot",
        "type": "slotted",
        "bore_mm": 0.0,
        "slot_width_mm": 2.0,
        "open_area_pct_typical": 12.0,
        "discharge_cd": 0.65,
        "max_velocity_m_s": 2.5,
        "density_per_m2_typical": 50.0,
        "notes": "Insert-style underdrain; map slot to lateral orifice in collector model separately.",
    },
    {
        "id": "leopold_imt_2mm",
        "vendor": "Leopold (style)",
        "product": "IMT slotted cap — 2.0 mm slot",
        "type": "slotted",
        "bore_mm": 0.0,
        "slot_width_mm": 2.0,
        "open_area_pct_typical": 10.0,
        "discharge_cd": 0.65,
        "max_velocity_m_s": 2.3,
        "density_per_m2_typical": 48.0,
        "notes": "Cap-style underdrain reference for dual-media beds.",
    },
]

_BY_ID: dict[str, dict[str, Any]] = {p["id"]: p for p in NOZZLE_PLATE_CATALOGUE}


def list_catalogue_products() -> list[dict[str, Any]]:
    return [dict(p) for p in NOZZLE_PLATE_CATALOGUE]


def get_catalogue_product(product_id: str | None) -> dict[str, Any] | None:
    if not product_id:
        return None
    return _BY_ID.get(str(product_id).strip())


def catalogue_patch_for_product(product_id: str) -> dict[str, Any]:
    """
    Sidebar SI patch from catalogue selection.

    Sets ``np_bore_dia`` (mm), ``np_density``, optional ``lateral_discharge_cd``,
    ``wedge_slot_width_mm`` for slotted types.
    """
    p = get_catalogue_product(product_id)
    if not p:
        return {}
    patch: dict[str, Any] = {
        "nozzle_catalogue_id": p["id"],
        "nozzle_catalogue_label": f"{p['vendor']} — {p['product']}",
        "np_density": float(p["density_per_m2_typical"]),
        "lateral_discharge_cd": float(p["discharge_cd"]),
    }
    if p["type"] == "drilled" and float(p.get("bore_mm") or 0) > 0:
        patch["np_bore_dia"] = float(p["bore_mm"])
        patch["lateral_orifice_d_mm"] = float(p["bore_mm"])
    if p["type"] == "slotted" and float(p.get("slot_width_mm") or 0) > 0:
        patch["wedge_slot_width_mm"] = float(p["slot_width_mm"])
        patch["lateral_construction"] = "Wedge wire screen lateral"
    return patch


def catalogue_display_rows() -> list[dict[str, Any]]:
    """Flat rows for UI table (SI values; format in UI)."""
    rows = []
    for p in NOZZLE_PLATE_CATALOGUE:
        rows.append({
            "id": p["id"],
            "vendor": p["vendor"],
            "product": p["product"],
            "type": p["type"],
            "bore_mm": p.get("bore_mm") or "—",
            "slot_mm": p.get("slot_width_mm") or "—",
            "ρ_typ (/m²)": p.get("density_per_m2_typical"),
            "Cd": p.get("discharge_cd"),
            "V_max (m/s)": p.get("max_velocity_m_s"),
        })
    return rows
