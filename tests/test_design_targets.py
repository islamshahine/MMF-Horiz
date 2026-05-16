"""Tests for engine.design_targets — target caps + grid search."""
from __future__ import annotations

import copy

import pytest

from engine.design_targets import (
    build_design_targets_summary,
    metrics_from_computed,
    normalize_targets,
    search_design_targets,
    target_violations,
    targets_active,
)
from engine.compute import compute_all
from tests.test_integration import _INPUTS


@pytest.fixture
def base():
    return copy.deepcopy(_INPUTS)


def test_normalize_targets_empty():
    t = normalize_targets({})
    assert targets_active(t) is False


def test_target_violations_lcow():
    t = normalize_targets({"max_lcow_usd_m3": 0.01})
    v = target_violations({"lcow_usd_m3": 0.05}, t)
    assert "target_lcow_exceeded" in v


def test_build_summary_disabled_without_targets(base):
    c = compute_all(base)
    s = build_design_targets_summary(base, c, targets={})
    assert s["enabled"] is False


def test_build_summary_baseline(base):
    c = compute_all(base)
    lcow = float((c.get("econ_bench") or {}).get("lcow", 0.1))
    targets = {"max_lcow_usd_m3": lcow * 10.0, "max_dp_dirty_bar": 100.0, "max_q_bw_m3h": 1.0e5}
    s = build_design_targets_summary(base, c, targets=targets)
    assert s["enabled"] is True
    assert s["baseline"]["meets_targets"] is True
    assert s["baseline"]["metrics"]["lcow_usd_m3"] == pytest.approx(lcow, rel=1e-3)


def test_search_finds_feasible_candidates(base):
    c = compute_all(base)
    lcow = float((c.get("econ_bench") or {}).get("lcow", 0.05))
    nf = int(base["n_filters"])
    out = search_design_targets(
        base,
        {
            "max_lcow_usd_m3": lcow * 2.0,
            "max_dp_dirty_bar": 100.0,
            "max_q_bw_m3h": 1.0e5,
        },
        {"n_filters": list(range(max(4, nf - 2), nf + 3))},
        top_k=3,
    )
    assert out["enabled"] is True
    assert out["evaluated"] >= 3
    assert out["meets_targets_count"] >= 1
    assert out["best"] is not None


def test_metrics_from_computed_keys(base):
    c = compute_all(base)
    m = metrics_from_computed(c)
    assert m["lcow_usd_m3"] > 0
    assert m["dp_dirty_bar"] >= 0
    assert m["q_bw_m3h"] >= 0
