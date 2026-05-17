"""Plotly figures for cycle uncertainty shaded bands (B4 — Filtration tab)."""
from __future__ import annotations

from typing import Any

from ui.helpers import dv, ulbl


def _try_import_go():
    import plotly.graph_objects as go

    return go


def figure_cycle_duration_band(
    *,
    optimistic_h: float,
    expected_h: float,
    conservative_h: float,
    title: str,
):
    """Horizontal shaded band for one scenario (optimistic–conservative cycle hours)."""
    go = _try_import_go()
    opt = dv(optimistic_h, "time_h")
    exp = dv(expected_h, "time_h")
    con = dv(conservative_h, "time_h")
    x_lo, x_hi = min(con, opt), max(con, opt)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=[x_lo, x_hi, x_hi, x_lo, x_lo],
            y=[-0.35, -0.35, 0.35, 0.35, -0.35],
            fill="toself",
            fillcolor="rgba(37, 99, 235, 0.22)",
            line=dict(width=0),
            name="Optimistic–conservative band",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[con, exp, opt],
            y=[0, 0, 0],
            mode="markers+text",
            marker=dict(
                size=[10, 14, 10],
                color=["#1a7a1a", "#2563eb", "#cc5500"],
            ),
            text=["Conservative", "Expected", "Optimistic"],
            textposition="top center",
            name="Corners",
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title=ulbl("time_h"),
        yaxis=dict(visible=False, range=[-0.8, 1.2]),
        height=280,
        margin=dict(t=48, b=40, l=24, r=24),
        showlegend=False,
    )
    return fig


def figure_scenario_cycle_bands(chart: dict[str, Any]):
    """Per-scenario cycle duration with asymmetric error bars (shaded band)."""
    go = _try_import_go()
    scenarios = chart.get("scenarios") or []
    opt = [dv(v, "time_h") for v in chart.get("cycle_optimistic_h") or []]
    exp = [dv(v, "time_h") for v in chart.get("cycle_expected_h") or []]
    con = [dv(v, "time_h") for v in chart.get("cycle_conservative_h") or []]
    plus = [max(0.0, o - e) for o, e in zip(opt, exp)]
    minus = [max(0.0, e - c) for e, c in zip(exp, con)]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=exp,
            y=scenarios,
            mode="markers",
            marker=dict(color="#2563eb", size=10),
            error_x=dict(
                type="data",
                symmetric=False,
                array=plus,
                arrayminus=minus,
                thickness=1.5,
                width=6,
                color="rgba(37, 99, 235, 0.45)",
            ),
            name="Expected ± band",
        )
    )
    fig.update_layout(
        title=f"Cycle duration by scenario — uncertainty band ({ulbl('time_h')})",
        xaxis_title=ulbl("time_h"),
        yaxis_title="Scenario",
        height=max(260, 52 * len(scenarios)),
        margin=dict(l=80, t=48, b=40),
    )
    return fig


def figure_dp_vs_loading_envelope(chart: dict[str, Any]):
    """ΔP_total vs solid loading with filled envelope between corners."""
    go = _try_import_go()
    m = chart.get("m_kg_m2") or []
    dp_opt = chart.get("dp_optimistic_bar") or []
    dp_exp = chart.get("dp_expected_bar") or []
    dp_con = chart.get("dp_conservative_bar") or []
    if not m or not dp_exp:
        return None

    x = [dv(v, "loading_kg_m2") for v in m]
    y_opt = [dv(v, "pressure_bar") for v in dp_opt]
    y_exp = [dv(v, "pressure_bar") for v in dp_exp]
    y_con = [dv(v, "pressure_bar") for v in dp_con]
    y_upper = [max(a, b) for a, b in zip(y_opt, y_con)]
    y_lower = [min(a, b) for a, b in zip(y_opt, y_con)]
    y_trig = dv(float(chart.get("dp_trigger_bar") or 0), "pressure_bar")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x + x[::-1],
            y=y_upper + y_lower[::-1],
            fill="toself",
            fillcolor="rgba(37, 99, 235, 0.18)",
            line=dict(width=0),
            name="Optimistic–conservative ΔP",
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y_exp,
            mode="lines+markers",
            line=dict(color="#2563eb", width=2.5),
            marker=dict(size=7),
            name="Expected",
        )
    )
    fig.add_hline(
        y=y_trig,
        line_dash="dash",
        line_color="#cc5500",
        annotation_text=f"BW trigger ({ulbl('pressure_bar')})",
        annotation_position="right",
    )
    fig.update_layout(
        title=f"ΔP vs solid loading — uncertainty envelope ({ulbl('pressure_bar')})",
        xaxis_title=ulbl("loading_kg_m2"),
        yaxis_title=ulbl("pressure_bar"),
        height=360,
        margin=dict(t=48, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig
