"""Deterministic collector BW-flow envelope sweeps."""

from engine.collector_envelope import build_collector_bw_flow_envelope
from engine.collector_hydraulics import compute_collector_hydraulics


def _kwargs_no_q():
    return dict(
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
        nozzle_plate_h_m=1.0,
        collector_h_m=4.2,
        use_geometry_lateral=True,
        lateral_material="Stainless steel",
        lateral_construction="Drilled perforated pipe",
        max_open_area_fraction=0.0,
        wedge_slot_width_mm=0.0,
        wedge_open_area_fraction=0.0,
        bw_head_mwc=15.0,
        discharge_coefficient=0.62,
        rho_water=1000.0,
        header_feed_mode="one_end",
    )


def test_envelope_inactive_for_zero_reference():
    out = build_collector_bw_flow_envelope(
        compute_kwargs=_kwargs_no_q(),
        reference_q_bw_m3h=0.0,
    )
    assert out["active"] is False


def test_envelope_sorted_flows_and_includes_design():
    ref = 120.0
    env = build_collector_bw_flow_envelope(
        compute_kwargs=_kwargs_no_q(),
        reference_q_bw_m3h=ref,
        n_points=5,
        q_low_frac=0.8,
        q_high_frac=1.1,
    )
    assert env["active"] is True
    qs = env["q_bw_m3h"]
    assert qs == sorted(qs)
    assert any(abs(q - ref) < 0.02 for q in qs)
    assert len(qs) >= 3


def test_envelope_header_velocity_increases_with_flow():
    ref = 100.0
    env = build_collector_bw_flow_envelope(
        compute_kwargs=_kwargs_no_q(),
        reference_q_bw_m3h=ref,
        n_points=6,
        q_low_frac=0.75,
        q_high_frac=1.2,
    )
    hv = [x for x in env["header_velocity_max_m_s"] if x is not None]
    assert len(hv) >= 2
    assert hv[-1] >= hv[0] * 0.98


def test_envelope_matches_single_solve_at_reference():
    kw = _kwargs_no_q()
    ref = 95.0
    direct = compute_collector_hydraulics(q_bw_m3h=ref, **kw)
    env = build_collector_bw_flow_envelope(
        compute_kwargs=kw,
        reference_q_bw_m3h=ref,
        n_points=3,
        q_low_frac=0.99,
        q_high_frac=1.01,
    )
    row = next(r for r in env["sweep_rows"] if abs(r["q_bw_m3h"] - ref) < 0.1)
    assert row["flow_imbalance_pct"] is not None
    assert abs(row["header_velocity_max_m_s"] - float(direct["header_velocity_max_m_s"])) < 0.02
