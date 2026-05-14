"""ui/tab_pump_costing.py — Pump performance, power & budgetary costing (EPC-style)."""
from __future__ import annotations

import io
from typing import Any

import pandas as pd
import streamlit as st

from engine.pump_performance import (
    _philosophy_capex_bundle,
    apply_cost_multipliers,
    build_pump_performance_package,
    economics_energy_from_pump_configuration,
    feed_bank_iec_motor_kw_each,
    plant_filtration_motor_kw_parallel_feed,
)
from ui.helpers import fmt, ulbl

try:
    import plotly.graph_objects as go
    _PLOTLY_OK = True
except ImportError:
    _PLOTLY_OK = False


def _fallback_package(inputs: dict, computed: dict) -> dict[str, Any]:
    """If compute did not attach pump_perf (older projects), build on the fly."""
    return build_pump_performance_package(
        inputs=inputs,
        hyd_prof=computed["hyd_prof"],
        energy=computed.get("energy") or {},
        bw_hyd=computed["bw_hyd"],
        bw_seq=computed["bw_seq"],
        bw_sizing=computed.get("bw_sizing") or {},
        q_per_filter=float(computed.get("q_per_filter") or 0.0),
        avg_area=float(computed.get("avg_area") or 0.0),
        total_flow=float(inputs.get("total_flow") or 0.0),
        streams=int(inputs.get("streams") or 1),
        n_filters=int(inputs.get("n_filters") or 1),
        hydraulic_assist=int(inputs.get("hydraulic_assist") or 0),
        rho_feed=float(computed.get("rho_feed") or 1025.0),
        rho_bw=float(computed.get("rho_bw") or 1025.0),
        pump_eta=float(inputs.get("pump_eta") or 0.75),
        motor_eta=float(inputs.get("motor_eta") or 0.95),
        bw_pump_eta=float(inputs.get("bw_pump_eta") or 0.72),
        bw_head_mwc=float(inputs.get("bw_head_mwc") or 15.0),
        bw_velocity=float(inputs.get("bw_velocity") or 30.0),
        bw_cycles_day=float(
            (computed.get("energy") or {}).get("bw_per_day_design")
            or inputs.get("bw_cycles_day")
            or 1.0
        ),
    )


def render_tab_pump_costing(inputs: dict, computed: dict):
    st.subheader("Pump performance, power & costing")
    st.caption(
        "Dry-installed centrifugal pumps and air blowers only — **no** submersible, deep-well, "
        "or vertical wet-pit turbine models. Configure **counts** and **metallurgy** for budgetary "
        "CAPEX; power uses parallel feed hydraulics and the BW sequence from **Backwash**."
    )

    pp = computed.get("pump_perf")
    if not pp:
        pp = _fallback_package(inputs, computed)

    auto = pp["auto"]
    feed0 = pp["feed_pump"]
    bw0 = pp["bw_pump"]
    bl = pp["blower"]
    phil = pp["philosophy"]
    eb = pp["energy_bridge"]
    capex_bl = pp.get("capex_baseline_usd") or {}
    bl_detail = (bl.get("detail") or {}) if isinstance(bl.get("detail"), dict) else {}
    n_bw_sys = int(computed.get("n_bw_systems") or 1)

    for w in pp.get("warnings") or []:
        st.warning(w)

    # ═══ 0 · Plant configuration (counts) ═══════════════════════════════════════
    with st.expander("0 · Plant configuration — pump & blower quantities", expanded=True):
        st.markdown(
            "**Feed:** parallel pumps **per stream** (identical duty pumps on a common header). "
            "**BW water:** installed pump **trains** (DOL 50 % philosophy vs VFD 100 % trains). "
            "**Blowers:** installed **units** for CAPEX; operating kWh uses the mode below."
        )
        r1, r2, r3, r4 = st.columns(4)
        n_feed_par = int(
            r1.number_input(
                "Parallel feed pumps / stream",
                min_value=1,
                max_value=8,
                value=int(st.session_state.get("pp_n_feed_parallel", 1)),
                key="pp_n_feed_parallel",
                help="Each stream is served by this many identical duty pumps in parallel.",
            )
        )
        n_bw_dol = int(
            r2.number_input(
                "BW pumps installed (DOL 50 % trains)",
                min_value=1,
                max_value=8,
                value=int(st.session_state.get("pp_n_bw_dol", 3)),
                key="pp_n_bw_dol",
                help="Typical **2 duty + 1 standby** at 50 % of design flow each → 3.",
            )
        )
        n_bw_vfd = int(
            r3.number_input(
                "BW pumps installed (VFD 100 % trains)",
                min_value=1,
                max_value=8,
                value=int(st.session_state.get("pp_n_bw_vfd", 2)),
                key="pp_n_bw_vfd",
                help="Typical **1 duty + 1 standby** full-speed frame with VFD → 2.",
            )
        )
        n_blow = int(
            r4.number_input(
                "Air blowers installed",
                min_value=1,
                max_value=6,
                value=int(st.session_state.get("pp_n_blowers", 1)),
                key="pp_n_blowers",
                help="CAPEX = n × unit package. Tie to BW hydraulic **trains** where applicable.",
            )
        )
        e1, e2 = st.columns(2)
        econ_phil = e1.radio(
            "BW pump energy for **Economics** tab (when aligned)",
            ["DOL", "VFD"],
            horizontal=True,
            key="pp_econ_bw_phil",
        )
        _bm_labels = {
            "single_duty": "1 × duty online (redundant units idle)",
            "twin_50_iso": "Twin centrifugal — both online at ~50 % flow each (rough Q³)",
        }
        blower_mode = e2.selectbox(
            "Blower operating mode (annual kWh)",
            ["single_duty", "twin_50_iso"],
            index=0,
            format_func=lambda k: _bm_labels[k],
            key="pp_blower_mode",
        )
        st.caption(
            f"Feasibility model: **{n_bw_sys}** BW hydraulic train(s). "
            "Installed blower count is often **one per train** or **N+1** for large plants."
        )

    streams = int(auto["streams"])
    total_flow = float(auto["total_flow_m3h"])
    q_stream = total_flow / max(1, streams)
    q_each_feed = q_stream / max(1, n_feed_par)
    n_feed_total = streams * n_feed_par

    # ═══ 1 Feed pump ═══════════════════════════════════════════════════════════
    with st.expander("1 · Feed pump design", expanded=True):
        fo1, fo2, fo3 = st.columns(3)
        orient = fo1.selectbox(
            "Pump orientation",
            ["Horizontal", "Vertical dry-installed"],
            key="pp_feed_orient",
            help="Vertical dry-pit / inline raises CAPEX ~10 % in the budget model.",
        )
        p_std = fo2.selectbox(
            "Pump / quality standard",
            ["Commercial", "ISO 5199", "API 610 OH2"],
            index=1,
            key="pp_feed_std",
        )
        mat = fo3.selectbox(
            "Wetted material",
            ["Cast iron", "Carbon steel", "SS316", "Duplex", "Super duplex"],
            index=2,
            key="pp_feed_mat",
        )
        s1, s2, s3 = st.columns(3)
        seal = s1.selectbox(
            "Seal type",
            ["Packing", "Single mechanical seal", "Dual seal / API Plan 53"],
            index=1,
            key="pp_feed_seal",
        )
        iec = s2.selectbox("Motor efficiency class", ["IE3", "IE4"], key="pp_feed_iec")
        vfd_feed = s3.checkbox("VFD on feed pumps", value=False, key="pp_feed_vfd")

        motor_eta_feed = 0.955 if iec == "IE3" else 0.965
        fp_kw = plant_filtration_motor_kw_parallel_feed(
            total_flow_m3h=total_flow,
            streams=streams,
            n_feed_pumps_parallel_per_stream=n_feed_par,
            head_dirty_mwc=float(auto["head_dirty_mwc"]),
            head_clean_mwc=float(auto["head_clean_mwc"]),
            rho_feed_kg_m3=float(auto["rho_feed_kg_m3"]),
            motor_eta=motor_eta_feed,
            pump_eta_user_cap=float(inputs.get("pump_eta") or 0.75),
        )
        iec_each = feed_bank_iec_motor_kw_each(
            q_stream_m3h=q_stream,
            n_parallel_pumps=n_feed_par,
            head_mwc=float(auto["head_dirty_mwc"]),
            rho_kg_m3=float(auto["rho_feed_kg_m3"]),
            motor_eta=motor_eta_feed,
            pump_eta_user_cap=float(inputs.get("pump_eta") or 0.75),
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(f"Flow / stream ({ulbl('flow_m3h')})", fmt(q_stream, "flow_m3h", 1))
        c2.metric(f"Flow / pump ({ulbl('flow_m3h')})", fmt(q_each_feed, "flow_m3h", 1))
        c3.metric("Parallel pumps / stream", str(n_feed_par))
        c4.metric("Feed pumps installed", str(n_feed_total))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Plant filtration avg (kW)", f"{fp_kw['p_filtration_plant_avg_kw']:.2f}")
        c2.metric(f"IEC motor / pump ({ulbl('power_kw')})", fmt(iec_each, "power_kw", 1))
        c3.metric("Installed motor sum (IEC)", fmt(iec_each * n_feed_total, "power_kw", 0))
        c4.metric("Ref. single-pump IEC (base)", fmt(feed0["motor_iec_kw"], "power_kw", 1))
        st.markdown(
            f"**Electrical (plant, dirty bed):** {fmt(fp_kw['p_filtration_plant_dirty_kw'], 'power_kw', 2)}  ·  "
            f"**clean:** {fmt(fp_kw['p_filtration_plant_clean_kw'], 'power_kw', 2)}  ·  "
            f"**Specific energy (filtration, central model):** {feed0['specific_energy_kwh_m3']:.4f} kWh/m³ "
            "(scaled in **Economics** when alignment is on)."
        )
        st.caption(
            f"Sidebar **pump η cap** = {float(inputs.get('pump_eta', 0.75)):.2f} · "
            f"**Motor η** = {motor_eta_feed:.3f} ({iec})."
        )

    # ═══ 2 Backwash pumps ═════════════════════════════════════════════════════
    with st.expander("2 · Backwash pump design — DOL vs VFD + metallurgy", expanded=True):
        st.markdown(
            "**DOL:** staging uses the sequence table; installed count sets **CAPEX**.  "
            "**VFD:** affinity on rated 100 % frame; installed count sets **CAPEX**."
        )
        bfo1, bfo2, bfo3 = st.columns(3)
        bw_orient = bfo1.selectbox(
            "BW pump orientation",
            ["Horizontal", "Vertical dry-installed"],
            key="pp_bw_orient",
        )
        bw_std = bfo2.selectbox(
            "BW pump standard",
            ["Commercial", "ISO 5199", "API 610 OH2"],
            index=1,
            key="pp_bw_std",
        )
        bw_mat = bfo3.selectbox(
            "BW wetted material",
            ["Cast iron", "Carbon steel", "SS316", "Duplex", "Super duplex"],
            index=2,
            key="pp_bw_mat",
        )
        bs1, bs2 = st.columns(2)
        bw_seal = bs1.selectbox(
            "BW seal type",
            ["Packing", "Single mechanical seal", "Dual seal / API Plan 53"],
            index=1,
            key="pp_bw_seal",
        )
        bw_vfd_allow = bs2.checkbox(
            "VFD allowance on VFD-philosophy BW trains (drives + filtering)",
            value=True,
            key="pp_bw_vfd_allow",
        )
        st.dataframe(pd.DataFrame(pp["sequence_stages"]), use_container_width=True, hide_index=True)
        b1, b2, b3 = st.columns(3)
        b1.metric("BW pump kWh/cycle (DOL)", f"{phil['DOL']['kwh_bw_pump_per_cycle']:.3f}")
        b2.metric("BW pump kWh/cycle (VFD)", f"{phil['VFD']['kwh_bw_pump_per_cycle']:.3f}")
        b3.metric("BW pump savings (yr)", f"{phil['annual_bw_pump_savings_kwh']:,.0f} kWh")
        st.caption(
            f"Screening: **{phil.get('screening_preference', '—')}**  ·  "
            f"Annual BW pump energy (DOL / VFD): "
            f"{phil['DOL']['kwh_bw_pump_yr']:,.0f} / {phil['VFD']['kwh_bw_pump_yr']:,.0f} kWh/yr  ·  "
            f"IEC frames — DOL half-train: **{bw0['motor_iec_kw_dol_half']:.1f}** kW · "
            f"VFD full: **{bw0['motor_iec_kw_vfd_full']:.1f}** kW"
        )

    # ═══ 3 Blower details ═══════════════════════════════════════════════════════
    with st.expander("3 · Air scour blower — performance & redundancy", expanded=True):
        if bl_detail.get("blower_dp_warning"):
            st.warning(bl_detail["blower_dp_warning"])
        g1, g2, g3 = st.columns(3)
        g1.metric(
            f"Design flow ({ulbl('air_flow_nm3h')})",
            fmt(float(auto.get("q_air_design_nm3h") or 0.0), "air_flow_nm3h", 0),
        )
        g2.metric(f"Motor ({ulbl('power_kw')})", fmt(bl["p_motor_kw"], "power_kw", 1))
        g3.metric("Pressure ratio P₂/P₁", f"{auto['blower_pressure_ratio']:.3f}")
        st.info(bl["technology_hint"])
        if bl_detail:
            st.markdown("**Sizing detail (from BW equipment model)**")
            st.table(pd.DataFrame([
                ["Submergence (est.)", f"{bl_detail.get('h_submergence_m', '—')} m"],
                ["ΔP hydrostatic (submergence)", f"{bl_detail.get('dp_sub_bar', '—')} bar"],
                ["ΔP air side (sparger / header / piping)", f"{bl_detail.get('blower_air_delta_p_bar', '—')} bar"],
                ["Vessel gauge (inputs)", f"{bl_detail.get('vessel_pressure_bar', '—')} bar — Nm³ conversion only"],
                ["P₁ (inlet)", f"{bl_detail.get('P1_pa', '—')} Pa"],
                ["P₂ (discharge)", f"{bl_detail.get('P2_pa', '—')} Pa"],
                ["ρ_air @ inlet", f"{bl_detail.get('rho_air_kg_m3', '—')} kg/m³"],
                ["Ideal gas power", f"{bl_detail.get('p_blower_ideal_kw', '—')} kW"],
                ["Shaft (η_blower)", f"{bl_detail.get('p_blower_shaft_kw', '—')} kW"],
                ["Blower η (model)", f"{bl_detail.get('blower_eta', '—')}"],
            ], columns=["Item", "Value"]))
        st.caption(
            f"**Installed blowers:** {n_blow}  ·  **Operating mode:** `{blower_mode}` — "
            "twin centrifugal mode is a rough **affinity** estimate; PD blowers track closer to flow."
        )

    # ═══ 4 Philosophy ═══════════════════════════════════════════════════════════
    with st.expander("4 · Pump configuration philosophy", expanded=False):
        st.markdown(
            "| Theme | DOL / fixed speed | VFD / variable speed |\n"
            "|---|---|---|\n"
            "| **CAPEX** | Lower drive cost | +VFDs, harmonics filters |\n"
            "| **Energy** | Higher BW pump kWh | Lower part-load kWh |\n"
            "| **Operability** | Simple staging | Tuning / DCS logic |\n"
            "| **Redundancy** | 3 × 50 % common | 2 × 100 % + VFD |\n"
        )

    # ═══ 5 Power summary ═════════════════════════════════════════════════════════
    with st.expander("5 · Power consumption summary", expanded=True):
        dol_inst = float(bw0["motor_iec_kw_dol_half"]) * float(n_bw_dol)
        vfd_inst = float(bw0["motor_iec_kw_vfd_full"]) * float(n_bw_vfd)
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Feed plant avg (recalc.)", f"{fp_kw['p_filtration_plant_avg_kw']:.2f} kW")
        p2.metric("BW DOL installed (IEC sum)", fmt(dol_inst, "power_kw", 1))
        p3.metric("BW VFD installed (IEC sum)", fmt(vfd_inst, "power_kw", 1))
        p4.metric("Peak BW stage (est.)", fmt(eb["peak_bw_stage_kw"], "power_kw", 1))
        st.markdown(
            f"**Annual (central model):** filtration **{eb['e_filt_kwh_yr']:,.0f}** kWh/yr · "
            f"BW pump **{eb['e_bw_pump_kwh_yr_model']:,.0f}** · blower **{eb['e_blower_kwh_yr']:,.0f}**  ·  "
            f"**kWh/m³ filtered (all loads):** {eb['kwh_per_m3_filtered']:.4f}"
        )
        st.caption(
            f"Sequence-integrated BW + blower (one filter, one cycle): **{eb['kwh_per_bw_filter_cycle']:.3f}** kWh  ·  "
            f"Plant-day sequence estimate: **{eb['kwh_bw_plant_day_sequence']:,.1f}** kWh/day."
        )
        if _PLOTLY_OK and pp["sequence_stages"]:
            t0 = 0.0
            xs, ys = [], []
            for row in pp["sequence_stages"]:
                dt = float(row["t_min"]) / 60.0
                xs.extend([t0, t0 + dt])
                ptot = float(row["P_total (kW)"])
                ys.extend([ptot, ptot])
                t0 += dt
            fig = go.Figure(go.Scatter(x=xs, y=ys, mode="lines", line_shape="hv", name="BW + blower"))
            fig.update_layout(
                title="Backwash sequence — instantaneous electrical load (one filter)",
                xaxis_title="Time from BW start (h)",
                yaxis_title="kW",
                height=360,
                margin=dict(t=50, b=40, l=50, r=20),
            )
            st.plotly_chart(fig, use_container_width=True)

    # ═══ 6 Budgetary costing ═════════════════════════════════════════════════════
    with st.expander("6 · Budgetary equipment costing (±25 %)", expanded=True):
        feed_mult = apply_cost_multipliers(
            material=mat,
            pump_standard=p_std,
            seal=seal,
            use_vfd=vfd_feed,
            vertical=(orient.startswith("Vertical")),
        )
        feed_cpx = (
            feed_mult["material"] * feed_mult["standard"]
            * feed_mult["seal"] * feed_mult["vertical"]
        )
        feed_vfd_m = float(feed_mult["vfd"])

        bw_mult = apply_cost_multipliers(
            material=bw_mat,
            pump_standard=bw_std,
            seal=bw_seal,
            use_vfd=False,
            vertical=(bw_orient.startswith("Vertical")),
        )
        bw_cpx = bw_mult["material"] * bw_mult["standard"] * bw_mult["seal"] * bw_mult["vertical"]
        bw_vfd_train_m = 1.35 * (1.0 if bw_vfd_allow else 1.0)

        capex_live = _philosophy_capex_bundle(
            bw_motor_iec_kw_dol_train=float(bw0["motor_iec_kw_dol_half"]),
            bw_motor_iec_kw_vfd_train=float(bw0["motor_iec_kw_vfd_full"]),
            blower_motor_kw=float(bl["p_motor_kw"]),
            feed_motor_kw_each=float(iec_each),
            n_feed_pumps_total=n_feed_total,
            n_bw_dol_trains=n_bw_dol,
            n_bw_vfd_trains=n_bw_vfd,
            n_blower_units=n_blow,
            feed_complex_mult=feed_cpx,
            feed_vfd_budget_mult=feed_vfd_m,
            bw_complex_mult=bw_cpx,
            bw_vfd_train_budget_mult=bw_vfd_train_m,
        )
        st.table(pd.DataFrame([
            ["Feed pumps (n × unit)", f"USD {capex_live['feed_pumps_all_usd']:,.0f}"],
            ["BW pumps — DOL (n trains)", f"USD {capex_live['dol_bw_total_usd']:,.0f}"],
            ["BW pumps — VFD (n trains)", f"USD {capex_live['vfd_bw_total_usd']:,.0f}"],
            ["Blowers (n × unit)", f"USD {capex_live['blower_package_total_usd']:,.0f}"],
            ["**Subtotal — DOL + blowers + feed**", f"**USD {capex_live['dol_grand_total_usd']:,.0f}**"],
            ["**Subtotal — VFD + blowers + feed**", f"**USD {capex_live['vfd_grand_total_usd']:,.0f}**"],
            ["Baseline package (reference)", f"USD {capex_bl.get('dol_grand_total_usd', 0):,.0f}"],
        ], columns=["Item", "Budgetary"]))
        st.caption(
            "Skid / base / coupling allowance per train. Not site piping, MCC building, installation, margin."
        )

    # ═══ 7 Recommendations ═══════════════════════════════════════════════════════
    with st.expander("7 · Engineering recommendations", expanded=False):
        for note in pp.get("engineering_notes") or []:
            st.markdown(f"- {note}")

    # ═══ 8 Export ═══════════════════════════════════════════════════════════════
    with st.expander("8 · Exportable summary tables", expanded=False):
        summary = pd.DataFrame([
            ["Total flow", fmt(auto["total_flow_m3h"], "flow_m3h", 1)],
            ["Streams × filters", f"{auto['streams']} × {auto['n_filters']}"],
            ["Parallel feed pumps / stream", str(n_feed_par)],
            ["Feed pumps installed", str(n_feed_total)],
            ["Flow / pump (feed)", fmt(q_each_feed, "flow_m3h", 2)],
            ["Plant feed avg kW (recalc.)", f"{fp_kw['p_filtration_plant_avg_kw']:.3f}"],
            ["Feed IEC motor / pump", fmt(iec_each, "power_kw", 1)],
            ["BW pumps installed DOL / VFD", f"{n_bw_dol} / {n_bw_vfd}"],
            ["Blowers installed", str(n_blow)],
            ["BW design flow", fmt(auto["q_bw_design_m3h"], "flow_m3h", 1)],
            ["BW head", fmt(auto["bw_head_mwc"], "pressure_mwc", 2)],
            ["Blower motor (duty)", fmt(bl["p_motor_kw"], "power_kw", 1)],
            ["Economics BW philosophy", str(st.session_state.get("pp_econ_bw_phil", "DOL"))],
            ["kWh/m³ filtered (all, central)", f"{eb['kwh_per_m3_filtered']:.4f}"],
            ["kWh/BW filter-cycle", f"{eb['kwh_per_bw_filter_cycle']:.3f}"],
        ], columns=["Parameter", "Value"])
        st.dataframe(summary, use_container_width=True, hide_index=True)
        csv_buf = io.StringIO()
        summary.to_csv(csv_buf, index=False)
        st.download_button(
            "Download summary CSV",
            data=csv_buf.getvalue().encode("utf-8"),
            file_name="AQUASIGHT_pump_performance_summary.csv",
            mime="text/csv",
        )
