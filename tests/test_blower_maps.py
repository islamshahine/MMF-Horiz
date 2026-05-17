"""Tests for engine.blower_maps — curves, VFD affinity, analysis bundle."""
from __future__ import annotations

import copy

import pytest

from engine.blower_maps import (
    CENTRIFUGAL_Q_MAX_NM3H,
    LOBE_Q_MAX_NM3H,
    ROOTS_LOBE_CURVE_ID,
    adiabatic_blower_power_at_flow,
    blowers_on_duty_from_inputs,
    build_blower_map_analysis,
    curve_shaft_kw,
    import_custom_curve_from_csv,
    import_custom_curve_grid,
    list_blower_curves,
    parse_vendor_curve_csv,
    pick_curve_id,
    vfd_affinity_shaft_kw,
    _CURVE_GRIDS,
)
from engine.compute import compute_all
from tests.test_integration import _INPUTS


def test_list_curves_nonempty():
    assert len(list_blower_curves()) >= 2


def test_lobe_grid_reaches_15k():
    spec = _CURVE_GRIDS[ROOTS_LOBE_CURVE_ID]
    assert spec["q_nm3h"][-1] >= LOBE_Q_MAX_NM3H - 1.0


def test_centrifugal_grid_reaches_50k():
    from engine.blower_maps import CENTRIFUGAL_CURVE_ID

    spec = _CURVE_GRIDS[CENTRIFUGAL_CURVE_ID]
    assert spec["q_nm3h"][-1] >= CENTRIFUGAL_Q_MAX_NM3H - 1.0


def test_curve_monotonic_with_flow():
    k1, _, _, _, _ = curve_shaft_kw(ROOTS_LOBE_CURVE_ID, 400.0, 0.5)
    k2, _, _, _, _ = curve_shaft_kw(ROOTS_LOBE_CURVE_ID, 800.0, 0.5)
    assert k2 > k1


def test_extrapolation_above_q_max():
    kw, in_env, _, extrap, flags = curve_shaft_kw(ROOTS_LOBE_CURVE_ID, 20_000.0, 0.5)
    assert kw > 0
    assert not in_env
    assert extrap
    assert flags.get("q_high")


def test_vfd_centrifugal_cubic():
    p = vfd_affinity_shaft_kw(100.0, 0.5, blower_type="centrifugal")
    assert abs(p - 12.5) < 0.1


def test_vfd_pd_linear():
    p = vfd_affinity_shaft_kw(100.0, 0.5, blower_type="positive_displacement")
    assert abs(p - 50.0) < 0.1


def test_auto_pick_oem_from_legacy():
    cid, switched, _ = pick_curve_id(16_000.0, ROOTS_LOBE_CURVE_ID, auto=True)
    assert switched
    assert cid == "oem_vendor_motor"


def test_map_split_uses_installed_count():
    assert blowers_on_duty_from_inputs({"pp_n_blowers": 3, "pp_blower_mode": "single_duty"}) == 3
    assert blowers_on_duty_from_inputs({"pp_n_blowers": 2}) == 2


def test_fleet_split():
    base = copy.deepcopy(_INPUTS)
    c = compute_all(base)
    bm = build_blower_map_analysis({**base, "pp_n_blowers": 2}, c)
    assert bm["enabled"]
    assert bm["fleet"]["n_on_duty"] == 2
    assert bm["fleet"]["q_per_machine_nm3h"] == pytest.approx(
        bm["fleet"]["q_total_nm3h"] / 2, rel=0.01,
    )


def test_adiabatic_per_machine_matches_fleet_over_n():
    base = copy.deepcopy(_INPUTS)
    c = compute_all(base)
    n = 3
    bm = build_blower_map_analysis({**base, "pp_n_blowers": n}, c)
    ad = bm["adiabatic"]
    assert ad["motor_kw_per_machine"] == pytest.approx(
        ad["motor_kw_fleet"] / n, rel=0.02,
    )
    assert bm["operating_point"]["q_nm3h"] == pytest.approx(
        bm["fleet"]["q_total_nm3h"] / n, rel=0.01,
    )


def test_chart_points_fleet_totals():
    base = copy.deepcopy(_INPUTS)
    c = compute_all(base)
    n = 2
    bm = build_blower_map_analysis(
        {**base, "pp_n_blowers": n, "pp_blower_mode": "twin_50_iso"},
        c,
    )
    cp = bm["chart_points"]
    assert cp["fleet_on_duty"]["q_nm3h"] == pytest.approx(bm["fleet"]["q_total_nm3h"], rel=0.01)
    assert cp["fleet_on_duty"]["map_shaft_kw"] == pytest.approx(
        cp["per_machine"]["map_shaft_kw"] * n, rel=0.01,
    )
    assert cp["fleet_on_duty"]["adiabatic_shaft_kw"] == pytest.approx(
        bm["adiabatic"]["shaft_kw_fleet"], rel=0.02,
    )
    assert bm["adiabatic"]["shaft_kw_fleet"] == pytest.approx(
        bm["adiabatic"]["shaft_kw_per_machine"] * n, rel=0.02,
    )


def test_adiabatic_scales_with_flow():
    p1 = adiabatic_blower_power_at_flow(1000.0, 0.45, blower_eta=0.7, motor_eta=0.95)
    p2 = adiabatic_blower_power_at_flow(2000.0, 0.45, blower_eta=0.7, motor_eta=0.95)
    assert abs(p2["shaft_kw"] / p1["shaft_kw"] - 2.0) < 0.05


def test_parse_vendor_csv_header_q():
    parsed = parse_vendor_curve_csv("q_nm3h,0.3,0.5\n100,10,15\n200,18,28\n")
    assert parsed["q_nm3h"] == [100.0, 200.0]
    assert parsed["dp_bar"] == [0.3, 0.5]


def test_custom_curve_import():
    import_custom_curve_grid(
        "test_curve",
        "Test",
        [100.0, 200.0],
        [0.3, 0.6],
        [[10.0, 20.0], [18.0, 36.0]],
        blower_type="positive_displacement",
    )
    kw, in_env, _, extrap, _ = curve_shaft_kw("test_curve", 150.0, 0.45)
    assert kw > 10.0
    assert in_env
    assert not extrap


def test_custom_curve_csv_import():
    import_custom_curve_from_csv(
        "test_csv_curve",
        "CSV test",
        "q_nm3h,0.4\n500,40\n1000,75\n",
    )
    kw, _, _, _, _ = curve_shaft_kw("test_csv_curve", 750.0, 0.4)
    assert kw > 50.0


def test_build_analysis_from_compute():
    base = copy.deepcopy(_INPUTS)
    c = compute_all(base)
    bm = build_blower_map_analysis(base, c)
    assert bm["enabled"] is True
    assert bm["curve_map"]["motor_kw"] > 0
    assert bm["adiabatic"]["motor_kw"] > 0
