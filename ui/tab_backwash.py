"""ui/tab_backwash.py — Backwash tab for AQUASIGHT™ MMF."""
import pandas as pd
import streamlit as st
from engine.backwash import bed_expansion as _bed_exp
from ui.helpers import (
    fmt,
    ulbl,
    dv,
    show_alert,
    localize_engine_message,
    collector_hyd_profile_display_df,
    orifice_network_display_df,
    cycle_matrix_temp_title,
    cycle_matrix_tss_row_title,
    backwash_sequence_steps_display_df,
    bw_timeline_stagger_label,
    fmt_si_range,
)
from ui.collector_hyd_schematic import (
    build_collector_elevation_figure,
    build_collector_underdrain_figure,
)
from ui.scroll_markers import inject_anchor


def render_tab_backwash(inputs: dict, computed: dict):
    inject_anchor("mmf-anchor-main-backwash")
    bw_col       = computed["bw_col"]
    bw_hyd       = computed["bw_hyd"]
    bw_seq       = computed["bw_seq"]
    air_scour_solve = computed.get("air_scour_solve")
    bw_timeline  = computed.get("bw_timeline") or {}
    filt_cycles  = computed["filt_cycles"]
    feasibility_matrix = computed["feasibility_matrix"]
    _load_data_cyc     = computed["load_data"]
    _tss_col_keys = computed["tss_col_keys"]
    _tss_vals     = computed["tss_vals"]
    _temp_col_keys = computed["temp_col_keys"]
    rho_bw       = computed["rho_bw"]
    mu_bw        = computed["mu_bw"]
    m_sol_low    = computed["m_sol_low"]
    m_sol_avg    = computed["m_sol_avg"]
    m_sol_high   = computed["m_sol_high"]
    w_tss_low    = computed["w_tss_low"]
    w_tss_avg    = computed["w_tss_avg"]
    w_tss_high   = computed["w_tss_high"]
    m_daily_low  = computed["m_daily_low"]
    m_daily_avg  = computed["m_daily_avg"]
    m_daily_high = computed["m_daily_high"]

    st.caption(
        "**Backwash** tab — **Plant backwash** (sections 1–5): bed expansion, duties, sequence, scheduling, timeline. "
        "**Collector design (1D)** (section 6): internal header/lateral model, studies, schematics. "
        "Inputs: **🔄 BW** sidebar (duty vs collector vs optional studies). "
        "**BW pump / blower detail:** **Pumps & power** tab."
    )

    layers             = inputs["layers"]
    freeboard_mm       = inputs["freeboard_mm"]
    air_scour_rate     = inputs["air_scour_rate"]
    airwater_step_water_m_h = float(inputs.get("airwater_step_water_m_h", 12.5))
    bw_temp            = inputs["bw_temp"]
    bw_s_drain         = inputs["bw_s_drain"]
    bw_s_air           = inputs["bw_s_air"]
    bw_s_airw          = inputs["bw_s_airw"]
    bw_s_hw            = inputs["bw_s_hw"]
    bw_s_settle        = inputs["bw_s_settle"]
    bw_s_fill          = inputs["bw_s_fill"]
    bw_total_min       = inputs["bw_total_min"]
    streams             = inputs["streams"]
    n_filters             = inputs["n_filters"]
    hydraulic_assist_bw = int(inputs.get("hydraulic_assist", 0))
    tss_low            = inputs["tss_low"]
    tss_avg            = inputs["tss_avg"]
    tss_high           = inputs["tss_high"]
    temp_low           = inputs["temp_low"]
    feed_temp          = inputs["feed_temp"]
    temp_high          = inputs["temp_high"]

    st.caption(
        "Read **top-down**: plant BW first (sections 1–5), then **Collector design (1D)** if you use the underdrain model."
    )

    with st.expander("1 · Plant backwash — bed, expansion & freeboard", expanded=True):
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
            localize_engine_message(
                f"**Max safe BW velocity: {fmt(bw_col['max_safe_bw_m_h'], 'velocity_m_h', 1)}** "
                f"(maintains ≥ {fmt(freeboard_mm, 'length_mm', 0)} freeboard below collector).  "
                f"Proposed BW: **{fmt(bw_col['proposed_bw_m_h'], 'velocity_m_h', 1)}**."
            )
        )
        st.caption(
            "Internal **header / lateral / perforation** results are in **section 6 · Collector design (1D)** below."
        )
        exp_rows = []
        _bw_integrity_alerts = []

        for L in bw_col["per_layer"]:
            if L.get("is_support"):
                _status = "Support layer — hydraulic bed lift not required"
            elif L.get("elutriation_risk"):
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
                "Media": L["media_type"],
                f"d10 ({ulbl('length_mm')})": round(dv(float(L["d10_mm"]), "length_mm"), 2),
                f"u_mf ({ulbl('velocity_m_h')})": round(dv(L["u_mf_m_h"], "velocity_m_h"), 2),
                f"u_t ({ulbl('velocity_m_h')})": round(dv(L["u_t_m_h"], "velocity_m_h"), 2),
                "ε₀": L["epsilon0"], "ε_f": L["eps_f"],
                f"Settled ({ulbl('length_m')})": round(dv(L["depth_settled_m"], "length_m"), 3),
                f"Expanded ({ulbl('length_m')})": round(dv(L["depth_expanded_m"], "length_m"), 3),
                "Expansion (%)": L["expansion_pct"], "Status": _status,
            })
        st.dataframe(pd.DataFrame(exp_rows), use_container_width=True, hide_index=True)
        _u_air = float(bw_hyd.get("air_scour_rate_m_h", air_scour_rate))
        _u_combined = airwater_step_water_m_h + _u_air
        exp_combined = _bed_exp(
            layers=layers,
            bw_velocity_m_h=_u_combined,
            water_temp_c=bw_temp,
            rho_water=rho_bw,
        )
        st.markdown(
            f"**Air + water combined phase (step ③ surrogate)** — "
            f"water **{fmt(airwater_step_water_m_h, 'velocity_m_h', 1)}** + air **{fmt(_u_air, 'velocity_m_h', 1)}** "
            f"→ **{fmt(_u_combined, 'velocity_m_h', 1)}** equivalent superficial:"
        )
        comb_rows = [{
            "Media": L["media_type"],
            f"u_mf ({ulbl('velocity_m_h')})": round(dv(L["u_mf_m_h"], "velocity_m_h"), 2),
            "Fluidised": "Yes ✅" if L["fluidised"] else "No",
            "ε_f": L["eps_f"],
            f"Settled ({ulbl('length_m')})": round(dv(L["depth_settled_m"], "length_m"), 3),
            f"Expanded ({ulbl('length_m')})": round(dv(L["depth_expanded_m"], "length_m"), 3),
            "Expansion (%)": L["expansion_pct"],
            "Note": (
                "Support layer — lift not required"
                if L.get("is_support")
                else (L["warning"] if L["warning"] else "OK")),
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
        bh3.metric(f"Air scour flow ({ulbl('air_flow_nm3h')})", fmt(bw_hyd["q_air_nm3h"], "air_flow_nm3h", 0))
        bh4.metric(f"Blower est. ({ulbl('power_kw')})",       fmt(bw_hyd['p_blower_est_kw'], 'power_kw', 1))
        if air_scour_solve is not None:
            _nm = air_scour_solve.get("nm3_m2_h")
            _nm_txt = fmt(_nm, "air_flux_nm3_m2h", 2) if isinstance(_nm, (int, float)) else "—"
            _ew = air_scour_solve.get("expansion_water_only_pct", "—")
            _dair = air_scour_solve.get("expansion_increment_from_air_pct", "—")
            _mot_auto = air_scour_solve.get("p_blower_motor_kw")
            _mot_s = (
                f" Thermo blower motor **{fmt(float(_mot_auto), 'power_kw', 1)}** "
                f"(minimum air rate for this target at current ΔP/η)."
                if isinstance(_mot_auto, (int, float)) and float(_mot_auto) >= 0
                else ""
            )
            st.success(
                f"**Auto-sized air scour** — target **{air_scour_solve['target_expansion_pct']:.1f} %** net expansion "
                f"at **{fmt(float(air_scour_solve.get('low_rate_water_m_h', 0)), 'velocity_m_h', 1)}** water + air.  "
                f"Air equivalent **{fmt(float(bw_hyd.get('air_scour_rate_m_h', 0)), 'velocity_m_h', 2)}** "
                f"({ulbl('velocity_m_h')})  (~**{_nm_txt}** @ 0 °C, 1 atm).  "
                f"R–Z split: water-only **{_ew} %** · increment from air **{_dair} %** · total **{air_scour_solve['expansion_at_velocity_pct']:.1f} %**."
                f"{_mot_s}"
                + ("" if air_scour_solve.get("ok") else "  ⚠️ Target not reached within solver scan limit.")
            )
            if air_scour_solve.get("blower_kw_note"):
                st.caption(air_scour_solve["blower_kw_note"])
            st.caption(air_scour_solve.get("note", ""))
        st.table(pd.DataFrame([
            ["Governing BW flow",
             f"{fmt(bw_hyd['q_bw_m3h'], 'flow_m3h', 1)} ({bw_hyd['bw_governs']})"],
            ["BW design capacity (×1.10)", fmt(bw_hyd['q_bw_design_m3h'], 'flow_m3h', 1)],
            ["Air design capacity (×1.10)", fmt(bw_hyd["q_air_design_nm3h"], "air_flow_nm3h", 1)],
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

    with st.expander("5 · Filter duty timeline (multi-day schematic)", expanded=False):
        _sm = bw_timeline.get("stagger_model", "—")
        _ktr = bw_timeline.get("bw_trains")
        _ktr_s = str(_ktr) if _ktr is not None else "—"
        _sd = bw_timeline.get("sim_demand")
        _sd_s = f"{_sd:.2f}" if isinstance(_sd, (int, float)) else "—"
        _hdays = int(bw_timeline.get("horizon_days") or max(1, round(float(bw_timeline.get("horizon_h", 24)) / 24)))
        st.caption(
            f"**Horizon:** {_hdays} day(s) · **Stagger:** {bw_timeline_stagger_label(_sm)} · "
            f"**BW trains required** (rated N, design temperature, average TSS): **{_ktr_s}** · "
            f"**Concurrent demand index:** **{_sd_s}**.  "
            "Green = operating; red = full backwash sequence. "
            "**Feasibility-train** mode spaces starts by **Δt_bw ÷ BW trains** (matches section 4). "
            "**Optimized trains** adjusts start times to reduce peak overlap — *scheduling aid only*, not plant DCS logic. "
            "**Uniform** is a smooth legacy comparison."
        )
        _opt = bw_timeline.get("optimizer") or {}
        if _sm == "optimized_trains" and _opt:
            o1, o2, o3 = st.columns(3)
            o1.metric(
                "Peak concurrent BW (optimized)",
                str(_opt.get("peak_optimized", "—")),
            )
            o2.metric(
                "Peak (feasibility spacing)",
                str(_opt.get("peak_feasibility_spacing", "—")),
            )
            o3.metric(
                "Peak reduction",
                str(_opt.get("improvement_filters", 0)),
                help="Filters fewer at peak vs feasibility-train spacing on this horizon.",
            )
        _hge = bw_timeline.get("hours_operating_ge_design_n_h")
        _heq = bw_timeline.get("hours_operating_eq_design_n_h")
        _hgt = bw_timeline.get("hours_operating_gt_design_n_h")
        _hn1 = bw_timeline.get("hours_operating_eq_n_minus_1_h")
        _hlt = bw_timeline.get("hours_operating_below_n_minus_1_h")
        _ndes = bw_timeline.get("n_design_online_total")
        _nphys = bw_timeline.get("n_physical_timeline")
        _horz = float(bw_timeline.get("horizon_h", 24.0))
        if isinstance(_hge, (int, float)) and _ndes is not None:
            _n1 = float(_hn1) if isinstance(_hn1, (int, float)) else 0.0
            _lt = float(_hlt) if isinstance(_hlt, (int, float)) else 0.0
            _eq = float(_heq) if isinstance(_heq, (int, float)) else float(_hge)
            _gt = float(_hgt) if isinstance(_hgt, (int, float)) else 0.0
            _nper = max(1, n_filters - hydraulic_assist_bw)
            _phys_txt = (
                f"{_nphys} physical" if isinstance(_nphys, int) else f"{streams}×{n_filters} physical"
            )
            st.info(
                f"**Plant-wide duty ({_phys_txt} on chart, {_hdays} d / {_horz:.0f} h window):** "
                f"**At N** — exactly **{_ndes}** units not in BW (rated set): **{_eq:.2f}** h · "
                f"**At N−1** — exactly **{_ndes - 1}** not in BW: **{_n1:.2f}** h · "
                f"**Below N−1**: **{_lt:.2f}** h.  "
                + (
                    f"**N+1 margin** (>{_ndes} online, spare filtering): **{_gt:.2f}** h · "
                    if hydraulic_assist_bw > 0
                    else ""
                )
                + f"*(≥ N total = **{float(_hge):.2f}** h = at N + margin.)*  "
                f"Design **N** = **{_nper}** / stream × **{streams}** → **{_ndes}** plant-wide.  "
                "Overlapping backwashes increase N−1 / below-N−1 time."
            )
        _tl = bw_timeline
        _frows = _tl.get("filters") or []
        if not _frows:
            st.info("No filter rows for timeline (check filter count).")
        else:
            try:
                import plotly.graph_objects as go
            except ImportError:
                st.warning("Plotly is not installed — cannot render the duty chart.")
                _frows = []
            else:
                fig = go.Figure()
                colors = {"operate": "#27ae60", "bw": "#c0392b"}
                legend_seen: set[str] = set()
                for row in _frows:
                    fid = int(row["filter_index"])
                    y = f"Filter {fid}"
                    for s in row["segments"]:
                        stt = str(s["state"])
                        t0 = float(s["t0"])
                        t1 = float(s["t1"])
                        dur = t1 - t0
                        if dur <= 1e-9:
                            continue
                        leg = "Backwash" if stt == "bw" else "Operate / online"
                        show = leg not in legend_seen
                        legend_seen.add(leg)
                        fig.add_trace(
                            go.Bar(
                                orientation="h",
                                y=[y],
                                x=[dur],
                                base=t0,
                                name=leg,
                                marker_color=colors.get(stt, "#7f8c8d"),
                                legendgroup=leg,
                                showlegend=show,
                                customdata=[[t1]],
                                hovertemplate=(
                                    "%{y}<br>%{base:.2f}–%{customdata[0]:.2f} h<br>"
                                    + leg + "<extra></extra>"
                                ),
                            )
                        )
                _hor = float(_tl.get("horizon_h", 24.0))
                fig.update_layout(
                    barmode="overlay",
                    height=max(360, min(920, 26 * len(_frows))),
                    margin=dict(l=72, r=24, t=48, b=48),
                    xaxis_title="Time (h)",
                    title=f"Filter duty — {_hdays} d horizon",
                    template="plotly_white",
                )
                fig.update_xaxes(range=[0.0, _hor])
                st.plotly_chart(fig, use_container_width=True, key="bw_timeline_gantt")
                _pk = _tl.get("peak_concurrent_bw", 0)
                st.metric(
                    "Peak filters in BW (this stagger model)",
                    str(int(_pk)) if _pk is not None else "—",
                )
                _cap_n = _tl.get("hours_operating_eq_design_n_h")
                _cap_n1 = _tl.get("hours_operating_eq_n_minus_1_h")
                _duty_line = ""
                if isinstance(_cap_n, (int, float)) and isinstance(_cap_n1, (int, float)):
                    _duty_line = (
                        f" **Duty (plant-wide):** ≈ **{float(_cap_n):.1f}** h at **N** · "
                        f"≈ **{float(_cap_n1):.1f}** h at **N−1** (not in BW count vs design N)."
                    )
                st.caption(
                    f"Filtration cycle (design TSS) ≈ **{_tl.get('t_cycle_h', '—')}** h · "
                    f"BW duration **{_tl.get('bw_duration_h', '—')}** h · "
                    f"repeat period **{_tl.get('period_h', '—')}** h.{_duty_line}  {_tl.get('note', '')}"
                )

    with st.expander("6 · Collector design (1D underdrain)", expanded=False):
        st.caption(
            "Internal **header + lateral + perforation** model. "
            "**Vessel §4 nozzles** (Backwash inlet/outlet on the shell) are screened separately below. "
            "Inputs: sidebar **🔄 BW → Collector / underdrain** and **Optional — collector studies**."
        )
        from ui.collector_design_panel import render_collector_design_panel
        render_collector_design_panel(computed, inputs)

    st.divider()
    bm1, bm2, bm3, bm4 = st.columns(4)
    bm1.metric(f"BW flow, design ({ulbl('flow_m3h')})", fmt(bw_hyd['q_bw_design_m3h'], 'flow_m3h', 0))
    bm2.metric(f"Air scour flow ({ulbl('air_flow_nm3h')})", fmt(bw_hyd["q_air_design_nm3h"], "air_flow_nm3h", 0))
    bm3.metric("BW duration",                          f"{bw_total_min} min")
    bm4.metric("Plant waste / day", fmt(bw_seq["waste_vol_daily_m3"], "volume_m3_per_day", 0))
