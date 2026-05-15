"""Format design_basis bundle for PDF / Word report sections (no Streamlit)."""
from __future__ import annotations

from typing import Any


def plain_text(s: str) -> str:
    """Strip lightweight markdown used in assumption strings."""
    return str(s).replace("**", "")


def design_basis_meta_rows(basis: dict[str, Any]) -> list[list[str]]:
    proj = basis.get("project") or {}
    return [
        ["Schema", str(basis.get("schema_version", "—"))],
        ["Generated (UTC)", str(basis.get("generated_at_utc", "—"))],
        ["Reference document", str(basis.get("doc_reference", "—"))],
        ["Project", str(proj.get("name", "—"))],
        ["Document", str(proj.get("document", "—"))],
        ["Revision", str(proj.get("revision", "—"))],
        ["Client", str(proj.get("client", "—") or "—")],
        ["Engineer", str(proj.get("engineer", "—") or "—")],
    ]


def traceability_table_rows(basis: dict[str, Any]) -> list[list[str]]:
    header = ["Output", "Value", "Unit", "Source", "Doc §"]
    rows: list[list[str]] = [header]
    for t in basis.get("traceability") or []:
        val = t.get("value_si", t.get("value", ""))
        rows.append([
            str(t.get("output", "")),
            str(val),
            str(t.get("unit", "")),
            str(t.get("source", "")),
            str(t.get("doc_section", "")),
        ])
    return rows


def collector_summary_rows(collector: dict[str, Any]) -> list[list[str]]:
    if not collector:
        return []
    dist = collector.get("distribution") or {}
    screen = collector.get("screening") or {}
    conv = dist.get("converged")
    conv_s = "Yes" if conv is True else ("No" if conv is False else "—")
    rows = [
        ["Method", str(collector.get("method", "—"))],
        ["Maldistribution (calc.)", str(collector.get("maldistribution_factor_calc", "—"))],
        ["Flow imbalance", f"{collector.get('flow_imbalance_pct', '—')} %"],
        ["Distribution iterations", str(dist.get("iterations", "—"))],
        ["Distribution converged", conv_s],
        ["Distribution residual (rel.)", str(dist.get("residual_rel", "—"))],
        ["Lateral DN (screening)", f"{screen.get('lateral_dn_suggest_mm', '—')} mm"],
        ["Perforation Ø (screening)", f"{screen.get('perforation_d_suggest_mm', '—')} mm"],
        ["Laterals (screening)", str(screen.get("n_laterals_suggested", "—"))],
    ]
    return rows
