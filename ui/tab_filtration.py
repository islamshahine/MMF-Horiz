"""ui/tab_filtration.py — Filtration tab for AQUASIGHT™ MMF."""
import pandas as pd
import streamlit as st
from engine.process import filter_loading
from engine.backwash import pressure_drop
from ui.helpers import show_alert


def render_tab_filtration(inputs: dict, computed: dict):
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
    _tss_labels        = computed["tss_labels"]
    _tss_vals          = computed["tss_vals"]
    _temp_labels       = computed["temp_labels"]
    _lv_severity       = computed["lv_severity_fn"]
    _ebct_severity     = computed["ebct_severity_fn"]

    velocity_threshold = inputs["velocity_threshold"]
    ebct_threshold     = inputs["ebct_threshold"]
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
    temp_low           = inputs["temp_low"]
    temp_high          = inputs["temp_high"]

    st.caption("Hydraulic loading, contact times, pressure drop and post-treatment across all redundancy scenarios.")

    with st.expander("🌊 Water properties — feed & backwash", expanded=False):
        w1, w2 = st.columns(2)
        with w1:
            st.markdown("**Feed water**")
            st.table(pd.DataFrame([
                ["Temperature",   f"{feed_wp['temp_c']:.1f} °C"],
                ["Salinity",      f"{feed_wp['salinity_ppt']:.2f} ppt"],
                ["Density",       f"{feed_wp['density_kg_m3']:.3f} kg/m³"],
                ["Viscosity",     f"{feed_wp['viscosity_cp']:.4f} cP"],
                ["TDS (approx.)", f"{feed_wp['tds_mg_l']:,.0f} mg/L"],
            ], columns=["Property", "Value"]))
        with w2:
            st.markdown("**Backwash water**")
            st.table(pd.DataFrame([
                ["Temperature",   f"{bw_wp['temp_c']:.1f} °C"],
                ["Salinity",      f"{bw_wp['salinity_ppt']:.2f} ppt"],
                ["Density",       f"{bw_wp['density_kg_m3']:.3f} kg/m³"],
                ["Viscosity",     f"{bw_wp['viscosity_cp']:.4f} cP"],
                ["TDS (approx.)", f"{bw_wp['tds_mg_l']:,.0f} mg/L"],
            ], columns=["Property", "Value"]))
        st.info(
            "Water properties feed directly into: terminal velocity (u_t), "
            "minimum fluidisation velocity (u_mf), Ergun pressure drop (ΔP), "
            "and nozzle velocity checks. "
            "BW water properties govern the expansion and collector check calculations."
        )

    st.markdown("#### Flow distribution by scenario")
    _flow_comp = []
    for x, a, q in load_data:
        lv = q / avg_area if avg_area > 0 else 0
        _lv_flag = ("Within envelope" if lv <= velocity_threshold
                    else "Approaching limit" if lv <= velocity_threshold * 1.05
                    else "Outside envelope")
        _flow_comp.append({
            "Scenario":             "N" if x == 0 else f"N-{x}",
            "Active filters":       a,
            "Flow / filter (m³/h)": round(q, 2),
            "LV (m/h)":             round(lv, 2),
            "Hydraulic status":     _lv_flag,
        })
    st.dataframe(pd.DataFrame(_flow_comp), use_container_width=True, hide_index=True)

    st.markdown("#### Operating envelope review by scenario")
    for x, a, q in load_data:
        label = "N (normal)" if x == 0 else f"N-{x}"
        with st.expander(f"Scenario {label} — {q:.1f} m³/h / filter", expanded=(x == 0)):
            rows = []
            _sc_lv_issues, _sc_ebct_issues = [], []
            for b in base:
                vel  = q / b["Area"] if b["Area"] > 0 else 0
                ebct = (b["Vol"] / q) * 60 if q > 0 else 0
                if b.get("is_support"):
                    _lv_sev, _eb_sev = None, None
                else:
                    _lv_sev = _lv_severity(vel, velocity_threshold)
                    _eb_sev = _ebct_severity(ebct, ebct_threshold)
                _lv_env = ("N/A" if b.get("is_support") else
                           "Within envelope" if not _lv_sev else
                           "Approaching limit" if _lv_sev == "advisory" else "Outside envelope")
                _eb_env = ("N/A" if b.get("is_support") else
                           "Within envelope" if not _eb_sev else
                           "Approaching limit" if _eb_sev == "advisory" else "Outside envelope")
                rows.append({
                    "Layer":         b["Type"],
                    "Area (m²)":     round(b["Area"], 3),
                    "LV (m/h)":      round(vel, 2),
                    "LV envelope":   _lv_env,
                    "EBCT (min)":    round(ebct, 2),
                    "EBCT envelope": _eb_env,
                })
                if _lv_sev: _sc_lv_issues.append((b["Type"], _lv_sev, vel))
                if _eb_sev: _sc_ebct_issues.append((b["Type"], _eb_sev, ebct))
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            if _sc_lv_issues:
                with st.expander(f"🟠 Hydraulic Loading — {len(_sc_lv_issues)} layer(s) outside envelope"):
                    for _layer, _sev, _vel in _sc_lv_issues:
                        show_alert(_sev, f"{_layer}: filtration velocity {_vel:.2f} m/h",
                            "Elevated filtration velocity increases risk of media disturbance "
                            "and localised particulate breakthrough.")
            if _sc_ebct_issues:
                with st.expander(f"🟡 Contact Time — {len(_sc_ebct_issues)} layer(s) below design target"):
                    for _layer, _sev, _ebct in _sc_ebct_issues:
                        show_alert(_sev, f"{_layer}: contact time {_ebct:.2f} min",
                            "Reduced contact time may compromise particulate capture "
                            "stability under peak hydraulic loading.")
            if not _sc_lv_issues and not _sc_ebct_issues:
                st.success("All layers operate within the recommended hydraulic envelope for this scenario.")

    with st.expander("Pressure drop — clean / moderate / dirty (all scenarios)", expanded=True):
        st.caption(
            f"Clean ΔP: Ergun equation on virgin bed.  "
            f"Moderate = 50 % loaded · Dirty = 100 % loaded — cake model (Ruth).  "
            f"α ({bw_dp['alpha_source']}) = {bw_dp['alpha_used_m_kg']/1e9:.1f} × 10⁹ m/kg  |  "
            f"M_max = {solid_loading:.2f} kg/m²"
        )
        _load_data_dp = filter_loading(total_flow, streams, n_filters, redundancy)
        _dp_summary = []
        for x, n_act, q in _load_data_dp:
            sc_label = "N" if x == 0 else f"N-{x}"
            sc_dp = pressure_drop(
                layers=layers, q_filter_m3h=q, avg_area_m2=avg_area,
                solid_loading_kg_m2=solid_loading,
                captured_density_kg_m3=captured_solids_density,
                water_temp_c=feed_temp, rho_water=rho_feed,
                alpha_m_kg=alpha_specific, dp_trigger_bar=dp_trigger_bar,
            )
            _dp_summary.append({
                "Scenario":          sc_label,
                "LV (m/h)":          sc_dp["u_m_h"],
                "ΔP clean (bar)":    sc_dp["dp_clean_bar"],
                "ΔP clean (mWC)":    sc_dp["dp_clean_mwc"],
                "ΔP moderate (bar)": sc_dp["dp_moderate_bar"],
                "ΔP dirty (bar)":    sc_dp["dp_dirty_bar"],
                "ΔP dirty (mWC)":    sc_dp["dp_dirty_mwc"],
            })
        st.markdown("**Summary — all scenarios**")
        st.dataframe(pd.DataFrame(_dp_summary), use_container_width=True, hide_index=True)
        st.markdown("**Per-layer breakdown — N scenario**")
        st.dataframe(pd.DataFrame(bw_dp["layers"]), use_container_width=True, hide_index=True)
        p1, p2, p3 = st.columns(3)
        p1.metric("ΔP clean (N)",    f"{bw_dp['dp_clean_bar']:.5f} bar",
                  delta=f"{bw_dp['dp_clean_mwc']:.3f} mWC", delta_color="off")
        p2.metric("ΔP moderate (N)", f"{bw_dp['dp_moderate_bar']:.5f} bar",
                  delta=f"{bw_dp['dp_moderate_mwc']:.3f} mWC", delta_color="off")
        p3.metric("ΔP dirty → nozzle plate ΔP", f"{bw_dp['dp_dirty_bar']:.5f} bar",
                  delta=f"{bw_dp['dp_dirty_mwc']:.3f} mWC", delta_color="off")

    with st.expander("Filtration cycle matrix — TSS × temperature", expanded=True):
        if filt_cycles and cycle_matrix:
            first_cyc = next(iter(filt_cycles.values()))
            st.info(
                f"**Ruth cake model** · BW setpoint {dp_trigger_bar:.2f} bar · "
                f"M_max {solid_loading:.2f} kg/m² · "
                f"α ({first_cyc['alpha_source']}) = {first_cyc['alpha_used_m_kg']/1e9:.1f} × 10⁹ m/kg · "
                f"Temperature range {temp_low:.0f} – {feed_temp:.0f} – {temp_high:.0f} °C"
            )
            for sc_lbl, sc_temps in cycle_matrix.items():
                _lv = filt_cycles[sc_lbl]["lv_m_h"]
                st.markdown(f"**Scenario {sc_lbl} · LV = {_lv:.1f} m/h**")
                mat_rows = []
                _by_sched = set()   # track which temp columns are M_max-limited
                for tss_lbl, tss_v in zip(_tss_labels, _tss_vals):
                    row = {"Feed TSS": tss_lbl}
                    for t_lbl in _temp_labels:
                        cyc_t = sc_temps[t_lbl]
                        tr = next((r for r in cyc_t["tss_results"] if r["TSS (mg/L)"] == tss_v), None)
                        _sched = "M_max" in cyc_t.get("note", "")
                        if _sched:
                            _by_sched.add(t_lbl)
                        _suffix = " ★" if _sched else ""
                        row[t_lbl] = f"{tr['Cycle duration (h)']:.1f} h{_suffix}" if tr else "—"
                    mat_rows.append(row)
                st.dataframe(pd.DataFrame(mat_rows).set_index("Feed TSS"), use_container_width=True)
                if _by_sched:
                    st.caption(
                        f"★ BW by solid loading schedule (M_max) — pressure trigger not reached at "
                        f"{', '.join(sorted(_by_sched))}. Lower α or higher dp setpoint would make "
                        "cycle length temperature-sensitive in those columns."
                    )
            with st.expander("ΔP vs M curve — N scenario, design temperature", expanded=False):
                st.dataframe(pd.DataFrame(first_cyc["dp_curve"]), use_container_width=True, hide_index=True)
        else:
            st.info("No filtration cycle data available.")

    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("LV — N scenario",        f"{q_per_filter/avg_area:.2f} m/h")
    m2.metric("Flow / filter (N)",       f"{q_per_filter:.1f} m³/h")
    m3.metric("Total filters",           f"{streams * n_filters}")
    m4.metric("Recommended LV envelope", f"≤ {velocity_threshold:.1f} m/h")

    with st.expander("🔷 Cartridge (polishing) filter sizing", expanded=False):
        ca1, ca2, ca3, ca4 = st.columns(4)
        ca1.metric("Elements required", str(cart_result["n_elements"]))
        ca2.metric("Housings required", str(cart_result["n_housings"]),
                   delta=f"{cart_result['n_elem_per_housing']} elem./housing", delta_color="off")
        ca3.metric("Flow / element", f"{cart_result['actual_flow_m3h_element']:.3f} m³/h",
                   delta=f"{cart_result['q_lpm_element']:.1f} lpm", delta_color="off")
        ca4.metric("Dirt hold / element", f"{cart_result['dhc_g_element']:.0f} g",
                   delta=f"{cart_result['element_ties']} TIE", delta_color="off")
        st.table(pd.DataFrame([
            ["Design flow",          f"{cart_result['design_flow_m3h']:,.1f} m³/h"],
            ["Element size",         cart_result["element_size"]],
            ["Rating",               f"{cart_result['rating_um']} µm absolute"],
            ["Elements required",    str(cart_result["n_elements"])],
            ["Housings required",    str(cart_result["n_housings"])],
            ["Flow / element",       f"{cart_result['actual_flow_m3h_element']:.3f} m³/h"],
            ["ΔP clean (BOL)",       f"{cart_result['dp_clean_bar']*1000:.1f} mbar"],
            ["ΔP EOL",               f"{cart_result['dp_eol_bar']:.2f} bar"],
            ["DHC / element",        f"{cart_result['dhc_g_element']:.0f} g"],
            ["Replacement interval", f"{cart_result['replacement_freq_days']:.0f} days"],
            ["Annual element cost",  f"USD {cart_result['annual_cost_usd']:,.0f}"],
        ], columns=["Parameter", "Value"]))
