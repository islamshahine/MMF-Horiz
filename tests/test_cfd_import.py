"""Tests for engine/cfd_import.py (C2 lite)."""
from engine.cfd_import import (
    build_cfd_import_comparison,
    compare_cfd_to_orifice_network,
    parse_cfd_results_csv,
)


def _model_rows():
    return [
        {"lateral_index": 1, "hole_index": 1, "velocity_m_s": 2.0, "flow_m3h": 10.0},
        {"lateral_index": 1, "hole_index": 2, "velocity_m_s": 2.5, "flow_m3h": 12.0},
    ]


def test_parse_cfd_csv():
    csv = (
        "lateral_index,hole_index,velocity_m_s\n"
        "1,1,2.1\n"
        "1,2,2.4\n"
    )
    rows, warns = parse_cfd_results_csv(csv)
    assert len(rows) == 2
    assert not warns
    assert rows[0]["velocity_m_s"] == 2.1


def test_compare_matched():
    cfd = [
        {"lateral_index": 1, "hole_index": 1, "velocity_m_s": 2.2},
        {"lateral_index": 1, "hole_index": 2, "velocity_m_s": 2.0},
    ]
    out = compare_cfd_to_orifice_network(cfd, _model_rows())
    assert out["enabled"] is True
    assert out["n_matched"] == 2
    assert out["max_abs_delta_velocity_pct"] is not None


def test_build_from_computed():
    csv = "lateral_index,hole_index,velocity_m_s\n1,1,2.0\n"
    computed = {"collector_hyd": {"orifice_network": _model_rows()}}
    out = build_cfd_import_comparison(csv, computed)
    assert out["n_matched"] >= 1
