"""Collector 1B+ — dual-end feed and CFD export."""

from engine.collector_cfd_export import (
    build_collector_cfd_bundle,
    build_cfd_export_bytes,
    normalize_cfd_export_format,
    orifice_network_to_csv,
)
from engine.collector_hydraulics import compute_collector_hydraulics
from engine.collector_manifold import (
    compare_feed_modes,
    solve_lateral_distribution_dual_end,
    solve_lateral_distribution_one_end,
)


def _base_kw():
    return dict(
        q_bw_m3h=120.0,
        filter_area_m2=28.0,
        cyl_len_m=22.0,
        nominal_id_m=5.5,
        np_bore_dia_mm=50.0,
        np_density_per_m2=45.0,
        collector_header_id_m=0.2,
        n_laterals=8,
        lateral_dn_mm=50.0,
        lateral_spacing_m=2.5,
        lateral_length_m=2.0,
        lateral_orifice_d_mm=8.0,
        n_orifices_per_lateral=6,
    )


def test_dual_end_produces_comparison():
    one = compute_collector_hydraulics(**_base_kw(), header_feed_mode="one_end")
    dual = compute_collector_hydraulics(**_base_kw(), header_feed_mode="dual_end")
    assert one["header_feed_mode"] == "one_end"
    assert dual["header_feed_mode"] == "dual_end"
    assert dual.get("feed_mode_comparison")
    assert len(dual.get("orifice_network") or []) >= 8


def test_orifice_network_and_cfd_bundle():
    out = compute_collector_hydraulics(**_base_kw())
    inputs = {"project_name": "T", "feed_temp": 25, "collector_header_feed_mode": "one_end"}
    computed = {
        "collector_hyd": out,
        "cyl_len": 22.0,
        "nominal_id": 5.5,
        "rho_bw": 1000.0,
        "mu_bw": 0.001,
    }
    bundle = build_collector_cfd_bundle(inputs, computed, export_timestamp_utc="2026-01-01T00:00:00Z")
    assert bundle["schema_version"].startswith("aquasight.collector_cfd")
    assert len(bundle["boundaries"]) >= 1
    data, fname, mime = build_cfd_export_bytes(bundle, "json")
    assert b"disclaimer" in data
    assert fname.endswith(".json")
    csv_bytes, _, _ = build_cfd_export_bytes(bundle, "csv_orifices")
    assert b"lateral_index" in csv_bytes


def test_cfd_export_format_normalizes_display_strings():
    assert normalize_cfd_export_format("json") == "json"
    assert normalize_cfd_export_format("JSON (full BC bundle)") == "json"
    assert normalize_cfd_export_format("CSV (orifice table only)") == "csv_orifices"


def test_build_cfd_export_accepts_legacy_ui_label():
    bundle = {"orifice_network": [{"lateral_index": 1, "hole_index": 1}]}
    data, fname, mime = build_cfd_export_bytes(bundle, "JSON (full BC bundle)")
    assert b"orifice_network" in data
    assert fname.endswith(".json")
def test_one_end_solver_converges():
    pos = [2.0, 4.0, 6.0, 8.0]
    segs = [2.0, 2.0, 2.0, 2.0]
    q, it, res, ok = solve_lateral_distribution_one_end(
        q_total_m3_s=0.05,
        positions_m=pos,
        segment_lengths_m=segs,
        d_header_m=0.2,
        d_lat_m=0.05,
        l_lat_m=1.5,
        n_orifices=4,
        friction_factor=0.02,
        headloss_factor=1.0,
        rho=1000.0,
    )
    assert len(q) == 4
    assert abs(sum(q) - 0.05) < 1e-6
    assert res < 0.01


def test_compare_feed_modes():
    cmp = compare_feed_modes([0.01, 0.012, 0.014, 0.016], [0.01, 0.011, 0.012, 0.013])
    assert "one_end" in cmp and "dual_end" in cmp
