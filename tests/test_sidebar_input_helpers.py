"""read_hidden_input — session / fallback when widget hidden."""

import streamlit as st

from ui.sidebar_input_helpers import read_hidden_input
from ui.ui_mode import SESSION_KEY


def test_read_hidden_uses_fallback_when_client():
    st.session_state[SESSION_KEY] = "client"
    val = read_hidden_input(
        "corrosion",
        lambda: 99.0,
        mode="client",
    )
    assert val == 1.5


def test_read_hidden_runs_widget_when_expert():
    st.session_state[SESSION_KEY] = "expert"
    val = read_hidden_input(
        "corrosion",
        lambda: 2.5,
        mode="expert",
    )
    assert val == 2.5
