"""Tests for fouling workflow helpers."""

from engine.fouling import (
    build_fouling_assessment,
    effective_sdi15_for_correlation,
    fouling_advisory_recommendations,
    fouling_confidence_level,
    fouling_cycle_uncertainty_crosscheck,
    water_stability_class,
)


def test_water_stability_class_escalates_with_algae():
    a = water_stability_class(severity="low", seasonal_variability="low", algae_risk="low")
    b = water_stability_class(severity="low", seasonal_variability="high", algae_risk="high")
    assert b["rank"] > a["rank"]


def test_fouling_confidence_increases_with_inputs():
    low = fouling_confidence_level(sdi15=0, mfi_index=0, tss_mg_l=0, has_upstream_uf_daf=False, seasonal_variability="unknown")
    high = fouling_confidence_level(sdi15=3, mfi_index=2, tss_mg_l=10, has_upstream_uf_daf=True, seasonal_variability="moderate")
    assert high["score"] > low["score"]


def test_effective_sdi15_blocked_uses_cap():
    val, warns = effective_sdi15_for_correlation(99.0, test_blocked=True, blocked_cap=8.0)
    assert val == 8.0
    assert any("blocked" in w.lower() or "∞" in w for w in warns)


def test_effective_sdi15_measured_passes_through():
    val, warns = effective_sdi15_for_correlation(3.5, test_blocked=False)
    assert val == 3.5
    assert warns == []


def test_fouling_advisory_returns_non_empty():
    rec = fouling_advisory_recommendations(severity="high", score=75, stability_label="aggressive", run_time_h=8.0)
    assert len(rec) >= 2


def test_build_fouling_assessment_structure():
    a = build_fouling_assessment(
        tss_mg_l=10.0, lv_m_h=10.0, sdi15=3.0, mfi_index=2.0,
        seasonal_variability="moderate", algae_risk="low",
    )
    assert a["solid_loading_kg_m2"] > 0
    assert "severity" in a and "confidence" in a
    assert a["cycle_crosscheck"]["available"] is False


def test_cycle_crosscheck_within_band():
    x = fouling_cycle_uncertainty_crosscheck(
        indicative_run_time_h=24.0,
        cycle_uncertainty_n={
            "cycle_optimistic_h": 20.0,
            "cycle_expected_h": 24.0,
            "cycle_conservative_h": 30.0,
            "spread_pct": 25.0,
        },
    )
    assert x["available"] is True
    assert x["alignment"] == "within_band"
