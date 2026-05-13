"""ui/tab_backwash.py — Backwash tab for AQUASIGHT™ MMF."""
import pandas as pd
import streamlit as st
from engine.backwash import bed_expansion as _bed_exp
from ui.helpers import (
    fmt, ulbl, dv, show_alert,
    cycle_matrix_temp_title, cycle_matrix_tss_row_title,
    backwash_sequence_steps_display_df,
)


def render_tab_backwash(inputs: dict, computed: dict):
    bw_col       = computed["bw_col"]
    bw_hyd       = computed["bw_hyd"]
    bw_seq       = computed["bw_seq"]
    bw_sizing    = computed["bw_sizing"]
    filt_cycles  = computed["filt_cycles"]
    feasibility_matrix = computed["feasibility_matrix"]
    _load_data_cyc     = computed["load_data"]
    _tss_col_keys = computed["tss_col_keys"]
    _tss_vals     = computed["tss_vals"]
    _temp_col_keys = computed["temp_col_keys"]
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
    temp_low           = inputs["temp_low"]
    feed_temp          = inputs["feed_temp"]
    temp_high          = inputs["temp_high"]

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
                _status = f"Below fluidisation threshold (u_mf = {fmt(L['u_mf_m_h'], 'velocity_m_h', 2)})"
                _bw_integrity_alerts.append(("warning" if freeboard_mm >= 150 else "advisory",
                    f"{L['media_type']}: hydraulic bed lift not achieved at current water rate",
                    "Backwash velocity is below the minimum fluidisation threshold for this media. "
                    "Air scour provides primary mechanical cleaning action."))
            exp_rows.append({
                "Media": L["media_type"], "d10 (mm)": L["d10_mm"],
                f"u_mf ({ulbl('velocity_m_h')})": round(dv(L["u_mf_m_h"], "velocity_m_h"), 2),
                f"u_t ({ulbl('velocity_m_h')})": round(dv(L["u_t_m_h"], "velocity_m_h"), 2),
                "ε₀": L["epsilon0"], "ε_f": L["eps_f"],
                f"Settled ({ulbl('length_m')})": round(dv(L["depth_settled_m"], "length_m"), 3),
                f"Expanded ({ulbl('length_m')})": round(dv(L["depth_expanded_m"], "length_m"), 3),
                "Expansion (%)": L["expansion_pct"], "Status": _status,
            })
        st.dataframe(pd.DataFrame(exp_rows), use_container_width=True, hide_index=True)
        exp_combined = _bed_exp(layers=layers, bw_velocity_m_h=air_scour_rate,
                                water_temp_c=bw_temp, rho_water=rho_bw)
        st.markdown(
            f"**Air + water combined phase** (equivalent velocity = "
            f"{fmt(air_scour_rate, 'velocity_m_h', 0)}):"
        )
        comb_rows = [{
            "Media": L["media_type"],
            f"u_mf ({ulbl('velocity_m_h')})": round(dv(L["u_mf_m_h"], "velocity_m_h"), 2),
            "Fluidised": "Yes ✅" if L["fluidised"] else "No",
            "ε_f": L["eps_f"],
            f"Settled ({ulbl('length_m')})": round(dv(L["depth_settled_m"], "length_m"), 3),
            f"Expanded ({ulbl('length_m')})": round(dv(L["depth_expanded_m"], "length_m"), 3),
            "Expansion (%)": L["expansion_pct"],
            "Note": L["warning"] if L["warning"] else "OK",
        } for L in exp_combined["layers"]]
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
            ["Governing BW flow",
             f"{fmt(bw_hyd['q_bw_m3h'], 'flow_m3h', 1)} ({bw_hyd['bw_governs']})"],
            ["BW design capacity (×1.10)", fmt(bw_hyd['q_bw_design_m3h'], 'flow_m3h', 1)],
            ["Air design capacity (×1.10)", fmt(bw_hyd['q_air_design_m3h'], 'flow_m3h', 1)],
            ["Blower power (est., η=0.65)", fmt(bw_hyd['p_blower_est_kw'], 'power_kw', 1)],
            ["BW water: ρ | μ",
             f"{fmt(rho_bw, 'density_kg_m3', 2)}  |  {fmt(mu_bw * 1000.0, 'viscosity_cp', 4)}"],
        ], columns=["Parameter", "Value"]))

    with st.expander("3 · BW sequence & waste volumes", expanded=True):
        st.dataframe(backwash_sequence_steps_display_df(bw_seq["steps"]),
                     use_container_width=True, hide_index=True)
        st.divider()
        w1, w2, w3, w4 = st.columns(4)
        w1.metric("BW duration (avg)",  f"{bw_seq['dur_total_avg_min']} min")
        w2.metric("Total vol / filter", fmt(bw_seq["total_vol_avg_m3"], "volume_m3", 0))
        w3.metric("Waste / filter",     fmt(bw_seq["waste_vol_avg_m3"], "volume_m3", 0))
        w4.metric("Plant waste / day", fmt(bw_seq["waste_vol_daily_m3"], "volume_m3_per_day", 0))
        st.markdown("**Waste volume & TSS mass balance**")
        st.table(pd.DataFrame([
            ["Low TSS",
             fmt(tss_low, "concentration_mg_l", 0),
             fmt(bw_seq["total_vol_low_m3"], "volume_m3", 0),
             fmt(m_sol_low, "mass_kg", 0),
             fmt(w_tss_low, "concentration_mg_l", 0),
             fmt(m_daily_low, "mass_rate_kg_d", 0)],
            ["Avg TSS",
             fmt(tss_avg, "concentration_mg_l", 0),
             fmt(bw_seq["total_vol_avg_m3"], "volume_m3", 0),
             fmt(m_sol_avg, "mass_kg", 0),
             fmt(w_tss_avg, "concentration_mg_l", 0),
             fmt(m_daily_avg, "mass_rate_kg_d", 0)],
            ["High TSS",
             fmt(tss_high, "concentration_mg_l", 0),
             fmt(bw_seq["total_vol_high_m3"], "volume_m3", 0),
             fmt(m_sol_high, "mass_kg", 0),
             fmt(w_tss_high, "concentration_mg_l", 0),
             fmt(m_daily_high, "mass_rate_kg_d", 0)],
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
            _temp_si_bw = {
                "temp_min": temp_low, "temp_design": feed_temp, "temp_max": temp_high,
            }
            _tss_si_bw = {
                "tss_low": tss_low, "tss_avg": tss_avg, "tss_high": tss_high,
            }
            for sc_lbl, sc_temps in feasibility_matrix.items():
                _lv = filt_cycles[sc_lbl]["lv_m_h"]
                _nact_f = next(n for x, n, _ in _load_data_cyc if ("N" if x == 0 else f"N-{x}") == sc_lbl)
                st.markdown(
                    f"---\n**Scenario {sc_lbl} · {_nact_f * streams} active filters plant-wide · "
                    f"LV = {fmt(_lv, 'velocity_m_h', 1)}**"
                )
                avail_rows = [{
                    "Feed TSS": cycle_matrix_tss_row_title(tss_key, _tss_si_bw[tss_key]),
                    **{
                        cycle_matrix_temp_title(tk, _temp_si_bw[tk]): (
                            f"{sc_temps[tk][tss_key]['avail_pct']:.1f} %"
                        )
                        for tk in _temp_col_keys
                    },
                } for tss_key in _tss_col_keys]
                st.markdown("*Availability (%)*")
                st.dataframe(pd.DataFrame(avail_rows).set_index("Feed TSS"), use_container_width=True)
                sim_rows = [{
                    "Feed TSS": cycle_matrix_tss_row_title(tss_key, _tss_si_bw[tss_key]),
                    **{
                        cycle_matrix_temp_title(tk, _temp_si_bw[tk]): (
                            f"{sc_temps[tk][tss_key]['sim_demand']:.2f} → "
                            f"{sc_temps[tk][tss_key]['bw_trains']} BW system(s)"
                        )
                        for tk in _temp_col_keys
                    },
                } for tss_key in _tss_col_keys]
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
            ["Design flow (duty)", fmt(bw_sizing["q_bw_design_m3h"], "flow_m3h", 1)],
            ["Total dynamic head",
             f"{fmt(bw_sizing['bw_head_mwc'], 'pressure_mwc', 1)} "
             f"({fmt(bw_sizing['bw_head_bar'], 'pressure_bar', 3)})"],
            ["Pump hydraulic efficiency", f"{bw_sizing['bw_pump_eta']*100:.0f} %"],
            ["Shaft power",               fmt(bw_sizing["p_pump_shaft_kw"], "power_kw", 1)],
            ["Motor power (absorbed)",    fmt(bw_sizing["p_pump_motor_kw"], "power_kw", 1)],
            ["Duty / standby",            f"{_n_bw_systems}D / 1S  (plant-wide)"],
        ], columns=["Parameter", "Value"]))
        st.markdown("### Air blower")
        b1, b2, b3, b4 = st.columns(4)
        b1.metric(f"Design flow ({ulbl('flow_m3h')})",      fmt(bw_sizing['q_air_design_m3h'], 'flow_m3h', 0))
        b2.metric(f"ΔP total ({ulbl('pressure_bar')})",    fmt(bw_sizing['dp_total_bar'], 'pressure_bar', 3))
        b3.metric(f"Shaft power ({ulbl('power_kw')})",     fmt(bw_sizing['p_blower_shaft_kw'], 'power_kw', 0))
        b4.metric(f"Motor power ({ulbl('power_kw')})",     fmt(bw_sizing['p_blower_motor_kw'], 'power_kw', 0))
        st.table(pd.DataFrame([
            ["Inlet volume flow",
             f"{fmt(bw_sizing['q_air_design_m3h'], 'flow_m3h', 1)}  "
             f"({fmt(bw_sizing['q_air_design_m3min'], 'flow_m3_min', 1)})"],
            ["Vessel back-pressure",
             f"{fmt(vessel_pressure_bar, 'pressure_bar', 2)} g"],
            ["Water submergence (≈ ID/2)",
             f"{fmt(bw_sizing['h_submergence_m'], 'length_m', 2)}  →  "
             f"{fmt(bw_sizing['dp_sub_bar'], 'pressure_bar', 3)}"],
            ["Total ΔP", fmt(bw_sizing["dp_total_bar"], "pressure_bar", 3)],
            ["Shaft power", fmt(bw_sizing["p_blower_shaft_kw"], "power_kw", 1)],
            ["Motor power (absorbed)", fmt(bw_sizing["p_blower_motor_kw"], "power_kw", 1)],
        ], columns=["Parameter", "Value"]))
        st.markdown("### BW water storage tank")
        t1, t2, t3 = st.columns(3)
        t1.metric("Vol/cycle/system", fmt(bw_sizing["bw_vol_per_cycle_m3"], "volume_m3", 0))
        t2.metric("Simultaneous syst.", f"{bw_sizing['n_bw_systems']}")
        t3.metric("Recommended tank", fmt(bw_sizing["v_tank_m3"], "volume_m3", 0),
                  help=f"Governs: {bw_sizing['tank_governs']}")
        st.table(pd.DataFrame([
            ["BW vol / filter / cycle (avg)", fmt(bw_sizing["bw_vol_per_cycle_m3"], "volume_m3", 1)],
            ["Simultaneous BW systems", str(bw_sizing["n_bw_systems"])],
            ["Volume — cycle-based", fmt(bw_sizing["v_cycle_m3"], "volume_m3", 0)],
            ["Volume — 10-min rule", fmt(bw_sizing["v_10min_m3"], "volume_m3", 0)],
            ["Recommended tank volume",
             f"{fmt(bw_sizing['v_tank_m3'], 'volume_m3', 0)}  (governs: {bw_sizing['tank_governs']})"],
        ], columns=["Parameter", "Value"]))

    st.divider()
    bm1, bm2, bm3, bm4 = st.columns(4)
    bm1.metric(f"BW flow, design ({ulbl('flow_m3h')})", fmt(bw_hyd['q_bw_design_m3h'], 'flow_m3h', 0))
    bm2.metric(f"Air scour flow ({ulbl('flow_m3h')})", fmt(bw_hyd['q_air_design_m3h'], 'flow_m3h', 0))
    bm3.metric("BW duration",                          f"{bw_total_min} min")
    bm4.metric("Plant waste / day", fmt(bw_seq["waste_vol_daily_m3"], "volume_m3_per_day", 0))
