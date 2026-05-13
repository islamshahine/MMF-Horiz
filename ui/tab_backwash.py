"""ui/tab_backwash.py — Backwash tab for AQUASIGHT™ MMF."""
import pandas as pd
import streamlit as st
from engine.backwash import bed_expansion as _bed_exp
from ui.helpers import fmt, ulbl, dv, show_alert


def render_tab_backwash(inputs: dict, computed: dict):
    bw_col       = computed["bw_col"]
    bw_hyd       = computed["bw_hyd"]
    bw_seq       = computed["bw_seq"]
    bw_sizing    = computed["bw_sizing"]
    filt_cycles  = computed["filt_cycles"]
    feasibility_matrix = computed["feasibility_matrix"]
    _load_data_cyc     = computed["load_data"]
    _tss_labels  = computed["tss_labels"]
    _tss_vals    = computed["tss_vals"]
    _temp_labels = computed["temp_labels"]
    rho_bw       = computed["rho_bw"]
    mu_bw        = computed["mu_bw"]
    _n_bw_systems = computed["n_bw_systems"]
    m_sol_low    = computed["m_sol_low"]
    m_sol_avg    = computed["m_sol_avg"]
    m_sol_high   = computed["m_sol_high"]
    w_tss_low    = computed["w_tss_low"]
    w_tss_avg    = computed["w_tss_avg"]
    w_tss_high   = computed["w_tss_high"]
    m_daily_low  = computed["m_daily_low"]
    m_daily_avg  = computed["m_daily_avg"]
    m_daily_high = computed["m_daily_high"]

    layers             = inputs["layers"]
    freeboard_mm       = inputs["freeboard_mm"]
    air_scour_rate     = inputs["air_scour_rate"]
    bw_temp            = inputs["bw_temp"]
    bw_s_drain         = inputs["bw_s_drain"]
    bw_s_air           = inputs["bw_s_air"]
    bw_s_airw          = inputs["bw_s_airw"]
    bw_s_hw            = inputs["bw_s_hw"]
    bw_s_settle        = inputs["bw_s_settle"]
    bw_s_fill          = inputs["bw_s_fill"]
    bw_total_min       = inputs["bw_total_min"]
    vessel_pressure_bar = inputs["vessel_pressure_bar"]
    streams            = inputs["streams"]
    tss_low            = inputs["tss_low"]
    tss_avg            = inputs["tss_avg"]
    tss_high           = inputs["tss_high"]

    st.caption("Backwash hydraulics, bed expansion, sequence and equipment sizing.")

    with st.expander("1 · Collector height check — media loss guard", expanded=True):
        status_color = "🔴" if bw_col["media_loss_risk"] else ("🟡" if "WARNING" in bw_col["status"] else "🟢")
        st.markdown(f"### {status_color} {bw_col['status']}")
        cc1, cc2, cc3, cc4 = st.columns(4)
        cc1.metric("Settled bed top",  fmt(bw_col['settled_top_m'],  'length_m', 3))
        cc2.metric("Expanded bed top", fmt(bw_col['expanded_top_m'], 'length_m', 3))
        cc3.metric("Collector height", fmt(bw_col['collector_h_m'],  'length_m', 3))
        cc4.metric("Freeboard",        fmt(bw_col['freeboard_m'],    'length_m', 3),
                   delta=f"{bw_col['freeboard_pct']:.1f}% of bed",
                   delta_color="normal" if bw_col["freeboard_m"] >= bw_col["min_freeboard_m"] else "inverse")
        st.info(
            f"**Max safe BW velocity: {fmt(bw_col['max_safe_bw_m_h'], 'velocity_m_h', 1)}** "
            f"(maintains ≥ {freeboard_mm:.0f} mm freeboard below collector).  "
            f"Proposed BW: **{fmt(bw_col['proposed_bw_m_h'], 'velocity_m_h', 1)}**."
        )
        exp_rows = []
        _bw_integrity_alerts = []
        for L in bw_col["per_layer"]:
            if L.get("elutriation_risk"):
                _status = "Approaching terminal velocity"
                _bw_integrity_alerts.append(("critical",
                    f"{L['media_type']}: backwash velocity approaches terminal settling velocity",
                    "Risk of progressive media loss over repeated backwash cycles. "
                    "Reduce backwash rate or raise the outlet collector."))
            elif L["fluidised"]:
                _status = f"Fluidised — {L['expansion_pct']}% bed expansion"
            else:
                _status = f"Below fluidisation threshold (u_mf = {L['u_mf_m_h']} m/h)"
                _bw_integrity_alerts.append(("warning" if freeboard_mm >= 150 else "advisory",
                    f"{L['media_type']}: hydraulic bed lift not achieved at current water rate",
                    "Backwash velocity is below the minimum fluidisation threshold for this media. "
                    "Air scour provides primary mechanical cleaning action."))
            exp_rows.append({
                "Media": L["media_type"], "d10 (mm)": L["d10_mm"],
                "u_mf (m/h)": L["u_mf_m_h"], "u_t (m/h)": L["u_t_m_h"],
                "ε₀": L["epsilon0"], "ε_f": L["eps_f"],
                "Settled (m)": L["depth_settled_m"], "Expanded (m)": L["depth_expanded_m"],
                "Expansion (%)": L["expansion_pct"], "Status": _status,
            })
        st.dataframe(pd.DataFrame(exp_rows), use_container_width=True, hide_index=True)
        exp_combined = _bed_exp(layers=layers, bw_velocity_m_h=air_scour_rate,
                                water_temp_c=bw_temp, rho_water=rho_bw)
        st.markdown(f"**Air + water combined phase** (equivalent velocity = {air_scour_rate:.0f} m/h):")
        comb_rows = [{"Media": L["media_type"], "u_mf (m/h)": L["u_mf_m_h"],
                      "Fluidised": "Yes ✅" if L["fluidised"] else "No",
                      "ε_f": L["eps_f"], "Settled (m)": L["depth_settled_m"],
                      "Expanded (m)": L["depth_expanded_m"], "Expansion (%)": L["expansion_pct"],
                      "Note": L["warning"] if L["warning"] else "OK"}
                     for L in exp_combined["layers"]]
        st.dataframe(pd.DataFrame(comb_rows), use_container_width=True, hide_index=True)
        if _bw_integrity_alerts:
            with st.expander(f"🔴 Backwash Integrity — {len(_bw_integrity_alerts)} concern(s) identified"):
                for _lvl, _ttl, _msg in _bw_integrity_alerts:
                    show_alert(_lvl, _ttl, _msg)
        ec1, ec2, ec3 = st.columns(3)
        ec1.metric("Settled bed",  fmt(exp_combined['total_settled_m'],  'length_m', 3))
        ec2.metric("Expanded bed", fmt(exp_combined['total_expanded_m'], 'length_m', 3))
        ec3.metric("Net expansion",f"{exp_combined['total_expansion_pct']:.1f} %")
        if bw_col["media_loss_risk"]:
            show_alert("critical", "Collector height insufficient — media carryover risk",
                f"The expanded bed top ({fmt(bw_col['expanded_top_m'], 'length_m', 3)}) reaches or exceeds "
                f"the BW outlet collector ({fmt(bw_col['collector_h_m'], 'length_m', 3)}). "
                f"Maximum safe backwash velocity: {fmt(bw_col['max_safe_bw_m_h'], 'velocity_m_h', 1)}.")

    with st.expander("2 · BW pump & air blower capacity", expanded=True):
        bh1, bh2, bh3, bh4 = st.columns(4)
        bh1.metric(f"BW flow ({ulbl('flow_m3h')})",            fmt(bw_hyd['q_bw_m3h'], 'flow_m3h', 0),           help=bw_hyd["bw_governs"])
        bh2.metric(f"BW LV actual ({ulbl('velocity_m_h')})",  fmt(bw_hyd['bw_lv_actual_m_h'], 'velocity_m_h', 1))
        bh3.metric(f"Air scour flow ({ulbl('flow_m3h')})",    fmt(bw_hyd['q_air_m3h'], 'flow_m3h', 0))
        bh4.metric(f"Blower est. ({ulbl('power_kw')})",       fmt(bw_hyd['p_blower_est_kw'], 'power_kw', 1))
        st.table(pd.DataFrame([
            ["Governing BW flow",          f"{bw_hyd['q_bw_m3h']:,.1f} m³/h ({bw_hyd['bw_governs']})"],
            ["BW design capacity (×1.10)", f"{bw_hyd['q_bw_design_m3h']:,.1f} m³/h"],
            ["Air design capacity (×1.10)",f"{bw_hyd['q_air_design_m3h']:,.1f} m³/h"],
            ["Blower power (est., η=0.65)",f"{bw_hyd['p_blower_est_kw']:.1f} kW"],
            ["BW water: ρ",                f"{rho_bw:.2f} kg/m³  |  μ={mu_bw*1000:.4f} cP"],
        ], columns=["Parameter", "Value"]))

    with st.expander("3 · BW sequence & waste volumes", expanded=True):
        st.dataframe(pd.DataFrame(bw_seq["steps"]), use_container_width=True, hide_index=True)
        st.divider()
        w1, w2, w3, w4 = st.columns(4)
        w1.metric("BW duration (avg)",  f"{bw_seq['dur_total_avg_min']} min")
        w2.metric("Total vol / filter", f"{bw_seq['total_vol_avg_m3']:.0f} m³")
        w3.metric("Waste / filter",     f"{bw_seq['waste_vol_avg_m3']:.0f} m³")
        w4.metric("Plant waste / day",  f"{bw_seq['waste_vol_daily_m3']:.0f} m³/d")
        st.markdown("**Waste volume & TSS mass balance**")
        st.table(pd.DataFrame([
            ["Low TSS",  f"{tss_low:.0f} mg/L",  f"{bw_seq['total_vol_low_m3']:.0f} m³",  f"{m_sol_low:.0f} kg",  f"{w_tss_low:.0f} mg/L",  f"{m_daily_low:,.0f} kg/d"],
            ["Avg TSS",  f"{tss_avg:.0f} mg/L",  f"{bw_seq['total_vol_avg_m3']:.0f} m³",  f"{m_sol_avg:.0f} kg",  f"{w_tss_avg:.0f} mg/L",  f"{m_daily_avg:,.0f} kg/d"],
            ["High TSS", f"{tss_high:.0f} mg/L", f"{bw_seq['total_vol_high_m3']:.0f} m³", f"{m_sol_high:.0f} kg", f"{w_tss_high:.0f} mg/L", f"{m_daily_high:,.0f} kg/d"],
        ], columns=["Scenario", "Feed TSS", "BW vol / filter", "Solids / filter", "Waste TSS conc.", "Plant solids / day"]))

    with st.expander("4 · BW scheduling & system feasibility", expanded=True):
        _bw_steps = [("① Gravity drain", bw_s_drain), ("② Air scour only", bw_s_air),
                     ("③ Air + low-rate water", bw_s_airw), ("④ High-rate water", bw_s_hw),
                     ("⑤ Settling", bw_s_settle), ("⑥ Fill & rinse", bw_s_fill)]
        cum = 0
        step_rows = []
        for nm, dur in _bw_steps:
            cum += dur
            step_rows.append({"Step": nm, "Duration (min)": dur, "Cumulative (min)": cum})
        step_rows.append({"Step": "TOTAL", "Duration (min)": bw_total_min, "Cumulative (min)": bw_total_min})
        cA, cB = st.columns([1, 2])
        with cA:
            st.markdown("**BW step breakdown**")
            st.dataframe(pd.DataFrame(step_rows), use_container_width=True, hide_index=True)
        with cB:
            st.markdown(f"**BW duration: {bw_total_min} min**")
        if feasibility_matrix:
            for sc_lbl, sc_temps in feasibility_matrix.items():
                _lv = filt_cycles[sc_lbl]["lv_m_h"]
                _nact_f = next(n for x, n, _ in _load_data_cyc if ("N" if x == 0 else f"N-{x}") == sc_lbl)
                st.markdown(f"---\n**Scenario {sc_lbl} · {_nact_f * streams} active filters plant-wide · LV = {_lv:.1f} m/h**")
                avail_rows = [{"Feed TSS": tss_lbl,
                               **{t_lbl: f"{sc_temps[t_lbl][tss_lbl]['avail_pct']:.1f} %" for t_lbl in _temp_labels}}
                              for tss_lbl in _tss_labels]
                st.markdown("*Availability (%)*")
                st.dataframe(pd.DataFrame(avail_rows).set_index("Feed TSS"), use_container_width=True)
                sim_rows = [{"Feed TSS": tss_lbl,
                             **{t_lbl: f"{sc_temps[t_lbl][tss_lbl]['sim_demand']:.2f} → {sc_temps[t_lbl][tss_lbl]['bw_trains']} BW system(s)"
                                for t_lbl in _temp_labels}}
                            for tss_lbl in _tss_labels]
                st.markdown("*BW systems required (plant-wide)*")
                st.dataframe(pd.DataFrame(sim_rows).set_index("Feed TSS"), use_container_width=True)

    with st.expander("5 · BW system equipment data sheet", expanded=True):
        st.markdown("### BW pump")
        p1, p2, p3, p4 = st.columns(4)
        p1.metric(f"Design flow ({ulbl('flow_m3h')})",       fmt(bw_sizing['q_bw_design_m3h'], 'flow_m3h', 0))
        p2.metric(f"Total head ({ulbl('pressure_mwc')})",   fmt(bw_sizing['bw_head_mwc'], 'pressure_mwc', 1))
        p3.metric(f"Shaft power ({ulbl('power_kw')})",      fmt(bw_sizing['p_pump_shaft_kw'], 'power_kw', 0))
        p4.metric(f"Motor power ({ulbl('power_kw')})",      fmt(bw_sizing['p_pump_motor_kw'], 'power_kw', 0))
        st.table(pd.DataFrame([
            ["Design flow (duty)",        f"{bw_sizing['q_bw_design_m3h']:,.1f} m³/h"],
            ["Total dynamic head",        f"{bw_sizing['bw_head_mwc']:.1f} mWC  ({bw_sizing['bw_head_bar']:.3f} bar)"],
            ["Pump hydraulic efficiency", f"{bw_sizing['bw_pump_eta']*100:.0f} %"],
            ["Shaft power",               f"{bw_sizing['p_pump_shaft_kw']:.1f} kW"],
            ["Motor power (absorbed)",    f"{bw_sizing['p_pump_motor_kw']:.1f} kW"],
            ["Duty / standby",            f"{_n_bw_systems}D / 1S  (plant-wide)"],
        ], columns=["Parameter", "Value"]))
        st.markdown("### Air blower")
        b1, b2, b3, b4 = st.columns(4)
        b1.metric(f"Design flow ({ulbl('flow_m3h')})",      fmt(bw_sizing['q_air_design_m3h'], 'flow_m3h', 0))
        b2.metric(f"ΔP total ({ulbl('pressure_bar')})",    fmt(bw_sizing['dp_total_bar'], 'pressure_bar', 3))
        b3.metric(f"Shaft power ({ulbl('power_kw')})",     fmt(bw_sizing['p_blower_shaft_kw'], 'power_kw', 0))
        b4.metric(f"Motor power ({ulbl('power_kw')})",     fmt(bw_sizing['p_blower_motor_kw'], 'power_kw', 0))
        st.table(pd.DataFrame([
            ["Inlet volume flow",          f"{bw_sizing['q_air_design_m3h']:,.1f} m³/h  ({bw_sizing['q_air_design_m3min']:.1f} m³/min)"],
            ["Vessel back-pressure",       f"{vessel_pressure_bar:.2f} bar g"],
            ["Water submergence (≈ ID/2)", f"{bw_sizing['h_submergence_m']:.2f} m  →  {bw_sizing['dp_sub_bar']:.3f} bar"],
            ["Total ΔP",                   f"{bw_sizing['dp_total_bar']:.3f} bar"],
            ["Shaft power",                f"{bw_sizing['p_blower_shaft_kw']:.1f} kW"],
            ["Motor power (absorbed)",     f"{bw_sizing['p_blower_motor_kw']:.1f} kW"],
        ], columns=["Parameter", "Value"]))
        st.markdown("### BW water storage tank")
        t1, t2, t3 = st.columns(3)
        t1.metric("Vol/cycle/system",  f"{bw_sizing['bw_vol_per_cycle_m3']:.0f} m³")
        t2.metric("Simultaneous syst.",f"{bw_sizing['n_bw_systems']}")
        t3.metric("Recommended tank",  f"{bw_sizing['v_tank_m3']:.0f} m³",
                  help=f"Governs: {bw_sizing['tank_governs']}")
        st.table(pd.DataFrame([
            ["BW vol / filter / cycle (avg)", f"{bw_sizing['bw_vol_per_cycle_m3']:.1f} m³"],
            ["Simultaneous BW systems",        f"{bw_sizing['n_bw_systems']}"],
            ["Volume — cycle-based",           f"{bw_sizing['v_cycle_m3']:.0f} m³"],
            ["Volume — 10-min rule",           f"{bw_sizing['v_10min_m3']:.0f} m³"],
            ["Recommended tank volume",        f"{bw_sizing['v_tank_m3']:.0f} m³  (governs: {bw_sizing['tank_governs']})"],
        ], columns=["Parameter", "Value"]))

    st.divider()
    bm1, bm2, bm3, bm4 = st.columns(4)
    bm1.metric(f"BW flow, design ({ulbl('flow_m3h')})", fmt(bw_hyd['q_bw_design_m3h'], 'flow_m3h', 0))
    bm2.metric(f"Air scour flow ({ulbl('flow_m3h')})", fmt(bw_hyd['q_air_design_m3h'], 'flow_m3h', 0))
    bm3.metric("BW duration",                          f"{bw_total_min} min")
    bm4.metric("Plant waste / day",                    f"{bw_seq['waste_vol_daily_m3']:.0f} m³/d")
