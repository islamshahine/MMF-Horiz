"""Tests for engine.spatial_distribution — Voronoi service areas."""
from __future__ import annotations

import copy

import pytest

from engine.spatial_distribution import (
    build_spatial_distribution,
    enrich_hole_network_with_spatial,
    voronoi_service_areas_grid,
)
from engine.compute import compute_all
from tests.test_integration import _INPUTS


def test_voronoi_uniform_grid_similar_areas():
    xs = [0.0, 1.0, 2.0, 0.0, 1.0, 2.0]
    ys = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
    areas = voronoi_service_areas_grid(xs, ys, x0=0.0, x1=2.0, y0=0.0, y1=1.0, nx=40, ny=40)
    assert len(areas) == 6
    assert max(areas) / min(areas) < 2.2  # grid Voronoi at bbox corners


def test_build_disabled_without_nozzle_plate():
    out = build_spatial_distribution({}, {"collector_nozzle_plate": {"active": False}})
    assert out["enabled"] is False


def test_build_filtration_flow_basis_uses_q_per_filter():
    holes = [
        {"station_m": 1.0, "y_plot_m": 0.0, "orifice_d_mm": 50.0},
        {"station_m": 2.0, "y_plot_m": 0.5, "orifice_d_mm": 50.0},
        {"station_m": 1.5, "y_plot_m": -0.5, "orifice_d_mm": 50.0},
    ]
    computed = {
        "q_per_filter": 185.5,
        "collector_nozzle_plate": {
            "active": True,
            "hole_network": holes,
            "field_x_start_m": 0.5,
            "field_x_end_m": 2.5,
            "field_y_plot_start_m": -1.0,
            "field_y_plot_end_m": 1.0,
            "chord_m": 2.0,
            "pitch_long_mm": 100.0,
            "pitch_trans_mm": 100.0,
        },
        "bw_hyd": {"q_bw_m3h": 999.0},
    }
    sp = build_spatial_distribution({}, computed, flow_basis="filtration")
    assert sp["enabled"] is True
    assert sp["flow_basis"] == "filtration"
    assert sp["q_basis_m3h"] == pytest.approx(185.5, rel=1e-6)
    assert "ASM-SPATIAL-003" in sp["assumption_ids"]


def test_build_from_synthetic_hole_network():
    holes = [
        {
            "station_m": 1.0,
            "y_plot_m": 0.0,
            "orifice_d_mm": 50.0,
            "flow_m3h": 10.0,
            "velocity_m_s": 1.0,
        },
        {
            "station_m": 2.0,
            "y_plot_m": 0.5,
            "orifice_d_mm": 50.0,
            "flow_m3h": 10.0,
            "velocity_m_s": 1.0,
        },
        {
            "station_m": 1.5,
            "y_plot_m": -0.5,
            "orifice_d_mm": 50.0,
            "flow_m3h": 10.0,
            "velocity_m_s": 1.0,
        },
    ]
    computed = {
        "collector_nozzle_plate": {
            "active": True,
            "q_bw_m3h": 300.0,
            "hole_network": holes,
            "field_x_start_m": 0.5,
            "field_x_end_m": 2.5,
            "field_y_plot_start_m": -1.0,
            "field_y_plot_end_m": 1.0,
            "chord_m": 2.0,
            "pitch_long_mm": 100.0,
            "pitch_trans_mm": 100.0,
            "layout_revision": 3,
        },
        "bw_hyd": {"q_bw_m3h": 300.0},
    }
    sp = build_spatial_distribution({}, computed)
    assert sp["enabled"] is True
    assert len(sp["nozzle_loading_factor"]) == 3
    assert 0.0 <= sp["hydraulic_uniformity_index"] <= 1.0


def test_enrich_hole_network():
    holes = [{"station_m": 1.0, "y_plot_m": 0.0}]
    sp = {
        "enabled": True,
        "nozzle_service_area_m2": [0.5],
        "nozzle_local_velocity_m_h": [40.0],
        "nozzle_loading_factor": [1.0],
    }
    out = enrich_hole_network_with_spatial(holes, sp)
    assert out[0]["service_area_m2"] == 0.5


def test_integration_compute_has_spatial_via_app_pattern():
    base = copy.deepcopy(_INPUTS)
    c = compute_all(base)
    from engine.spatial_distribution import build_spatial_distribution

    sp = build_spatial_distribution(base, c)
    if (c.get("collector_nozzle_plate") or {}).get("active"):
        assert sp.get("enabled") is True
        assert sp.get("n_nozzles", 0) >= 2
