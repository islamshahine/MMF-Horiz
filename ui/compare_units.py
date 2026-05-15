"""Design B compare-tab widgets — unit-toggle sync (display values in session_state)."""
from __future__ import annotations

import streamlit as st

from engine.units import display_value, transpose_display_value

# Streamlit widget keys on the Compare tab → quantity (must match tab_compare editable fields).
COMPARE_B_WIDGET_QUANTITIES: dict[str, str] = {
    "b_nominal_id": "length_m",
    "b_total_length": "length_m",
    "b_nozzle_plate_h": "length_m",
    "b_collector_h": "length_m",
    "b_bw_velocity": "velocity_m_h",
    "b_air_scour_rate": "velocity_m_h",
}


def reconvert_compare_b_widgets(old_system: str, new_system: str) -> None:
    """Transpose Compare Design B number_input session keys when unit_system changes."""
    if old_system == new_system:
        return
    for wkey, qty in COMPARE_B_WIDGET_QUANTITIES.items():
        if wkey not in st.session_state:
            continue
        v = st.session_state[wkey]
        if not isinstance(v, (int, float)):
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        st.session_state[wkey] = transpose_display_value(fv, qty, old_system, new_system)


def seed_compare_b_widgets_from_si(b_si: dict, unit_system: str) -> None:
    """Push SI compare_inputs_b values into widget session keys (e.g. after reset to A)."""
    for wkey, qty in COMPARE_B_WIDGET_QUANTITIES.items():
        field = wkey[2:]  # b_nominal_id → nominal_id
        if field not in b_si:
            continue
        val = b_si[field]
        if isinstance(val, (int, float)):
            st.session_state[wkey] = float(display_value(float(val), qty, unit_system))
    sm = str(b_si.get("air_scour_mode", "manual")).strip().lower()
    if sm in ("manual", "auto_expansion"):
        st.session_state["b_air_scour_mode_sel"] = sm
    if "air_scour_target_expansion_pct" in b_si:
        st.session_state["b_air_scour_target_expansion_pct"] = float(
            b_si["air_scour_target_expansion_pct"]
        )
