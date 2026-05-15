"""Tests for design basis export bundle."""

from engine.design_basis import build_design_basis
from engine.design_basis_report import (
    collector_summary_rows,
    design_basis_meta_rows,
    plain_text,
    traceability_table_rows,
)


def test_design_basis_includes_collector_traceability():
    inputs = {"project_name": "Test", "bw_velocity": 30.0}
    computed = {
        "q_per_filter": 1300.0,
        "maldistribution_factor": 1.08,
        "maldistribution_from_collector_model": True,
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
    basis = build_design_basis(inputs, computed)
    assert basis["schema_version"] == "1.0"
    assert basis["project"]["name"] == "Test"
    assert len(basis["assumptions"]) >= 3
    assert basis["collector"]["distribution"]["converged"] is True
    assert any(t["output"] == "q_per_filter" for t in basis["traceability"])


def test_design_basis_report_formatters():
    basis = build_design_basis(
        {"project_name": "P", "doc_number": "DOC-1", "revision": "A"},
        {"q_per_filter": 100.0, "maldistribution_factor": 1.0},
    )
    assert plain_text("**bold** text") == "bold text"
    assert len(design_basis_meta_rows(basis)) >= 5
    trace = traceability_table_rows(basis)
    assert trace[0][0] == "Output"
    assert len(trace) >= 2
    assert collector_summary_rows({}) == []


def test_pdf_includes_design_basis_section_when_requested():
    from engine.pdf_report import PDF_OK, build_pdf

    if not PDF_OK:
        return
    inputs = {"project_name": "T", "doc_number": "X", "revision": "0", "nominal_id": 3.0,
              "total_length": 10.0, "total_flow": 1000.0, "streams": 1, "n_filters": 4,
              "redundancy": 1, "hydraulic_assist": 0}
    computed = {
        "q_per_filter": 250.0,
        "avg_area": 1.0,
        "mech": {"od_m": 3.1, "t_shell_min_mm": 10, "t_shell_design_mm": 12,
                 "t_head_min_mm": 10, "t_head_design_mm": 12},
        "design_basis": build_design_basis(inputs, {"q_per_filter": 250.0}),
    }
    pdf_min = build_pdf(inputs, computed, {})
    pdf_full = build_pdf(inputs, computed, {"design_basis": True})
    assert pdf_full[:4] == b"%PDF"
    assert len(pdf_full) > len(pdf_min) + 500
