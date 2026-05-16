"""Tests for engine/collector_nozzle_plate.py — BW nozzle-plate screening."""

import math

from engine.collector_nozzle_plate import (
    compute_nozzle_plate_bw_hydraulics,
    plate_axial_extent_m,
    staggered_plate_layout,
)
from engine.compute import compute_all
from engine.mechanical import nozzle_plate_area
from engine.validators import REFERENCE_FALLBACK_INPUTS
import copy


def test_plate_axial_extent_head_inset():
    x0, x1, inset = plate_axial_extent_m(
        cyl_len_m=21.0, h_dish_m=1.375, pitch_m=0.1, edge_m=0.05,
    )
    assert 0 < x0 < x1 < 21.0
    assert inset >= 0.05


def test_brick_layout_fills_chord_not_centerline_only():
    lay = staggered_plate_layout(
        cyl_len_m=21.0,
        n_holes_total=1400,
        chord_m=4.289,
        h_dish_m=1.375,
        bore_d_mm=50.0,
    )
    assert lay["layout_mode"] == "brick_rows"
    assert lay["n_rows_across_chord"] >= 5
    ys = {h[1] for h in lay["holes_xy"]}
    assert len(ys) >= 5
    assert max(ys) - min(ys) > 0.5


def test_brick_pitch_from_plate_area():
    geo = nozzle_plate_area(1.0, 5.5, 19.55, 1.375)
    lay = staggered_plate_layout(
        cyl_len_m=22.3,
        total_length_m=22.3,
        straight_cyl_len_m=19.55,
        h_dish_m=1.375,
        vessel_id_m=5.5,
        nozzle_plate_h_m=1.0,
        n_holes_total=500,
        chord_m=geo["chord_m"],
        plate_area_total_m2=geo["area_total_m2"],
        area_cyl_m2=geo["area_cyl_m2"],
        area_one_dish_m2=geo["area_one_dish_m2"],
        bore_d_mm=50.0,
    )
    p_expect = max(0.075, math.sqrt(geo["area_total_m2"] / 500))
    assert abs(lay["pitch_trans_m"] - p_expect) < 0.02


def test_layout_places_holes_in_dish_heads():
    geo = nozzle_plate_area(1.0, 5.5, 19.55, 1.375)
    h_d = 1.375
    total = 19.55 + 2 * h_d
    lay = staggered_plate_layout(
        cyl_len_m=total,
        total_length_m=total,
        straight_cyl_len_m=19.55,
        h_dish_m=h_d,
        vessel_id_m=5.5,
        nozzle_plate_h_m=1.0,
        n_holes_total=800,
        chord_m=geo["chord_m"],
        plate_area_total_m2=geo["area_total_m2"],
        area_cyl_m2=geo["area_cyl_m2"],
        area_one_dish_m2=geo["area_one_dish_m2"],
        bore_d_mm=50.0,
    )
    assert lay.get("includes_dish_heads") is True
    assert int(lay.get("n_holes_in_dish_zones", 0) or 0) > 0
    left = [x for x, *_ in lay["holes_xy"] if x < h_d - 0.05]
    right = [x for x, *_ in lay["holes_xy"] if x > h_d + 19.55 + 0.05]
    assert len(left) > 0
    assert len(right) > 0


def test_odd_row_stagger_longitudinal():
    lay = staggered_plate_layout(
        cyl_len_m=21.0,
        n_holes_total=200,
        chord_m=4.289,
        bore_d_mm=50.0,
    )
    rows = lay["plate_rows"]
    assert len(rows) >= 2
    x0_even = rows[0]["x_positions_m"][0]
    x0_odd = rows[1]["x_positions_m"][0]
    assert abs(abs(x0_odd - x0_even) - lay["pitch_long_m"] / 2.0) < 0.05


def test_nozzle_plate_active_with_bw_flow():
    out = compute_nozzle_plate_bw_hydraulics(
        q_bw_m3h=150.0,
        nozzle_plate_area_m2=90.0,
        cyl_len_m=22.0,
        nominal_id_m=5.5,
        np_bore_dia_mm=50.0,
        np_density_per_m2=45.0,
        n_holes_total=1260,
        collector_header_id_m=0.2,
        nozzle_plate_h_m=1.0,
        chord_m=4.289,
        h_dish_m=1.375,
    )
    assert out["active"] is True
    assert out["layout"] == "brick_rows"
    holes = out.get("hole_network") or []
    assert len(holes) >= 100
    ys = {round(h["y_plot_m"], 3) for h in holes}
    assert len(ys) >= 3
    even = [h for h in holes if not h.get("staggered")][:2]
    odd = [h for h in holes if h.get("staggered")][:2]
    assert even[0]["station_m"] < odd[0]["station_m"]


def test_nozzle_plate_zero_flow_inactive():
    out = compute_nozzle_plate_bw_hydraulics(
        q_bw_m3h=0.0,
        nozzle_plate_area_m2=20.0,
        cyl_len_m=10.0,
        nominal_id_m=5.0,
        np_bore_dia_mm=40.0,
        np_density_per_m2=50.0,
        collector_header_id_m=0.2,
        nozzle_plate_h_m=1.0,
        chord_m=3.0,
    )
    assert out["active"] is False


def test_compute_all_includes_collector_nozzle_plate():
    inp = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    c = compute_all(inp)
    npb = c.get("collector_nozzle_plate") or {}
    assert npb.get("active") is True
    assert npb.get("layout") == "brick_rows"
    assert int(npb.get("layout_revision", 0) or 0) >= 3
    assert int(npb.get("n_rows_across_chord", 0) or 0) >= 3
    holes = npb.get("hole_network") or []
    ys = {round(h.get("y_plot_m", 0), 2) for h in holes}
    assert len(ys) >= 3


def test_narrow_chord_still_multiple_rows_when_feasible():
    lay = staggered_plate_layout(
        cyl_len_m=21.0,
        n_holes_total=80,
        chord_m=1.27,
        bore_d_mm=50.0,
    )
    assert lay["n_rows_across_chord"] >= 2
    assert lay["actual_holes_from_layout"] <= 80
