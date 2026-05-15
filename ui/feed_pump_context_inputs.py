"""Feed-path hydraulic losses and pump/motor efficiencies for **Pumps & power**.

Values merge into the sidebar ``out`` dict (see ``merge_feed_hydraulics_into_out``) because the
sidebar column runs before the main tabs each Streamlit rerun.
"""
from __future__ import annotations

import copy

import streamlit as st

from engine.units import display_value, unit_label


# (inputs dict key, session_state widget key, default SI value, quantity for display_value)
_FEED_HYDR: tuple[tuple[str, str, float, str], ...] = (
    ("np_slot_dp", "np_slot", 0.02, "pressure_bar"),
    ("p_residual", "p_res", 2.50, "pressure_bar"),
    ("dp_inlet_pipe", "dp_in", 0.30, "pressure_bar"),
    ("dp_dist", "dp_dist", 0.02, "pressure_bar"),
    ("dp_outlet_pipe", "dp_out", 0.20, "pressure_bar"),
    ("static_head", "stat_h", 0.0, "pressure_mwc"),
)

_ETAS: tuple[tuple[str, str, float], ...] = (
    ("pump_eta", "pump_e", 0.75),
    ("bw_pump_eta", "bwp_e", 0.72),
)


def motor_eta_from_iec_class(iec: str | None) -> float:
    """Nominal motor efficiency used for all electrical conversions (feed, BW, blower)."""
    return 0.955 if (iec or "IE3") == "IE3" else 0.965


def _resolve_motor_iec_class(out: dict) -> str:
    """Prefer Pumps-tab widget; else persisted ``motor_iec_class`` / legacy ``motor_eta`` in ``out``."""
    raw = st.session_state.get("pp_feed_iec")
    if raw in ("IE3", "IE4"):
        return str(raw)
    mc = out.get("motor_iec_class")
    if mc in ("IE3", "IE4"):
        return str(mc)
    mt = out.get("motor_eta")
    if isinstance(mt, (int, float)) and float(mt) > 0:
        m = float(mt)
        return "IE4" if abs(m - 0.965) <= abs(m - 0.955) else "IE3"
    return "IE3"


def merge_feed_hydraulics_into_out(out: dict, unit_system: str) -> None:
    """Populate ``out`` from session_state (widgets on Pumps tab) or display defaults."""
    for out_key, ss_key, si_def, qty in _FEED_HYDR:
        if ss_key in st.session_state:
            out[out_key] = st.session_state[ss_key]
        else:
            out[out_key] = float(display_value(si_def, qty, unit_system))
    for out_key, ss_key, default in _ETAS:
        out[out_key] = st.session_state[ss_key] if ss_key in st.session_state else default
    iec = _resolve_motor_iec_class(out)
    out["motor_iec_class"] = iec
    out["motor_eta"] = motor_eta_from_iec_class(iec)


def reconcile_si_inputs_with_pump_widgets(inputs_si: dict) -> dict:
    """Return a new SI ``inputs`` dict with Pumps-tab hydraulics merged from ``st.session_state``.

    ``render_sidebar`` ends with ``merge_feed_hydraulics_into_out`` then ``convert_inputs``. When the
    input column is hidden, ``inputs`` is taken from ``mmf_last_inputs`` only — without this call,
    changes on **Pumps & power** (nozzle ΔP, residual, piping, η, motor class) would not reach
    ``compute_all`` until the sidebar runs again.
    """
    merged = copy.deepcopy(inputs_si)
    unit_system = str(merged.get("unit_system") or "metric")
    merge_feed_hydraulics_into_out(merged, unit_system)
    from engine.units import convert_inputs

    return convert_inputs(merged, unit_system)


def render_hydraulics_and_efficiency_columns(unit_system: str) -> None:
    """Two-column panel: pressure budget (left) vs η inputs (right)."""
    ch, ce = st.columns([1.15, 0.85])
    with ch:
        st.markdown("**Feed path — pressure budget**")
        st.number_input(
            f"Strainer nozzle plate ΔP at design LV ({unit_label('pressure_bar', unit_system)})",
            value=float(display_value(0.02, "pressure_bar", unit_system)),
            step=float(display_value(0.005, "pressure_bar", unit_system)),
            min_value=0.0,
            format="%.3f",
            key="np_slot",
        )
        st.number_input(
            f"Required downstream pressure ({unit_label('pressure_bar', unit_system)} g)",
            value=float(display_value(2.50, "pressure_bar", unit_system)),
            step=float(display_value(0.25, "pressure_bar", unit_system)),
            min_value=0.0,
            key="p_res",
        )
        st.number_input(
            f"Inlet piping losses ({unit_label('pressure_bar', unit_system)})",
            value=float(display_value(0.30, "pressure_bar", unit_system)),
            step=float(display_value(0.05, "pressure_bar", unit_system)),
            min_value=0.0,
            key="dp_in",
        )
        st.number_input(
            f"Inlet distributor ΔP ({unit_label('pressure_bar', unit_system)})",
            value=float(display_value(0.02, "pressure_bar", unit_system)),
            step=float(display_value(0.01, "pressure_bar", unit_system)),
            min_value=0.0,
            key="dp_dist",
        )
        st.number_input(
            f"Outlet piping losses ({unit_label('pressure_bar', unit_system)})",
            value=float(display_value(0.20, "pressure_bar", unit_system)),
            step=float(display_value(0.05, "pressure_bar", unit_system)),
            min_value=0.0,
            key="dp_out",
        )
        _lbl_sth = f"Static elevation head ({unit_label('pressure_mwc', unit_system)})"
        st.number_input(
            _lbl_sth,
            value=float(display_value(0.0, "pressure_mwc", unit_system)),
            step=float(display_value(0.5, "pressure_mwc", unit_system)),
            key="stat_h",
        )
    with ce:
        st.markdown("**Pump η & motor class (same as compute & energy)**")
        st.caption(
            "Pump hydraulic η caps are set here. **Motor electrical η** follows **IEC efficiency class** below "
            "(feed, BW, and blower)."
        )
        st.number_input(
            "Filtration pump hydraulic η (cap)",
            value=0.75,
            step=0.01,
            min_value=0.30,
            max_value=0.95,
            key="pump_e",
            help="Upper cap on hydraulic η; the model may use a lower creeping-η estimate per duty point.",
        )
        st.number_input(
            "BW pump hydraulic η",
            value=0.72,
            step=0.01,
            min_value=0.30,
            max_value=0.95,
            key="bwp_e",
        )
        st.selectbox(
            "Motor efficiency class",
            ["IE3", "IE4"],
            key="pp_feed_iec",
            help="Maps to nominal motor η: IE3 → 0.955, IE4 → 0.965 (all rotating electrical loads).",
        )
