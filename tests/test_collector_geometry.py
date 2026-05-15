"""Tests for underdrain vessel geometry."""

import math

import pytest

from engine.collector_geometry import chord_half_width_m, lateral_geometry_from_vessel
from engine.collector_hydraulics import compute_collector_hydraulics


def test_chord_at_mid_height():
    r = 2.75
    h = 1.0
    l = chord_half_width_m(r, h)
    assert abs(l - math.sqrt(2 * r * h - h * h)) < 1e-6


def test_theta_and_lmax_increase_with_collector_height():
    low = lateral_geometry_from_vessel(
        vessel_id_m=5.5, nozzle_plate_h_m=1.0, collector_h_m=2.0, cyl_len_m=20.0,
    )
    high = lateral_geometry_from_vessel(
        vessel_id_m=5.5, nozzle_plate_h_m=1.0, collector_h_m=3.5, cyl_len_m=20.0,
    )
    assert high["lateral_length_max_m"] > low["lateral_length_max_m"]
    assert high["theta_deg"] >= low["theta_deg"]


def test_hydraulics_includes_geometry():
    out = compute_collector_hydraulics(
        q_bw_m3h=80.0,
        filter_area_m2=25.0,
        cyl_len_m=20.0,
        nominal_id_m=5.5,
        np_bore_dia_mm=50.0,
        np_density_per_m2=50.0,
        collector_header_id_m=0.25,
        n_laterals=4,
        lateral_dn_mm=50.0,
        nozzle_plate_h_m=1.0,
        collector_h_m=3.9,
        use_geometry_lateral=True,
    )
    assert out["theta_deg"] > 0
    assert out["lateral_length_max_m"] > 0
    assert out["lateral_length_m"] <= out["lateral_length_max_m"] + 0.01


def test_max_collector_centerline_height():
    from engine.collector_geometry import max_collector_centerline_height_m

    assert max_collector_centerline_height_m(5.5, 0.65) == pytest.approx(5.5 - 0.1 - 0.325)
    assert max_collector_centerline_height_m(5.5, 0.25) == pytest.approx(5.275)


def test_material_open_area_limits():
    from engine.collector_geometry import lateral_material_open_area_limit

    pvc = lateral_material_open_area_limit("PVC")
    ss = lateral_material_open_area_limit("Stainless steel")
    assert pvc["open_area_max_fraction"] == 0.12
    assert ss["open_area_max_fraction"] == 0.25
    assert pvc["open_area_max_fraction"] < ss["open_area_max_fraction"]


def test_structural_open_area_cap():
    from engine.collector_geometry import structural_perforation_limits

    ok = structural_perforation_limits(
        lateral_dn_mm=50.0,
        lateral_length_m=2.5,
        orifice_d_mm=10.0,
        n_perforations=5,
        lateral_material="PVC",
    )
    assert ok["structural_ok"]
    assert ok["open_area_fraction"] <= 0.12 + 1e-6

    bad = structural_perforation_limits(
        lateral_dn_mm=50.0,
        lateral_length_m=1.0,
        orifice_d_mm=15.0,
        n_perforations=120,
        lateral_material="PVC",
    )
    assert not bad["structural_ok"]
    assert bad["open_area_fraction"] > 0.12 - 1e-6
    assert bad["n_perforations_max_structural"] < 120
