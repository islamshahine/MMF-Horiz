"""Backward-compat wrappers around ui_mode."""

import streamlit as st

from ui.ui_mode import SESSION_KEY
from ui.ui_profile import (
    is_client_mode,
    is_engineer_mode,
    is_expert_mode,
    merge_client_sidebar_defaults,
    visible_main_tab_labels,
)


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
    assert "total_flow" in out or out.get("bw_velocity") is not None
