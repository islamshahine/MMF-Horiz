"""ui/tab_filtration.py — Filtration tab for AQUASIGHT™ MMF."""
import pandas as pd
import streamlit as st
from engine.process import filter_loading
from engine.backwash import pressure_drop
from engine.thresholds import layer_ebct_floor_min, layer_lv_cap_m_h
from ui.helpers import (
    fmt, ulbl, dv, show_alert, pressure_drop_layers_display_frames,
    cycle_matrix_temp_title, cycle_matrix_tss_row_title,     filtration_dp_curve_display_df,
    cycle_driver_decomposition_display_df,
    metric_explain_help,
    render_metric_explain_panel,
    ST_DATAFRAME_KW,
)
from ui.scroll_markers import inject_anchor
from ui.filtration_uncertainty_charts import (
    figure_cycle_duration_band,
    figure_dp_vs_loading_envelope,
    figure_scenario_cycle_bands,
)
from ui.monte_carlo_charts import figure_cycle_duration_histogram
from ui.spatial_loading_panel import render_spatial_loading_panel


def render_tab_filtration(inputs: dict, computed: dict):
    inject_anchor("mmf-anchor-main-filtration")
    load_data          = computed["load_data"]
    avg_area           = computed["avg_area"]
    base               = computed["base"]
    bw_dp              = computed["bw_dp"]
    filt_cycles        = computed["filt_cycles"]
    cycle_matrix       = computed["cycle_matrix"]
    feed_wp            = computed["feed_wp"]
    bw_wp              = computed["bw_wp"]
    rho_feed           = computed["rho_feed"]
    q_per_filter       = computed["q_per_filter"]
    cart_result        = computed["cart_result"]
    _tss_col_keys      = computed["tss_col_keys"]
    _tss_vals          = computed["tss_vals"]
    _temp_col_keys     = computed["temp_col_keys"]
    _lv_severity       = computed["lv_severity_fn"]
    _ebct_severity     = computed["ebct_severity_fn"]

    def _scenario_lv_status(q, base_rows, inp):
        worst_rank = 0
        rank_map = {"advisory": 1, "warning": 2, "critical": 3}
        for b in base_rows:
            if b.get("is_support"):
                continue
            ar = float(b.get("Area", 0.0))
            if ar <= 1e-12:
                continue
            vel = q / ar
            cap = layer_lv_cap_m_h(b, inputs_fallback=inp)
            sev = _lv_severity(vel, cap)
            worst_rank = max(worst_rank, rank_map.get(sev or "", 0))
        if worst_rank >= 3:
            return "Outside envelope"
        if worst_rank >= 2:
            return "Approaching limit"
        if worst_rank >= 1:
            return "Approaching limit"
        return "Within envelope"
    solid_loading      = inputs["solid_loading"]
    captured_solids_density = inputs["captured_solids_density"]
    feed_temp          = inputs["feed_temp"]
    alpha_specific     = inputs["alpha_specific"]
    dp_trigger_bar     = inputs["dp_trigger_bar"]
    layers             = inputs["layers"]
    total_flow         = inputs["total_flow"]
    streams            = inputs["streams"]
    n_filters          = inputs["n_filters"]
    redundancy         = inputs["redundancy"]
    hydraulic_assist   = int(inputs.get("hydraulic_assist", 0))
    temp_low           = inputs["temp_low"]
    temp_high          = inputs["temp_high"]
    tss_low            = inputs["tss_low"]
    tss_avg            = inputs["tss_avg"]
    tss_high           = inputs["tss_high"]

    _mal = float(computed.get("maldistribution_factor", 1.0) or 1.0)
    _sl_eff = float(computed.get("solid_loading_effective_kg_m2", solid_loading))
    _la_list = computed.get("layer_areas_m2") or []
    _layer_areas_kw = _la_list if len(_la_list) == len(layers) else None

    st.caption(
        "**Filtration** (main tab) — **results** from sidebar inputs: hydraulics, ΔP summaries, cycles, cartridge. "
        "Edit duty, water, **M_max / α / fouling** on **🧱 Media** sidebar; **per-layer ΔP tables** → **🧱 Media** tab §3."
    )
    st.caption(
        "**LV / EBCT** use **chordal slice areas** per layer. **Ergun + cake** share the same **filtration maldistribution factor** as **🧱 Media** §3; "
        "full layer tables and capture-weight narrative live there — this tab keeps scenario roll-ups."
    )
    render_metric_explain_panel(
        inputs,
        computed,
        [
            "q_per_filter",
            "solid_loading_effective",
            "maldistribution_factor",
            "dp_dirty",
            "cycle_expected_h",
            "cycle_uncertainty_spread",
            "operating_envelope_n",
        ],
    )

    with st.expander("🌊 Water properties — feed & backwash", expanded=False):
        w1, w2 = st.columns(2)
        with w1:
            st.markdown("**Feed water**")
            st.dataframe(pd.DataFrame([
                ["Temperature",   fmt(feed_wp['temp_c'], 'temperature_c', 1)],
                ["Salinity",      f"{feed_wp['salinity_ppt']:.2f} {ulbl('salinity_ppt')}"],
                ["Density",       fmt(feed_wp['density_kg_m3'], 'density_kg_m3', 3)],
                ["Viscosity",     fmt(feed_wp['viscosity_cp'], 'viscosity_cp', 4)],
                ["TDS (approx.)", f"{feed_wp['tds_mg_l']:,.0f} {ulbl('concentration_mg_l')}"],
            ], columns=["Property", "Value"]), **ST_DATAFRAME_KW)
        with w2:
            st.markdown("**Backwash water**")
            st.dataframe(pd.DataFrame([
                ["Temperature",   fmt(bw_wp['temp_c'], 'temperature_c', 1)],
                ["Salinity",      f"{bw_wp['salinity_ppt']:.2f} {ulbl('salinity_ppt')}"],
                ["Density",       fmt(bw_wp['density_kg_m3'], 'density_kg_m3', 3)],
                ["Viscosity",     fmt(bw_wp['viscosity_cp'], 'viscosity_cp', 4)],
                ["TDS (approx.)", f"{bw_wp['tds_mg_l']:,.0f} {ulbl('concentration_mg_l')}"],
            ], columns=["Property", "Value"]), **ST_DATAFRAME_KW)
        st.info(
            "Water properties feed directly into: terminal velocity (u_t), "
            "minimum fluidisation velocity (u_mf), Ergun pressure drop (ΔP), "
            "and nozzle velocity checks. "
            "BW water properties govern the expansion and collector check calculations."
        )

    st.markdown("#### Flow distribution by scenario")
    _flow_comp = []
    for x, a, q in load_data:
        lv = (q / avg_area) * _mal if avg_area > 0 else 0.0
        _lv_flag = _scenario_lv_status(q, base, inputs)
        _flow_comp.append({
            "Scenario":                              "N" if x == 0 else f"N-{x}",
            "Active filters":                        a,
            f"Flow / filter ({ulbl('flow_m3h')})":   round(dv(q, 'flow_m3h'), 2),
            f"LV ({ulbl('velocity_m_h')})":           round(dv(lv, 'velocity_m_h'), 2),
            "Hydraulic status":                      _lv_flag,
        })
    st.dataframe(pd.DataFrame(_flow_comp), **ST_DATAFRAME_KW)

    st.markdown("#### Operating envelope review by scenario")
    for x, a, q in load_data:
        label = "N (normal)" if x == 0 else f"N-{x}"
        with st.expander(f"Scenario {label} — {fmt(q, 'flow_m3h', 1)} / filter", expanded=(x == 0)):
            rows = []
            _sc_lv_issues, _sc_ebct_issues = [], []
            for b in base:
                vel  = q / b["Area"] if b["Area"] > 0 else 0
                ebct = (b["Vol"] / q) * 60 if q > 0 else 0
                if b.get("is_support"):
                    _lv_sev, _eb_sev = None, None
                else:
                    _lv_cap = layer_lv_cap_m_h(b, inputs_fallback=inputs)
                    _eb_floor = layer_ebct_floor_min(b, inputs_fallback=inputs)
                    _lv_sev = _lv_severity(vel, _lv_cap)
                    _eb_sev = _ebct_severity(ebct, _eb_floor)
                _lv_env = ("N/A" if b.get("is_support") else
                           "Within envelope" if not _lv_sev else
                           "Approaching limit" if _lv_sev == "advisory" else "Outside envelope")
                _eb_env = ("N/A" if b.get("is_support") else
                           "Within envelope" if not _eb_sev else
                           "Approaching limit" if _eb_sev == "advisory" else "Outside envelope")
                rows.append({
                    "Layer":                         b["Type"],
                    f"Area ({ulbl('area_m2')})":     round(dv(b["Area"], 'area_m2'), 3),
                    f"LV ({ulbl('velocity_m_h')})":  round(dv(vel, 'velocity_m_h'), 2),
                    "LV envelope":                   _lv_env,
                    f"EBCT ({ulbl('time_min')})":    round(ebct, 2),
                    "EBCT envelope":                 _eb_env,
                })
                if _lv_sev: _sc_lv_issues.append((b["Type"], _lv_sev, vel))
                if _eb_sev: _sc_ebct_issues.append((b["Type"], _eb_sev, ebct))
            st.dataframe(pd.DataFrame(rows), **ST_DATAFRAME_KW)
            if _sc_lv_issues:
                with st.expander(f"🟠 Hydraulic Loading — {len(_sc_lv_issues)} layer(s) outside envelope"):
                    for _layer, _sev, _vel in _sc_lv_issues:
                        show_alert(_sev, f"{_layer}: filtration velocity {fmt(_vel, 'velocity_m_h', 2)}",
                            "Elevated filtration velocity increases risk of media disturbance "
                            "and localised particulate breakthrough.")
            if _sc_ebct_issues:
                with st.expander(f"🟡 Contact Time — {len(_sc_ebct_issues)} layer(s) below design target"):
                    for _layer, _sev, _ebct in _sc_ebct_issues:
                        show_alert(_sev, f"{_layer}: contact time {fmt(_ebct, 'time_min', 2)}",
                            "Reduced contact time may compromise particulate capture "
                            "stability under peak hydraulic loading.")
            if not _sc_lv_issues and not _sc_ebct_issues:
                st.success("All layers operate within the recommended hydraulic envelope for this scenario.")

    with st.expander("Pressure drop — clean / moderate / dirty (all scenarios)", expanded=True):
        st.caption(
            f"Summary vs **🧱 Media** tab §3 (same α, M_max).  "
            f"α ({bw_dp['alpha_source']}) = {bw_dp['alpha_used_m_kg']/1e9:.1f} {ulbl('alpha_m_kg')}  |  "
            f"M_max (effective) = {fmt(_sl_eff, 'loading_kg_m2', 2)}"
        )
        _load_data_dp = filter_loading(
            total_flow, streams, n_filters, redundancy, hydraulic_assist,
        )
        _dp_summary = []
        for x, n_act, q in _load_data_dp:
            sc_label = "N" if x == 0 else f"N-{x}"
            sc_dp = pressure_drop(
                layers=layers, q_filter_m3h=q, avg_area_m2=avg_area,
                solid_loading_kg_m2=_sl_eff,
                captured_density_kg_m3=captured_solids_density,
                water_temp_c=feed_temp, rho_water=rho_feed,
                alpha_m_kg=alpha_specific, dp_trigger_bar=dp_trigger_bar,
                layer_areas_m2=_layer_areas_kw,
                maldistribution_factor=_mal,
                alpha_calibration_factor=float(
                    computed.get("alpha_calibration_factor", 1.0) or 1.0),
            )
            _dp_summary.append({
                "Scenario":                              sc_label,
                f"LV ({ulbl('velocity_m_h')})":          round(dv(sc_dp["u_m_h"], 'velocity_m_h'), 2),
                f"ΔP clean ({ulbl('pressure_bar')})":    round(dv(sc_dp["dp_clean_bar"], 'pressure_bar'), 5),
                f"ΔP clean ({ulbl('pressure_mwc')})":    round(dv(sc_dp["dp_clean_mwc"], 'pressure_mwc'), 3),
                f"ΔP mod. ({ulbl('pressure_bar')})":     round(dv(sc_dp["dp_moderate_bar"], 'pressure_bar'), 5),
                f"ΔP mod. ({ulbl('pressure_mwc')})":     round(dv(sc_dp["dp_moderate_mwc"], 'pressure_mwc'), 3),
                f"ΔP dirty ({ulbl('pressure_bar')})":    round(dv(sc_dp["dp_dirty_bar"], 'pressure_bar'), 5),
                f"ΔP dirty ({ulbl('pressure_mwc')})":    round(dv(sc_dp["dp_dirty_mwc"], 'pressure_mwc'), 3),
            })
        st.markdown("**Summary — all scenarios**")
        st.dataframe(pd.DataFrame(_dp_summary), **ST_DATAFRAME_KW)
        st.markdown("**Per-layer breakdown — N scenario**")
        _layers_full, _ = pressure_drop_layers_display_frames(bw_dp["layers"])
        st.dataframe(_layers_full, **ST_DATAFRAME_KW)
        p1, p2, p3 = st.columns(3)
        p1.metric(
            f"ΔP clean (N) ({ulbl('pressure_bar')})",
            fmt(bw_dp["dp_clean_bar"], "pressure_bar", 5),
            delta=fmt(bw_dp["dp_clean_mwc"], "pressure_mwc", 3),
            delta_color="off",
            help=metric_explain_help("dp_dirty", inputs, computed) or None,
        )
        p2.metric(
            f"ΔP moderate (N) ({ulbl('pressure_bar')})",
            fmt(bw_dp["dp_moderate_bar"], "pressure_bar", 5),
            delta=fmt(bw_dp["dp_moderate_mwc"], "pressure_mwc", 3),
            delta_color="off",
        )
        p3.metric(
            f"ΔP dirty → nozzle plate ({ulbl('pressure_bar')})",
            fmt(bw_dp["dp_dirty_bar"], "pressure_bar", 5),
            delta=fmt(bw_dp["dp_dirty_mwc"], "pressure_mwc", 3),
            delta_color="off",
            help=metric_explain_help("dp_dirty", inputs, computed) or None,
        )

    _np_plate = computed.get("collector_nozzle_plate") or {}
    _sp_filt = computed.get("spatial_distribution_filtration") or {}
    if _sp_filt.get("enabled") and _np_plate.get("active"):
        render_metric_explain_panel(
            inputs,
            computed,
            ["spatial_uniformity_filtration"],
            title="Nozzle plate uniformity — filtration service",
        )
        render_spatial_loading_panel(
            _sp_filt,
            _np_plate,
            chart_key="spatial_loading_heatmap_filtration",
            phase_label="filtration",
            expanded=False,
        )
    elif _np_plate.get("active") and not _sp_filt.get("enabled"):
        st.caption(
            _sp_filt.get("note", "Spatial filtration map unavailable — check nozzle layout.")
        )

    with st.expander("Filtration cycle matrix — TSS × temperature", expanded=True):
        if filt_cycles and cycle_matrix:
            first_cyc = next(iter(filt_cycles.values()))
            st.info(
                f"**Ruth cake model** · BW setpoint {fmt(dp_trigger_bar, 'pressure_bar', 2)} · "
                f"M_max {fmt(solid_loading, 'loading_kg_m2', 2)} · "
                f"α ({first_cyc['alpha_source']}) = {first_cyc['alpha_used_m_kg']/1e9:.1f} {ulbl('alpha_m_kg')} · "
                f"Temperature range {fmt(temp_low, 'temperature_c', 0)} — "
                f"{fmt(feed_temp, 'temperature_c', 0)} — {fmt(temp_high, 'temperature_c', 0)}"
            )
            _temp_si = {
                "temp_min": temp_low, "temp_design": feed_temp, "temp_max": temp_high,
            }
            _tss_si = {
                "tss_low": tss_low, "tss_avg": tss_avg, "tss_high": tss_high,
            }
            _temp_order = {"temp_min": 0, "temp_design": 1, "temp_max": 2}
            for sc_lbl, sc_temps in cycle_matrix.items():
                _lv = filt_cycles[sc_lbl]["lv_m_h"]
                st.markdown(f"**Scenario {sc_lbl} · LV = {fmt(_lv, 'velocity_m_h', 1)}**")
                mat_rows = []
                _by_sched = set()   # track which temp columns are M_max-limited
                for tss_key in _tss_col_keys:
                    tss_v = _tss_si[tss_key]
                    row = {"Feed TSS": cycle_matrix_tss_row_title(tss_key, tss_v)}
                    for tk in _temp_col_keys:
                        col_disp = cycle_matrix_temp_title(tk, _temp_si[tk])
                        cyc_t = sc_temps[tk]
                        tr = next((r for r in cyc_t["tss_results"] if r["TSS (mg/L)"] == tss_v), None)
                        _sched = "M_max" in cyc_t.get("note", "")
                        if _sched:
                            _by_sched.add(tk)
                        _suffix = " ★" if _sched else ""
                        row[col_disp] = (
                            f"{fmt(float(tr['Cycle duration (h)']), 'time_h', 1)}{_suffix}"
                            if tr else "—"
                        )
                    mat_rows.append(row)
                st.dataframe(pd.DataFrame(mat_rows).set_index("Feed TSS"), use_container_width=True)
                if _by_sched:
                    _sched_disp = ", ".join(
                        cycle_matrix_temp_title(k, _temp_si[k])
                        for k in sorted(_by_sched, key=lambda x: _temp_order.get(x, 99))
                    )
                    st.caption(
                        f"★ BW by solid loading schedule (M_max) — pressure trigger not reached at "
                        f"{_sched_disp}. Lower α or higher dp setpoint would make "
                        "cycle length temperature-sensitive in those columns."
                    )
            with st.expander("ΔP vs M curve — N scenario, design temperature", expanded=False):
                st.dataframe(
                    filtration_dp_curve_display_df(first_cyc["dp_curve"]),
                    **ST_DATAFRAME_KW,
                )
                _cu_charts = computed.get("cycle_uncertainty_charts") or {}
                _dp_env = _cu_charts.get("dp_vs_loading_envelope")
                if _dp_env and _dp_env.get("m_kg_m2"):
                    try:
                        _fig_dp = figure_dp_vs_loading_envelope(_dp_env)
                        if _fig_dp is not None:
                            st.plotly_chart(
                                _fig_dp,
                                use_container_width=True,
                                key="filtration_dp_vs_m_uncertainty",
                            )
                            st.caption(
                                "Shaded band: **optimistic–conservative** corner cases on α, TSS, "
                                "capture, and maldistribution (same method as cycle uncertainty)."
                            )
                    except ImportError:
                        pass
        else:
            st.info("No filtration cycle data available.")

    _cycle_unc = computed.get("cycle_uncertainty") or {}
    if _cycle_unc:
        with st.expander("Cycle duration uncertainty — optimistic / expected / conservative", expanded=False):
            st.caption(
                "Deterministic cycle band at **design TSS** (not Monte Carlo). "
                "**Corner-case envelope** — optimistic / expected / conservative with "
                "α calibration, feed TSS, capture efficiency, and **filtration maldistribution factor** varied together. "
                "**Driver decomposition** (N scenario) — same four factors perturbed **one at a time** "
                "and ranked by cycle swing (table and chart below)."
            )
            _unc_rows = []
            for _sc, _u in _cycle_unc.items():
                _unc_rows.append({
                    "Scenario": _sc,
                    f"Optimistic ({ulbl('time_h')})": fmt(_u["cycle_optimistic_h"], "time_h", 1),
                    f"Expected ({ulbl('time_h')})": fmt(_u["cycle_expected_h"], "time_h", 1),
                    f"Conservative ({ulbl('time_h')})": fmt(_u["cycle_conservative_h"], "time_h", 1),
                    "Spread %": f"{_u['spread_pct']:.1f}",
                    "Stability": _u["stability"],
                })
            st.dataframe(pd.DataFrame(_unc_rows), **ST_DATAFRAME_KW)
            _u_n = _cycle_unc.get("N") or {}
            if _u_n:
                st.info(_u_n.get("stability_note", ""))
                _dec = _u_n.get("driver_decomposition") or {}
                if _dec.get("summary"):
                    st.caption(_dec["summary"])
                for _line in _dec.get("narratives") or []:
                    st.markdown(_line)
                if _dec.get("drivers"):
                    st.dataframe(
                        cycle_driver_decomposition_display_df(_dec["drivers"]),
                        **ST_DATAFRAME_KW,
                    )
                try:
                    import plotly.graph_objects as go

                    _fig = figure_cycle_duration_band(
                        optimistic_h=float(_u_n["cycle_optimistic_h"]),
                        expected_h=float(_u_n["cycle_expected_h"]),
                        conservative_h=float(_u_n["cycle_conservative_h"]),
                        title=f"N scenario — cycle duration band ({ulbl('time_h')})",
                    )
                    st.plotly_chart(_fig, use_container_width=True, key="cycle_unc_band_bar")
                    _cu_charts = computed.get("cycle_uncertainty_charts") or {}
                    _sc_band = _cu_charts.get("scenario_cycle_band")
                    if _cu_charts.get("enabled") and _sc_band and len(_sc_band.get("scenarios") or []) > 1:
                        _fig_sc = figure_scenario_cycle_bands(_sc_band)
                        st.plotly_chart(
                            _fig_sc,
                            use_container_width=True,
                            key="cycle_unc_scenario_bands",
                        )
                    _plot = _dec.get("plot") or {}
                    _labels = _plot.get("driver_labels") or []
                    _d_opt = _plot.get("delta_optimistic_h") or []
                    _d_con = _plot.get("delta_conservative_h") or []
                    if _labels and (_d_opt or _d_con):
                        _fig2 = go.Figure()
                        _fig2.add_trace(
                            go.Bar(
                                name="Optimistic corner (alone)",
                                y=_labels,
                                x=[dv(x, "time_h") if x is not None else 0 for x in _d_opt],
                                orientation="h",
                                marker_color="#1a7a1a",
                            )
                        )
                        _fig2.add_trace(
                            go.Bar(
                                name="Conservative corner (alone)",
                                y=_labels,
                                x=[dv(x, "time_h") if x is not None else 0 for x in _d_con],
                                orientation="h",
                                marker_color="#cc5500",
                            )
                        )
                        _fig2.update_layout(
                            barmode="overlay",
                            title=f"Driver decomposition — Δ cycle vs expected ({ulbl('time_h')})",
                            xaxis_title=f"Δ vs expected ({ulbl('time_h')})",
                            height=max(280, 44 * len(_labels)),
                            margin=dict(l=160, t=48, b=40),
                        )
                        st.plotly_chart(
                            _fig2,
                            use_container_width=True,
                            key="cycle_unc_driver_tornado",
                        )
                except ImportError:
                    pass

    from ui.ui_mode import is_expert_mode

    if is_expert_mode():
        with st.expander("Monte Carlo lite — optional cycle sampling (N scenario)", expanded=False):
            from ui.monte_carlo_controls import render_monte_carlo_lite_controls

            render_monte_carlo_lite_controls()
            _mc = computed.get("monte_carlo_cycle") or {}
            if not st.session_state.get("mc_lite_enabled"):
                st.info("Enable the checkbox above, then **Apply** in the input column to run samples.")
            elif not _mc.get("enabled"):
                st.warning(
                    _mc.get("reason", "Sampling did not complete — check hydraulics and try **Apply** again.")
                )
            else:
                st.caption(_mc.get("note", ""))
                pct = _mc.get("percentiles_h") or {}
                c1, c2, c3, c4 = st.columns(4)
                c1.metric(f"P10 ({ulbl('time_h')})", fmt(pct.get("p10"), "time_h", 1))
                c2.metric(f"P50 ({ulbl('time_h')})", fmt(pct.get("p50"), "time_h", 1))
                c3.metric(f"P90 ({ulbl('time_h')})", fmt(pct.get("p90"), "time_h", 1))
                c4.metric("Samples", f"{_mc.get('n_samples_finite', 0)} / {_mc.get('n_samples_requested', 0)}")
                det = _mc.get("deterministic_envelope_h") or {}
                st.caption(
                    f"Deterministic envelope — optimistic {fmt(det.get('optimistic'), 'time_h', 1)} · "
                    f"expected {fmt(det.get('expected'), 'time_h', 1)} · "
                    f"conservative {fmt(det.get('conservative'), 'time_h', 1)}"
                )
                try:
                    _fig_mc = figure_cycle_duration_histogram(_mc)
                    if _fig_mc is not None:
                        st.plotly_chart(
                            _fig_mc,
                            use_container_width=True,
                            key="monte_carlo_cycle_hist",
                        )
                except ImportError:
                    st.info("Install **plotly** for the Monte Carlo histogram.")

    _op_env = computed.get("operating_envelope") or {}
    if _op_env.get("enabled"):
        with st.expander("Operating envelope — LV × EBCT feasibility map", expanded=False):
            st.caption(_op_env.get("note", ""))
            _pts = [p for p in (_op_env.get("scenario_points") or []) if p.get("lv_m_h") is not None]
            if _pts:
                _labels = [p["scenario"] for p in _pts]
                _idx = st.select_slider(
                    "Highlight redundancy scenario",
                    options=list(range(len(_pts))),
                    format_func=lambda i: _labels[i],
                    key="operating_envelope_scenario_idx",
                )
                _sel = _pts[_idx]
                c1, c2, c3 = st.columns(3)
                c1.metric(
                    f"LV — {_sel['scenario']} ({ulbl('velocity_m_h')})",
                    fmt(_sel["lv_m_h"], "velocity_m_h", 2),
                )
                c2.metric(
                    f"Min EBCT — {_sel['scenario']} ({ulbl('time_min')})",
                    fmt(_sel["ebct_min_min"], "time_min", 2),
                )
                c3.metric("Envelope class", str(_sel.get("region", "—")).title())
                try:
                    import plotly.graph_objects as go

                    _lv_ax = [dv(v, "velocity_m_h") for v in _op_env["lv_axis_m_h"]]
                    _eb_ax = [dv(v, "time_min") for v in _op_env["ebct_axis_min"]]
                    _z = _op_env.get("severity_rank_matrix") or []
                    _fig_env = go.Figure(
                        data=go.Heatmap(
                            x=_lv_ax,
                            y=_eb_ax,
                            z=_z,
                            zmin=0,
                            zmax=3,
                            colorscale=[
                                [0.0, "#1a7a1a"],
                                [0.24, "#1a7a1a"],
                                [0.25, "#b8860b"],
                                [0.49, "#b8860b"],
                                [0.50, "#cc5500"],
                                [0.74, "#cc5500"],
                                [0.75, "#cc2222"],
                                [1.0, "#cc2222"],
                            ],
                            colorbar=dict(
                                title="Class",
                                tickvals=[0, 1, 2, 3],
                                ticktext=["Stable", "Marginal", "Elevated", "Critical"],
                            ),
                            hovertemplate=(
                                f"LV %{{x:.2f}} {ulbl('velocity_m_h')}<br>"
                                f"EBCT %{{y:.2f}} {ulbl('time_min')}<br>"
                                "%{customdata}<extra></extra>"
                            ),
                            customdata=[
                                [_op_env["region_matrix"][j][i] for i in range(len(_lv_ax))]
                                for j in range(len(_eb_ax))
                            ],
                        )
                    )
                    _fig_env.add_trace(
                        go.Scatter(
                            x=[dv(p["lv_m_h"], "velocity_m_h") for p in _pts],
                            y=[dv(p["ebct_min_min"], "time_min") for p in _pts],
                            mode="markers+text",
                            text=[p["scenario"] for p in _pts],
                            textposition="top center",
                            marker=dict(
                                size=[14 if i == _idx else 9 for i in range(len(_pts))],
                                color=[
                                    "#ffffff" if i == _idx else "#94a3b8"
                                    for i in range(len(_pts))
                                ],
                                line=dict(width=2, color="#0f172a"),
                            ),
                            name="Scenarios",
                        )
                    )
                    _fig_env.update_layout(
                        title=f"Operating envelope ({ulbl('velocity_m_h')} vs {ulbl('time_min')})",
                        xaxis_title=ulbl("velocity_m_h"),
                        yaxis_title=f"Min layer EBCT ({ulbl('time_min')})",
                        height=420,
                        margin=dict(t=48, b=48),
                        showlegend=False,
                    )
                    st.plotly_chart(_fig_env, use_container_width=True, key="operating_envelope_heatmap")
                except ImportError:
                    st.info("Install **plotly** for the operating envelope heatmap.")
                _stab = sum(
                    1
                    for row in (_op_env.get("region_matrix") or [])
                    for c in row
                    if c == "stable"
                )
                _tot = sum(len(row) for row in (_op_env.get("region_matrix") or [])) or 1
                st.caption(
                    f"Reference caps: LV ≤ {fmt(_op_env.get('lv_cap_reference_m_h'), 'velocity_m_h', 2)} · "
                    f"EBCT ≥ {fmt(_op_env.get('ebct_floor_reference_min'), 'time_min', 2)} · "
                    f"Grid stable cells ≈ {100 * _stab / _tot:.0f}% (screening only)."
                )

    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(f"LV — N scenario ({ulbl('velocity_m_h')})", fmt((q_per_filter / avg_area) * _mal, 'velocity_m_h', 2))
    m2.metric(f"Flow / filter, N ({ulbl('flow_m3h')})",   fmt(q_per_filter, 'flow_m3h', 1))
    m3.metric("Total filters",                             f"{streams * n_filters}")
    m4.metric("LV / EBCT setpoints", "Per media layer")

    with st.expander("🔷 Cartridge (polishing) filter sizing", expanded=False):
        ca1, ca2, ca3, ca4 = st.columns(4)
        ca1.metric("Elements required", str(cart_result["n_elements"]))
        ca2.metric("Housings required", str(cart_result["n_housings"]),
                   delta=f"{cart_result['n_elem_per_housing']} elem./housing", delta_color="off")
        ca3.metric(f"Flow / element ({ulbl('flow_m3h')})",
                   fmt(cart_result['actual_flow_m3h_element'], 'flow_m3h', 3),
                   delta=fmt(cart_result["q_lpm_element"], "flow_l_min", 1),
                   delta_color="off")
        ca4.metric(
            f"Dirt hold / element ({ulbl('mass_kg')})",
            fmt(float(cart_result["dhc_g_element"]) / 1000.0, "mass_kg", 2),
            delta=f"{cart_result['element_ties']} TIE",
            delta_color="off",
        )
        st.dataframe(pd.DataFrame([
            [f"Design flow ({ulbl('flow_m3h')})", fmt(cart_result['design_flow_m3h'], 'flow_m3h', 1)],
            ["Element size",         cart_result["element_size"]],
            ["Rating",               f"{cart_result['rating_um']} µm absolute"],
            ["Elements required",    str(cart_result["n_elements"])],
            ["Housings required",    str(cart_result["n_housings"])],
            [f"Flow / element ({ulbl('flow_m3h')})", fmt(cart_result['actual_flow_m3h_element'], 'flow_m3h', 3)],
            ["ΔP clean (BOL)",       fmt(cart_result["dp_clean_bar"], "pressure_bar", 4)],
            ["ΔP EOL",               fmt(cart_result["dp_eol_bar"], "pressure_bar", 4)],
            [f"DHC / element ({ulbl('mass_kg')})", fmt(float(cart_result["dhc_g_element"]) / 1000.0, "mass_kg", 2)],
            ["DHC basis",            (
                "Vendor datasheet" if cart_result.get("dhc_basis") == "vendor_override"
                else "Model (g/TIE × rating)"
            )],
            ["Replacement interval", f"{cart_result['replacement_freq_days']:.0f} days"],
            ["Annual element cost",  f"USD {cart_result['annual_cost_usd']:,.0f}"],
        ], columns=["Parameter", "Value"]), **ST_DATAFRAME_KW)
