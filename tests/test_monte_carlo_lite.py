"""Tests for engine/monte_carlo_lite.py (Tier C1)."""
import copy

from engine.compute import compute_all
from engine.monte_carlo_lite import build_monte_carlo_cycle_lite
from engine.validators import REFERENCE_FALLBACK_INPUTS


def test_monte_carlo_lite_percentiles():
    out = compute_all(copy.deepcopy(REFERENCE_FALLBACK_INPUTS))
    mc = build_monte_carlo_cycle_lite(
        REFERENCE_FALLBACK_INPUTS,
        out,
        n_samples=80,
        seed=1,
    )
    assert mc["enabled"] is True
    pct = mc["percentiles_h"]
    assert pct["p10"] <= pct["p50"] <= pct["p90"]
    assert mc["n_samples_finite"] >= 10
    assert mc["histogram"]["counts"]


def test_monte_carlo_reproducible_seed():
    out = compute_all(copy.deepcopy(REFERENCE_FALLBACK_INPUTS))
    a = build_monte_carlo_cycle_lite(
        REFERENCE_FALLBACK_INPUTS, out, n_samples=60, seed=99,
    )
    b = build_monte_carlo_cycle_lite(
        REFERENCE_FALLBACK_INPUTS, out, n_samples=60, seed=99,
    )
    assert a["percentiles_h"] == b["percentiles_h"]


def test_monte_carlo_disabled_without_hydraulics():
    mc = build_monte_carlo_cycle_lite({}, {}, n_samples=100)
    assert mc["enabled"] is False
