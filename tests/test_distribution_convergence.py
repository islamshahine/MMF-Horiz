"""Distribution solver convergence flag must follow residual."""

from engine.collector_hydraulics import (
    DISTRIBUTION_TOL_REL,
    distribution_metadata_available,
    distribution_residual_rel,
    distribution_solver_converged,
    refresh_collector_distribution_metadata,
)


def test_converged_when_residual_zero():
    blob = {"distribution_residual_rel": 0.0}
    assert distribution_metadata_available(blob)
    assert distribution_residual_rel(blob) == 0.0
    assert distribution_solver_converged(blob) is True
    assert distribution_solver_converged({
        "distribution_residual_rel": 0.0,
        "distribution_converged": False,
    }) is True


def test_not_converged_when_residual_high():
    assert distribution_solver_converged({
        "distribution_residual_rel": DISTRIBUTION_TOL_REL + 0.01,
        "distribution_converged": True,
    }) is False


def test_legacy_blob_without_residual_is_not_converged():
    assert distribution_metadata_available({"maldistribution_factor_calc": 1.1}) is False
    assert distribution_residual_rel({"maldistribution_factor_calc": 1.1}) is None
    assert distribution_solver_converged({"maldistribution_factor_calc": 1.1}) is False


def test_refresh_fills_legacy_collector_hyd():
    inputs = {
        "bw_velocity": 30.0,
        "n_bw_laterals": 4,
        "lateral_dn_mm": 50.0,
        "collector_header_id_m": 0.59,
        "nozzle_plate_h": 1.0,
        "collector_h": 4.2,
        "np_bore_dia": 50.0,
        "np_density": 10.0,
    }
    computed = {
        "avg_area": 120.0,
        "q_per_filter": 1300.0,
        "cyl_len": 8.0,
        "nominal_id": 5.5,
        "rho_bw": 1000.0,
        "collector_hyd": {"maldistribution_factor_calc": 1.05},
    }
    refresh_collector_distribution_metadata(inputs, computed)
    ch = computed["collector_hyd"]
    assert distribution_metadata_available(ch)
    assert distribution_residual_rel(ch) is not None
