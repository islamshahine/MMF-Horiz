"""ui/helpers.py — Shared UI helper functions for AQUASIGHT™ MMF."""
import streamlit as st


def fmt(si_val, quantity: str, decimals: int = 2) -> str:
    """
    Format SI value in the current unit system.
    Reads unit_system from st.session_state (defaults to 'metric').
    Usage: fmt(computed["q_per_filter"], "flow_m3h", 1)
    """
    from engine.units import format_value
    system = st.session_state.get("unit_system", "metric")
    return format_value(si_val, quantity, system, decimals)


def ulbl(quantity: str) -> str:
    """
    Return unit label for the current unit system.
    Usage: ulbl("flow_m3h") → "m³/h" or "gpm"
    """
    from engine.units import unit_label
    system = st.session_state.get("unit_system", "metric")
    return unit_label(quantity, system)


def dv(si_val, quantity: str):
    """
    Convert SI value to display value for the current unit system.
    Usage: dv(1312.5, "flow_m3h")
    """
    from engine.units import display_value
    system = st.session_state.get("unit_system", "metric")
    return display_value(si_val, quantity, system)


def show_alert(level: str, title: str, message: str) -> None:
    """Render a severity-coloured alert box using inline CSS."""
    _styles = {
        "info":     {"bg": "#0a1628", "border": "#1e40af", "icon": "ℹ️"},
        "advisory": {"bg": "#1a1500", "border": "#b8860b", "icon": "⚠️"},
        "warning":  {"bg": "#1a0a00", "border": "#cc5500", "icon": "🟠"},
        "critical": {"bg": "#1a0000", "border": "#cc0000", "icon": "🔴"},
    }
    s = _styles.get(level, _styles["info"])
    st.markdown(
        f"""<div style="
            background:{s['bg']}; border-left:4px solid {s['border']};
            border-radius:4px; padding:10px 14px; margin:6px 0;">
        <strong>{s['icon']} {title}</strong><br>{message}
        </div>""",
        unsafe_allow_html=True,
    )
