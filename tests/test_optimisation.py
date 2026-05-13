"""Tests for engine/optimisation.py — constraints + grid ranking via compute_all."""
import copy

import pytest

from engine.optimisation import constraint_check, evaluate_candidate, optimise_design
from tests.test_integration import _INPUTS


@pytest.fixture
def base():
    return copy.deepcopy(_INPUTS)


def test_reference_design_feasible_under_default_constraints(base):
    from engine.compute import compute_all

    c = compute_all(base)
    r = constraint_check(c, base, None)
    assert r["feasible"] is True


def test_low_n_filters_infeasible_lv(base):
    from engine.compute import compute_all

    bad = copy.deepcopy(base)
    bad["n_filters"] = 10
    c = compute_all(bad)
    r = constraint_check(c, bad, None)
    assert r["feasible"] is False
    assert "lv_exceeds_threshold" in r["violations"]


def test_strict_dp_constraint_can_fail(base):
    from engine.compute import compute_all

    c = compute_all(base)
    r = constraint_check(c, base, {"max_dp_dirty_bar": 1.0})
    assert r["feasible"] is False
    assert "dp_dirty_exceeds_cap" in r["violations"]


def test_tight_steel_cap_infeasible(base):
    from engine.compute import compute_all

    c = compute_all(base)
    w = float(c["w_total"])
    r = constraint_check(c, base, {"max_steel_kg": w * 0.5})
    assert r["feasible"] is False
    assert "steel_weight_exceeds_cap" in r["violations"]


def test_optimise_prefers_lower_capex_among_feasible(base):
    patches = [
        {"n_filters": 16},
        {"n_filters": 18},
        {"n_filters": 20},
        {"n_filters": 8},
    ]
    out = optimise_design(base, patches, objective="capex", top_k=3)
    assert out["feasible_count"] == 3
    assert len(out["top"]) == 3
    caps = [row["metrics"]["total_capex_usd"] for row in out["top"]]
    assert caps == sorted(caps)
    assert out["top"][0]["patch"]["n_filters"] == 16
    assert out["top"][-1]["patch"]["n_filters"] == 20


def test_evaluate_candidate_returns_metrics(base):
    ev = evaluate_candidate(base)
    assert ev["feasible"] is True
    assert ev["metrics"]["total_capex_usd"] > 0
    assert ev["metrics"]["steel_kg"] > 0
