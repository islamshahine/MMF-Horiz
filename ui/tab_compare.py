"""Design Comparison tab: Design A = sidebar; Design B = session compare_inputs_b; run compute_all twice."""

import pandas as pd
import streamlit as st

from engine.comparison import compare_designs
from engine.compute import compute_all
from engine.financial_economics import calculate_incremental_economics
from engine.units import convert_inputs, display_value, unit_label
from ui.helpers import fmt, ulbl, dv


def render_tab_compare(inputs: dict, computed: dict) -> None:
    """Render the Design Comparison tab."""
    st.subheader("⚖️ Design Comparison")
    st.caption(
        "Compare two design alternatives side-by-side. "
        "Design A is always the current sidebar design. "
        "Design B is configured below."
    )
    st.markdown("### Design A — Current design")
    st.caption("Reflects current sidebar inputs.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Flow / filter", fmt(computed.get("q_per_filter", 0), "flow_m3h", 1))
    c2.metric("Nominal ID", fmt(inputs.get("nominal_id", 0), "length_m", 3))
    c3.metric("Filters", f"{inputs.get('n_filters', 0)} × {inputs.get('streams', 1)} streams")
    c4.metric("Assessment", computed.get("overall_risk", "—"))
    st.divider()
    st.markdown("### Design B — Alternative design")
    st.caption("Modify the parameters below. All other inputs are copied from Design A.")
    if "compare_inputs_b" not in st.session_state:
        st.session_state["compare_inputs_b"] = dict(inputs)
    if st.button("↺  Reset B to Design A", key="reset_b_btn"):
        st.session_state["compare_inputs_b"] = dict(inputs)
    b = st.session_state["compare_inputs_b"]
    bc1, bc2 = st.columns(2)
    with bc1:
        st.markdown("**Process**")
        b["n_filters"] = int(st.number_input(
            "Total physical number of filters / stream",
            value=int(b.get("n_filters", 16)),
            min_value=1,
            step=1,
            key="b_n_filters",
        ))
        b["streams"] = int(st.number_input(
            "Streams", value=int(b.get("streams", 1)), min_value=1, step=1, key="b_streams"))
        _ha = [0, 1, 2, 3, 4]
        _hi = min(max(int(b.get("hydraulic_assist", 0)), 0), 4)
        b["hydraulic_assist"] = int(st.selectbox(
            "Standby (physical / stream)",
            _ha,
            format_func=lambda k: (
                "0 — no spare" if k == 0 else f"{k} spare(s) — N+{k} bank"
            ),
            index=_ha.index(_hi),
            key="b_hydraulic_assist",
        ))
        _n_b_design = int(b["n_filters"]) - int(b["hydraulic_assist"])
        st.session_state["b_n_design_display"] = str(_n_b_design)
        st.text_input(
            "Calculated N filters / stream",
            disabled=True,
            key="b_n_design_display",
            help=(
                "Total physical number of filters / stream minus "
                "standby (physical / stream); design N for hydraulics."
            ),
        )
        _ro = [0, 1, 2, 3, 4]
        _r = min(max(int(b.get("redundancy", 0)), 0), 4)
        b["redundancy"] = int(st.selectbox(
            "Outage depth", _ro, index=_ro.index(_r), key="b_redundancy"))
        st.markdown("**Vessel geometry**")
        b["nominal_id"] = st.number_input(
            f"Nominal ID ({ulbl('length_m')})",
            value=float(dv(b.get("nominal_id", 5.5), "length_m")),
            min_value=0.5, step=0.1, key="b_nominal_id")
        b["total_length"] = st.number_input(
            f"Total length T/T ({ulbl('length_m')})",
            value=float(dv(b.get("total_length", 24.3), "length_m")),
            min_value=1.0, step=0.1, key="b_total_length")
        _eg = b.get("end_geometry", "Elliptic 2:1")
        b["end_geometry"] = st.selectbox(
            "End geometry", ["Elliptic 2:1", "Torispherical 10%"],
            index=0 if _eg == "Elliptic 2:1" else 1, key="b_end_geometry")
    with bc2:
        st.markdown("**Media**")
        b["nozzle_plate_h"] = st.number_input(
            f"Nozzle plate h ({ulbl('length_m')})",
            value=float(dv(b.get("nozzle_plate_h", 1.0), "length_m")),
            min_value=0.1, step=0.05, key="b_nozzle_plate_h")
        st.markdown("**Backwash**")
        b["bw_velocity"] = st.number_input(
            f"BW velocity ({ulbl('velocity_m_h')})",
            value=float(dv(b.get("bw_velocity", 30.0), "velocity_m_h")),
            min_value=1.0, step=5.0, key="b_bw_velocity")
        b["collector_h"] = st.number_input(
            f"Collector height ({ulbl('length_m')})",
            value=float(dv(b.get("collector_h", 4.2), "length_m")),
            min_value=0.5, step=0.1, key="b_collector_h")
        b["air_scour_rate"] = st.number_input(
            f"Air scour rate ({ulbl('velocity_m_h')})",
            value=float(dv(b.get("air_scour_rate", 55.0), "velocity_m_h")),
            min_value=1.0, step=5.0, key="b_air_scour_rate")
    st.session_state["compare_inputs_b"] = b
    lbl_a = st.text_input("Design A label", value="Design A (current)", key="compare_label_a")
    lbl_b = st.text_input("Design B label", value="Design B (alternative)", key="compare_label_b")

    st.divider()
    run_cmp = st.button("▶  Run comparison", use_container_width=True, key="run_compare_btn", type="primary")

    if run_cmp or st.session_state.get("compare_result"):
        if run_cmp:
            try:
                _system = st.session_state.get("unit_system", "metric")
                b_si = convert_inputs(dict(b), _system)
                with st.spinner("Computing Design B..."):
                    computed_b = compute_all(b_si)
                result = compare_designs(
                    computed_a=computed,
                    computed_b=computed_b,
                    label_a=lbl_a,
                    label_b=lbl_b,
                )
                st.session_state["compare_result"] = result
                st.session_state["compare_computed_b"] = computed_b
            except Exception as e:
                st.error(f"Comparison failed: {e}")
                st.session_state.pop("compare_result", None)
                st.session_state.pop("compare_computed_b", None)

        result = st.session_state.get("compare_result")
        if result:
            st.markdown(f"### Results: {result['label_a']} vs {result['label_b']}")
            w = result["overall_winner"]
            k1, k2, k3 = st.columns(3)
            k1.metric("Significant differences", result["n_significant"])
            k2.metric(f"Metrics favouring {result['label_a']}", result["n_favours_a"])
            k3.metric(f"Metrics favouring {result['label_b']}", result["n_favours_b"])
            st.info(result["summary"])

            st.markdown("#### Side-by-side metrics")
            st.caption(
                "🟡 Amber = significant difference (> threshold %). "
                "🟢 = favours that design."
            )
            system = st.session_state.get("unit_system", "metric")
            rows = []
            for m in result["metrics"]:
                qty = m["unit_quantity"]
                dec = m["decimals"]

                def cell(v):
                    if v is None:
                        return "—"
                    return fmt(v, qty, dec)

                val_a_str = cell(m["val_a"])
                val_b_str = cell(m["val_b"])
                pct = m["pct_diff"]
                pct_str = f"{pct:+.1f}%" if pct is not None else "—"
                fav = m["favours"]
                flag_a = " 🟢" if fav == "A" else ""
                flag_b = " 🟢" if fav == "B" else ""
                sig = "🟡" if m["is_significant"] else "  "
                rows.append({
                    "": sig,
                    "Metric": m["label"],
                    result["label_a"]: val_a_str + flag_a,
                    result["label_b"]: val_b_str + flag_b,
                    "Difference": pct_str,
                })

            df = pd.DataFrame(rows)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "": st.column_config.TextColumn(width="small"),
                    "Metric": st.column_config.TextColumn(width="medium"),
                    "Difference": st.column_config.TextColumn(width="small"),
                },
            )

            if w != "equal":
                win_name = result["label_a"] if w == "A" else result["label_b"]
                na, nb = result["n_favours_a"], result["n_favours_b"]
                st.success(
                    f"**{win_name}** performs better on more metrics "
                    f"({max(na, nb)} vs {min(na, nb)} metrics). "
                    "Review the table above for details."
                )
            else:
                st.info("Both designs perform similarly across all evaluated metrics.")

            st.markdown("#### Export")
            exp_rows = []
            for m in result["metrics"]:
                q = m["unit_quantity"]
                ulb = unit_label(q, system)

                def fv(v):
                    if v is None:
                        return ""
                    return round(display_value(v, q, system), m["decimals"])

                pdiff = m["pct_diff"]
                exp_rows.append({
                    "Metric": m["label"],
                    "Unit": ulb,
                    result["label_a"]: fv(m["val_a"]),
                    result["label_b"]: fv(m["val_b"]),
                    "Diff %": round(pdiff, 1) if pdiff is not None else "",
                    "Significant": m["is_significant"],
                    "Favours": m["favours"],
                })
            exp_df = pd.DataFrame(exp_rows)
            st.download_button(
                label="⬇️  Download comparison (.csv)",
                data=exp_df.to_csv(index=False),
                file_name="aquasight_comparison.csv",
                mime="text/csv",
                use_container_width=True,
            )

            _fin_a = computed.get("econ_financial") or {}
            _fin_b = st.session_state.get("compare_computed_b", {}).get("econ_financial") or {}
            if _fin_a and _fin_b:
                st.markdown("#### Incremental lifecycle economics (B − A)")
                _inc = calculate_incremental_economics(_fin_a, _fin_b)
                ic1, ic2, ic3 = st.columns(3)
                ic1.metric("Δ CAPEX (B−A)", f"USD {_inc['delta_capex_usd']:,.0f}")
                ic2.metric("Δ NPV", f"USD {_inc['delta_npv_usd']:,.0f}")
                ic3.metric("Δ Year-1 operating cash", f"USD {_inc['delta_first_year_operating_cash_usd']:,.0f}")
                st.caption(_inc.get("economic_summary", ""))
