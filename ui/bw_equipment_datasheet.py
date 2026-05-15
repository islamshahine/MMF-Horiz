"""Shared BW pump / blower / tank equipment data sheet (Pumps & power tab)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.helpers import fmt, ulbl


def render_bw_system_equipment_datasheet(
    *,
    bw_sizing: dict,
    vessel_pressure_bar: float,
    blower_air_delta_p_bar: float,
    n_bw_systems: int,
    expanded: bool = True,
) -> None:
    """Pump, blower, and BW storage tank duty tables from ``bw_system_sizing``."""
    with st.expander(
        "BW system equipment — pump, blower & storage tank",
        expanded=expanded,
    ):
        st.caption(
            "Engineering duty from the BW equipment model (`engine/backwash.py` · `bw_system_sizing`). "
            "Philosophy (DOL/VFD), installed counts, and CAPEX live in the sections above."
        )
        st.markdown("#### BW pump")
        p1, p2, p3, p4 = st.columns(4)
        p1.metric(f"Design flow ({ulbl('flow_m3h')})", fmt(bw_sizing["q_bw_design_m3h"], "flow_m3h", 0))
        p2.metric(f"Total head ({ulbl('pressure_mwc')})", fmt(bw_sizing["bw_head_mwc"], "pressure_mwc", 1))
        p3.metric(f"Shaft power ({ulbl('power_kw')})", fmt(bw_sizing["p_pump_shaft_kw"], "power_kw", 0))
        p4.metric(f"Motor power ({ulbl('power_kw')})", fmt(bw_sizing["p_pump_motor_kw"], "power_kw", 0))
        st.dataframe(
            pd.DataFrame([
                ["Design flow (duty)", fmt(bw_sizing["q_bw_design_m3h"], "flow_m3h", 1)],
                [
                    "Total dynamic head",
                    f"{fmt(bw_sizing['bw_head_mwc'], 'pressure_mwc', 1)} "
                    f"({fmt(bw_sizing['bw_head_bar'], 'pressure_bar', 3)})",
                ],
                ["Pump hydraulic efficiency", f"{bw_sizing['bw_pump_eta'] * 100:.0f} %"],
                ["Shaft power", fmt(bw_sizing["p_pump_shaft_kw"], "power_kw", 1)],
                ["Motor power (absorbed)", fmt(bw_sizing["p_pump_motor_kw"], "power_kw", 1)],
                ["Duty / standby", f"{n_bw_systems}D / 1S  (plant-wide)"],
            ], columns=["Parameter", "Value"]),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### Air scour blower")
        if bw_sizing.get("blower_dp_warning"):
            st.warning(bw_sizing["blower_dp_warning"])
        b1, b2, b3, b4 = st.columns(4)
        b1.metric(f"Design flow ({ulbl('air_flow_nm3h')})", fmt(bw_sizing["q_air_design_nm3h"], "air_flow_nm3h", 0))
        b2.metric(f"ΔP total ({ulbl('pressure_bar')})", fmt(bw_sizing["dp_total_bar"], "pressure_bar", 3))
        b3.metric(f"Shaft power ({ulbl('power_kw')})", fmt(bw_sizing["p_blower_shaft_kw"], "power_kw", 0))
        b4.metric(f"Motor power ({ulbl('power_kw')})", fmt(bw_sizing["p_blower_motor_kw"], "power_kw", 0))
        st.dataframe(
            pd.DataFrame([
                [
                    "Inlet volume flow (normal)",
                    fmt(bw_sizing["q_air_design_nm3h"], "air_flow_nm3h", 1) + "  (0 °C, 1 atm dry)",
                ],
                [
                    "Vessel operating gauge (inputs)",
                    f"{fmt(vessel_pressure_bar, 'pressure_bar', 2)} g — Nm³ conversion only",
                ],
                [
                    "Air-side ΔP (beyond submergence)",
                    f"{fmt(float(bw_sizing.get('blower_air_delta_p_bar', blower_air_delta_p_bar)), 'pressure_bar', 3)} g",
                ],
                [
                    "Water submergence (≈ ID/2)",
                    f"{fmt(bw_sizing['h_submergence_m'], 'length_m', 2)}  →  "
                    f"{fmt(bw_sizing['dp_sub_bar'], 'pressure_bar', 3)}",
                ],
                ["P₁ inlet (absolute)", f"{float(bw_sizing['P1_pa']):,.0f} Pa"],
                ["P₂ discharge (absolute)", f"{float(bw_sizing['P2_pa']):,.0f} Pa"],
                ["Total ΔP (P₂−P₁)", fmt(bw_sizing["dp_total_bar"], "pressure_bar", 3)],
                ["Shaft power", fmt(bw_sizing["p_blower_shaft_kw"], "power_kw", 1)],
                ["Motor power (absorbed)", fmt(bw_sizing["p_blower_motor_kw"], "power_kw", 1)],
            ], columns=["Parameter", "Value"]),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("#### BW water storage tank")
        t1, t2, t3 = st.columns(3)
        t1.metric("Vol/cycle/system", fmt(bw_sizing["bw_vol_per_cycle_m3"], "volume_m3", 0))
        t2.metric("Simultaneous syst.", f"{bw_sizing['n_bw_systems']}")
        t3.metric(
            "Recommended tank",
            fmt(bw_sizing["v_tank_m3"], "volume_m3", 0),
            help=f"Governs: {bw_sizing['tank_governs']}",
        )
        st.dataframe(
            pd.DataFrame([
                ["BW vol / filter / cycle (avg)", fmt(bw_sizing["bw_vol_per_cycle_m3"], "volume_m3", 1)],
                ["Simultaneous BW systems", str(bw_sizing["n_bw_systems"])],
                ["Volume — cycle-based", fmt(bw_sizing["v_cycle_m3"], "volume_m3", 0)],
                ["Volume — 10-min rule", fmt(bw_sizing["v_10min_m3"], "volume_m3", 0)],
                [
                    "Recommended tank volume",
                    f"{fmt(bw_sizing['v_tank_m3'], 'volume_m3', 0)}  (governs: {bw_sizing['tank_governs']})",
                ],
            ], columns=["Parameter", "Value"]),
            use_container_width=True,
            hide_index=True,
        )
