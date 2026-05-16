"""Tests for engine.operating_envelope — LV × EBCT feasibility grid."""
from __future__ import annotations

from engine.operating_envelope import (
    _cell_worst_rank,
    _rank_to_region,
    build_operating_envelope,
)


def _base_one_layer():
    return [
        {
            "Layer": "Anthracite",
            "Area": 25.0,
            "Vol": 12.5,
            "is_support": False,
            "lv_threshold_m_h": 10.0,
            "ebct_threshold_min": 8.0,
        },
    ]


def test_cell_rank_stable_inside_envelope():
    base = _base_one_layer()
    assert _cell_worst_rank(9.0, 9.0, base) == 0
    assert _rank_to_region(0) == "stable"


def test_cell_rank_critical_high_lv():
    base = _base_one_layer()
    # 10% over cap → critical (>15% rule uses 11.6+ for critical; 11 is warning)
    assert _cell_worst_rank(11.0, 9.0, base) == 2  # warning at 10%
    assert _cell_worst_rank(12.0, 9.0, base) == 3  # critical at 20%


def test_cell_rank_critical_low_ebct():
    base = _base_one_layer()
    assert _cell_worst_rank(8.0, 5.5, base) == 3  # >25% below EBCT floor → critical


def test_build_envelope_disabled_without_geometry():
    out = build_operating_envelope({}, {"base": [], "avg_area": 0, "load_data": []})
    assert out["enabled"] is False


def test_build_envelope_scenario_points_and_grid():
    base = _base_one_layer()
    computed = {
        "base": base,
        "avg_area": 25.0,
        "load_data": [(0, 6, 200.0), (1, 5, 240.0)],
    }
    inputs = {"redundancy": 1}
    env = build_operating_envelope(inputs, computed, n_lv=12, n_ebct=12)
    assert env["enabled"] is True
    assert len(env["lv_axis_m_h"]) == 12
    assert len(env["ebct_axis_min"]) == 12
    assert len(env["region_matrix"]) == 12
    assert len(env["scenario_points"]) == 2
    assert env["scenario_points"][0]["scenario"] == "N"
    assert env["scenario_points"][1]["scenario"] == "N-1"
    n_lv = env["scenario_points"][0]["lv_m_h"]
    assert abs(n_lv - 200.0 / 25.0) < 0.01
    assert env["scenario_points"][1]["lv_m_h"] > n_lv


def test_region_matrix_labels():
    base = _base_one_layer()
    computed = {
        "base": base,
        "avg_area": 25.0,
        "load_data": [(0, 6, 150.0)],
    }
    env = build_operating_envelope({}, computed, n_lv=10, n_ebct=10)
    regions = {c for row in env["region_matrix"] for c in row}
    assert "stable" in regions
    assert regions.issubset({"stable", "marginal", "elevated", "critical"})
