"""UI — import external CFD CSV and compare to 1D model (C2 lite)."""
from __future__ import annotations

import streamlit as st

from ui.helpers import fmt, ulbl


def render_cfd_import_panel(computed: dict, *, key_prefix: str = "cfd_import") -> None:
    """Upload + show ``computed['cfd_import_comparison']`` (built in app.py)."""
    _ch = computed.get("collector_hyd") or {}
    if not _ch.get("orifice_network"):
        return

    with st.expander(
        "External CFD results — import & compare (C2 lite)",
        expanded=False,
    ):
        st.caption(
            "Upload a CSV from OpenFOAM / Fluent / STAR-CCM+ with **lateral_index**, "
            "**hole_index**, and **velocity_m_s** (or **flow_m3h**). "
            "Export the template from *Optional — export for external CFD* above, run CFD externally, "
            "then fill in solved velocities and re-upload. **Not** an in-app CFD solve."
        )
        _up = st.file_uploader(
            "CFD results CSV",
            type=["csv", "txt"],
            key=f"{key_prefix}_uploader",
        )
        if _up is not None:
            st.session_state["mmf_cfd_import_text"] = _up.getvalue().decode("utf-8", errors="replace")
        if st.button("Clear imported CFD", key=f"{key_prefix}_clear"):
            st.session_state.pop("mmf_cfd_import_text", None)
            st.rerun()

        _cmp = computed.get("cfd_import_comparison") or {}
        if not st.session_state.get("mmf_cfd_import_text"):
            st.info("No file loaded — upload a CSV to compare against the 1D orifice table.")
            return
        if not _cmp.get("enabled"):
            st.warning(_cmp.get("reason") or _cmp.get("parse_warnings", ["Comparison failed"])[0])
            for w in _cmp.get("parse_warnings") or []:
                st.caption(f"Parse: {w}")
            return

        st.caption(_cmp.get("disclaimer", ""))
        st.success(_cmp.get("summary", ""))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Matched holes", str(_cmp.get("n_matched", 0)))
        c2.metric(
            "Mean |ΔV| %",
            f"{_cmp.get('mean_abs_delta_velocity_pct', 0):.1f}"
            if _cmp.get("mean_abs_delta_velocity_pct") is not None
            else "—",
        )
        c3.metric(
            "Max |ΔV| %",
            f"{_cmp.get('max_abs_delta_velocity_pct', 0):.1f}"
            if _cmp.get("max_abs_delta_velocity_pct") is not None
            else "—",
        )
        c4.metric("Unmatched CFD rows", str(_cmp.get("n_unmatched_cfd", 0)))

        import pandas as pd

        rows = _cmp.get("rows") or []
        if rows:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)
            try:
                import plotly.graph_objects as go

                v_m = [r["model_velocity_m_s"] for r in rows if r.get("model_velocity_m_s")]
                v_c = [r["cfd_velocity_m_s"] for r in rows if r.get("cfd_velocity_m_s")]
                if v_m and v_c and len(v_m) == len(v_c):
                    fig = go.Figure()
                    fig.add_trace(
                        go.Scatter(
                            x=v_m,
                            y=v_c,
                            mode="markers",
                            name="Holes",
                        )
                    )
                    mx = max(max(v_m), max(v_c)) * 1.05
                    fig.add_trace(
                        go.Scatter(
                            x=[0, mx],
                            y=[0, mx],
                            mode="lines",
                            line=dict(dash="dash", color="#888"),
                            name="1:1",
                        )
                    )
                    fig.update_layout(
                        title=f"CFD vs 1D velocity ({ulbl('velocity_m_s')})",
                        xaxis_title=f"1D model ({ulbl('velocity_m_s')})",
                        yaxis_title=f"CFD ({ulbl('velocity_m_s')})",
                        height=360,
                    )
                    st.plotly_chart(
                        fig, use_container_width=True, key=f"{key_prefix}_scatter",
                    )
            except ImportError:
                pass
