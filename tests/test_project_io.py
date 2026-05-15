"""Tests for engine.project_io — project JSON and _ui_session (pp_* / ab_*)."""

import json

import pytest

from engine.project_io import (
    PERSISTED_STREAMLIT_KEYS,
    coerce_persist_session_value,
    engine_inputs_dict,
    get_widget_state_map,
    inputs_to_json,
    json_to_inputs,
    widget_display_scalar,
)
from engine.units import display_value, si_value
from engine.validators import REFERENCE_FALLBACK_INPUTS


def test_coerce_persist_session_value_numpy_scalar():
    np = pytest.importorskip("numpy")
    assert coerce_persist_session_value(np.int64(4)) == 4
    assert coerce_persist_session_value(np.float64(1.25)) == 1.25
    assert coerce_persist_session_value(np.bool_(True)) is True


def test_inputs_to_json_round_trip_ui_session():
    base = {
        "project_name": "P1",
        "doc_number": "D1",
        "streams": 1,
        "motor_iec_class": "IE3",
    }
    ui = {
        "pp_n_feed_parallel": 2,
        "pp_align_econ_energy": True,
        "ab_elevation_amsl_m": 100.0,
        "ab_site_location_notes": "coastal",
    }
    raw = inputs_to_json(base, ui_session_overrides=ui)
    data = json.loads(raw)
    assert "_ui_session" in data
    assert data["_ui_session"]["pp_n_feed_parallel"] == 2
    assert data["_ui_session"]["pp_align_econ_energy"] is True
    assert data["_ui_session"]["ab_site_location_notes"] == "coastal"

    loaded = json_to_inputs(raw)
    assert loaded.get("streams") == 1
    assert "_ui_session" in loaded
    wmap = get_widget_state_map(loaded)
    assert wmap["pp_n_feed_parallel"] == 2
    assert wmap["pp_align_econ_energy"] is True
    assert wmap["ab_elevation_amsl_m"] == 100.0
    assert wmap["ab_site_location_notes"] == "coastal"

    eng = engine_inputs_dict(loaded)
    assert "_ui_session" not in eng


def test_ui_session_pp_feed_iec_wins_over_motor_iec_class():
    """Saved pump-tab IEC class must not be overwritten by economics motor_iec_class."""
    base = {
        "project_name": "P1",
        "doc_number": "D1",
        "streams": 1,
        "motor_iec_class": "IE3",
    }
    raw = inputs_to_json(base, ui_session_overrides={"pp_feed_iec": "IE4"})
    loaded = json_to_inputs(raw)
    wmap = get_widget_state_map(loaded)
    assert wmap.get("pp_feed_iec") == "IE4"


def test_get_widget_state_map_imperial_ab_elevation_display():
    """_ui_session stores SI; widget map uses display when project unit_system is imperial."""
    loaded = {
        "project_name": "P1",
        "doc_number": "D1",
        "streams": 1,
        "unit_system": "imperial",
        "_ui_session": {"ab_elevation_amsl_m": 100.0},
    }
    wmap = get_widget_state_map(loaded)
    assert abs(float(wmap["ab_elevation_amsl_m"]) - 328.084) < 0.05


def test_get_widget_state_map_imperial_converts_sidebar_quantities():
    """Scalar sidebar keys (e.g. total_flow) load as imperial display, not raw SI."""
    loaded = {
        **REFERENCE_FALLBACK_INPUTS,
        "project_name": "P1",
        "doc_number": "D1",
        "unit_system": "imperial",
    }
    wmap = get_widget_state_map(loaded)
    si_flow = float(REFERENCE_FALLBACK_INPUTS["total_flow"])
    assert abs(float(wmap["total_flow"]) - display_value(si_flow, "flow_m3h", "imperial")) < 0.5


def test_get_widget_state_map_imperial_layer_depth_display():
    loaded = {
        "project_name": "P1",
        "doc_number": "D1",
        "streams": 1,
        "unit_system": "imperial",
        "layers": [{"Type": "Fine sand", "Depth": 0.8, "is_support": False, "capture_frac": 1.0}],
    }
    wmap = get_widget_state_map(loaded)
    assert abs(float(wmap["ld_0"]) - display_value(0.8, "length_m", "imperial")) < 0.02


def test_widget_display_scalar_round_trip():
    v = 5.5
    disp = widget_display_scalar(v, "nominal_id", "imperial")
    back = si_value(float(disp), "length_m", "imperial")
    assert back == pytest.approx(v, rel=1e-3)


