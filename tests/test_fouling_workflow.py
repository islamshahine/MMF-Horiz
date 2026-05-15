"""Tests for fouling workflow helpers."""

from engine.fouling import (
    effective_sdi15_for_correlation,
    fouling_advisory_recommendations,
    fouling_confidence_level,
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
