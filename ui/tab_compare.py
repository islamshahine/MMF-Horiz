"""Design Comparison tab: Design A = sidebar; Design B = session compare_inputs_b; Part B adds results."""

import streamlit as st
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
            "Filters / stream", value=int(b.get("n_filters", 16)), min_value=1, step=1, key="b_n_filters"))
        b["streams"] = int(st.number_input(
            "Streams", value=int(b.get("streams", 1)), min_value=1, step=1, key="b_streams"))
        _ro = [0, 1, 2, 3, 4]
        _r = min(max(int(b.get("redundancy", 0)), 0), 4)
        b["redundancy"] = int(st.selectbox("Redundancy", _ro, index=_ro.index(_r), key="b_redundancy"))
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
    _lbl_a = st.text_input("Design A label", value="Design A (current)", key="compare_label_a")
    _lbl_b = st.text_input("Design B label", value="Design B (alternative)", key="compare_label_b")
