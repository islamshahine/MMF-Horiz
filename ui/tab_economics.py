"""ui/tab_economics.py — Economics tab for AQUASIGHT™ MMF."""
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as _go
    _PLOTLY_OK = True
except ImportError:
    _PLOTLY_OK = False

from ui.helpers import fmt, ulbl, dv, fmt_annual_flow_volume, fmt_si_range


def render_tab_economics(inputs: dict, computed: dict):
    econ_capex  = computed["econ_capex"]
    econ_opex   = computed["econ_opex"]
    econ_bench  = computed["econ_bench"]
    econ_carbon = computed["econ_carbon"]

    steel_cost_usd_kg  = inputs["steel_cost_usd_kg"]
    engineering_pct    = inputs["engineering_pct"]
    contingency_pct    = inputs["contingency_pct"]
    media_replace_years = inputs["media_replace_years"]
    grid_intensity     = inputs["grid_intensity"]
    steel_carbon_kg    = inputs["steel_carbon_kg"]
    concrete_carbon_kg = inputs["concrete_carbon_kg"]
    discount_rate      = inputs.get("discount_rate", 5.0)
    design_life_years  = inputs.get("design_life_years", 20)
    streams            = inputs["streams"]
    n_filters          = inputs["n_filters"]

    _n_total_vessels = streams * n_filters

    st.subheader("Economics — CAPEX · OPEX · Carbon · Benchmarks")

    em1, em2, em3, em4 = st.columns(4)
    em1.metric("Total CAPEX",
               f"USD {econ_capex['total_capex_usd']:,.0f}",
               delta=f"{fmt(econ_bench['capex_per_m3d'], 'cost_usd_per_m3d', 1)}  {econ_bench['capex_status']}",
               delta_color="off")
    em2.metric("Annual OPEX",
               f"USD {econ_opex['total_opex_usd_yr']:,.0f}/yr",
               delta=f"{fmt(econ_bench['opex_per_m3'], 'cost_usd_per_m3', 4)}  {econ_bench['opex_status']}",
               delta_color="off")
    em3.metric("LCOW",
               fmt(econ_bench["lcow"], "cost_usd_per_m3", 4),
               delta=econ_bench["lcow_status"],
               delta_color="off")
    em4.metric("CO₂ operational",
               fmt(econ_carbon["co2_per_m3_operational"], "co2_intensity_kg_m3", 4),
               delta=econ_bench["carbon_status"],
               delta_color="off")

    with st.expander("1 · CAPEX breakdown", expanded=True):
        _capex_items = {
            "Steel (structure)": econ_capex["steel_cost_usd"],
            "Erection":          econ_capex["erection_usd"],
            "Piping":            econ_capex["piping_usd"],
            "Instrumentation":   econ_capex["instrumentation_usd"],
            "Civil works":       econ_capex["civil_usd"],
            "Engineering":       econ_capex["engineering_usd"],
            "Contingency":       econ_capex["contingency_usd"],
        }
        c_left, c_right = st.columns([1, 1])
        with c_left:
            _total = max(econ_capex["total_capex_usd"], 1)
            st.table(pd.DataFrame(
                [[k, f"USD {v:,.0f}", f"{v/_total*100:.1f} %"]
                 for k, v in _capex_items.items()]
                + [["**TOTAL**",
                    f"**USD {econ_capex['total_capex_usd']:,.0f}**",
                    "**100 %**"]],
                columns=["Item", "Cost (USD)", "Share"]))
            st.caption(
                f"{_n_total_vessels} vessels · steel {fmt(steel_cost_usd_kg, 'cost_usd_per_kg', 2)} · "
                f"engineering {engineering_pct:.0f} % · contingency {contingency_pct:.0f} %"
            )
        with c_right:
            if _PLOTLY_OK:
                _fig_cap = _go.Figure(_go.Pie(
                    labels=list(_capex_items.keys()),
                    values=list(_capex_items.values()),
                    hole=0.35,
                    textinfo="label+percent",
                    textfont_size=11,
                ))
                _fig_cap.update_layout(
                    title="CAPEX split", showlegend=False,
                    margin=dict(t=40, b=10, l=10, r=10), height=340,
                )
                st.plotly_chart(_fig_cap, use_container_width=True)
            else:
                st.info("Install plotly for pie charts.")

    with st.expander("2 · Annual OPEX breakdown", expanded=True):
        _opex_items = {
            "Energy":             econ_opex["energy_cost_usd_yr"],
            "Media replacement":  econ_opex["media_cost_usd_yr"],
            "Nozzle replacement": econ_opex["nozzle_cost_usd_yr"],
            "Labour":             econ_opex["labour_cost_usd_yr"],
            "Chemicals":          econ_opex["chemical_cost_usd_yr"],
        }
        o_left, o_right = st.columns([1, 1])
        with o_left:
            _total_op = max(econ_opex["total_opex_usd_yr"], 1)
            st.table(pd.DataFrame(
                [[k, f"USD {v:,.0f}/yr", f"{v/_total_op*100:.1f} %"]
                 for k, v in _opex_items.items()]
                + [["**TOTAL**",
                    f"**USD {econ_opex['total_opex_usd_yr']:,.0f}/yr**",
                    "**100 %**"]],
                columns=["Item", "Cost (USD/yr)", "Share"]))
            st.caption(
                f"Specific OPEX: **{fmt(econ_opex['opex_per_m3_usd'], 'cost_usd_per_m3', 4)}**  ·  "
                f"Annual flow: {fmt_annual_flow_volume(econ_opex['annual_flow_m3'])}  ·  "
                f"Media interval: {media_replace_years:.0f} yr"
            )
        with o_right:
            if _PLOTLY_OK:
                _fig_op = _go.Figure(_go.Pie(
                    labels=list(_opex_items.keys()),
                    values=list(_opex_items.values()),
                    hole=0.35,
                    textinfo="label+percent",
                    textfont_size=11,
                ))
                _fig_op.update_layout(
                    title="OPEX split", showlegend=False,
                    margin=dict(t=40, b=10, l=10, r=10), height=340,
                )
                st.plotly_chart(_fig_op, use_container_width=True)

    with st.expander("3 · Carbon footprint", expanded=True):
        cf1, cf2, cf3, cf4 = st.columns(4)
        cf1.metric("Operational CO₂/yr",
                   fmt(econ_carbon["co2_operational_kg_yr"], "mass_kg", 0) + "/yr")
        cf2.metric("Construction CO₂",
                   fmt(econ_carbon["co2_construction_kg"] / 1000.0, "mass_t", 1))
        cf3.metric("Lifecycle CO₂",
                   fmt(econ_carbon["co2_lifecycle_kg"] / 1000.0, "mass_t", 1),
                   delta=f"over {econ_carbon['design_life_years']} yr",
                   delta_color="off")
        cf4.metric("Specific operational",
                   fmt(econ_carbon["co2_per_m3_operational"], "co2_intensity_kg_m3", 4),
                   delta=econ_bench["carbon_status"], delta_color="off")
        st.table(pd.DataFrame([
            ["Operational CO₂ / year",
             fmt(econ_carbon["co2_operational_kg_yr"], "mass_kg", 0) + "/yr",
             f"Grid: {fmt(grid_intensity, 'co2_kg_per_kwh', 3)}"],
            ["Construction — steel",
             fmt(econ_carbon["co2_steel_kg"], "mass_kg", 0),
             f"{steel_carbon_kg:.2f} kgCO₂/kg steel"],
            ["Construction — media",
             fmt(econ_carbon["co2_media_kg"], "mass_kg", 0),
             "Weighted by mass"],
            ["Construction — concrete",
             fmt(econ_carbon["co2_concrete_kg"], "mass_kg", 0),
             f"{concrete_carbon_kg:.2f} kgCO₂/kg"],
            ["Lifecycle total",
             fmt(econ_carbon["co2_lifecycle_kg"], "mass_kg", 0),
             f"= {fmt(econ_carbon['co2_lifecycle_kg'] / 1000.0, 'mass_t', 1)} "
             f"over {econ_carbon['design_life_years']} yr"],
            ["Specific — operational",
             fmt(econ_carbon["co2_per_m3_operational"], "co2_intensity_kg_m3", 4),
             econ_bench["carbon_status"]],
            ["Specific — lifecycle",
             fmt(econ_carbon["co2_per_m3_lifecycle"], "co2_intensity_kg_m3", 4),
             "Incl. construction, amortised"],
        ], columns=["Item", "Value", "Basis"]))

    with st.expander("4 · Global benchmark comparison", expanded=True):
        st.caption(
            "Benchmarks: horizontal MMF for SWRO / brackish pre-treatment "
            "(Middle East / Mediterranean, 2024 basis). "
            "🟢 = within range · 🟡 = borderline · 🔴 = outside range."
        )
        st.table(pd.DataFrame([
            ["CAPEX",
             fmt(econ_bench["capex_per_m3d"], "cost_usd_per_m3d", 2),
             fmt_si_range(econ_bench["capex_bench_si"][0], econ_bench["capex_bench_si"][1],
                          "cost_usd_per_m3d", 0, 0),
             econ_bench["capex_status"]],
            ["OPEX",
             fmt(econ_bench["opex_per_m3"], "cost_usd_per_m3", 4),
             fmt_si_range(econ_bench["opex_bench_si"][0], econ_bench["opex_bench_si"][1],
                          "cost_usd_per_m3", 3, 3),
             econ_bench["opex_status"]],
            ["Operational carbon",
             fmt(econ_bench["co2_per_m3"], "co2_intensity_kg_m3", 4),
             fmt_si_range(econ_bench["co2_bench_si"][0], econ_bench["co2_bench_si"][1],
                          "co2_intensity_kg_m3", 3, 3),
             econ_bench["carbon_status"]],
            ["LCOW",
             fmt(econ_bench["lcow"], "cost_usd_per_m3", 4),
             fmt_si_range(econ_bench["lcow_bench_si"][0], econ_bench["lcow_bench_si"][1],
                          "cost_usd_per_m3", 2, 2),
             econ_bench["lcow_status"]],
        ], columns=["Metric", "Project", "Benchmark range", "Status"]))
        st.caption(
            f"Daily capacity: {fmt(econ_bench['daily_flow_m3d'], 'flow_m3d', 1)}  ·  "
            f"Annual flow: {fmt_annual_flow_volume(econ_bench['annual_flow_m3'])}  ·  "
            f"LCOW = (CAPEX × CRF + OPEX) / annual flow  ·  "
            f"CRF = {econ_bench['crf']:.4f}  "
            f"({discount_rate:.1f} % discount · {design_life_years} yr life)"
        )
