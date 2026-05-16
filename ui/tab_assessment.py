"""ui/tab_assessment.py — Assessment tab for AQUASIGHT™ MMF."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from engine.sensitivity import OUTPUT_DEFS, run_sensitivity, tornado_narrative
from engine.thresholds import layer_ebct_floor_min, layer_lv_cap_m_h
from ui.helpers import dv, fmt, ulbl
from ui.scroll_markers import inject_anchor

_SENS_OUTPUT_QTY = {
    "lv": "velocity_m_h",
    "ebct": "time_min",
    "dp": "pressure_bar",
}


def _robustness_display_df(rob_rows: list) -> "pd.DataFrame":
    """Format compute ``rob_rows`` (SI ``lv_m_h``) for the current unit system."""
    import pandas as pd

    recs = []
    _lv_col = f"Filtration rate ({ulbl('velocity_m_h')})"
    for row in rob_rows or []:
        r = dict(row)
        lv_si = r.pop("lv_m_h", None)
        r.pop("Filtration rate", None)
        if lv_si is None:
            r[_lv_col] = "—"
        else:
            r[_lv_col] = fmt(float(lv_si), "velocity_m_h", 2)
        recs.append(r)
    cols = ["Scenario", _lv_col, "Hydraulic status", "EBCT status", "Overall"]
    if not recs:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame(recs)[cols]


def _sensitivity_output_labels() -> dict[str, str]:
    return {
        "lv": f"Peak LV ({ulbl('velocity_m_h')})",
        "ebct": f"Min EBCT ({ulbl('time_min')})",
        "capex": "Total CAPEX (M USD)",
        "dp": f"Dirty media ΔP ({ulbl('pressure_bar')})",
    }


def _fmt_sens_value(out_key: str, si_val: float) -> str:
    if out_key == "capex":
        return f"{si_val:.4g} M USD"
    qty = _SENS_OUTPUT_QTY.get(out_key)
    if qty:
        return fmt(si_val, qty, 4)
    return f"{si_val:.4g}"


def render_tab_assessment(inputs: dict, computed: dict):
    inject_anchor("mmf-anchor-main-assessment")
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

    design_pressure    = inputs["design_pressure"]
    design_temp        = inputs["design_temp"]
    total_flow         = inputs["total_flow"]
    streams            = inputs["streams"]
    n_filters          = inputs["n_filters"]
    redundancy         = inputs["redundancy"]
    hydraulic_assist   = int(inputs.get("hydraulic_assist", 0))
    corrosion          = inputs["corrosion"]
    velocity_threshold = float(inputs.get("velocity_threshold") or 12.0)

    st.subheader("Process assessment")

    _basis = computed.get("design_basis") or {}
    if _basis.get("assumptions_catalog") or _basis.get("traceability"):
        with st.expander("Design basis — key assumptions & traceability", expanded=False):
            st.caption(
                f"Schema **{_basis.get('schema_version', '—')}** · "
                f"Full export on **Report** tab."
            )
            for _a in (_basis.get("assumptions_catalog") or [])[:6]:
                st.markdown(f"- **{_a.get('id', '')}** — {_a.get('text', '')}")
            _tr = _basis.get("traceability") or []
            if _tr:
                st.markdown("**Traced outputs (sample)**")
                for _t in _tr[:8]:
                    _v = _t.get("value_si", _t.get("value", "—"))
                    st.markdown(
                        f"- **{_t.get('label', _t.get('output', ''))}:** {_v} {_t.get('unit', '')}"
                    )

    with st.expander("Process model scope — effluent, RTD, breakthrough", expanded=False):
        st.markdown(
            "This release focuses on **hydraulic envelope** (LV, EBCT), **scalar cake / solid loading** "
            "(M_max, α), and **mass-based** cartridge life. It does **not** predict effluent TSS, "
            "axial residence-time distribution (RTD), or breakthrough curves. "
            "For consent-linked solids or polish quality, cross-check with pilot data, vendor norms, "
            "or dedicated filtration models."
        )

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
    _rob_df = _robustness_display_df(rob_rows)

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
            _ebct_df = pd.DataFrame(
                all_ebct_issues,
                columns=["Scenario", "Layer", "Severity", "ebct_min"],
            )
            _ebct_df[f"EBCT ({ulbl('time_min')})"] = _ebct_df["ebct_min"].apply(
                lambda v: fmt(float(v), "time_min", 2)
            )
            st.dataframe(
                _ebct_df.drop(columns=["ebct_min"]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.success("No EBCT violations across any scenario.")

    st.divider()

    st.markdown("### Key design parameters")
    _thr_rows = []
    for L in inputs.get("layers") or []:
        if not isinstance(L, dict):
            continue
        if L.get("is_support"):
            _thr_rows.append({
                "Layer": L.get("Type", ""),
                f"Max LV ({ulbl('velocity_m_h')})": "— (support)",
                f"Min EBCT ({ulbl('time_min')})": "— (support)",
            })
        else:
            _thr_rows.append({
                "Layer": L.get("Type", ""),
                f"Max LV ({ulbl('velocity_m_h')})": fmt(
                    layer_lv_cap_m_h(L, inputs_fallback=inputs), "velocity_m_h", 2
                ),
                f"Min EBCT ({ulbl('time_min')})": fmt(
                    layer_ebct_floor_min(L, inputs_fallback=inputs), "time_min", 1
                ),
            })
    st.markdown("**Per-layer LV / EBCT setpoints**")
    st.dataframe(pd.DataFrame(_thr_rows), use_container_width=True, hide_index=True)

    kp3, kp4 = st.columns(2)

    st.table(pd.DataFrame([
        [f"Total flow ({ulbl('flow_m3h')})",
         fmt(total_flow, 'flow_m3h', 1)],
        ["Streams × installed filters",
         f"{streams} × {n_filters} = {streams*n_filters} vessels"],
        ["Standby filters (physical / stream)", str(hydraulic_assist)],
        ["Outage depth modelled", f"N-{redundancy}"],
        ["Hydraulic paths (design N, plant-wide)",
         f"{streams * max(1, n_filters - hydraulic_assist)} "
         f"({streams} stream(s) × {max(1, n_filters - hydraulic_assist)} path(s))"],
        [f"Nominal ID ({ulbl('length_m')})",
         fmt(nominal_id, 'length_m', 3)],
        [f"Filter area ({ulbl('area_m2')})",
         fmt(avg_area, 'area_m2', 4)],
        ["LV / EBCT setpoints", "Per media layer (see table above)"],
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

    with st.expander(
        "Filter-count study — hydraulics, ranking & apply to sidebar",
        expanded=False,
    ):
        from ui.design_optim_ui import render_design_optimisation_panel

        render_design_optimisation_panel(
            inputs,
            n_filters=int(n_filters),
            velocity_threshold=float(velocity_threshold),
            hydraulic_assist=int(hydraulic_assist),
            redundancy=int(redundancy),
        )

    st.divider()

    # ── Sensitivity / Tornado Analysis ───────────────────────────────────────
    st.markdown("### Sensitivity analysis (tornado chart)")
    st.caption(
        "One-at-a-time (OAT) analysis: each input is varied by its stated "
        "percentage while all others are held constant. Bars show deviation "
        "from the base-case value."
    )
    with st.expander("What each output metric means (tornado Y-axis context)", expanded=False):
        for _od in OUTPUT_DEFS:
            st.markdown(f"**{_od['label']}**  \n{_od.get('description', '—')}")
    _out_labels = _sensitivity_output_labels()
    _out_desc = {od["key"]: od.get("description", "") for od in OUTPUT_DEFS}
    _sens_col1, _sens_col2 = st.columns([2, 1])
    with _sens_col1:
        _sel_out = st.selectbox(
            "Output metric", list(_out_labels.keys()),
            format_func=lambda k: _out_labels[k], key="_sens_out_sel",
        )
    with _sens_col2:
        _run_btn = st.button("Run sensitivity", key="_sens_run",
                             use_container_width=True)
    if _desc_sel := _out_desc.get(_sel_out, ""):
        st.caption(_desc_sel)
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
        _lo_lbls = [
            f"{r['lo_label']}  ({_fmt_sens_value(_sel_out, float(r['lo']))})"
            for r in _rows
        ]
        _hi_lbls = [
            f"{r['hi_label']}  ({_fmt_sens_value(_sel_out, float(r['hi']))})"
            for r in _rows
        ]
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
        _base_val = float(_rows[0]["base"]) if _rows else 0.0
        _fig.update_layout(
            barmode="relative",
            title=dict(text=f"Sensitivity — {_out_labels[_sel_out]}  "
                            f"(base = {_fmt_sens_value(_sel_out, _base_val)})", x=0.01),
            xaxis_title=f"Deviation from base  [{_out_labels[_sel_out]}]",
            yaxis=dict(autorange="reversed"),
            height=max(300, 60 + 40 * len(_params)),
            margin=dict(l=20, r=20, t=50, b=40),
            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
            font_color="#e0e0e0", legend=dict(orientation="h", y=-0.15),
        )
        _fig.add_vline(x=0, line_width=1, line_color="#888")
        st.plotly_chart(_fig, use_container_width=True)
        st.markdown(
            tornado_narrative(_rows, output_label=_out_labels[_sel_out]),
        )
    elif not _sens_res:
        st.info("Press **Run sensitivity** to generate the tornado chart.")
