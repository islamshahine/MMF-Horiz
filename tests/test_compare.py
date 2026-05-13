"""Tests for engine/compare.py — public facade and helpers."""
import pytest

from engine import compare
from engine.compare import (
    COMPARISON_METRICS,
    compare_designs,
    compare_numeric,
    compare_severity,
    diff_value,
    generate_delta_summary,
)


def test_compare_numeric_is_diff_value():
    assert compare_numeric is diff_value
    d = compare_numeric(10.0, 12.0, threshold_pct=5.0, higher_is_better=False)
    assert d["pct_diff"] == pytest.approx(20.0)
    assert d["favours"] == "A"


def test_compare_severity_stable_beats_critical():
    r = compare_severity("STABLE", "CRITICAL")
    assert r["better"] == "A"
    assert r["same"] is False


def test_compare_severity_b_better():
    r = compare_severity("ELEVATED", "MARGINAL")
    assert r["better"] == "B"


def test_compare_severity_tie():
    r = compare_severity("STABLE", "STABLE")
    assert r["same"] is True
    assert r["better"] is None


def test_compare_severity_unknown_no_winner():
    r = compare_severity("STABLE", "UNKNOWN")
    assert r["better"] is None


def test_generate_delta_summary():
    full = compare_designs({}, {}, "X", "Y")
    assert generate_delta_summary(full) == full["summary"]


def test_reexports_match_comparison():
    from engine import comparison as _impl

    assert compare.compare_designs is _impl.compare_designs
    assert compare.COMPARISON_METRICS is _impl.COMPARISON_METRICS
    assert len(COMPARISON_METRICS) == len(_impl.COMPARISON_METRICS)
