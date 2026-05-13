"""Tests for engine/energy.py — BW duty split and helpers."""
import pytest

from engine.energy import bw_equipment_hours_per_event


def test_bw_equipment_hours_default_sequence():
    steps = [
        {
            "Step": "Partial drainage",
            "Dur avg (min)": 10,
            "Water rate (m/h)": 5.0,
            "Source": "Filter drainage",
        },
        {
            "Step": "Air scour only",
            "Dur avg (min)": 2,
            "Water rate (m/h)": 0.0,
            "Source": "Air",
        },
        {
            "Step": "Air + low water rate",
            "Dur avg (min)": 5,
            "Water rate (m/h)": 12.5,
            "Source": "Air + brine",
        },
        {
            "Step": "High water rate",
            "Dur avg (min)": 10,
            "Water rate (m/h)": 30.0,
            "Source": "Brine",
        },
        {
            "Step": "Rinse — raw water",
            "Dur avg (min)": 20,
            "Water rate (m/h)": 12.5,
            "Source": "Raw water",
        },
    ]
    assert len(steps) == 5
    pump_h, blow_h = bw_equipment_hours_per_event(steps, fallback_total_h=1.0)
    assert pump_h == pytest.approx(45.0 / 60.0, rel=1e-6)
    assert blow_h == pytest.approx(7.0 / 60.0, rel=1e-6)


def test_bw_equipment_hours_empty_fallback():
    pump_h, blow_h = bw_equipment_hours_per_event(None, fallback_total_h=0.633)
    assert pump_h == pytest.approx(0.633, rel=1e-9)
    assert blow_h == pytest.approx(0.633, rel=1e-9)
