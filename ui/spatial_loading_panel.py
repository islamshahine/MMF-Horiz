"""Shared Voronoi nozzle loading map — Backwash and Filtration tabs."""
from __future__ import annotations

import streamlit as st

from ui.helpers import fmt, ulbl


def spatial_plot_sample(
    xy: list,
    lf: list,
    *,
    max_points: int = 1500,
) -> tuple[list, list]:
    """
    Downsample for Plotly without stripe artefacts.

    Global stride on brick/staggered hole order picks alternating rows
    and looks like a red/green checkerboard — not a change in the Voronoi model.
    """
    n = min(len(xy), len(lf))
    if n <= max_points:
        return xy[:n], lf[:n]
    from collections import defaultdict

    by_row: dict[float, list[int]] = defaultdict(list)
    for i in range(n):
        by_row[round(float(xy[i][1]), 3)].append(i)
    per_row = max(1, max_points // max(1, len(by_row)))
    picked: list[int] = []
    for _y in sorted(by_row.keys()):
        idxs = by_row[_y]
        if len(idxs) <= per_row:
            picked.extend(idxs)
        else:
            step = max(1, len(idxs) // per_row)
            picked.extend(idxs[::step])
    if len(picked) > max_points:
        picked = picked[:: max(1, len(picked) // max_points)]
    picked = sorted(set(picked))[:max_points]
    return [xy[i] for i in picked], [lf[i] for i in picked]


def spatial_loading_color_limits(lf: list[float]) -> tuple[float, float]:
    """Color scale centred on LF=1; wide enough for true outliers (e.g. edge holes)."""
    if not lf:
        return 0.85, 1.15
    lo = min(lf)
    hi = max(lf)
    span = max(hi - lo, 0.12)
    pad = max(0.08, 0.12 * span)
    cmin = min(0.85, lo - pad)
    cmax = max(1.15, hi + pad)
    if cmax - cmin < 0.2:
        mid = (hi + lo) / 2.0
        cmin, cmax = mid - 0.1, mid + 0.1
    return cmin, cmax


def spatial_loading_figure(
    xy: list,
    lf: list[float],
    np_plate: dict,
    *,
    cmin: float,
    cmax: float,
    phase_title: str = "Backwash",
) -> "go.Figure":
    """Voronoi LF markers on top of full plate outline (both dish heads)."""
    import plotly.graph_objects as go

    fig = go.Figure()
    ol_x = list(np_plate.get("plate_outline_x_m") or [])
    ol_top = list(np_plate.get("plate_outline_y_top_m") or [])
    ol_bot = list(np_plate.get("plate_outline_y_bot_m") or [])
    if len(ol_x) >= 2 and len(ol_top) == len(ol_x) and len(ol_bot) == len(ol_x):
        fig.add_trace(
            go.Scatter(
                x=ol_x + ol_x[::-1],
                y=ol_top + ol_bot[::-1],
                fill="toself",
                mode="lines",
                line=dict(color="#64748b", width=1.2),
                fillcolor="rgba(148, 163, 184, 0.18)",
                name="Nozzle plate outline (both heads)",
                hoverinfo="skip",
            )
        )
    x_cyl0 = float(np_plate.get("x_cyl_start_m") or 0)
    x_cyl1 = float(np_plate.get("x_cyl_end_m") or 0)
    l_plate = float(
        np_plate.get("total_length_m") or np_plate.get("cyl_len_m") or 0
    )
    w_chord = float(np_plate.get("chord_m") or 0)
    if x_cyl1 > x_cyl0 and w_chord > 0:
        for _xv, _lbl in ((x_cyl0, "Cyl start"), (x_cyl1, "Cyl end")):
            fig.add_shape(
                type="line",
                x0=_xv,
                x1=_xv,
                y0=-w_chord / 2 - 0.04 * w_chord,
                y1=w_chord / 2 + 0.04 * w_chord,
                line=dict(color="#94a3b8", width=1, dash="dot"),
                layer="below",
            )
    fig.add_trace(
        go.Scatter(
            x=[p[0] for p in xy],
            y=[p[1] for p in xy],
            mode="markers",
            marker=dict(
                size=9,
                color=lf,
                colorscale="RdYlGn_r",
                cmin=cmin,
                cmax=cmax,
                colorbar=dict(title="Loading factor"),
            ),
            text=[f"LF={lf[i]:.2f}" for i in range(len(lf))],
            hovertemplate="x %{x:.2f} m<br>y %{y:.2f} m<br>%{text}<extra></extra>",
            name="Loading factor",
        )
    )
    _x_pad = max(0.08 * l_plate, 0.4) if l_plate > 0 else 0.4
    _y_pad = max(0.12 * w_chord, 0.25) if w_chord > 0 else 0.25
    fig.update_layout(
        title=f"Nozzle loading factor — {phase_title} (plan view, SI m)",
        xaxis_title="Along drum (m)",
        yaxis_title="Across chord (m)",
        height=400,
        margin=dict(t=48, b=40),
        xaxis=dict(
            range=[-_x_pad, l_plate + _x_pad] if l_plate > 0 else None,
        ),
        yaxis=dict(
            range=[-w_chord / 2 - _y_pad, w_chord / 2 + _y_pad] if w_chord > 0 else None,
            scaleanchor="x",
            scaleratio=1,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def render_spatial_loading_panel(
    spatial: dict,
    np_plate: dict,
    *,
    chart_key: str,
    phase_label: str = "backwash",
    expanded: bool = False,
    in_expander: bool = True,
) -> None:
    """Metrics + Plotly map for ``spatial_distribution`` or ``spatial_distribution_filtration``."""
    if not spatial.get("enabled"):
        return

    _phase_title = "Filtration service" if phase_label == "filtration" else "Backwash"
    _exp_title = (
        "Spatial hydraulic loading — Voronoi map (filtration service)"
        if phase_label == "filtration"
        else "Spatial hydraulic loading — Voronoi map"
    )

    def _body() -> None:
        st.caption(spatial.get("note", ""))
        if phase_label == "filtration":
            st.caption(
                f"**Q basis:** {spatial.get('flow_basis_note', 'filtration q_per_filter')} — "
                f"lumped split of **{fmt(spatial.get('q_basis_m3h'), 'flow_m3h', 1)}** "
                f"across Voronoi service areas (not bed channeling or RTD)."
            )
        u1, u2, u3, u4 = st.columns(4)
        u1.metric(
            "Uniformity index",
            f"{float(spatial.get('hydraulic_uniformity_index', 0)):.2f}",
        )
        u2.metric(
            "Max loading factor",
            f"{float(spatial.get('max_loading_factor', 0)):.2f}",
        )
        u3.metric(
            "Min loading factor",
            f"{float(spatial.get('min_loading_factor', 0)):.2f}",
        )
        u4.metric(
            f"Q basis ({ulbl('flow_m3h')})",
            fmt(spatial.get("q_basis_m3h"), "flow_m3h", 1),
        )
        for _flag in spatial.get("advisory_flags") or []:
            st.warning(_flag.replace("_", " "))
        try:
            _xy_full = list(spatial.get("nozzle_xy_m") or [])
            _lf_full = [float(v) for v in (spatial.get("nozzle_loading_factor") or [])]
            _n_full = min(len(_xy_full), len(_lf_full))
            if _n_full > 12000:
                _xy_plot, _lf_plot = spatial_plot_sample(_xy_full, _lf_full)
            else:
                _xy_plot, _lf_plot = _xy_full[:_n_full], _lf_full[:_n_full]
            _cmin, _cmax = spatial_loading_color_limits(_lf_plot)
            _l_plate = float(
                np_plate.get("total_length_m") or np_plate.get("cyl_len_m") or 0
            )
            _x_cyl1 = float(np_plate.get("x_cyl_end_m") or 0)
            _h_d = float(np_plate.get("h_dish_m") or 0)
            _n_dish = int(np_plate.get("n_holes_in_dish_zones") or 0)
            _n_cyl = int(np_plate.get("n_holes_in_cyl_zone") or 0)
            st.caption(
                "Grey outline = **full nozzle plate** (left + right dish heads + cylinder). "
                "Coloured dots = Voronoi **loading factor** at each placed hole. "
                f"Holes: **{_n_cyl}** in cylindrical zone, **{_n_dish}** in dish zones."
            )
            if _n_full > len(_xy_plot):
                st.caption(
                    f"Markers shown: **{len(_xy_plot)}** of **{_n_full}** "
                    "(row-stratified sample; metrics use all holes)."
                )
            if _xy_full and _l_plate > 0:
                _x_max = max(p[0] for p in _xy_full)
                if _h_d > 0.01 and _x_max < _l_plate - _h_d * 0.85:
                    st.info(
                        "No nozzles reach the **right dish head** in this layout — "
                        "columns fill from the left until the target hole count is met. "
                        "The outline still shows the right head; compare the **nozzle plate plan** "
                        "on the Backwash tab. Reduce density or increase hole count to cover both heads."
                    )
            if _xy_plot and _lf_plot:
                _fig_sp = spatial_loading_figure(
                    _xy_plot,
                    _lf_plot,
                    np_plate,
                    cmin=_cmin,
                    cmax=_cmax,
                    phase_title=_phase_title,
                )
                st.plotly_chart(_fig_sp, use_container_width=True, key=chart_key)
        except ImportError:
            st.info("Install **plotly** for spatial loading map.")

    if in_expander:
        with st.expander(_exp_title, expanded=expanded):
            _body()
    else:
        _body()
