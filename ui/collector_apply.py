"""Apply collector screening / 1D model suggestions to sidebar session widgets."""
from __future__ import annotations

from typing import Any


def suggested_collector_inputs_si(collector_hyd: dict | None) -> dict[str, Any]:
    """Map ``collector_hyd`` outputs to SI input keys (no Streamlit)."""
    ch = collector_hyd or {}
    if not ch:
        return {}
    des = ch.get("design") or {}
    patch: dict[str, Any] = {}

    n_sug = des.get("n_laterals_suggested") or ch.get("n_laterals")
    if n_sug:
        patch["n_bw_laterals"] = max(1, min(24, int(n_sug)))

    dn = des.get("lateral_dn_suggest_mm") or ch.get("lateral_dn_mm")
    if dn and float(dn) > 0:
        patch["lateral_dn_mm"] = float(dn)

    sp = ch.get("lateral_spacing_m") or des.get("lateral_spacing_used_m")
    if sp and float(sp) > 0:
        patch["lateral_spacing_m"] = float(sp)

    orf = des.get("perforation_d_suggest_mm") or ch.get("lateral_orifice_d_mm")
    if orf and float(orf) > 0:
        patch["lateral_orifice_d_mm"] = float(orf)

    n_perf = ch.get("n_orifices_per_lateral")
    if n_perf and int(n_perf) > 0:
        patch["n_orifices_per_lateral"] = int(n_perf)

    mal = ch.get("maldistribution_factor_calc")
    if mal and float(mal) >= 1.0:
        patch["use_calculated_maldistribution"] = True
        patch["maldistribution_factor"] = min(2.0, float(mal))

    patch["use_geometry_lateral"] = True
    patch["lateral_length_m"] = 0.0

    hid = ch.get("collector_header_id_m")
    if hid and float(hid) > 0:
        patch["collector_header_id_m"] = float(hid)

    return patch


def apply_collector_suggested_design(computed: dict) -> None:
    """Write suggested collector inputs into ``st.session_state`` (display units)."""
    import streamlit as st

    from engine.units import display_value

    patch_si = suggested_collector_inputs_si(computed.get("collector_hyd"))
    if not patch_si:
        return

    us = st.session_state.get("unit_system", "metric")
    linked_header = bool(st.session_state.get("collector_header_id_linked", True))

    if "n_bw_laterals" in patch_si:
        st.session_state["n_bw_laterals"] = int(patch_si["n_bw_laterals"])
    if "lateral_dn_mm" in patch_si:
        st.session_state["lateral_dn_mm"] = display_value(
            patch_si["lateral_dn_mm"], "length_mm", us,
        )
    if "lateral_spacing_m" in patch_si:
        st.session_state["lateral_spacing_m"] = display_value(
            patch_si["lateral_spacing_m"], "length_m", us,
        )
    if "lateral_orifice_d_mm" in patch_si:
        st.session_state["lateral_orifice_d_mm"] = display_value(
            patch_si["lateral_orifice_d_mm"], "length_mm", us,
        )
    if "n_orifices_per_lateral" in patch_si:
        st.session_state["n_orifices_per_lateral"] = int(patch_si["n_orifices_per_lateral"])
    if "use_calculated_maldistribution" in patch_si:
        st.session_state["use_calculated_maldistribution"] = bool(
            patch_si["use_calculated_maldistribution"]
        )
    if "maldistribution_factor" in patch_si:
        st.session_state["maldistribution_factor"] = float(patch_si["maldistribution_factor"])
    if "use_geometry_lateral" in patch_si:
        st.session_state["use_geometry_lateral"] = True
    if "lateral_length_m" in patch_si:
        st.session_state["lateral_length_m"] = 0.0

    if not linked_header and "collector_header_id_m" in patch_si:
        st.session_state["collector_header_id_manual"] = display_value(
            patch_si["collector_header_id_m"], "length_m", us,
        )


def apply_collector_patch_to_session(patch_si: dict[str, Any], unit_system: str) -> None:
    """Apply an SI patch dict (from optimizer or screening) to Streamlit widget keys."""
    import streamlit as st

    from engine.units import display_value

    if not patch_si:
        return
    if "n_bw_laterals" in patch_si:
        st.session_state["n_bw_laterals"] = int(patch_si["n_bw_laterals"])
    if "lateral_dn_mm" in patch_si:
        st.session_state["lateral_dn_mm"] = display_value(
            patch_si["lateral_dn_mm"], "length_mm", unit_system,
        )
    if "lateral_spacing_m" in patch_si:
        st.session_state["lateral_spacing_m"] = display_value(
            patch_si["lateral_spacing_m"], "length_m", unit_system,
        )
    if "lateral_orifice_d_mm" in patch_si:
        st.session_state["lateral_orifice_d_mm"] = display_value(
            patch_si["lateral_orifice_d_mm"], "length_mm", unit_system,
        )
    if "n_orifices_per_lateral" in patch_si:
        st.session_state["n_orifices_per_lateral"] = int(patch_si["n_orifices_per_lateral"])
    if "use_calculated_maldistribution" in patch_si:
        st.session_state["use_calculated_maldistribution"] = bool(
            patch_si["use_calculated_maldistribution"],
        )
    if "maldistribution_factor" in patch_si:
        st.session_state["maldistribution_factor"] = float(patch_si["maldistribution_factor"])
    if patch_si.get("use_geometry_lateral"):
        st.session_state["use_geometry_lateral"] = True
        st.session_state["lateral_length_m"] = display_value(0.0, "length_m", unit_system)
    linked_header = bool(st.session_state.get("collector_header_id_linked", True))
    if not linked_header and "collector_header_id_m" in patch_si:
        st.session_state["collector_header_id_manual"] = display_value(
            patch_si["collector_header_id_m"], "length_m", unit_system,
        )
