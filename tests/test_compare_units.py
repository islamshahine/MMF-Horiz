"""Compare tab unit-toggle helpers."""
import pytest

from engine.units import display_value, si_value, transpose_display_value
from ui.compare_units import COMPARE_B_WIDGET_QUANTITIES


def test_compare_widget_quantities_match_tab_compare_fields():
    assert COMPARE_B_WIDGET_QUANTITIES["b_nominal_id"] == "length_m"
    assert COMPARE_B_WIDGET_QUANTITIES["b_bw_velocity"] == "velocity_m_h"
    assert len(COMPARE_B_WIDGET_QUANTITIES) == 6


def test_compare_widget_transpose_roundtrip():
    si_id = 5.5
    disp_i = display_value(si_id, "length_m", "imperial")
    back = si_value(
        transpose_display_value(disp_i, "length_m", "imperial", "metric"),
        "length_m",
        "metric",
    )
    assert back == pytest.approx(si_id, rel=1e-6)
