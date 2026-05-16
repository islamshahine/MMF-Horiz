"""ui/tab_economics.py — Economics tab for AQUASIGHT™ MMF."""
import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as _go
    from plotly.subplots import make_subplots as _make_subplots
    _PLOTLY_OK = True
except ImportError:
    _PLOTLY_OK = False
    _make_subplots = None  # type: ignore[misc, assignment]

from engine.economics import global_benchmark_comparison, npv_lifecycle_cost_profile
from engine.financial_economics import build_econ_financial
from engine.pump_performance import economics_energy_from_pump_configuration

from ui.helpers import fmt, ulbl, dv, fmt_annual_flow_volume, fmt_si_range
from engine.units import display_value as _display_value
from ui.scroll_markers import inject_anchor


def _migrate_pump_econ_align_key() -> None:
    """One-time: legacy checkbox lived on Economics; canonical key is on Pumps tab."""
    if "pp_align_econ_energy" not in st.session_state and "econ_align_pump_tab_energy" in st.session_state:
        st.session_state["pp_align_econ_energy"] = bool(
            st.session_state["econ_align_pump_tab_energy"]
        )


def render_tab_economics(inputs: dict, computed: dict):
    inject_anchor("mmf-anchor-main-economics")
    econ_capex = computed["econ_capex"]
    econ_npv = computed.get("econ_npv") or {}
    energy = computed.get("energy") or {}

    steel_cost_usd_kg = inputs["steel_cost_usd_kg"]
    erection_usd_per_kg_steel = float(inputs.get("erection_usd_per_kg_steel", 0.625))
    labor_usd_per_kg_steel = float(inputs.get("labor_usd_per_kg_steel", 0.25))
    civil_usd_per_kg_working = float(inputs.get("civil_usd_per_kg_working", 0.10))
    engineering_pct = inputs["engineering_pct"]
    contingency_pct = inputs["contingency_pct"]
    media_replace_years = inputs["media_replace_years"]
    grid_intensity = inputs["grid_intensity"]
    steel_carbon_kg = inputs["steel_carbon_kg"]
    concrete_carbon_kg = inputs["concrete_carbon_kg"]
    discount_rate = inputs.get("discount_rate", 5.0)
    design_life_years = inputs.get("design_life_years", 20)
    streams = inputs["streams"]
    n_filters = inputs["n_filters"]
    _n_total_vessels = streams * n_filters
    elec_tariff = float(inputs.get("elec_tariff") or 0.1)

    econ_opex = computed["econ_opex"]
    econ_carbon = computed["econ_carbon"]
    econ_bench = computed["econ_bench"]
    econ_financial = computed.get("econ_financial") or {}

    _migrate_pump_econ_align_key()
    align_econ = bool(st.session_state.get("pp_align_econ_energy", False))
    if align_econ and computed.get("pump_perf") and computed.get("hyd_prof"):
        pp = computed["pump_perf"]
        hyd = computed["hyd_prof"]
        ek = economics_energy_from_pump_configuration(
            energy,
            pp,
            hyd,
            total_flow_m3h=float(inputs["total_flow"]),
            streams=int(inputs["streams"]),
            n_feed_pumps_parallel_per_stream=int(st.session_state.get("pp_n_feed_parallel", 1)),
            pump_eta_user=float(inputs.get("pump_eta") or 0.75),
            motor_eta_feed=float(inputs.get("motor_eta") or 0.955),
            rho_feed=float(computed.get("rho_feed") or 1025.0),
            bw_philosophy=str(st.session_state.get("pp_econ_bw_phil", "DOL")),
            blower_operating_mode=str(st.session_state.get("pp_blower_mode", "single_duty")),
            n_blowers_running=int(st.session_state.get("pp_n_blowers", 1)),
        )
        old_kwh = float(econ_opex.get("energy_kwh_yr") or 0.0)
        new_kwh = float(ek["energy_kwh_yr"])
        old_ecost = float(econ_opex.get("energy_cost_usd_yr") or 0.0)
        new_ecost = new_kwh * elec_tariff
        d_total = new_ecost - old_ecost
        annual_flow_m3 = float(econ_opex.get("annual_flow_m3") or 1.0)
        new_total_opex = float(econ_opex["total_opex_usd_yr"]) + d_total
        econ_opex = {
            **econ_opex,
            "energy_kwh_yr": round(new_kwh),
            "energy_kwh_filtration_yr": ek["energy_kwh_filtration_yr"],
            "energy_kwh_bw_pump_yr": ek["energy_kwh_bw_pump_yr"],
            "energy_kwh_blower_yr": ek["energy_kwh_blower_yr"],
            "energy_cost_usd_yr": round(new_ecost),
            "total_opex_usd_yr": round(new_total_opex),
            "opex_per_m3_usd": round(new_total_opex / max(annual_flow_m3, 1.0), 4),
        }
        r_k = new_kwh / max(old_kwh, 1e-9)
        new_co2_op = float(econ_carbon["co2_operational_kg_yr"]) * r_k
        dlife = int(design_life_years)
        afm_c = float(econ_carbon.get("annual_flow_m3") or annual_flow_m3)
        life_flow = afm_c * max(dlife, 1)
        new_life = float(econ_carbon["co2_construction_kg"]) + new_co2_op * max(dlife, 1)
        econ_carbon = {
            **econ_carbon,
            "co2_operational_kg_yr": round(new_co2_op),
            "co2_lifecycle_kg": round(new_life),
            "co2_per_m3_operational": round(new_co2_op / max(afm_c, 1.0), 4),
            "co2_per_m3_lifecycle": round(new_life / max(life_flow, 1.0), 4),
        }
        econ_bench = global_benchmark_comparison(
            capex_total_usd=float(econ_capex["total_capex_usd"]),
            opex_usd_year=float(econ_opex["total_opex_usd_yr"]),
            total_flow_m3h=float(inputs["total_flow"]),
            n_filters=int(_n_total_vessels),
            design_life_years=dlife,
            co2_per_m3=float(econ_carbon["co2_per_m3_operational"]),
            electricity_tariff=elec_tariff,
            operating_hours=float(inputs.get("op_hours_yr") or 8400.0),
            discount_rate_pct=float(discount_rate),
        )
        econ_npv = npv_lifecycle_cost_profile(
            capex_total_usd=float(econ_capex["total_capex_usd"]),
            annual_opex_usd=float(econ_opex["total_opex_usd_yr"]),
            discount_rate_pct=float(discount_rate),
            design_life_years=dlife,
        )
        econ_financial = build_econ_financial(
            inputs=inputs,
            econ_capex=econ_capex,
            econ_opex=econ_opex,
            econ_carbon=econ_carbon,
            econ_bench=econ_bench,
            lining_result=computed.get("lining_result") or {},
            n_vessels=int(_n_total_vessels),
        )

    st.subheader("Economics — CAPEX · OPEX · Carbon · Benchmarks")
    st.caption(
        "**Energy model (default):** central metered-style kWh from **compute**. "
        "Enable **Link Economics electricity to pump model** on the **Pumps & power** tab to rescale "
        "filtration kWh (parallel feed pumps, **motor efficiency class**), BW pump kWh (DOL vs VFD philosophy), and "
        "blower kWh (operating mode) — then OPEX energy, CO₂ operational, benchmarks, and NPV follow that scenario."
    )
    if st.session_state.get("pp_align_econ_energy"):
        st.info(
            "**Pump-model linkage is active** (configured on **Pumps & power** → **Power & Economics linkage**). "
            "Metrics below use that tab’s parallel feed count, **motor efficiency class** (IE3/IE4), BW philosophy, and blower mode "
            "when **compute** includes pump hydraulics. **Lifecycle financial (expander 6)** is rebuilt from the same linked "
            "OPEX so NPV / IRR / cash flows match headline energy."
        )

    em1, em2, em3, em4 = st.columns(4)
    em1.metric("Total CAPEX",
               f"USD {econ_capex['total_capex_usd']:,.0f}",
               delta=f"{fmt(econ_bench['capex_per_m3d'], 'cost_usd_per_m3d', 1)}  {econ_bench['capex_status']}",
               delta_color="off")
    em2.metric("Annual OPEX",
               f"USD {econ_opex['total_opex_usd_yr']:,.0f}/yr",
               delta=f"{fmt(econ_bench['opex_per_m3'], 'cost_usd_per_m3', 4)}  {econ_bench['opex_status']}",
               delta_color="off")
    em3.metric(f"LCOW ({ulbl('cost_usd_per_m3')})",
               fmt(econ_bench["lcow"], "cost_usd_per_m3", 4),
               delta=econ_bench["lcow_status"],
               delta_color="off")
    em4.metric(f"CO₂ operational ({ulbl('co2_intensity_kg_m3')})",
               fmt(econ_carbon["co2_per_m3_operational"], "co2_intensity_kg_m3", 4),
               delta=econ_bench["carbon_status"],
               delta_color="off")

    _cycle_econ = computed.get("cycle_economics") or {}
    if _cycle_econ:
        with st.expander(
            "LCOW band — cycle uncertainty (optimistic / expected / conservative)",
            expanded=False,
        ):
            st.caption(_cycle_econ.get("note", ""))
            lc1, lc2, lc3, lc4 = st.columns(4)
            lc1.metric(
                f"LCOW optimistic ({ulbl('cost_usd_per_m3')})",
                fmt(_cycle_econ["lcow_optimistic_usd_m3"], "cost_usd_per_m3", 4),
                help="Longer run time between backwashes — lower BW energy OPEX.",
            )
            lc2.metric(
                f"LCOW expected ({ulbl('cost_usd_per_m3')})",
                fmt(_cycle_econ["lcow_expected_usd_m3"], "cost_usd_per_m3", 4),
            )
            lc3.metric(
                f"LCOW conservative ({ulbl('cost_usd_per_m3')})",
                fmt(_cycle_econ["lcow_conservative_usd_m3"], "cost_usd_per_m3", 4),
                help="Shorter run time — more backwashes — higher BW energy OPEX.",
            )
            lc4.metric(
                "LCOW spread",
                f"{_cycle_econ.get('lcow_spread_pct', 0):.1f} %",
            )
            st.caption(
                f"Headline LCOW metric uses the base OPEX case "
                f"({fmt(econ_bench['lcow'], 'cost_usd_per_m3', 4)}). "
                f"Band scales **BW pump + blower** energy only "
                f"(×{_cycle_econ.get('bw_energy_scale_optimistic', 1):.3f} optimistic · "
                f"×{_cycle_econ.get('bw_energy_scale_conservative', 1):.3f} conservative vs expected cycle). "
                f"See **Filtration → cycle uncertainty** for run-time hours."
            )

    with st.expander("1 · CAPEX breakdown", expanded=True):
        _capex_items = {
            "Steel (structure)": econ_capex["steel_cost_usd"],
            "Erection":          econ_capex["erection_usd"],
            "Field labor (steel)": econ_capex["labor_usd"],
            "Piping":            econ_capex["piping_usd"],
            "Instrumentation":   econ_capex["instrumentation_usd"],
            "Civil works":       econ_capex["civil_usd"],
            "Engineering":       econ_capex["engineering_usd"],
            "Contingency":       econ_capex["contingency_usd"],
        }
        c_left, c_right = st.columns([1, 1])
        with c_left:
            _total = max(econ_capex["total_capex_usd"], 1)
            st.dataframe(
                pd.DataFrame(
                    [[k, f"USD {v:,.0f}", f"{v/_total*100:.1f} %"]
                     for k, v in _capex_items.items()]
                    + [["**TOTAL**",
                        f"**USD {econ_capex['total_capex_usd']:,.0f}**",
                        "**100 %**"]],
                    columns=["Item", "Cost (USD)", "Share"],
                ),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                f"{_n_total_vessels} vessels · installed steel **{fmt(float(computed.get('w_total') or 0), 'mass_kg', 0)}** / vessel · "
                f"operating weight **{fmt(float((computed.get('wt_oper') or {}).get('w_operating_kg') or 0), 'mass_kg', 0)}** / vessel · "
                f"steel **{fmt(steel_cost_usd_kg, 'cost_usd_per_kg', 2)}** · "
                f"erection **{fmt(erection_usd_per_kg_steel, 'cost_usd_per_kg', 2)}** · "
                f"labor **{fmt(labor_usd_per_kg_steel, 'cost_usd_per_kg', 2)}** · "
                f"civil **{fmt(civil_usd_per_kg_working, 'cost_usd_per_kg', 2)}** / op. kg · "
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
            st.dataframe(
                pd.DataFrame(
                    [[k, f"USD {v:,.0f}/yr", f"{v/_total_op*100:.1f} %"]
                     for k, v in _opex_items.items()]
                    + [["**TOTAL**",
                        f"**USD {econ_opex['total_opex_usd_yr']:,.0f}/yr**",
                        "**100 %**"]],
                    columns=["Item", "Cost (USD/yr)", "Share"],
                ),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                f"Specific OPEX: **{fmt(econ_opex['opex_per_m3_usd'], 'cost_usd_per_m3', 4)}**  ·  "
                f"Annual flow: {fmt_annual_flow_volume(econ_opex['annual_flow_m3'])}  ·  "
                f"Media interval: {media_replace_years:.0f} yr  ·  "
                "BW duty hours and optional pump-model linkage: **Pumps & power** tab."
            )
            if econ_opex.get("energy_kwh_filtration_yr") is not None:
                _ef = float(econ_opex["energy_kwh_filtration_yr"])
                _ebw = float(econ_opex["energy_kwh_bw_pump_yr"])
                _ebl = float(econ_opex["energy_kwh_blower_yr"])
                _kwh_tot = float(econ_opex.get("energy_kwh_yr") or (_ef + _ebw + _ebl))
                _ec_usd = float(econ_opex["energy_cost_usd_yr"])
                st.caption(
                    f"**Annual electricity (metered-style):** filtration **{_ef:,.0f}** · "
                    f"BW pump **{_ebw:,.0f}** · blower **{_ebl:,.0f}** kWh/yr → **total {_kwh_tot:,.0f}** kWh/yr. "
                    f"The **Energy** row above is **{_kwh_tot:,.0f}** kWh/yr × **{elec_tariff:g}** USD/kWh ≈ **USD {_ec_usd:,.0f}/yr** "
                    f"(**Pumps & power** shows the same kWh total as **linked model** when pump-model linkage is on)."
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
        cf1.metric(f"Operational CO₂ ({ulbl('mass_kg')}/yr)",
                   fmt(econ_carbon["co2_operational_kg_yr"], "mass_kg", 0) + "/yr")
        cf2.metric(f"Construction CO₂ ({ulbl('mass_t')})",
                   fmt(econ_carbon["co2_construction_kg"] / 1000.0, "mass_t", 1))
        cf3.metric(f"Lifecycle CO₂ ({ulbl('mass_t')})",
                   fmt(econ_carbon["co2_lifecycle_kg"] / 1000.0, "mass_t", 1),
                   delta=f"over {econ_carbon['design_life_years']} yr",
                   delta_color="off")
        cf4.metric(f"Specific operational ({ulbl('co2_intensity_kg_m3')})",
                   fmt(econ_carbon["co2_per_m3_operational"], "co2_intensity_kg_m3", 4),
                   delta=econ_bench["carbon_status"], delta_color="off")
        st.dataframe(
            pd.DataFrame([
                ["Operational CO₂ / year",
                 fmt(econ_carbon["co2_operational_kg_yr"], "mass_kg", 0) + "/yr",
                 f"Grid: {fmt(grid_intensity, 'co2_kg_per_kwh', 3)}"],
                ["Construction — steel",
                 fmt(econ_carbon["co2_steel_kg"], "mass_kg", 0),
                 f"{fmt(steel_carbon_kg, 'co2_per_kg_material', 2)} steel"],
                ["Construction — media",
                 fmt(econ_carbon["co2_media_kg"], "mass_kg", 0),
                 "Weighted by mass"],
                ["Construction — concrete",
                 fmt(econ_carbon["co2_concrete_kg"], "mass_kg", 0),
                 fmt(concrete_carbon_kg, "co2_per_kg_material", 2)],
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
            ], columns=["Item", "Value", "Basis"]),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("4 · Global benchmark comparison", expanded=True):
        st.caption(
            "Benchmarks: horizontal MMF for SWRO / brackish pre-treatment "
            "(Middle East / Mediterranean, 2024 basis). "
            "🟢 = within range · 🟡 = borderline · 🔴 = outside range."
        )
        st.dataframe(
            pd.DataFrame([
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
            ], columns=["Metric", "Project", "Benchmark range", "Status"]),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            f"Daily capacity: {fmt(econ_bench['daily_flow_m3d'], 'flow_m3d', 1)}  ·  "
            f"Annual flow: {fmt_annual_flow_volume(econ_bench['annual_flow_m3'])}  ·  "
            f"LCOW = (CAPEX × CRF + OPEX) / annual flow  ·  "
            f"CRF = {econ_bench['crf']:.4f}  "
            f"({discount_rate:.1f} % discount · {design_life_years} yr life)"
        )

    with st.expander("5 · NPV — lifecycle cost (discounted)", expanded=False):
        st.caption(
            "**Simplified cost PV:** one line per year = total engineering **OPEX** (same mix as the OPEX table) "
            f"discounted at **{discount_rate:.1f} %/yr** over **{design_life_years} yr** (design life). "
            "Use **expander 6** for full cash flows (replacements, escalation, tax, IRR)."
        )
        _npv = float(econ_npv.get("npv_total_usd") or 0.0)
        _yrs = econ_npv.get("years") or []
        _cum = econ_npv.get("cumulative_pv_usd") or []
        _bar = econ_npv.get("annual_discounted_usd") or []
        n1, n2 = st.columns(2)
        n1.metric(
            "Lifecycle NPV (costs)",
            f"USD {_npv:,.0f}",
        )
        n2.metric(
            "Horizon",
            f"{int(econ_npv.get('design_life_years') or design_life_years)} yr",
            delta=f"{discount_rate:.1f} %/yr discount",
            delta_color="off",
        )
        st.caption(
            "Cash-flow model: **year 0** = total CAPEX; **years 1–N** = total annual OPEX "
            "(energy, chemicals, labour, levelized media and nozzle replacement). "
            "Values are **outflows** (negative); NPV is the discounted sum through the design life."
        )
        if _PLOTLY_OK and _make_subplots is not None and len(_yrs) == len(_cum) == len(_bar):
            _fig_npv = _make_subplots(
                rows=2,
                cols=1,
                row_heights=[0.55, 0.45],
                vertical_spacing=0.14,
                subplot_titles=(
                    "Cumulative present value of costs (USD)",
                    "Discounted cash flow by year (USD)",
                ),
            )
            _fig_npv.add_trace(
                _go.Scatter(
                    x=_yrs,
                    y=_cum,
                    mode="lines+markers",
                    name="Cumulative PV",
                    line=dict(width=2),
                    marker=dict(size=6),
                    hovertemplate="Year %{x}<br>Cumulative PV %{y:$,,.0f}<extra></extra>",
                ),
                row=1,
                col=1,
            )
            _fig_npv.add_hline(y=0, line_dash="dot", line_color="rgba(128,128,128,0.6)", row=1, col=1)
            _fig_npv.add_trace(
                _go.Bar(
                    x=_yrs,
                    y=_bar,
                    name="Discounted flow",
                    marker_color="rgba(55, 126, 184, 0.75)",
                    hovertemplate="Year %{x}<br>PV %{y:$,,.0f}<extra></extra>",
                ),
                row=2,
                col=1,
            )
            _fig_npv.update_yaxes(tickformat=",.0f", row=1, col=1)
            _fig_npv.update_yaxes(tickformat=",.0f", row=2, col=1)
            _fig_npv.update_xaxes(title_text="Year", row=2, col=1)
            _fig_npv.update_layout(
                showlegend=False,
                height=480,
                margin=dict(t=36, b=36, l=56, r=16),
            )
            st.plotly_chart(_fig_npv, use_container_width=True)
        elif not _PLOTLY_OK:
            st.info("Install plotly for the NPV chart.")
        else:
            st.warning("NPV series unavailable for this result.")

    _ef = econ_financial
    if _ef:
        with st.expander("6 · Lifecycle financial (cash flow · NPV · IRR)", expanded=False):
            st.caption(
                "**Full techno-economic model** (vs **expander 5** simple PV of total OPEX): cash flows use "
                "**engineering OPEX splits** (energy, chemicals, labour), **scheduled maintenance** (% CAPEX/yr), "
                "**discrete replacement** events (media / nozzles / lining), **escalation**, optional **annual benefit** "
                "for IRR, **tax**, **depreciation**, and **salvage**. Horizon **"
                f"{int(inputs.get('project_life_years') or design_life_years)} yr** project life "
                f"(expander 5 uses **{design_life_years} yr** design life). "
                "When **pump-model linkage** is on, **energy** matches the linked OPEX row above."
            )
            f1, f2, f3, f4 = st.columns(4)
            f1.metric("NPV (net CF)", f"USD {_ef.get('npv', 0):,.0f}")
            _irr = _ef.get("irr_pct")
            f2.metric("IRR", f"{_irr:.2f} %" if _irr is not None else "—")
            _roi = _ef.get("roi_pct")
            f3.metric("ROI (simple)", f"{_roi:.1f} %" if _roi is not None else "—")
            _spb = _ef.get("simple_payback_years")
            f4.metric("Simple payback", f"{_spb:.2f} yr" if _spb is not None else "—")
            st.markdown(_ef.get("economic_summary", ""))
            _tbl_cf = _ef.get("cashflow_table") or []
            if _tbl_cf:
                st.markdown("**Cash flow (first years)**")
                st.dataframe(
                    pd.DataFrame(_tbl_cf[: min(8, len(_tbl_cf))]),
                    use_container_width=True,
                    hide_index=True,
                )
            if _PLOTLY_OK and _make_subplots is not None:
                _years = [int(r["year"]) for r in _tbl_cf]
                _und = _ef.get("undiscounted_cumulative_net_usd") or []
                _dpv = _ef.get("discounted_pv_by_year") or []
                if _years and len(_und) == len(_years):
                    _fig1 = _make_subplots(
                        rows=2, cols=2,
                        subplot_titles=(
                            "Cumulative net (undiscounted)",
                            "Cumulative NPV (discounted)",
                            "Annual OPEX + replacements (USD)",
                            "CAPEX vs year-1 operating cash",
                        ),
                        vertical_spacing=0.14,
                        horizontal_spacing=0.10,
                    )
                    _fig1.add_trace(
                        _go.Scatter(x=_years, y=_und, name="Undisc.", line=dict(width=2)),
                        row=1, col=1,
                    )
                    _fig1.add_trace(
                        _go.Scatter(x=_years, y=_dpv, name="Disc. NPV", line=dict(width=2)),
                        row=1, col=2,
                    )
                    _opex_es = _ef.get("annual_opex_escalation_curve") or []
                    if _opex_es:
                        _fig1.add_trace(
                            _go.Scatter(
                                x=[r["year"] for r in _opex_es],
                                y=[r["total_opex_components_usd"] for r in _opex_es],
                                name="OPEX+repl.",
                                line=dict(width=2),
                            ),
                            row=2, col=1,
                        )
                    _capex_v = float(econ_capex.get("total_capex_usd", 0) or 0)
                    _y1op = float(_ef.get("first_year_operating_cash_usd") or 0.0)
                    _fig1.add_trace(
                        _go.Bar(
                            x=["CAPEX", "Yr-1 net operating"],
                            y=[_capex_v, abs(_y1op)],
                            marker_color=["#1f77b4", "#ff7f0e"],
                        ),
                        row=2, col=2,
                    )
                    _fig1.update_layout(height=520, showlegend=False, margin=dict(t=40, b=30, l=50, r=20))
                    st.plotly_chart(_fig1, use_container_width=True)

                _repl = _ef.get("replacement_schedule") or []
                if _repl:
                    _fig2 = _go.Figure()
                    _fig2.add_trace(_go.Scatter(
                        x=[r["year"] for r in _repl],
                        y=[1] * len(_repl),
                        mode="markers",
                        marker=dict(size=14, symbol="diamond"),
                        text=[",".join(r["events"]) for r in _repl],
                        hovertemplate="Year %{x}<br>%{text}<extra></extra>",
                    ))
                    _fig2.update_layout(
                        title="Replacement event timeline (marker = event year)",
                        xaxis_title="Year", yaxis_visible=False, height=220,
                        margin=dict(t=50, b=40),
                    )
                    st.plotly_chart(_fig2, use_container_width=True)

                _sens = _ef.get("npv_sensitivity") or {}
                if len(_sens) > 1:
                    _base_np = float(_sens.get("base_npv_usd", 0) or 0)
                    _sens_order = (
                        ("discount_plus10pct", "Discount +10 %"),
                        ("energy_escalation_plus10pct", "Energy escalation +10 %"),
                        ("capex_plus10pct", "CAPEX +10 %"),
                        ("life_plus1yr", "Project life +1 yr"),
                    )
                    _theta = []
                    _rd = []
                    for _sk, _pretty in _sens_order:
                        if _sk not in _sens:
                            continue
                        _theta.append(_pretty)
                        _rd.append(float(_sens[_sk]) - _base_np)
                    if len(_theta) >= 2:
                        _theta.append(_theta[0])
                        _rd.append(_rd[0])
                        _fig3 = _go.Figure(
                            _go.Scatterpolar(
                                r=_rd,
                                theta=_theta,
                                fill="toself",
                                fillcolor="rgba(44, 160, 44, 0.22)",
                                mode="lines+markers",
                                name="ΔNPV",
                                line=dict(color="#2ca02c", width=2.5),
                                marker=dict(size=9, color="#217821"),
                                hovertemplate="%{theta}<br>ΔNPV %{r:$,.0f}<extra></extra>",
                            )
                        )
                        _fig3.update_layout(
                            title="NPV sensitivity spider (ΔNPV vs base case, USD)",
                            polar=dict(
                                bgcolor="rgba(248,249,250,0.9)",
                                angularaxis=dict(direction="clockwise", linecolor="#ccc"),
                                radialaxis=dict(
                                    gridcolor="rgba(0,0,0,0.08)",
                                    title=dict(text="ΔNPV (USD)"),
                                ),
                            ),
                            height=420,
                            margin=dict(t=56, b=40, l=48, r=48),
                            showlegend=False,
                        )
                        st.plotly_chart(_fig3, use_container_width=True)
                        st.caption(
                            "Each spoke is a **one-at-a-time** stress vs the current inputs: "
                            "higher discount, higher energy escalation, +10 % CAPEX, or +1 yr project life. "
                            "Polygon shows **ΔNPV** (scenario NPV − base NPV); same discount rate as LCOW unless noted."
                        )

                _sc = _ef.get("co2_vs_cost_scatter") or []
                if len(_sc) > 1:
                    _us = str(inputs.get("unit_system") or "metric")
                    _fig4 = _go.Figure(_go.Scatter(
                        x=[
                            _display_value(float(p["co2_kg_cumulative"]) / 1000.0, "mass_t", _us)
                            for p in _sc
                        ],
                        y=[p["undiscounted_cost_usd"] / 1e6 for p in _sc],
                        mode="lines+markers",
                        name="Path",
                    ))
                    _fig4.update_layout(
                        title=f"Cumulative CO₂ vs cumulative cost ({ulbl('mass_t')} · MUSD)",
                        xaxis_title=f"Cumulative operational + construction CO₂ ({ulbl('mass_t')})",
                        yaxis_title="Cumulative cost (MUSD)",
                        height=360,
                    )
                    st.plotly_chart(_fig4, use_container_width=True)

                _disc = float(inputs.get("discount_rate", 5.0) or 5.0)
                st.caption(
                    f"Discount rate for NPV curves: **{_disc:.1f} %/yr** · "
                    f"Project life: **{inputs.get('project_life_years') or design_life_years}** yr · "
                    f"Inflation: **{inputs.get('inflation_rate', 0):.1f} %/yr**"
                )

    _deg = computed.get("lifecycle_degradation") or {}
    if _deg:
        with st.expander("7 · Lifecycle degradation (advisory)", expanded=False):
            st.caption(_deg.get("doc_note", ""))
            st.caption(
                f"Condition **100 %** = fresh after replacement; below **{_deg.get('replacement_threshold_pct', 35):.0f} %** "
                f"= advisory replacement zone. Horizon **{_deg.get('horizon_years', '—')} yr**."
            )
            for _f in _deg.get("findings") or []:
                _msg = f"**{_f.get('topic', '')}** — {_f.get('detail', '')}"
                if _f.get("severity") == "warning":
                    st.warning(_msg)
                elif _f.get("severity") == "advisory":
                    st.info(_msg)
                else:
                    st.caption(_msg)
            _comps = _deg.get("components") or {}
            if _PLOTLY_OK and _comps:
                _fig_d = _go.Figure()
                for _key, _block in _comps.items():
                    _curve = _block.get("curve") or []
                    if not _curve:
                        continue
                    _fig_d.add_trace(_go.Scatter(
                        x=[p["year"] for p in _curve],
                        y=[p["condition_pct"] for p in _curve],
                        mode="lines",
                        name=_block.get("label", _key),
                        hovertemplate=(
                            "Year %{x}<br>Condition %{y:.0f} %<extra>"
                            + str(_block.get("label", _key))
                            + "</extra>"
                        ),
                    ))
                _fig_d.add_hline(
                    y=float(_deg.get("replacement_threshold_pct", 35)),
                    line_dash="dash",
                    line_color="rgba(255,120,0,0.7)",
                    annotation_text="Replacement advisory",
                )
                _fig_d.update_layout(
                    title="Component condition index (sawtooth after each replacement)",
                    xaxis_title="Project year",
                    yaxis_title="Condition %",
                    yaxis_range=[0, 105],
                    height=400,
                    margin=dict(t=48, b=40, l=56, r=16),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                )
                st.plotly_chart(_fig_d, use_container_width=True)
            _sum_rows = []
            for _key, _block in _comps.items():
                _sum_rows.append({
                    "Component": _block.get("label", _key),
                    "Nominal interval (yr)": _block.get("nominal_interval_years"),
                    "Stress ×": _block.get("stress_factor"),
                    "Effective interval (yr)": _block.get("effective_interval_years"),
                    "Replacements (model)": ", ".join(
                        str(y) for y in (_block.get("suggested_replacement_years") or [])
                    ) or "—",
                    f"Condition @ yr {_deg.get('horizon_years')}": _block.get("condition_at_horizon_pct"),
                })
            if _sum_rows:
                st.dataframe(pd.DataFrame(_sum_rows), use_container_width=True, hide_index=True)
            with st.expander("Stress drivers by component", expanded=False):
                for _key, _block in _comps.items():
                    st.markdown(f"**{_block.get('label', _key)}**")
                    for _d in _block.get("drivers") or []:
                        st.markdown(f"- {_d}")
