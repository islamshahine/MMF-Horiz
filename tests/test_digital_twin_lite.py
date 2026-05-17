"""Tests for engine/digital_twin_lite.py (C4)."""
import copy

from engine.compute import compute_all
from engine.digital_twin_lite import build_digital_twin_lite, parse_ops_telemetry_csv
from engine.validators import REFERENCE_FALLBACK_INPUTS


def test_parse_ops_csv():
    csv = "cycle_hours_h,dp_dirty_bar\n12.0,0.95\n10.5,0.88\n"
    rows, warns = parse_ops_telemetry_csv(csv)
    assert len(rows) == 2
    assert not warns


def test_build_suggests_alpha_when_cycle_longer_than_model():
    out = compute_all(copy.deepcopy(REFERENCE_FALLBACK_INPUTS))
    cu = (out.get("cycle_uncertainty") or {}).get("N") or {}
    exp = float(cu.get("cycle_expected_h") or 8.0)
    plant_cycle = exp * 1.25
    csv = f"cycle_hours_h\n{plant_cycle}\n{plant_cycle}\n{plant_cycle}\n"
    twin = build_digital_twin_lite(csv, REFERENCE_FALLBACK_INPUTS, out)
    assert twin["enabled"] is True
    patch = twin["suggested_patches"]
    assert "alpha_calibration_factor" in patch
    assert patch["alpha_calibration_factor"] < float(
        out.get("alpha_calibration_factor", 1.0) or 1.0
    ) + 0.01


def test_build_disabled_on_empty():
    twin = build_digital_twin_lite("", {}, {})
    assert twin["enabled"] is False
