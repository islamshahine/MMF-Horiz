"""Tests for engine.uncertainty — cycle duration envelopes."""

import copy

import pytest

from engine.compute import compute_all
from engine.uncertainty import cycle_duration_envelope
from engine.validators import REFERENCE_FALLBACK_INPUTS


def _minimal_layers():
    return [
        {
            "Type": "Fine sand",
            "Depth": 0.8,
            "d10": 0.8,
            "cu": 1.5,
            "epsilon0": 0.42,
            "rho_p_eff": 2650.0,
            "psi": 0.85,
            "is_support": False,
            "capture_frac": 1.0,
        },
    ]


def test_cycle_duration_envelope_ordering():
    env = cycle_duration_envelope(
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
    assert env["cycle_optimistic_h"] >= env["cycle_expected_h"] >= env["cycle_conservative_h"]
    assert env["spread_pct"] >= 0
    assert env["stability"] in ("narrow", "moderate", "wide")
    assert env["method"] == "deterministic_corner_cases"


def test_compute_all_includes_cycle_uncertainty():
    inp = copy.deepcopy(REFERENCE_FALLBACK_INPUTS)
    out = compute_all(inp)
    cu = out.get("cycle_uncertainty")
    assert isinstance(cu, dict)
    assert "N" in cu
    assert "cycle_expected_h" in cu["N"]
