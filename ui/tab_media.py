"""ui/tab_media.py — Media tab for AQUASIGHT™ MMF."""
import pandas as pd
import streamlit as st
from engine.media import get_layer_intelligence
from engine.process import filter_loading
from engine.backwash import pressure_drop
from ui.helpers import fmt, ulbl, dv


def render_tab_media(inputs: dict, computed: dict):
    geo_rows   = computed["geo_rows"]
    base       = computed["base"]
    bw_dp      = computed["bw_dp"]
    avg_area   = computed["avg_area"]
    rho_feed   = computed["rho_feed"]
    mu_feed    = computed["mu_feed"]

    solid_loading            = inputs["solid_loading"]
    captured_solids_density  = inputs["captured_solids_density"]
    feed_temp                = inputs["feed_temp"]
    alpha_specific           = inputs["alpha_specific"]
    dp_trigger_bar           = inputs["dp_trigger_bar"]
    total_flow               = inputs["total_flow"]
    streams                  = inputs["streams"]
    n_filters                = inputs["n_filters"]
    redundancy               = inputs["redundancy"]
    layers                   = inputs["layers"]

    st.subheader("Media design")

    with st.expander("1 · Geometric volumes", expanded=True):
        df_geo = pd.DataFrame(geo_rows, columns=[
            "Item", "Depth (m)", "Avg area (m²)",
            "V_cyl (m³)", "V_ends (m³)", "Total vol (m³)"])
        st.dataframe(df_geo.style.format({
            "Depth (m)":      "{:.3f}",
            "Avg area (m²)":  "{:.4f}",
            "V_cyl (m³)":     "{:.4f}",
            "V_ends (m³)":    "{:.4f}",
            "Total vol (m³)": "{:.4f}",
        }), use_container_width=True, hide_index=True)

    with st.expander("2 · Media properties", expanded=True):
        df_med = pd.DataFrame(base)[
            ["Type", "Depth", "Vol", "Area", "rho_p_eff", "epsilon0", "d10", "cu"]
        ].rename(columns={
            "Type":      "Media",
            "Depth":     "Depth (m)",
            "Vol":       "Vol (m³)",
            "Area":      "Avg area (m²)",
            "rho_p_eff": "ρ (kg/m³)",
            "epsilon0":  "ε₀",
            "d10":       "d10 (mm)",
            "cu":        "CU",
        })
        st.dataframe(df_med, use_container_width=True, hide_index=True)

    with st.expander("3 · Pressure drop — clean/moderate/dirty (all scenarios)", expanded=True):
        st.caption(
            f"Clean ΔP: Ergun equation on virgin bed.  "
            f"Moderate = 50% loaded · Dirty = 100% loaded — cake model (Ruth): "
            f"ΔP_cake = α × μ × LV × M.  "
            f"α ({bw_dp['alpha_source']}) = "
            f"{bw_dp['alpha_used_m_kg']/1e9:.1f} × 10⁹ m/kg  |  "
            f"M_max = {solid_loading:.2f} kg/m²  |  "
            f"Feed: ρ={rho_feed:.1f} kg/m³, μ={mu_feed*1000:.4f} cP"
        )
        _load_data_dp = filter_loading(total_flow, streams, n_filters, redundancy)
        _dp_summary = []
        for x, _n_act, q in _load_data_dp:
            sc_label = "N" if x == 0 else f"N-{x}"
            sc_dp = pressure_drop(
                layers=layers,
                q_filter_m3h=q,
                avg_area_m2=avg_area,
                solid_loading_kg_m2=solid_loading,
                captured_density_kg_m3=captured_solids_density,
                water_temp_c=feed_temp,
                rho_water=rho_feed,
                alpha_m_kg=alpha_specific,
                dp_trigger_bar=dp_trigger_bar,
            )
            _dp_summary.append({
                "Scenario":                              sc_label,
                f"LV ({ulbl('velocity_m_h')})":          round(dv(sc_dp["u_m_h"], 'velocity_m_h'), 2),
                f"ΔP clean ({ulbl('pressure_bar')})":    round(dv(sc_dp["dp_clean_bar"], 'pressure_bar'), 5),
                "ΔP clean (mWC)":                        sc_dp["dp_clean_mwc"],
                f"ΔP mod. ({ulbl('pressure_bar')})":     round(dv(sc_dp["dp_moderate_bar"], 'pressure_bar'), 5),
                f"ΔP dirty ({ulbl('pressure_bar')})":    round(dv(sc_dp["dp_dirty_bar"], 'pressure_bar'), 5),
                "ΔP dirty (mWC)":                        sc_dp["dp_dirty_mwc"],
            })
        st.markdown("**Summary — all scenarios**")
        st.dataframe(pd.DataFrame(_dp_summary),
                     use_container_width=True, hide_index=True)
        st.markdown("**Per-layer breakdown — N scenario**")
        st.dataframe(pd.DataFrame(bw_dp["layers"]),
                     use_container_width=True, hide_index=True)
        p1, p2, p3 = st.columns(3)
        p1.metric(f"ΔP clean (N) ({ulbl('pressure_bar')})",
                  fmt(bw_dp['dp_clean_bar'], 'pressure_bar', 5),
                  delta=f"{bw_dp['dp_clean_mwc']:.3f} mWC", delta_color="off")
        p2.metric(f"ΔP moderate (N) ({ulbl('pressure_bar')})",
                  fmt(bw_dp['dp_moderate_bar'], 'pressure_bar', 5),
                  delta=f"{bw_dp['dp_moderate_mwc']:.3f} mWC", delta_color="off")
        p3.metric(f"ΔP dirty ({ulbl('pressure_bar')})",
                  fmt(bw_dp['dp_dirty_bar'], 'pressure_bar', 5),
                  delta=f"{bw_dp['dp_dirty_mwc']:.3f} mWC", delta_color="off")

    with st.expander("4 · Media inventory", expanded=True):
        total_vessels = streams * n_filters
        inv_rows = []
        total_mass = 0
        for b in base:
            mf = b["Vol"] * b["rho_p_eff"]
            mt = mf * total_vessels
            total_mass += mt
            inv_rows.append({
                "Media":            b["Type"],
                "d10/CU":           f"{b['d10']}/{b['cu']}",
                f"Vol/filter ({ulbl('volume_m3')})":  round(dv(b["Vol"], 'volume_m3'), 4),
                f"Mass/filter ({ulbl('mass_kg')})":   round(dv(mf, 'mass_kg')),
                f"Total mass ({ulbl('mass_kg')})":    round(dv(mt, 'mass_kg')),
            })
        st.dataframe(pd.DataFrame(inv_rows),
                     use_container_width=True, hide_index=True)
        i1, i2, i3 = st.columns(3)
        i1.metric("Total filters", total_vessels)
        i2.metric(f"Total media ({ulbl('mass_kg')})", fmt(total_mass, 'mass_kg', 0))
        i3.metric(f"Per filter ({ulbl('mass_kg')})",
                  fmt(total_mass / total_vessels, 'mass_kg', 0)
                  if total_vessels else "—")

    with st.expander("5 · Clogging analysis — N scenario", expanded=True):
        st.caption(
            f"Captured solids density: **{captured_solids_density:.0f} kg/m³**  |  "
            f"Total solid loading: **{solid_loading:.2f} kg/m²**"
        )
        clog_cols = [
            "Media", "Support", "Capture (%)",
            "Solid load (kg/m²)", "Solid vol (m³/m²)",
            "ΔεF", "Clogging (%)", "ε clean",
            "Cake ΔP mod (bar)", "Cake ΔP dirty (bar)",
        ]
        clog_df = pd.DataFrame(bw_dp["layers"])[clog_cols]
        st.dataframe(clog_df, use_container_width=True, hide_index=True)
        st.caption(
            "Support layers (e.g., Gravel) retain no solids. "
            "Cake ΔP = α × μ × LV × M, distributed by capture fraction. "
            "ΔεF shown for reference only — cake model, not voidage reduction, "
            "drives moderate/dirty ΔP."
        )

    with st.expander("6 · Media Engineering Intelligence", expanded=True):
        _intel, _arr_warns = get_layer_intelligence(layers)

        st.markdown("**Bed arrangement validation**")
        if _arr_warns:
            for _w in _arr_warns:
                (st.warning if _w["level"] == "warning" else st.info)(_w["message"])
        else:
            st.success("Density stratification correct — bed will restratify after BW. ✓")

        st.divider()
        st.markdown("**Per-layer process intelligence**")
        for _row in _intel:
            _lbl = f"Layer {_row['layer']} — {_row['media']}"
            _c1, _c2, _c3 = st.columns(3)
            _c1.markdown(f"**{_lbl}**")
            _c2.caption(f"BW expansion: **{_row['bw_tendency']}**")
            _c3.caption(f"Density class: **{_row['density_class']}**")
            st.caption(f"Function: {_row['function']}")
            st.caption(f"Process role: {_row['process_role']}")
            for _note in _row["notes"]:
                st.info(_note)
            st.markdown("---")
