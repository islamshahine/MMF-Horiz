"""Tests for engine/uncertainty_cycle.py — driver decomposition."""

import copy

from engine.compute import compute_all
from engine.uncertainty import cycle_duration_envelope
from engine.uncertainty_cycle import decompose_cycle_drivers
from engine.validators import REFERENCE_FALLBACK_INPUTS
from tests.test_uncertainty import _minimal_layers


def _base_kw():
    return dict(
        layers=_minimal_layers(),
        q_filter_m3h=1312.5,
        avg_area_m2=50.0,
        solid_loading_kg_m2=1.5,
        captured_density_kg_m3=1020.0,
        water_temp_c=27.0,
        rho_water=1025.0,
        dp_trigger_bar=1.0,
        alpha_m_kg=0.0,
        layer_areas_m2=None,
        maldistribution_factor=1.0,
        alpha_calibration_factor=1.0,
        tss_capture_efficiency=1.0,
        design_tss_mg_l=10.0,
    )


def test_decompose_cycle_drivers_structure():
    kw = _base_kw()
    env = cycle_duration_envelope(**kw)
    dec = decompose_cycle_drivers(**kw, expected_h=env["cycle_expected_h"])
    assert dec["method"] == "one_at_a_time_corner_perturbation"
    assert len(dec["drivers"]) == 4
    assert len(dec["narratives"]) == 4
    plot = dec["plot"]
    assert len(plot["driver_labels"]) == 4
    assert len(plot["swing_h"]) == 4
    assert dec["summary"]


def test_envelope_includes_driver_decomposition():
    env = cycle_duration_envelope(**_base_kw())
    dec = env.get("driver_decomposition") or {}
    assert dec.get("drivers")
    assert dec.get("plot")


def test_compute_all_preserves_cycle_economics_keys():
    out = compute_all(copy.deepcopy(REFERENCE_FALLBACK_INPUTS))
    cu = out.get("cycle_uncertainty") or {}
    assert "N" in cu
    n = cu["N"]
    for key in (
        "cycle_optimistic_h",
        "cycle_expected_h",
        "cycle_conservative_h",
        "spread_pct",
        "stability",
    ):
        assert key in n
    assert (n.get("driver_decomposition") or {}).get("drivers")
    ce = out.get("cycle_economics") or {}
    assert "lcow_expected_usd_m3" in ce or "lcow_optimistic_usd_m3" in ce
