"""On-demand staged orifice cache helpers."""

from ui.collector_staged_cache import staged_model_fingerprint


def test_staged_fingerprint_stable():
    work = {"nozzle_plate_h": 1.0, "collector_h": 4.0}
    computed = {
        "avg_area": 28.0,
        "cyl_len": 20.0,
        "nominal_id": 5.0,
        "q_per_filter": 12.0,
        "collector_hyd": {
            "orifice_network": [{"q": 1.0}],
            "lateral_orifice_d_mm": 8.0,
        },
    }
    a = staged_model_fingerprint(work, computed, 3)
    b = staged_model_fingerprint(work, computed, 3)
    assert a == b
    assert staged_model_fingerprint(work, computed, 2) != a
