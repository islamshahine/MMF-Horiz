"""ui/tab_economics.py — Economics tab for AQUASIGHT™ MMF."""
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as _go
    _PLOTLY_OK = True
except ImportError:
    _PLOTLY_OK = False


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
    streams            = inputs["streams"]
    n_filters          = inputs["n_filters"]

    _n_total_vessels = streams * n_filters

    st.subheader("Economics — CAPEX · OPEX · Carbon · Benchmarks")

    em1, em2, em3, em4 = st.columns(4)
    em1.metric("Total CAPEX",
               f"USD {econ_capex['total_capex_usd']:,.0f}",
               delta=f"{econ_bench['capex_per_m3d']:.1f} USD/m³/d  {econ_bench['capex_status']}",
               delta_color="off")
    em2.metric("Annual OPEX",
               f"USD {econ_opex['total_opex_usd_yr']:,.0f}/yr",
               delta=f"{econ_bench['opex_per_m3']:.4f} USD/m³  {econ_bench['opex_status']}",
               delta_color="off")
    em3.metric("LCOW",
               f"{econ_bench['lcow']:.4f} USD/m³",
               delta=econ_bench["lcow_status"],
               delta_color="off")
    em4.metric("CO₂ operational",
               f"{econ_carbon['co2_per_m3_operational']:.4f} kgCO₂/m³",
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
                f"{_n_total_vessels} vessels · steel {steel_cost_usd_kg:.2f} USD/kg · "
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
                f"Specific OPEX: **{econ_opex['opex_per_m3_usd']:.4f} USD/m³**  ·  "
                f"Annual flow: {econ_opex['annual_flow_m3']/1e6:.2f} Mm³/yr  ·  "
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
                   f"{econ_carbon['co2_operational_kg_yr']/1000:,.1f} t/yr")
        cf2.metric("Construction CO₂",
                   f"{econ_carbon['co2_construction_kg']/1000:,.1f} t")
        cf3.metric("Lifecycle CO₂",
                   f"{econ_carbon['co2_lifecycle_kg']/1000:,.1f} t",
                   delta=f"over {econ_carbon['design_life_years']} yr",
                   delta_color="off")
        cf4.metric("Specific operational",
                   f"{econ_carbon['co2_per_m3_operational']:.4f} kgCO₂/m³",
                   delta=econ_bench["carbon_status"], delta_color="off")
        st.table(pd.DataFrame([
            ["Operational CO₂ / year",
             f"{econ_carbon['co2_operational_kg_yr']:,.0f} kg/yr",
             f"Grid: {grid_intensity:.3f} kgCO₂/kWh"],
            ["Construction — steel",
             f"{econ_carbon['co2_steel_kg']:,.0f} kg",
             f"{steel_carbon_kg:.2f} kgCO₂/kg steel"],
            ["Construction — media",
             f"{econ_carbon['co2_media_kg']:,.0f} kg",
             "Weighted by mass"],
            ["Construction — concrete",
             f"{econ_carbon['co2_concrete_kg']:,.0f} kg",
             f"{concrete_carbon_kg:.2f} kgCO₂/kg"],
            ["Lifecycle total",
             f"{econ_carbon['co2_lifecycle_kg']:,.0f} kg",
             f"= {econ_carbon['co2_lifecycle_kg']/1000:.1f} t "
             f"over {econ_carbon['design_life_years']} yr"],
            ["Specific — operational",
             f"{econ_carbon['co2_per_m3_operational']:.4f} kgCO₂/m³",
             econ_bench["carbon_status"]],
            ["Specific — lifecycle",
             f"{econ_carbon['co2_per_m3_lifecycle']:.4f} kgCO₂/m³",
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
             f"{econ_bench['capex_per_m3d']:.2f} USD/m³/d",
             econ_bench["capex_benchmark"],
             econ_bench["capex_status"]],
            ["OPEX",
             f"{econ_bench['opex_per_m3']:.4f} USD/m³",
             econ_bench["opex_benchmark"],
             econ_bench["opex_status"]],
            ["Operational carbon",
             f"{econ_bench['co2_per_m3']:.4f} kgCO₂/m³",
             econ_bench["carbon_benchmark"],
             econ_bench["carbon_status"]],
            ["LCOW",
             f"{econ_bench['lcow']:.4f} USD/m³",
             econ_bench["lcow_benchmark"],
             econ_bench["lcow_status"]],
        ], columns=["Metric", "Project", "Benchmark range", "Status"]))
        st.caption(
            f"Daily capacity: {econ_bench['daily_flow_m3d']:,.0f} m³/d  ·  "
            f"Annual flow: {econ_bench['annual_flow_m3']/1e6:.2f} Mm³/yr  ·  "
            f"LCOW basis: CRF = 8 % (≈ 12-yr payback at 5 %)."
        )
