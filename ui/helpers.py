"""ui/helpers.py — Shared UI helper functions for AQUASIGHT™ MMF."""
import streamlit as st


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
