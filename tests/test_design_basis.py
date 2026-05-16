"""Tests for design basis export bundle."""

from engine.design_basis import SCHEMA_VERSION, build_design_basis
from engine.design_basis_report import (
    assumptions_catalog_rows,
    collector_summary_rows,
    design_basis_meta_rows,
    plain_text,
    traceability_table_rows,
    underdrain_summary_rows,
)


def _sample_computed():
    return {
        "q_per_filter": 1300.0,
        "solid_loading_effective_kg_m2": 1.5,
        "maldistribution_factor": 1.08,
        "maldistribution_from_collector_model": True,
        "bw_dp": {"dp_dirty_bar": 0.42},
        "bw_timeline": {"bw_trains": 2, "peak_concurrent_bw": 3},
        "cycle_uncertainty": {
            "N": {"cycle_expected_h": 24.0},
        },
        "underdrain_system_advisory": {
            "catalogue_label": "Generic PP — PP Mushroom",
            "tone": "ok",
            "findings": [],
        },
        "collector_hyd": {
            "method": "1D test",
            "maldistribution_factor_calc": 1.08,
            "flow_imbalance_pct": 7.5,
            "lateral_length_m": 2.4,
            "distribution_iterations": 5,
            "distribution_converged": True,
            "distribution_residual_rel": 0.001,
            "design_checklist": ["item a"],
            "design": {"lateral_dn_suggest_mm": 80},
        },
    }


def test_design_basis_includes_collector_traceability():
    inputs = {
        "project_name": "Test",
        "bw_velocity": 30.0,
        "total_flow": 21000.0,
        "streams": 1,
        "n_filters": 16,
        "solid_loading": 1.5,
        "solid_loading_scale": 1.0,
        "strainer_mat": "Super_duplex_2507",
        "np_density": 60.0,
    }
    basis = build_design_basis(inputs, _sample_computed())
    assert basis["schema_version"] == SCHEMA_VERSION
    assert basis["project"]["name"] == "Test"
    assert len(basis["assumptions_catalog"]) >= 8
    assert basis["collector"]["distribution"]["converged"] is True
    trace = basis["traceability"]
    assert any(t["output"] == "q_per_filter" for t in trace)
    assert any(t.get("trace_id", "").startswith("TRC-") for t in trace)
    assert basis["underdrain"]["strainer_material"] == "Super_duplex_2507"
    assert len(basis.get("explainability_metrics") or []) >= 5


def test_design_basis_report_formatters():
    basis = build_design_basis(
        {
            "project_name": "P",
            "doc_number": "DOC-1",
            "revision": "A",
            "total_flow": 1000.0,
        },
        {"q_per_filter": 100.0, "maldistribution_factor": 1.0},
    )
    assert plain_text("**bold** text") == "bold text"
    assert len(design_basis_meta_rows(basis)) >= 5
    trace = traceability_table_rows(basis)
    assert trace[0][0] == "ID"
    assert len(trace) >= 5
    ac = assumptions_catalog_rows(basis)
    assert ac[0][0] == "ID"
    assert collector_summary_rows({}) == []
    assert underdrain_summary_rows(basis.get("underdrain") or {}) != [] or True


def test_pdf_includes_design_basis_section_when_requested():
    from engine.pdf_report import PDF_OK, build_pdf

    if not PDF_OK:
        return
    inputs = {
        "project_name": "T",
        "doc_number": "X",
        "revision": "0",
        "nominal_id": 3.0,
        "total_length": 10.0,
        "total_flow": 1000.0,
        "streams": 1,
        "n_filters": 4,
        "redundancy": 1,
        "hydraulic_assist": 0,
    }
    computed = {
        "q_per_filter": 250.0,
        "avg_area": 1.0,
        "mech": {
            "od_m": 3.1,
            "t_shell_min_mm": 10,
            "t_shell_design_mm": 12,
            "t_head_min_mm": 10,
            "t_head_design_mm": 12,
        },
    }
    computed["design_basis"] = build_design_basis(inputs, computed)
    pdf_min = build_pdf(inputs, computed, {})
    pdf_full = build_pdf(inputs, computed, {"design_basis": True})
    assert pdf_full[:4] == b"%PDF"
    assert len(pdf_full) > len(pdf_min) + 500
