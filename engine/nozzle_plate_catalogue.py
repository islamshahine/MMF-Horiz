"""
Underdrain / nozzle-plate product catalogue (screening references).

Pressurized horizontal MMF nozzle-plate products only — not gravity-filter blocks
or feed / backwash-out collector drilled orifices.

Not vendor-certified submittals — use for bore, Cd, density, and strainer alloy starting points only.
"""
from __future__ import annotations

from typing import Any, Dict, List

# Drilled false-bottom industry band (mechanical screening) — wedge/mushroom often higher.
DRILLED_DENSITY_TYPICAL_MIN = 45.0
DRILLED_DENSITY_TYPICAL_MAX = 55.0
NOZZLE_DENSITY_INPUT_MIN = 35.0
NOZZLE_DENSITY_INPUT_MAX = 100.0

# Representative products for pressurized MMF underdrain screening (SI stored).
NOZZLE_PLATE_CATALOGUE: list[dict[str, Any]] = [
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
        "body_material": "SS / Duplex / Super duplex wedge wire",
        "strainer_body_family": "metal",
        "strainer_material_options": ("SS316", "Duplex_2205", "Super_duplex_2507", "Super_duplex_PREN42"),
        "notes": "High-efficiency wedge-wire lateral/screen for gravel-less beds.",
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
        "body_material": "SS / Duplex / Super duplex wedge wire",
        "strainer_body_family": "metal",
        "strainer_material_options": ("SS316", "Duplex_2205", "Super_duplex_2507", "Super_duplex_PREN42"),
        "notes": "Wedge-wire screen for coarse sand or fine gravel contact layers.",
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
        "body_material": "SS / polymer insert",
        "strainer_body_family": "metal",
        "strainer_material_options": ("SS316", "Duplex_2205", "Super_duplex_2507"),
        "notes": "Insert-style underdrain; map slot to lateral orifice in collector model separately.",
    },
    {
        "id": "pp_mushroom_fine_0.2",
        "vendor": "Generic PP",
        "product": "PP Mushroom Nozzle — 0.2 mm slot",
        "type": "mushroom",
        "bore_mm": 20.0,
        "slot_width_mm": 0.20,
        "open_area_pct_typical": 5.5,
        "discharge_cd": 0.62,
        "max_velocity_m_s": 1.4,
        "density_per_m2_typical": 60.0,
        "body_material": "PP",
        "strainer_body_family": "polymer",
        "strainer_material_fixed": "PP",
        "notes": "Polypropylene mushroom nozzle for direct 0.6 mm sand placement.",
    },
    {
        "id": "pp_mushroom_fine_0.5",
        "vendor": "Generic PP",
        "product": "PP Mushroom Nozzle — 0.5 mm slot",
        "type": "mushroom",
        "bore_mm": 20.0,
        "slot_width_mm": 0.50,
        "open_area_pct_typical": 5.0,
        "discharge_cd": 0.62,
        "max_velocity_m_s": 1.6,
        "density_per_m2_typical": 55.0,
        "body_material": "PP",
        "strainer_body_family": "polymer",
        "strainer_material_fixed": "PP",
        "notes": "Polypropylene mushroom nozzle for coarse sand direct placement.",
    },
    {
        "id": "pp_mushroom_coarse_1",
        "vendor": "Generic PP",
        "product": "PP Mushroom Nozzle — 1.0 mm slot",
        "type": "mushroom",
        "bore_mm": 24.0,
        "slot_width_mm": 1.00,
        "open_area_pct_typical": 4.8,
        "discharge_cd": 0.64,
        "max_velocity_m_s": 2.2,
        "density_per_m2_typical": 50.0,
        "body_material": "PP",
        "strainer_body_family": "polymer",
        "strainer_material_fixed": "PP",
        "notes": "Polypropylene mushroom nozzle used with fine support gravel layers.",
    },
    {
        "id": "pp_mushroom_coarse_2",
        "vendor": "Generic PP",
        "product": "PP Mushroom Nozzle — 2.0 mm slot",
        "type": "mushroom",
        "bore_mm": 24.0,
        "slot_width_mm": 2.00,
        "open_area_pct_typical": 4.5,
        "discharge_cd": 0.65,
        "max_velocity_m_s": 2.4,
        "density_per_m2_typical": 48.0,
        "body_material": "PP",
        "strainer_body_family": "polymer",
        "strainer_material_fixed": "PP",
        "notes": "Polypropylene mushroom nozzle optimized for 5 mm support gravel beds.",
    },
    {
        "id": "hdpe_mushroom_fine_0.5",
        "vendor": "Generic HDPE",
        "product": "HDPE Mushroom Nozzle — 0.5 mm slot",
        "type": "mushroom",
        "bore_mm": 20.0,
        "slot_width_mm": 0.50,
        "open_area_pct_typical": 5.0,
        "discharge_cd": 0.62,
        "max_velocity_m_s": 1.6,
        "density_per_m2_typical": 55.0,
        "body_material": "HDPE",
        "strainer_body_family": "polymer",
        "strainer_material_fixed": "HDPE",
        "notes": "HDPE mushroom nozzle — brackish / low-temperature duty; confirm mechanical rating.",
    },
    {
        "id": "hdpe_mushroom_coarse_2",
        "vendor": "Generic HDPE",
        "product": "HDPE Mushroom Nozzle — 2.0 mm slot",
        "type": "mushroom",
        "bore_mm": 24.0,
        "slot_width_mm": 2.00,
        "open_area_pct_typical": 4.5,
        "discharge_cd": 0.65,
        "max_velocity_m_s": 2.4,
        "density_per_m2_typical": 48.0,
        "body_material": "HDPE",
        "strainer_body_family": "polymer",
        "strainer_material_fixed": "HDPE",
        "notes": "HDPE mushroom with support gravel — common for corrosion-resistant underdrains.",
    },
]

_REMOVED_CATALOGUE_IDS = frozenset({
    "generic_drilled_50",
    "generic_drilled_38",
    "hdpe_drilled_38",
    "collector_drilled_50",
    "collector_drilled_38",
    "collector_drilled_hdpe_38",
    "leopold_imt_2mm",
})

_BY_ID: dict[str, dict[str, Any]] = {p["id"]: p for p in NOZZLE_PLATE_CATALOGUE}


def list_catalogue_products() -> list[dict[str, Any]]:
    return [dict(p) for p in NOZZLE_PLATE_CATALOGUE]


def list_catalogue_products_sorted() -> list[dict[str, Any]]:
    return sorted(
        NOZZLE_PLATE_CATALOGUE,
        key=lambda p: (str(p.get("vendor", "")), str(p.get("product", ""))),
    )


def catalogue_select_label(product_id: str) -> str:
    if not product_id:
        return "Custom (manual)"
    p = get_catalogue_product(product_id)
    if not p:
        return product_id
    return f"{p['vendor']} — {p['product']}"


def get_catalogue_product(product_id: str | None) -> dict[str, Any] | None:
    if not product_id:
        return None
    pid = str(product_id).strip()
    if pid in _REMOVED_CATALOGUE_IDS:
        return None
    return _BY_ID.get(pid)


def catalogue_application_warnings(product_id: str | None) -> List[Dict[str, str]]:
    """Stale underdrain catalogue IDs from older builds."""
    pid = str(product_id or "").strip()
    if pid in _REMOVED_CATALOGUE_IDS:
        return [{
            "severity": "warning",
            "topic": "Catalogue entry removed",
            "detail": (
                f"**{pid}** is no longer in the underdrain nozzle list "
                "(gravity-filter and collector-drilled references were removed). "
                "Choose a mushroom or wedge-wire product, or use **Custom (manual)**."
            ),
        }]
    return []


def uses_drilled_density_band(product_id: str | None) -> bool:
    """45–55 /m² band applies to pressurized drilled false-bottom plates (manual entry)."""
    p = get_catalogue_product(product_id)
    if not p:
        return True
    return str(p.get("type", "")).lower() == "drilled"


def catalogue_patch_for_product(
    product_id: str,
    *,
    salinity_ppt: float = 35.0,
) -> dict[str, Any]:
    """
    Sidebar SI patch from catalogue selection.

    Sets ``np_bore_dia``, ``np_density``, ``lateral_discharge_cd``, slot width,
    optional ``strainer_mat``, and ``underdrain_type``.
    """
    p = get_catalogue_product(product_id)
    if not p:
        return {}
    label = f"{p['vendor']} — {p['product']}"
    patch: dict[str, Any] = {
        "nozzle_catalogue_id": p["id"],
        "nozzle_catalogue_label": label,
        "np_density": float(p["density_per_m2_typical"]),
        "lateral_discharge_cd": float(p["discharge_cd"]),
        "underdrain_type": "nozzle_plate",
    }
    ptype = str(p.get("type", "")).lower()
    if ptype == "drilled" and float(p.get("bore_mm") or 0) > 0:
        patch["np_bore_dia"] = float(p["bore_mm"])
        patch["lateral_orifice_d_mm"] = float(p["bore_mm"])
    if ptype in ("slotted", "mushroom") and float(p.get("slot_width_mm") or 0) > 0:
        patch["wedge_slot_width_mm"] = float(p["slot_width_mm"])
        if ptype == "slotted":
            patch["lateral_construction"] = "Wedge wire screen lateral"
    if ptype == "mushroom":
        if float(p.get("bore_mm") or 0) > 0:
            patch["np_bore_dia"] = float(p["bore_mm"])
            patch["lateral_orifice_d_mm"] = float(p["bore_mm"])
        patch["lateral_construction"] = "Drilled perforated pipe"
    from engine.strainer_materials import resolve_strainer_for_catalogue

    patch["strainer_mat"] = resolve_strainer_for_catalogue(p, salinity_ppt)
    return patch


def density_input_guidance(*, catalogue_id: str | None, np_density: float) -> List[str]:
    """Advisory lines for Media sidebar density field."""
    lines: List[str] = []
    dens = float(np_density)
    if uses_drilled_density_band(catalogue_id):
        if DRILLED_DENSITY_TYPICAL_MIN <= dens <= DRILLED_DENSITY_TYPICAL_MAX:
            lines.append(
                f"Density **{dens:.0f} /m²** is within the usual **drilled false-bottom** band "
                f"(**{DRILLED_DENSITY_TYPICAL_MIN:.0f}–{DRILLED_DENSITY_TYPICAL_MAX:.0f} /m²**)."
            )
        else:
            lines.append(
                f"Density **{dens:.0f} /m²** is outside the usual drilled band "
                f"**{DRILLED_DENSITY_TYPICAL_MIN:.0f}–{DRILLED_DENSITY_TYPICAL_MAX:.0f} /m²** — "
                "confirm with layout / supplier."
            )
    else:
        p = get_catalogue_product(catalogue_id)
        typ = float(p["density_per_m2_typical"]) if p else dens
        lines.append(
            f"**{p['type'].title() if p else 'Catalogue'}** products often use **{typ:.0f} /m²** typical "
            f"(your input **{dens:.0f} /m²**). Wedge-wire and mushroom counts are not limited to 45–55."
        )
    return lines


def catalogue_display_rows(*, salinity_ppt: float = 35.0) -> list[dict[str, Any]]:
    """Flat rows for UI table (SI values)."""
    from engine.strainer_materials import catalogue_strainer_hint

    rows = []
    for p in NOZZLE_PLATE_CATALOGUE:
        rows.append({
            "id": p["id"],
            "vendor": p["vendor"],
            "product": p["product"],
            "type": p["type"],
            "body": p.get("body_material", "—"),
            "bore_mm": p.get("bore_mm") or "—",
            "slot_mm": p.get("slot_width_mm") or "—",
            "ρ_typ (/m²)": p.get("density_per_m2_typical"),
            "Cd": p.get("discharge_cd"),
            "V_max (m/s)": p.get("max_velocity_m_s"),
            "strainer": catalogue_strainer_hint(p, salinity_ppt),
            "description": p.get("notes", ""),
        })
    return rows


def underdrain_inputs_summary(inputs: dict) -> Dict[str, Any]:
    """Single summary for Media / BW / compute — links plate, catalogue, strainer."""
    cid = str(inputs.get("nozzle_catalogue_id") or "").strip()
    if cid in _REMOVED_CATALOGUE_IDS:
        cid = ""
    prod = get_catalogue_product(cid) if cid else None
    dens = float(inputs.get("np_density") or 0.0)
    return {
        "catalogue_id": cid or None,
        "catalogue_label": inputs.get("nozzle_catalogue_label") or (
            f"{prod['vendor']} — {prod['product']}" if prod else "Custom (manual)"
        ),
        "product_type": prod.get("type") if prod else "custom",
        "np_density_per_m2": dens,
        "np_bore_mm": float(inputs.get("np_bore_dia") or 0.0),
        "strainer_material": str(inputs.get("strainer_mat") or ""),
        "density_guidance": density_input_guidance(catalogue_id=cid, np_density=dens),
        "uses_drilled_density_band": uses_drilled_density_band(cid),
    }
