"""Tests for engine/sensitivity.py — OAT tornado data + narrative helper."""

import copy

import pytest

from engine.sensitivity import (
    OUTPUT_DEFS,
    PARAM_DEFS,
    run_sensitivity,
    tornado_narrative,
)
from tests.test_integration import _INPUTS


@pytest.fixture
def base_inputs():
    return copy.deepcopy(_INPUTS)


def test_run_sensitivity_keys_match_outputs(base_inputs):
    """run_sensitivity returns one row list per OUTPUT_DEFS key."""
    tiny = [p for p in PARAM_DEFS if p["key"] in ("total_flow", "n_filters")]
    out = run_sensitivity(base_inputs, param_defs=tiny)
    assert set(out.keys()) == {od["key"] for od in OUTPUT_DEFS}
    for ok in out:
        assert isinstance(out[ok], list)
        assert len(out[ok]) == len(tiny)


def test_run_sensitivity_rows_sorted_by_abs_swing(base_inputs):
    """Each output's rows are ordered by |swing| descending."""
    subset = PARAM_DEFS[:3]
    out = run_sensitivity(base_inputs, param_defs=subset)
    for rows in out.values():
        swings = [abs(float(r["swing"])) for r in rows]
        assert swings == sorted(swings, reverse=True)


def test_run_sensitivity_row_schema(base_inputs):
    tiny = [{"key": "bw_velocity", "label": "BW velocity", "pct": 15.0}]
    out = run_sensitivity(base_inputs, param_defs=tiny)
    row = out["lv"][0]
    for k in ("param", "base", "lo", "hi", "swing", "lo_label", "hi_label"):
        assert k in row


def test_run_sensitivity_total_flow_moves_lv(base_inputs):
    out = run_sensitivity(
        base_inputs,
        param_defs=[{"key": "total_flow", "label": "Total flow", "pct": 20.0}],
    )
    lv_rows = out["lv"]
    assert len(lv_rows) == 1
    assert abs(float(lv_rows[0]["swing"])) > 1e-6


def test_tornado_narrative_includes_base_and_drivers():
    rows = [
        {
            "param": "Total flow",
            "base": 11.82,
            "lo": 9.4,
            "hi": 14.2,
            "swing": 4.8,
            "lo_label": "−20%",
            "hi_label": "+20%",
        },
        {
            "param": "No. of filters",
            "base": 11.82,
            "lo": 13.5,
            "hi": 10.6,
            "swing": -2.9,
            "lo_label": "−2",
            "hi_label": "+2",
        },
        {
            "param": "BW velocity",
            "base": 11.82,
            "lo": 11.82,
            "hi": 11.82,
            "swing": 0.0,
            "lo_label": "−20%",
            "hi_label": "+20%",
        },
    ]
    txt = tornado_narrative(rows, output_label="Peak LV (m/h)", top_k=3)
    assert "11.82" in txt
    assert "Total flow" in txt
    assert "BW velocity" in txt
    assert "Near-zero" in txt


def test_tornado_narrative_empty_rows():
    assert tornado_narrative([], output_label="X") == ""
