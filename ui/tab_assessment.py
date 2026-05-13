"""ui/tab_assessment.py — Assessment tab for AQUASIGHT™ MMF."""
import copy

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine.compute import compute_all
from engine.sensitivity import OUTPUT_DEFS, run_sensitivity
from ui.helpers import dv, fmt, ulbl


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
            _lv_df = pd.DataFrame(all_lv_issues,
                                  columns=["Scenario", "Layer", "Severity", "lv_si"])
            _lv_df[f"LV ({ulbl('velocity_m_h')})"] = _lv_df["lv_si"].apply(
                lambda v: round(dv(v, 'velocity_m_h'), 2))
            st.dataframe(_lv_df.drop(columns=["lv_si"]),
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
    kp1.metric(f"Velocity threshold ({ulbl('velocity_m_h')})", fmt(velocity_threshold, 'velocity_m_h', 1))
    kp2.metric("EBCT threshold",                               f"{ebct_threshold:.1f} min")
    kp3.metric(f"Design pressure ({ulbl('pressure_bar')})",    fmt(design_pressure, 'pressure_bar', 2))
    kp4.metric("Design temperature", fmt(design_temp, "temperature_c", 0))

    st.table(pd.DataFrame([
        [f"Total flow ({ulbl('flow_m3h')})",
         fmt(total_flow, 'flow_m3h', 1)],
        ["Streams × filters",
         f"{streams} × {n_filters} = {streams*n_filters} vessels"],
        ["Redundancy",          f"N-{redundancy}"],
        ["Active filters (N)",  f"{streams*n_filters - redundancy*streams}"],
        [f"Nominal ID ({ulbl('length_m')})",
         fmt(nominal_id, 'length_m', 3)],
        [f"Filter area ({ulbl('area_m2')})",
         fmt(avg_area, 'area_m2', 4)],
        [f"Velocity threshold ({ulbl('velocity_m_h')})",
         fmt(velocity_threshold, 'velocity_m_h', 1)],
        ["EBCT threshold",      f"{ebct_threshold:.1f} min"],
        ["Material",            material_name],
        [f"Design pressure ({ulbl('pressure_bar')})",
         fmt(design_pressure, 'pressure_bar', 2)],
        ["Design temperature",  fmt(design_temp, "temperature_c", 0)],
        [f"Corrosion allowance ({ulbl('length_mm')})",
         fmt(corrosion, 'length_mm', 1)],
        [f"Empty weight ({ulbl('mass_kg')})",
         fmt(w_total, 'mass_kg', 0)],
        [f"Operating weight ({ulbl('mass_kg')})",
         fmt(wt_oper['w_operating_kg'], 'mass_kg', 0)],
    ], columns=["Parameter", "Value"]))

    st.divider()

    # ── Design sweep: n_filters vs N-scenario LV (optimisation roadmap MVP) ─
    with st.expander("Design sweep — filters per stream vs N-scenario LV", expanded=False):
        st.caption(
            "Vary **n_filters** (per stream) over a band; each row runs full **compute_all** "
            "on a copy of inputs. **N** scenario LV is compared to **velocity_threshold**. "
            "Does not change sidebar values."
        )
        _nf_cur = int(n_filters)
        _red = int(redundancy)
        _nf_min = max(_red + 1, 1)
        _c1, _c2, _c3 = st.columns(3)
        with _c1:
            _nf_lo = st.number_input(
                "From n_filters",
                min_value=_nf_min,
                max_value=80,
                value=_nf_cur,
                key="_nf_sweep_lo",
            )
        with _c2:
            _nf_hi = st.number_input(
                "To n_filters",
                min_value=_nf_min,
                max_value=80,
                value=min(_nf_cur + 8, 80),
                key="_nf_sweep_hi",
            )
        with _c3:
            _run_sweep = st.button("Run sweep", key="_nf_sweep_run", use_container_width=True)
        if int(_nf_hi) < int(_nf_lo):
            st.error("**To** must be greater than or equal to **From**.")
        elif _run_sweep:
            _span = int(_nf_hi) - int(_nf_lo) + 1
            if _span > 48:
                st.warning(
                    f"This sweep runs **{_span}** full models — expect a short wait."
                )
            _lv_hdr = f"LV — N scenario ({ulbl('velocity_m_h')})"
            _thr_hdr = f"Threshold ({ulbl('velocity_m_h')})"
            _rows = []
            with st.spinner(f"Running {_span} scenarios…"):
                for _nf in range(int(_nf_lo), int(_nf_hi) + 1):
                    _inp = copy.deepcopy(inputs)
                    _inp["n_filters"] = _nf
                    try:
                        _comp = compute_all(_inp)
                        _fc = _comp.get("filt_cycles") or {}
                        _lv_si = float((_fc.get("N") or {}).get("lv_m_h", 0.0))
                        _ok = _lv_si <= float(velocity_threshold)
                        _rows.append({
                            "n (per stream)": _nf,
                            _lv_hdr: fmt(_lv_si, "velocity_m_h", 2),
                            _thr_hdr: fmt(float(velocity_threshold), "velocity_m_h", 2),
                            "Within envelope": "Yes" if _ok else "No",
                        })
                    except Exception as _ex:
                        _rows.append({
                            "n (per stream)": _nf,
                            _lv_hdr: "—",
                            _thr_hdr: fmt(float(velocity_threshold), "velocity_m_h", 2),
                            "Within envelope": f"Error: {_ex!s}"[:120],
                        })
            st.dataframe(
                pd.DataFrame(_rows),
                use_container_width=True,
                hide_index=True,
            )

    st.divider()

    # ── Sensitivity / Tornado Analysis ───────────────────────────────────────
    st.markdown("### Sensitivity analysis (tornado chart)")
    st.caption(
        "One-at-a-time (OAT) analysis: each input is varied by its stated "
        "percentage while all others are held constant. Bars show deviation "
        "from the base-case value."
    )
    _out_labels = {od["key"]: od["label"] for od in OUTPUT_DEFS}
    _sens_col1, _sens_col2 = st.columns([2, 1])
    with _sens_col1:
        _sel_out = st.selectbox(
            "Output metric", list(_out_labels.keys()),
            format_func=lambda k: _out_labels[k], key="_sens_out_sel",
        )
    with _sens_col2:
        _run_btn = st.button("Run sensitivity", key="_sens_run",
                             use_container_width=True)
    if _run_btn:
        with st.spinner("Running sensitivity analysis (18 simulations)…"):
            st.session_state["_sens_results"] = run_sensitivity(inputs)
        st.success("Done.")
    _sens_res = st.session_state.get("_sens_results")
    if _sens_res and _sel_out in _sens_res:
        _rows = _sens_res[_sel_out]
        _params  = [r["param"]          for r in _rows]
        _lo_dev  = [r["lo"]  - r["base"] for r in _rows]
        _hi_dev  = [r["hi"]  - r["base"] for r in _rows]
        _lo_lbls = [f"{r['lo_label']}  ({r['lo']:.3g})"  for r in _rows]
        _hi_lbls = [f"{r['hi_label']}  ({r['hi']:.3g})"  for r in _rows]
        _fig = go.Figure()
        _fig.add_trace(go.Bar(
            y=_params, x=_lo_dev, orientation="h", name="Low input",
            marker_color="#c0392b",
            customdata=_lo_lbls, hovertemplate="%{y}: %{customdata}<extra></extra>",
        ))
        _fig.add_trace(go.Bar(
            y=_params, x=_hi_dev, orientation="h", name="High input",
            marker_color="#27ae60",
            customdata=_hi_lbls, hovertemplate="%{y}: %{customdata}<extra></extra>",
        ))
        _base_val = _rows[0]["base"] if _rows else 0
        _fig.update_layout(
            barmode="relative",
            title=dict(text=f"Sensitivity — {_out_labels[_sel_out]}  "
                            f"(base = {_base_val:.4g})", x=0.01),
            xaxis_title=f"Deviation from base  [{_out_labels[_sel_out]}]",
            yaxis=dict(autorange="reversed"),
            height=max(300, 60 + 40 * len(_params)),
            margin=dict(l=20, r=20, t=50, b=40),
            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
            font_color="#e0e0e0", legend=dict(orientation="h", y=-0.15),
        )
        _fig.add_vline(x=0, line_width=1, line_color="#888")
        st.plotly_chart(_fig, use_container_width=True)
    elif not _sens_res:
        st.info("Press **Run sensitivity** to generate the tornado chart.")
