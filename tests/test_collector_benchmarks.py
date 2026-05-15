"""Regression benchmarks for collector 1A/1B — hand-calc style expectations."""

from engine.collector_benchmarks import (
    run_collector_benchmark_suite,
    suite_all_passed,
    check_collector_hyd_sanity,
    check_profile_flow_conservation,
)
from engine.collector_hydraulics import compute_collector_hydraulics


def test_benchmark_suite_all_pass():
    results = run_collector_benchmark_suite()
    assert len(results) >= 8
    failed = [r for r in results if not r["passed"]]
    assert not failed, failed


def test_suite_all_passed_helper():
    assert suite_all_passed()


def test_sanity_on_typical_output():
    out = compute_collector_hydraulics(
        q_bw_m3h=120.0,
        filter_area_m2=25.0,
        cyl_len_m=22.0,
        nominal_id_m=5.5,
        np_bore_dia_mm=50.0,
        np_density_per_m2=40.0,
        collector_header_id_m=0.25,
        n_laterals=6,
        lateral_dn_mm=50.0,
        lateral_spacing_m=3.0,
        lateral_length_m=2.5,
    )
    rows = check_collector_hyd_sanity(out)
    assert all(r["ok"] == "yes" for r in rows)


def test_flow_conservation_tight_tolerance():
    out = compute_collector_hydraulics(
        q_bw_m3h=150.0,
        filter_area_m2=28.0,
        cyl_len_m=22.0,
        nominal_id_m=5.5,
        np_bore_dia_mm=50.0,
        np_density_per_m2=45.0,
        collector_header_id_m=0.30,
        n_laterals=6,
        lateral_dn_mm=50.0,
        lateral_spacing_m=3.2,
        lateral_length_m=2.4,
    )
    ok, _ = check_profile_flow_conservation(out, rtol=0.01)
    assert ok
