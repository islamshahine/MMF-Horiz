"""Smoke tests for PDF report and mechanical drawing (optional deps)."""

from __future__ import annotations

import pytest

from engine.compute import compute_all
from engine.pdf_report import PDF_OK, build_pdf
from engine.validators import REFERENCE_FALLBACK_INPUTS


@pytest.mark.skipif(not PDF_OK, reason="reportlab not installed")
def test_build_pdf_process_section_bytes():
    inp = dict(REFERENCE_FALLBACK_INPUTS)
    out = compute_all(inp)
    sections = {"process": True, "design_basis": False}
    blob = build_pdf(inp, out, sections, unit_system="metric")
    assert isinstance(blob, bytes)
    assert len(blob) > 2000
    assert blob[:4] == b"%PDF"


def test_vessel_section_elevation_runs():
    matplotlib = pytest.importorskip("matplotlib")
    from engine.drawing import vessel_section_elevation

    layers = [
        {"Type": "Gravel", "Depth": 0.2, "is_support": True},
        {"Type": "Sand", "Depth": 0.5, "is_support": False},
    ]
    bw_exp = {"layers": [], "total_expansion_pct": 0.0, "total_expanded_m": 0.9}
    fig = vessel_section_elevation(
        vessel_id_m=3.0,
        total_length_m=12.0,
        h_dish_m=0.8,
        nozzle_plate_h_m=0.9,
        layers=layers,
        collector_h_m=1.2,
        bw_exp=bw_exp,
        show_expansion=False,
        figsize=(8, 4),
    )
    assert fig is not None
    matplotlib.pyplot.close(fig)
