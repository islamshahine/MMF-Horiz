"""Collapsed-layout: pump hydraulics merge into SI inputs before compute."""

import copy

import pytest
import streamlit as st

from engine.compute import compute_all
from engine.units import display_value, si_value
from engine.validators import REFERENCE_FALLBACK_INPUTS
from ui.feed_pump_context_inputs import reconcile_si_inputs_with_pump_widgets


@pytest.fixture(autouse=True)
def _clear_pump_hydraulic_widgets():
    for k in ("np_slot", "p_res", "dp_in", "dp_dist", "dp_out", "stat_h", "pump_e", "bwp_e", "pp_feed_iec"):
        st.session_state.pop(k, None)
    yield


def test_reconcile_applies_session_residual_metric():
    inp = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    inp["unit_system"] = "metric"
    inp["p_residual"] = 2.5
    st.session_state["p_res"] = 1.75
    out = reconcile_si_inputs_with_pump_widgets(inp)
    assert abs(float(out["p_residual"]) - 1.75) < 1e-9


def test_reconcile_then_compute_runs():
    inp = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    inp["unit_system"] = "metric"
    st.session_state["p_res"] = 1.8
    merged = reconcile_si_inputs_with_pump_widgets(inp)
    r = compute_all(merged)
    assert r["input_validation"]["valid"] is True
    assert "hyd_prof" in r


def test_reconcile_imperial_pump_widget_to_si():
    """Collapsed layout: pump tab widgets in display units must merge as SI bar."""
    inp = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    inp["unit_system"] = "imperial"
    disp_bar = display_value(1.75, "pressure_bar", "imperial")
    st.session_state["p_res"] = disp_bar
    out = reconcile_si_inputs_with_pump_widgets(inp)
    assert abs(float(out["p_residual"]) - 1.75) < 1e-3
    assert abs(float(out["p_residual"]) - si_value(float(disp_bar), "pressure_bar", "imperial")) < 1e-3
