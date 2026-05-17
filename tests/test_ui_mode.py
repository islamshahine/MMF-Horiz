"""UI mode configuration — display filter only."""

import streamlit as st

from ui.layout_enhancements import MAIN_TAB_LABELS, SIDEBAR_TAB_LABELS
from ui.ui_mode import (
    CALIBRATION_KEYS,
    CRITICAL_INPUT_KEYS,
    HIDDEN_KEYS,
    MODE_LABELS,
    UI_MODES,
    fallback_value,
    get_mode_config,
    is_calibration_key,
    merge_hidden_input_defaults,
    mode_allows,
    normalize_mode,
    visible_main_tab_labels,
)


def test_mode_allows_calibration():
    assert mode_allows("total_flow", "client") is True
    assert mode_allows("alpha_calibration_factor", "client") is False
    assert mode_allows("alpha_calibration_factor", "engineer") is False
    assert mode_allows("alpha_calibration_factor", "expert") is True


def test_critical_inputs_never_hidden_client():
    client_hidden = HIDDEN_KEYS["client"]
    for key in CRITICAL_INPUT_KEYS:
        assert key not in client_hidden, f"critical hidden in client: {key}"


def test_get_mode_config_flags():
    cfg_c = get_mode_config("client")
    assert cfg_c["read_only_hint"] is True
    assert cfg_c["show_tier_c_results"] is False
    cfg_e = get_mode_config("expert")
    assert cfg_e["show_calibration_knobs"] is True
    assert cfg_e["show_tier_c_results"] is True


def test_visible_main_tabs_labels_match_layout():
    for mode in UI_MODES:
        visible = visible_main_tab_labels(MAIN_TAB_LABELS, mode)
        for lbl in visible:
            assert lbl in MAIN_TAB_LABELS
    client = visible_main_tab_labels(MAIN_TAB_LABELS, "client")
    assert "⚖️ Compare" not in client


def test_visible_sidebar_tabs_client_subset():
    cfg = get_mode_config("client")
    assert len(cfg["visible_sidebar_tabs"]) == 3
    assert cfg["visible_sidebar_tabs"][0] in SIDEBAR_TAB_LABELS


def test_merge_hidden_defaults_client():
    st.session_state["ui_mode"] = "client"
    out = merge_hidden_input_defaults({})
    assert out["alpha_calibration_factor"] == 1.0
    assert out["maldistribution_factor"] == 1.0


def test_calibration_keys_subset():
    for key in CALIBRATION_KEYS:
        assert is_calibration_key(key)
    assert fallback_value("total_flow") == 21000.0


def test_normalize_mode_invalid():
    assert normalize_mode("bogus") == "engineer"
