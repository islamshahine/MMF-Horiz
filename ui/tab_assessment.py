"""ui/tab_assessment.py — Assessment tab for AQUASIGHT™ MMF."""
import pandas as pd
import streamlit as st


def render_tab_assessment(inputs: dict, computed: dict):
    overall_risk    = computed["overall_risk"]
    risk_color      = computed["risk_color"]
    risk_border     = computed["risk_border"]
    risk_icon       = computed["risk_icon"]
    drivers         = computed["drivers"]
    impacts         = computed["impacts"]
    recommendations = computed["recommendations"]
    n_criticals     = computed["n_criticals"]
    n_warnings      = computed["n_warnings"]
    n_advisories    = computed["n_advisories"]
    rob_rows        = computed["rob_rows"]
    all_lv_issues   = computed["all_lv_issues"]
    all_ebct_issues = computed["all_ebct_issues"]
    nominal_id      = computed["nominal_id"]
    avg_area        = computed["avg_area"]
    material_name   = computed["material_name"]
    w_total         = computed["w_total"]
    wt_oper         = computed["wt_oper"]

    velocity_threshold = inputs["velocity_threshold"]
    ebct_threshold     = inputs["ebct_threshold"]
    design_pressure    = inputs["design_pressure"]
    design_temp        = inputs["design_temp"]
    total_flow         = inputs["total_flow"]
    streams            = inputs["streams"]
    n_filters          = inputs["n_filters"]
    redundancy         = inputs["redundancy"]
    corrosion          = inputs["corrosion"]

    st.subheader("Process assessment")

    st.markdown(
        f"""<div style="
            background:{risk_color}; border:2px solid {risk_border};
            border-radius:8px; padding:18px 24px; margin-bottom:16px;">
        <span style="font-size:1.6rem; font-weight:700;">
            {risk_icon} Overall assessment: {overall_risk}
        </span>
        </div>""",
        unsafe_allow_html=True,
    )

    _col_drv, _col_imp = st.columns([1, 1])
    with _col_drv:
        st.markdown("**Key drivers**")
        for d in drivers:
            st.markdown(f"- {d}")
    with _col_imp:
        st.markdown("**Operational impacts**")
        for i in impacts[overall_risk]:
            st.markdown(f"- {i}")

    st.info(recommendations[overall_risk])

    ac1, ac2, ac3 = st.columns(3)
    ac1.metric("Critical violations", n_criticals,  delta_color="off")
    ac2.metric("Warning violations",  n_warnings,   delta_color="off")
    ac3.metric("Advisory notices",    n_advisories, delta_color="off")

    st.divider()

    st.markdown("### Design Robustness Index")
    st.caption(
        "Per-scenario hydraulic status across the full redundancy range. "
        "Stable = all parameters within envelope. "
        "Marginal = one advisory. Sensitive = one warning. Critical = critical violation."
    )
    _rob_df = pd.DataFrame(rob_rows)

    def _color_overall(val):
        colors = {
            "Stable":    "background-color:#0a3a0a; color:#7fff7f",
            "Marginal":  "background-color:#2a2000; color:#ffd700",
            "Sensitive": "background-color:#2a1200; color:#ff8c00",
            "Critical":  "background-color:#3a0000; color:#ff4444",
        }
        return colors.get(val, "")

    st.dataframe(
        _rob_df.style.map(_color_overall, subset=["Overall"]),
        use_container_width=True, hide_index=True,
    )

    st.divider()

    with st.expander("Filtration velocity violations",
                     expanded=bool(all_lv_issues)):
        if all_lv_issues:
            st.dataframe(
                pd.DataFrame(all_lv_issues,
                             columns=["Scenario", "Layer", "Severity", "LV (m/h)"]),
                use_container_width=True, hide_index=True)
        else:
            st.success("No filtration velocity violations across any scenario.")

    with st.expander("EBCT violations", expanded=bool(all_ebct_issues)):
        if all_ebct_issues:
            st.dataframe(
                pd.DataFrame(all_ebct_issues,
                             columns=["Scenario", "Layer", "Severity", "EBCT (min)"]),
                use_container_width=True, hide_index=True)
        else:
            st.success("No EBCT violations across any scenario.")

    st.divider()

    st.markdown("### Key design parameters")
    kp1, kp2, kp3, kp4 = st.columns(4)
    kp1.metric("Velocity threshold", f"{velocity_threshold:.1f} m/h")
    kp2.metric("EBCT threshold",     f"{ebct_threshold:.1f} min")
    kp3.metric("Design pressure",    f"{design_pressure:.2f} bar")
    kp4.metric("Design temperature", f"{design_temp:.0f} °C")

    st.table(pd.DataFrame([
        ["Total flow",
         f"{total_flow:,.1f} m³/h"],
        ["Streams × filters",
         f"{streams} × {n_filters} = {streams*n_filters} vessels"],
        ["Redundancy",
         f"N-{redundancy}"],
        ["Active filters (N)",
         f"{streams*n_filters - redundancy*streams}"],
        ["Nominal ID",
         f"{nominal_id:.3f} m"],
        ["Filter area (avg)",
         f"{avg_area:.4f} m²"],
        ["Velocity threshold",
         f"{velocity_threshold:.1f} m/h"],
        ["EBCT threshold",
         f"{ebct_threshold:.1f} min"],
        ["Material",
         material_name],
        ["Design pressure",
         f"{design_pressure:.2f} barg"],
        ["Design temperature",
         f"{design_temp:.0f} °C"],
        ["Corrosion allowance",
         f"{corrosion:.1f} mm"],
        ["Empty weight",
         f"{w_total/1000:.3f} t"],
        ["Operating weight",
         f"{wt_oper['w_operating_t']:.3f} t"],
    ], columns=["Parameter", "Value"]))
