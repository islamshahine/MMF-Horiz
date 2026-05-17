"""Tests for cycle uncertainty chart payloads (B4)."""
import copy

from engine.compute import compute_all
from engine.uncertainty import cycle_duration_envelope
from engine.uncertainty_charts import build_cycle_uncertainty_charts, dp_vs_loading_envelope
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


def test_dp_vs_loading_envelope_shape():
    env = dp_vs_loading_envelope(**_base_kw())
    assert len(env["m_kg_m2"]) == 5
    assert len(env["dp_expected_bar"]) == 5
    assert env["dp_trigger_bar"] == 1.0
    assert max(env["dp_optimistic_bar"]) >= min(env["dp_conservative_bar"])


def test_envelope_includes_dp_chart_series():
    row = cycle_duration_envelope(**_base_kw())
    dp = row.get("dp_vs_loading_envelope") or {}
    assert dp.get("m_kg_m2")


def test_build_cycle_uncertainty_charts():
    cu = {
        "N": {
            "cycle_optimistic_h": 12.0,
            "cycle_expected_h": 10.0,
            "cycle_conservative_h": 8.0,
            "design_tss_mg_l": 10.0,
            "dp_vs_loading_envelope": {
                "m_kg_m2": [0.0, 1.0],
                "dp_optimistic_bar": [0.1, 0.2],
                "dp_expected_bar": [0.1, 0.25],
                "dp_conservative_bar": [0.1, 0.3],
                "dp_trigger_bar": 1.0,
            },
        },
        "N-1": {
            "cycle_optimistic_h": 11.0,
            "cycle_expected_h": 9.0,
            "cycle_conservative_h": 7.0,
        },
    }
    charts = build_cycle_uncertainty_charts(cu)
    assert charts["enabled"] is True
    band = charts["scenario_cycle_band"]
    assert band["scenarios"] == ["N", "N-1"]
    assert charts["dp_vs_loading_envelope"]["m_kg_m2"]


def test_compute_all_includes_cycle_uncertainty_charts():
    out = compute_all(copy.deepcopy(REFERENCE_FALLBACK_INPUTS))
    charts = out.get("cycle_uncertainty_charts") or {}
    assert charts.get("enabled") is True
    assert charts.get("scenario_cycle_band", {}).get("scenarios")
    assert charts.get("dp_vs_loading_envelope", {}).get("m_kg_m2")
