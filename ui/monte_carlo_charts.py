"""Plotly charts for Monte Carlo lite (C1)."""
from __future__ import annotations

from typing import Any

from ui.helpers import dv, ulbl


def figure_cycle_duration_histogram(mc: dict[str, Any]):
    import plotly.graph_objects as go

    hist = mc.get("histogram") or {}
    edges = hist.get("bin_edges_h") or []
    counts = hist.get("counts") or []
    if not edges or not counts or len(edges) < 2:
        return None

    x_centers = []
    for i in range(len(counts)):
        x_centers.append(dv((edges[i] + edges[i + 1]) / 2.0, "time_h"))

    pct = mc.get("percentiles_h") or {}
    fig = go.Figure(
        data=[
            go.Bar(
                x=x_centers,
                y=counts,
                marker_color="rgba(37, 99, 235, 0.65)",
                name="Sample count",
            )
        ]
    )
    for label, key, color in (
        ("P10", "p10", "#1a7a1a"),
        ("P50", "p50", "#2563eb"),
        ("P90", "p90", "#cc5500"),
    ):
        v = pct.get(key)
        if v is not None:
            fig.add_vline(
                x=dv(float(v), "time_h"),
                line_dash="dash",
                line_color=color,
                annotation_text=label,
            )
    det = mc.get("deterministic_envelope_h") or {}
    for label, key, color in (
        ("Det. opt.", "optimistic", "#1a7a1a"),
        ("Det. exp.", "expected", "#6366f1"),
        ("Det. con.", "conservative", "#cc5500"),
    ):
        v = det.get(key)
        if v is not None:
            fig.add_vline(
                x=dv(float(v), "time_h"),
                line_dash="dot",
                line_color=color,
                line_width=1,
                annotation_text=label,
            )
    fig.update_layout(
        title=f"Monte Carlo cycle duration — N scenario ({ulbl('time_h')})",
        xaxis_title=ulbl("time_h"),
        yaxis_title="Count",
        height=340,
        margin=dict(t=48, b=40),
        bargap=0.05,
    )
    return fig
