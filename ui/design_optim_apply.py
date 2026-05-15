"""Apply plant-level optimisation patches to Streamlit session widgets."""
from __future__ import annotations

from typing import Any

from engine.project_io import WIDGET_KEY_MAP
from engine.units import display_value

# SI input keys the grid ranker may patch (extend as optimise_design patches grow).
PLANT_PATCH_QUANTITIES: dict[str, str | None] = {
    "n_filters": None,
    "redundancy": None,
    "hydraulic_assist": None,
    "streams": None,
    "nominal_id": "length_m",
    "total_length": "length_m",
    "total_flow": "flow_m3h",
    "bw_velocity": "velocity_m_h",
    "dp_trigger_bar": "pressure_bar",
}


def _widget_key(inputs_key: str) -> str:
    return WIDGET_KEY_MAP.get(inputs_key, inputs_key)


def plant_patch_to_session_updates(
    patch: dict[str, Any],
    unit_system: str,
) -> dict[str, Any]:
    """Map SI ``patch`` from ``optimise_design`` to ``session_state`` widget values."""
    updates: dict[str, Any] = {}
    for key, val in patch.items():
        if key not in PLANT_PATCH_QUANTITIES or val is None:
            continue
        wgt = _widget_key(key)
        qty = PLANT_PATCH_QUANTITIES[key]
        if qty is None:
            if key in ("n_filters", "redundancy", "hydraulic_assist", "streams"):
                updates[wgt] = int(val)
            else:
                updates[wgt] = val
        else:
            updates[wgt] = display_value(float(val), qty, unit_system)
    return updates


def apply_plant_patch_to_session(patch: dict[str, Any], unit_system: str) -> list[str]:
    """Write patch into ``st.session_state``; return list of applied input keys."""
    import streamlit as st

    wgt_to_inp = {_widget_key(inp): inp for inp in PLANT_PATCH_QUANTITIES}
    applied: list[str] = []
    for wgt, wval in plant_patch_to_session_updates(patch, unit_system).items():
        st.session_state[wgt] = wval
        applied.append(wgt_to_inp.get(wgt, wgt))
    return applied


def objective_display_name(objective: str) -> str:
    return {
        "capex": "Total CAPEX (USD)",
        "opex": "Annual OPEX (USD/yr)",
        "steel": "Empty steel weight (kg)",
        "carbon": "Lifecycle CO₂ (kg)",
    }.get(objective, objective)


_OBJECTIVE_METRIC_KEYS = {
    "capex": "total_capex_usd",
    "opex": "total_opex_usd_yr",
    "steel": "steel_kg",
    "carbon": "co2_lifecycle_kg",
}


def objective_metric_key(objective: str) -> str:
    return _OBJECTIVE_METRIC_KEYS.get(objective, "total_capex_usd")
