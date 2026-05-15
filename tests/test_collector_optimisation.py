"""Tests for collector 1D grid optimiser."""

from engine.collector_optimisation import optimise_collector_design


def _base_ctx():
    return {
        "q_bw_m3h": 3331.0,
        "filter_area_m2": 120.0,
        "cyl_len_m": 22.0,
        "nominal_id_m": 5.5,
        "np_bore_dia_mm": 50.0,
        "np_density_per_m2": 10.0,
        "collector_header_id_m": 0.788,
        "n_bw_laterals": 4,
        "lateral_dn_mm": 50.0,
        "nozzle_plate_h_m": 1.0,
        "collector_h_m": 4.2,
        "use_geometry_lateral": True,
        "lateral_material": "Stainless steel",
        "lateral_construction": "Drilled perforated pipe",
    }


def test_optimise_returns_patch():
    out = optimise_collector_design(_base_ctx())
    assert out["ok"] is True
    assert out["candidates_evaluated"] >= 1
    assert "n_bw_laterals" in out["patch"]
    assert out["collector_hyd"].get("maldistribution_factor_calc", 0) >= 1.0


def test_optimise_zero_flow_fails():
    ctx = _base_ctx()
    ctx["q_bw_m3h"] = 0.0
    out = optimise_collector_design(ctx)
    assert out["ok"] is False
