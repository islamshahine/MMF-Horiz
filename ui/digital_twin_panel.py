"""Digital twin lite — plant CSV upload and Apply patches (C4)."""
from __future__ import annotations

import streamlit as st

from engine.units import display_value
from ui.helpers import fmt, ulbl


def apply_twin_patches_to_session(patches: dict, unit_system: str) -> list[str]:
    """Write suggested SI patches to sidebar widget keys."""
    applied: list[str] = []
    if "alpha_calibration_factor" in patches:
        st.session_state["alpha_calibration_factor"] = float(patches["alpha_calibration_factor"])
        applied.append("alpha_calibration_factor")
    if "tss_avg" in patches:
        st.session_state["tss_avg"] = display_value(float(patches["tss_avg"]), "concentration_mg_l", unit_system)
        applied.append("tss_avg")
    return applied


def render_digital_twin_panel(inputs: dict, computed: dict) -> None:
    twin = computed.get("digital_twin_lite") or {}
    unit_sys = str(inputs.get("unit_system") or "metric")

    apply_msg = st.session_state.pop("_digital_twin_apply_msg", None)
    if apply_msg:
        st.success(apply_msg)

    with st.expander("Digital twin lite — plant telemetry → recalibrate α", expanded=False):
        st.caption(
            "Upload SCADA / DCS export. Need **cycle_hours_h** (preferred) and/or **dp_dirty_bar** "
            "per row. Optional: **lv_m_h**, **tss_mg_l**. Extra columns (e.g. timestamp) are ignored. "
            "Suggests α calibration factor vs the Ruth screening model. "
            "**Apply recalibration** updates sidebar widgets — then press **Apply** on the input column."
        )
        st.markdown("**Example CSV (copy header + add your rows):**")
        st.code(
            "cycle_hours_h,dp_dirty_bar,lv_m_h,tss_mg_l\n"
            "10.8,0.91,11.2,7.5\n"
            "11.2,0.94,11.0,8.1\n"
            "9.6,0.88,11.5,7.8",
            language=None,
        )
        up = st.file_uploader(
            "Plant telemetry CSV",
            type=["csv", "txt"],
            key="mmf_ops_telemetry_uploader",
        )
        if up is not None:
            st.session_state["mmf_ops_telemetry_text"] = up.getvalue().decode(
                "utf-8", errors="replace",
            )
        if st.button("Clear telemetry", key="mmf_ops_telemetry_clear"):
            st.session_state.pop("mmf_ops_telemetry_text", None)
            st.rerun()

        if not st.session_state.get("mmf_ops_telemetry_text"):
            st.info("Upload a CSV to compare plant cycles / ΔP to the current model.")
            return

        if not twin.get("enabled"):
            st.warning(twin.get("reason") or twin.get("summary", "Calibration unavailable."))
            for w in twin.get("parse_warnings") or []:
                st.caption(f"Parse: {w}")
            return

        st.caption(twin.get("disclaimer", ""))
        st.success(f"{twin.get('summary', '')} Confidence: **{twin.get('confidence', '—')}**.")

        obs = twin.get("observed") or {}
        mod = twin.get("model") or {}
        c1, c2, c3, c4 = st.columns(4)
        if obs.get("cycle_hours_median") is not None:
            c1.metric(
                f"Plant cycle median ({ulbl('time_h')})",
                fmt(obs["cycle_hours_median"], "time_h", 1),
            )
        if mod.get("cycle_expected_h") is not None:
            c2.metric(
                f"Model expected ({ulbl('time_h')})",
                fmt(mod["cycle_expected_h"], "time_h", 1),
            )
        if obs.get("dp_dirty_bar_mean") is not None:
            c3.metric(
                f"Plant ΔP mean ({ulbl('pressure_bar')})",
                fmt(obs["dp_dirty_bar_mean"], "pressure_bar", 3),
            )
        if mod.get("dp_dirty_bar") is not None:
            c4.metric(
                f"Model ΔP dirty ({ulbl('pressure_bar')})",
                fmt(mod["dp_dirty_bar"], "pressure_bar", 3),
            )

        for line in twin.get("rationale") or []:
            st.markdown(f"- {line}")

        patches = twin.get("suggested_patches") or {}
        if patches:
            st.markdown("**Suggested sidebar patches (SI engine values)**")
            st.json(patches)
            if st.button("Apply recalibration to sidebar", type="primary", key="digital_twin_apply"):
                applied = apply_twin_patches_to_session(patches, unit_sys)
                st.session_state["_digital_twin_apply_msg"] = (
                    f"Applied: {', '.join(applied)}. Press **Apply** in the input column to recompute."
                )
                st.rerun()
