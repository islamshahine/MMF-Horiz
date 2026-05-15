"""Multi-case compare workspace."""

import copy

import pytest

from engine.compare_workspace import (
    MAX_COMPARE_CASES,
    compare_many_designs,
    snapshot_case_inputs,
)
from engine.compute import compute_all
from tests.test_integration import _INPUTS


def test_snapshot_case():
    c = snapshot_case_inputs(_INPUTS, label="Base")
    assert c["label"] == "Base"
    assert c["inputs"]["total_flow"] == _INPUTS["total_flow"]


def test_compare_many_requires_two():
    with pytest.raises(ValueError):
        compare_many_designs([("A", {})])


def test_compare_many_two_cases():
    a = compute_all(copy.deepcopy(_INPUTS))
    b_inp = copy.deepcopy(_INPUTS)
    b_inp["n_filters"] = 20
    b = compute_all(b_inp)
    out = compare_many_designs([("Design 1", a), ("Design 2", b)])
    assert out["n_cases"] == 2
    assert len(out["metrics"]) == len(out["labels"]) or len(out["metrics"]) > 0
    assert out["labels"] == ["Design 1", "Design 2"]
    q_row = next(r for r in out["metrics"] if "Flow" in r["metric"])
    assert q_row["Design 1"] != q_row["Design 2"]


def test_max_cases_constant():
    assert MAX_COMPARE_CASES == 4
