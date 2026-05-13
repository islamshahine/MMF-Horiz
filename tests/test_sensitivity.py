"""Tests for engine/sensitivity.py tornado narrative helper."""

from engine.sensitivity import tornado_narrative


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
