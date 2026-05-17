"""UI mode session helpers (legacy test module name)."""

import streamlit as st

from ui.ui_mode import SESSION_KEY, merge_client_sidebar_defaults, visible_main_tab_labels
from ui.ui_mode import is_client_mode, is_engineer_mode, is_expert_mode


def _set_mode(mode: str) -> None:
    st.session_state[SESSION_KEY] = mode


def test_visible_main_tabs_client_hides_compare():
    _set_mode("client")
    all_tabs = ("💧 Filtration", "⚖️ Compare", "🎯 Assessment")
    visible = visible_main_tab_labels(all_tabs)
    assert "⚖️ Compare" not in visible
    assert "💧 Filtration" in visible


def test_engineer_not_client():
    _set_mode("engineer")
    assert is_engineer_mode()
    assert not is_client_mode()
    assert not is_expert_mode()


def test_expert_flags():
    _set_mode("expert")
    assert is_expert_mode()
    assert is_engineer_mode()


def test_merge_client_defaults_fills_calibration_keys():
    _set_mode("client")
    out = merge_client_sidebar_defaults({})
    assert out["alpha_calibration_factor"] == 1.0
    assert out.get("total_flow") == 21000.0
