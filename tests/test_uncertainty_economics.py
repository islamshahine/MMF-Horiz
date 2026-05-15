"""Tests for cycle uncertainty → LCOW envelope."""

import copy

import pytest

from engine.uncertainty import cycle_duration_envelope
from engine.uncertainty_economics import lcow_envelope_from_cycle_uncertainty
from tests.test_integration import _INPUTS
from engine.compute import compute_all


def test_lcow_band_ordering():
    cu = cycle_duration_envelope(
        layers=_INPUTS["layers"],
        q_filter_m3h=1000.0,
        avg_area_m2=25.0,
        solid_loading_kg_m2=1.5,
        captured_density_kg_m3=1020.0,
        water_temp_c=27.0,
        rho_water=1000.0,
        dp_trigger_bar=1.0,
        alpha_m_kg=1e12,
        layer_areas_m2=None,
        maldistribution_factor=1.0,
        alpha_calibration_factor=1.0,
        tss_capture_efficiency=1.0,
        design_tss_mg_l=10.0,
    )
    econ_opex = {
        "total_opex_usd_yr": 500_000.0,
        "energy_cost_usd_yr": 200_000.0,
        "energy_kwh_filtration_yr": 1_000_000.0,
        "energy_kwh_bw_pump_yr": 300_000.0,
        "energy_kwh_blower_yr": 100_000.0,
        "annual_flow_m3": 10_000_000.0,
    }
    band = lcow_envelope_from_cycle_uncertainty(
        capex_total_usd=5_000_000.0,
        econ_opex=econ_opex,
        cycle_uncertainty_n=cu,
        discount_rate_pct=5.0,
        design_life_years=20,
        annual_flow_m3=10_000_000.0,
        electricity_tariff=0.10,
    )
    assert band["lcow_optimistic_usd_m3"] <= band["lcow_expected_usd_m3"]
    assert band["lcow_expected_usd_m3"] <= band["lcow_conservative_usd_m3"]
    assert band["bw_energy_scale_optimistic"] <= 1.0
    assert band["bw_energy_scale_conservative"] >= 1.0
    if cu["cycle_conservative_h"] < cu["cycle_expected_h"] - 0.01:
        assert band["bw_energy_scale_conservative"] > 1.0


def test_compute_all_includes_cycle_economics():
    inp = copy.deepcopy(_INPUTS)
    out = compute_all(inp)
    ce = out.get("cycle_economics") or {}
    assert ce
    assert "lcow_expected_usd_m3" in ce
    assert ce["lcow_optimistic_usd_m3"] <= ce["lcow_conservative_usd_m3"]
