"""Tests for engine/coating.py — internal areas and lining cost branches."""

import pytest

from engine.coating import (
    PROTECTION_TYPES,
    internal_surface_areas,
    lining_cost,
)


def test_internal_surface_areas_elliptic_keys_and_nozzle_plate():
    a0 = internal_surface_areas(3.0, 12.0, 0.75, "Elliptic 2:1", 0.0)
    a1 = internal_surface_areas(3.0, 12.0, 0.75, "Elliptic 2:1", 4.5)
    for k in (
        "a_cylinder_m2",
        "a_one_head_m2",
        "a_two_heads_m2",
        "a_shell_m2",
        "a_nozzle_plate_m2",
        "a_total_m2",
    ):
        assert k in a0
    assert a0["a_cylinder_m2"] > 100
    assert a0["a_shell_m2"] == pytest.approx(
        a0["a_cylinder_m2"] + a0["a_two_heads_m2"], rel=1e-9
    )
    assert a1["a_total_m2"] == pytest.approx(a0["a_total_m2"] + 4.5, rel=1e-9)
    assert a1["a_nozzle_plate_m2"] == 4.5


def test_elliptic_heads_exceed_toris_approximation():
    """Elliptic 2:1 integration should give larger head area than torispherical stub."""
    ell = internal_surface_areas(4.0, 8.0, 1.0, "Elliptic 2:1", 0.0)
    tor = internal_surface_areas(4.0, 8.0, 1.0, "Torispherical", 0.0)
    assert ell["a_two_heads_m2"] > tor["a_two_heads_m2"]
    assert ell["a_shell_m2"] > tor["a_shell_m2"]


def test_lining_cost_none():
    areas = internal_surface_areas(2.0, 10.0, 0.5, "Elliptic 2:1", 0.0)
    r = lining_cost("None", areas)
    assert r["total_cost_usd"] == 0
    assert r["weight_kg"] == 0
    r2 = lining_cost(None, areas)
    assert r2["total_cost_usd"] == 0


def test_lining_cost_rubber_epoxy_ceramic_positive():
    areas = internal_surface_areas(3.0, 10.0, 0.7, "Elliptic 2:1", 12.0)
    rub = lining_cost(
        "Rubber lining",
        areas,
        rubber_type="EPDM",
        rubber_thickness_mm=4.0,
        rubber_layers=2,
    )
    assert rub["total_cost_usd"] > 0
    assert rub["material_cost_usd"] > 0
    assert rub["labor_cost_usd"] > 0
    assert rub["id_deduction_mm"] == pytest.approx(8.0)
    assert rub["detail"]["Type"] == "EPDM"

    ep = lining_cost("Epoxy coating", areas, epoxy_type="High-build epoxy", epoxy_coats=2)
    assert ep["total_cost_usd"] > 0
    assert ep["id_deduction_mm"] == 0
    assert ep["weight_kg"] > 0

    ce = lining_cost(
        "Ceramic coating",
        areas,
        ceramic_type="Ceramic-filled epoxy",
        ceramic_coats=2,
    )
    assert ce["total_cost_usd"] > 0
    assert ce["weight_kg"] > ep["weight_kg"]


def test_lining_cost_unknown_protection_returns_zero_cost():
    areas = internal_surface_areas(2.0, 6.0, 0.5, "Elliptic 2:1", 0.0)
    r = lining_cost("Future hyperline", areas)
    assert r["total_cost_usd"] == 0
    assert r["protection_type"] == "Future hyperline"


def test_protection_types_catalogue():
    assert "Rubber lining" in PROTECTION_TYPES
    assert "Epoxy coating" in PROTECTION_TYPES
