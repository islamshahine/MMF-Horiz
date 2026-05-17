"""Collector envelope kwargs / fingerprint helpers."""

from ui.collector_envelope_cache import (
    collector_compute_kwargs,
    envelope_model_fingerprint,
    reference_q_bw_m3h,
)


def test_reference_q_bw_uses_area_and_velocity():
    work = {"bw_velocity": 30.0}
    computed = {"avg_area": 10.0, "q_per_filter": 5.0}
    q = reference_q_bw_m3h(work, computed)
    assert q >= 30.0 * 10.0


def test_collector_kwargs_match_compute_shape():
    work = {
        "nozzle_plate_h": 1.0,
        "collector_h": 4.0,
        "n_bw_laterals": 6,
        "lateral_dn_mm": 50.0,
        "bw_temp": 25.0,
        "bw_sal": 35.0,
    }
    computed = {"avg_area": 28.0, "cyl_len": 20.0, "nominal_id": 5.0}
    kw = collector_compute_kwargs(work, computed)
    assert kw["filter_area_m2"] == 28.0
    assert kw["n_laterals"] == 6
    assert kw["rho_water"] > 900.0


def test_fingerprint_stable_for_same_inputs():
    work = {
        "nozzle_plate_h": 1.0,
        "collector_h": 4.0,
        "bw_velocity": 30.0,
        "bw_temp": 25.0,
        "bw_sal": 35.0,
    }
    computed = {"avg_area": 28.0, "cyl_len": 20.0, "nominal_id": 5.0, "q_per_filter": 12.0}
    assert envelope_model_fingerprint(work, computed) == envelope_model_fingerprint(work, computed)
