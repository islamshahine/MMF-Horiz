"""Tests for 1D collector / lateral hydraulics."""

from engine.collector_hydraulics import compute_collector_hydraulics


def test_collector_hyd_zero_flow_defaults_mal_one():
    out = compute_collector_hydraulics(
        q_bw_m3h=0.0,
        filter_area_m2=20.0,
        cyl_len_m=20.0,
        nominal_id_m=5.5,
        np_bore_dia_mm=50.0,
        np_density_per_m2=50.0,
        collector_header_id_m=0.25,
        n_laterals=4,
        lateral_dn_mm=50.0,
    )
    assert out["maldistribution_factor_calc"] == 1.0
    assert out["profile"] == []


def test_collector_hyd_mal_at_least_one_with_flow():
    out = compute_collector_hydraulics(
        q_bw_m3h=120.0,
        filter_area_m2=25.0,
        cyl_len_m=22.0,
        nominal_id_m=5.5,
        np_bore_dia_mm=50.0,
        np_density_per_m2=40.0,
        collector_header_id_m=0.15,
        n_laterals=6,
        lateral_dn_mm=40.0,
        lateral_spacing_m=3.0,
        lateral_length_m=2.5,
    )
    assert out["maldistribution_factor_calc"] >= 1.0
    assert out["distribution_iterations"] >= 1
    assert out["distribution_converged"] is True
    assert out["distribution_residual_rel"] < 0.01
    assert len(out["profile"]) == 6
    assert out["flow_imbalance_pct"] >= 0.0


def test_collector_hyd_smaller_header_raises_mal():
    loose = compute_collector_hydraulics(
        q_bw_m3h=200.0,
        filter_area_m2=30.0,
        cyl_len_m=24.0,
        nominal_id_m=5.5,
        np_bore_dia_mm=50.0,
        np_density_per_m2=50.0,
        collector_header_id_m=0.35,
        n_laterals=8,
        lateral_dn_mm=50.0,
    )
    tight = compute_collector_hydraulics(
        q_bw_m3h=200.0,
        filter_area_m2=30.0,
        cyl_len_m=24.0,
        nominal_id_m=5.5,
        np_bore_dia_mm=50.0,
        np_density_per_m2=50.0,
        collector_header_id_m=0.12,
        n_laterals=8,
        lateral_dn_mm=50.0,
    )
    assert tight["maldistribution_factor_calc"] >= loose["maldistribution_factor_calc"]


def test_perforations_auto_not_nozzle_plate_split():
    """Auto count uses lateral length pitch, not nozzle-plate holes / N laterals."""
    out = compute_collector_hydraulics(
        q_bw_m3h=100.0,
        filter_area_m2=111.0,
        cyl_len_m=24.0,
        nominal_id_m=5.5,
        np_bore_dia_mm=50.0,
        np_density_per_m2=50.0,
        collector_header_id_m=0.25,
        n_laterals=10,
        lateral_dn_mm=50.0,
        lateral_length_m=2.5,
        n_orifices_per_lateral=0,
    )
    n_plate = int(out["nozzle_plate_holes_ref"])
    n_per_lat = int(out["n_orifices_per_lateral"])
    assert n_plate > 1000
    assert n_per_lat < 100
    assert int(out["n_orifices_total"]) == n_per_lat * 10
    assert n_per_lat != n_plate // 10
