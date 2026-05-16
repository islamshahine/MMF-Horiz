"""Multi-case compare workspace."""

import copy

import pytest

from engine.compare_workspace import (
    COMPARE_TABLE_PAGE_SIZE,
    MAX_COMPARE_SELECTION,
    MAX_LIBRARY_CASES,
    compare_many_designs,
    slice_compare_result,
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
    assert len(out["metrics"]) > 0
    assert out["labels"] == ["Design 1", "Design 2"]
    q_row = next(r for r in out["metrics"] if "Flow" in r["metric"])
    assert q_row["Design 1"] != q_row["Design 2"]


def test_compare_many_five_cases():
    cases = []
    for i in range(5):
        inp = copy.deepcopy(_INPUTS)
        inp["n_filters"] = 8 + i
        cases.append((f"Case {i + 1}", compute_all(inp)))
    out = compare_many_designs(cases)
    assert out["n_cases"] == 5
    assert out["n_pages"] == 2
    assert len(out["labels"]) == 5


def test_compare_many_rejects_over_cap():
    cases = [("A", {}), ("B", {}), ("C", {}), ("D", {}), ("E", {}), ("F", {}), ("G", {})]
    cases += [("H", {}), ("I", {}), ("J", {}), ("K", {}), ("L", {}), ("M", {})]
    with pytest.raises(ValueError, match=str(MAX_COMPARE_SELECTION)):
        compare_many_designs(cases)


def test_slice_compare_result_pages():
    a = compute_all(copy.deepcopy(_INPUTS))
    b_inp = copy.deepcopy(_INPUTS)
    b_inp["n_filters"] = 20
    b = compute_all(b_inp)
    c_inp = copy.deepcopy(_INPUTS)
    c_inp["n_filters"] = 12
    c = compute_all(c_inp)
    d_inp = copy.deepcopy(_INPUTS)
    d_inp["n_filters"] = 16
    d = compute_all(d_inp)
    full = compare_many_designs([("A", a), ("B", b), ("C", c), ("D", d), ("E", a)])
    p0 = slice_compare_result(full, 0, page_size=COMPARE_TABLE_PAGE_SIZE)
    p1 = slice_compare_result(full, 1, page_size=COMPARE_TABLE_PAGE_SIZE)
    assert len(p0["labels"]) == 4
    assert len(p1["labels"]) == 1
    assert p0["page"] == 0
    assert p1["page"] == 1
    assert p0["all_labels"] == full["labels"]


def test_limits_constants():
    assert MAX_LIBRARY_CASES >= MAX_COMPARE_SELECTION
    assert MAX_COMPARE_SELECTION >= 4
    assert COMPARE_TABLE_PAGE_SIZE == 4
