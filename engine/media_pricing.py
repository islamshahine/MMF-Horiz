"""
Regional media **budget reference** (USD) — not a quote or API.

Uses Economics-tab media unit costs when present; otherwise typical USD/m³ fill bands.
"""
from __future__ import annotations

from typing import Any

# Typical delivered bulk fill (USD/m³ in place — screening order of magnitude)
_DEFAULT_USD_PER_M3: dict[str, float] = {
    "Gravel": 90.0,
    "Fine sand": 160.0,
    "Anthracite": 380.0,
    "Garnet": 520.0,
    "MnO2": 1200.0,
    "Custom": 200.0,
}

REGION_FACTOR: dict[str, float] = {
    "global": 1.0,
    "gcc": 1.12,
    "western_europe": 1.18,
    "southeast_asia": 0.93,
    "north_america": 1.05,
}


def _usd_m3_for_type(layer_type: str, inputs: dict) -> float:
    t = str(layer_type or "Custom")
    low = t.lower()
    if "gravel" in low:
        return float(inputs.get("econ_media_gravel") or _DEFAULT_USD_PER_M3["Gravel"])
    if "sand" in low or "anthracite" in low:
        if "anthracite" in low:
            return float(inputs.get("econ_media_anthracite") or _DEFAULT_USD_PER_M3["Anthracite"])
        return float(inputs.get("econ_media_sand") or _DEFAULT_USD_PER_M3["Fine sand"])
    for key, val in _DEFAULT_USD_PER_M3.items():
        if key.lower() in low or low in key.lower():
            return float(val)
    return float(_DEFAULT_USD_PER_M3["Custom"])


def estimate_media_inventory_budget(
    *,
    base_layers: list[dict],
    n_filters: int,
    streams: int,
    inputs: dict | None = None,
    region: str = "global",
) -> dict[str, Any]:
    """
    One-time fill cost estimate (all parallel filters).

    ``base_layers`` = ``computed["base"]`` with ``Vol`` (m³) per row.
    """
    inputs = inputs or {}
    reg = str(region or "global").strip().lower()
    fac = float(REGION_FACTOR.get(reg, 1.0))
    n_plant = max(1, int(n_filters) * int(streams))

    lines: list[dict[str, Any]] = []
    total = 0.0
    for b in base_layers:
        vol_one = float(b.get("Vol", 0.0) or 0.0)
        if vol_one <= 0:
            continue
        mtype = str(b.get("Type", "Media"))
        usd_m3 = _usd_m3_for_type(mtype, inputs)
        cost_layer = vol_one * n_plant * usd_m3 * fac
        total += cost_layer
        lines.append({
            "media": mtype,
            "vol_one_filter_m3": round(vol_one, 3),
            "plant_vol_m3": round(vol_one * n_plant, 2),
            "usd_per_m3": round(usd_m3 * fac, 1),
            "extended_usd": round(cost_layer, 0),
        })

    return {
        "region": reg,
        "region_factor": fac,
        "n_filters": int(n_filters),
        "streams": int(streams),
        "filters_plant_wide": n_plant,
        "lines": lines,
        "total_fill_usd": round(total, 0),
        "disclaimer": "Budget reference only — confirm with purchase orders / local vendors.",
    }
