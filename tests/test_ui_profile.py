"""Client vs engineer UI profile helpers."""

import streamlit as st

from ui.ui_profile import (
    PROFILE_CLIENT,
    _PROFILE_KEY,
    merge_client_sidebar_defaults,
    visible_main_tab_labels,
)


def _set_client_profile() -> None:
    st.session_state[_PROFILE_KEY] = PROFILE_CLIENT


def test_visible_main_tabs_client_hides_compare():
    _set_client_profile()
    all_tabs = ("💧 Filtration", "⚖️ Compare", "🎯 Assessment")
    visible = visible_main_tab_labels(all_tabs)
    assert "⚖️ Compare" not in visible
    assert "💧 Filtration" in visible


def test_merge_client_defaults_fills_calibration_keys():
    _set_client_profile()
    out = merge_client_sidebar_defaults({})
    assert out["alpha_calibration_factor"] == 1.0
    assert out["maldistribution_factor"] == 1.0
    assert "captured_solids_density" in out
