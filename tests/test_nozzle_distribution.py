"""Tests for engine.nozzle_plate_distribution — triangular stagger layout."""

import math

import pytest

from engine.mechanical import nozzle_plate_area
from engine.nozzle_plate_distribution import (
    build_triangular_nozzle_layout,
    generate_triangular_candidates,
    pitch_from_density,
)
from engine.collector_nozzle_plate import staggered_plate_layout, chord_at_axial_x


def _plate_geo():
    geo = nozzle_plate_area(1.0, 5.5, 19.55, 1.375)
    h_d = 1.375
    total = 19.55 + 2 * h_d
    return geo, h_d, total


def test_n_total_from_density():
    geo, h_d, total = _plate_geo()
    dens = 55.0
    n_target = int(round(dens * geo["area_total_m2"]))
    tri = build_triangular_nozzle_layout(
        plate_area_m2=geo["area_total_m2"],
        chord_width_m=geo["chord_m"],
        total_length_m=total,
        straight_cyl_len_m=19.55,
        vessel_id_m=5.5,
        nozzle_plate_h_m=1.0,
        h_dish_m=h_d,
        bore_d_mm=50.0,
        n_holes_total=0,
        np_density_per_m2=dens,
    )
    assert abs(tri["n_placed"] - n_target) / n_target <= 0.01


def test_points_inside_geometry():
    geo, h_d, total = _plate_geo()
    tri = build_triangular_nozzle_layout(
        plate_area_m2=geo["area_total_m2"],
        chord_width_m=geo["chord_m"],
        total_length_m=total,
        straight_cyl_len_m=19.55,
        vessel_id_m=5.5,
        nozzle_plate_h_m=1.0,
        h_dish_m=h_d,
        bore_d_mm=50.0,
        n_holes_total=800,
        np_density_per_m2=45.0,
    )
    d_m = 0.05
    edge = max(0.5 * tri["pitch_m"], 1.5 * d_m)
    for x, y, *_ in tri["holes_xy"]:
        w = chord_at_axial_x(
            x,
            h_plate_m=1.0,
            vessel_radius_m=2.75,
            h_dish_m=h_d,
            straight_cyl_len_m=19.55,
        )
        assert abs(y) <= w / 2.0 - min(edge, w * 0.12) + 0.002
        assert edge <= x <= total - edge + 0.01


def test_minimum_spacing():
    geo, h_d, total = _plate_geo()
    dens = 40.0
    tri = build_triangular_nozzle_layout(
        plate_area_m2=geo["area_total_m2"],
        chord_width_m=geo["chord_m"],
        total_length_m=total,
        straight_cyl_len_m=19.55,
        vessel_id_m=5.5,
        nozzle_plate_h_m=1.0,
        h_dish_m=h_d,
        bore_d_mm=50.0,
        n_holes_total=0,
        np_density_per_m2=dens,
    )
    p = float(tri["pitch_m"])
    p_min = max(2.5 * 0.05, 0.05 + 0.05)
    assert p >= p_min - 1e-9
    info = pitch_from_density(
        plate_area_m2=geo["area_total_m2"],
        n_total=int(round(dens * geo["area_total_m2"])),
        bore_d_m=0.05,
    )
    assert info["pitch_m"] >= info["pitch_min_m"] - 1e-9


def test_axial_utilization_above_95_percent():
    geo, h_d, total = _plate_geo()
    tri = build_triangular_nozzle_layout(
        plate_area_m2=geo["area_total_m2"],
        chord_width_m=geo["chord_m"],
        total_length_m=total,
        straight_cyl_len_m=19.55,
        vessel_id_m=5.5,
        nozzle_plate_h_m=1.0,
        h_dish_m=h_d,
        bore_d_mm=50.0,
        n_holes_total=1200,
        np_density_per_m2=50.0,
    )
    assert float(tri["axial_utilization"]) >= 0.95


def test_staggered_offset_exists():
    geo, h_d, total = _plate_geo()
    p = 0.12
    cand = generate_triangular_candidates(
        total_length_m=total,
        chord_width_m=geo["chord_m"],
        pitch_m=p,
        bore_d_m=0.05,
        h_plate_m=1.0,
        vessel_radius_m=2.75,
        h_dish_m=h_d,
        straight_cyl_len_m=19.55,
    )
    xs_even = {round(h[0], 4) for h in cand if not h[4]}
    xs_odd = {round(h[0], 4) for h in cand if h[4]}
    assert xs_even
    assert xs_odd
    assert xs_even != xs_odd


def test_staggered_plate_layout_integration():
    geo, h_d, total = _plate_geo()
    lay = staggered_plate_layout(
        cyl_len_m=total,
        total_length_m=total,
        straight_cyl_len_m=19.55,
        h_dish_m=h_d,
        vessel_id_m=5.5,
        nozzle_plate_h_m=1.0,
        n_holes_total=600,
        chord_m=geo["chord_m"],
        plate_area_total_m2=geo["area_total_m2"],
        np_density_per_m2=48.0,
        bore_d_mm=50.0,
    )
    assert lay["layout_mode"] == "triangular_stagger"
    xs = [h[0] for h in lay["holes_xy"]]
    assert max(xs) >= total * 0.88
    assert min(xs) <= total * 0.12
