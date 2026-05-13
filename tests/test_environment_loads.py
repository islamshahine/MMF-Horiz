"""Tests for engine/environment_loads.py."""
import pytest

from engine.environment_loads import compute_environment_structural


def test_wind_dynamic_pressure_40_ms():
    r = compute_environment_structural({"basic_wind_ms": 40.0, "wind_exposure": "C"})
    q = 0.5 * 1.25 * 40.0 ** 2
    assert r["wind_dynamic_pressure_pa"] == pytest.approx(q, rel=1e-9)


def test_marine_external_paint_notes():
    r = compute_environment_structural({
        "external_environment": "Marine / coastal (aggressive external)",
        "basic_wind_ms": 0.0,
    })
    assert "C5-M" in r["paint_system_iso_note"] or "C5-M" in r["paint_system_layers_note"]


def test_seismic_rows_when_not_evaluated():
    r = compute_environment_structural({"seismic_design_category": "Not evaluated"})
    rows = r["seismic_table_rows"]
    assert any("Not evaluated" in str(x) for row in rows for x in row)
