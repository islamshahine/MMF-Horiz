"""Plotly plan-view schematic for inlet feed / BW outlet collector (1D model)."""
from __future__ import annotations

import math
from typing import Any

from ui.helpers import fmt, ulbl

try:
    import plotly.graph_objects as go
    _PLOTLY_OK = True
except ImportError:
    _PLOTLY_OK = False
    go = None  # type: ignore


def _vis_diameter_m(nominal_m: float, min_m: float = 0.018) -> float:
    """Ensure pipe/orifice is visible on plan view without losing label truth."""
    return max(nominal_m, min_m)


def _resolve_label_ys(anchors: list[float], min_gap_m: float) -> list[float]:
    """Nudge label centres so stacked callouts do not overlap (data coordinates)."""
    if not anchors:
        return []
    n = len(anchors)
    order = sorted(range(n), key=lambda i: anchors[i])
    ys = [anchors[i] for i in order]
    for j in range(1, n):
        if ys[j] - ys[j - 1] < min_gap_m:
            ys[j] = ys[j - 1] + min_gap_m
    for j in range(n - 2, -1, -1):
        if ys[j + 1] - ys[j] < min_gap_m:
            ys[j] = ys[j + 1] - min_gap_m
    out = list(anchors)
    for k, i in enumerate(order):
        out[i] = ys[k]
    return out


def _add_plan_horizontal_dimension(
    fig: "go.Figure",
    *,
    x0: float,
    x1: float,
    y_line: float,
    label_html: str,
    tick_h: float,
    color: str = "#475569",
    label_above: bool = True,
    label_y: float | None = None,
) -> None:
    """Simple c–c dimension: horizontal line, end ticks, centered label (data coords, m)."""
    xa, xb = (x0, x1) if x0 <= x1 else (x1, x0)
    if abs(xb - xa) < 1e-6:
        return
    fig.add_shape(
        type="line", x0=xa, x1=xb, y0=y_line, y1=y_line,
        line=dict(color=color, width=1.5), layer="above",
    )
    for xv in (xa, xb):
        fig.add_shape(
            type="line", x0=xv, x1=xv, y0=y_line - tick_h, y1=y_line + tick_h,
            line=dict(color=color, width=1.5), layer="above",
        )
    xm = 0.5 * (xa + xb)
    if label_y is not None:
        y_lbl = float(label_y)
    else:
        y_lbl = y_line + tick_h * 2.4 if label_above else y_line - tick_h * 2.4
    fig.add_annotation(
        x=xm, y=y_lbl,
        text=label_html,
        showarrow=False,
        font=dict(size=9, color=color),
        bgcolor="rgba(248,250,252,0.95)",
        bordercolor=color,
        borderwidth=1,
        borderpad=3,
    )


def _orifice_positions_along_lateral(
  n_orf: int, y_start: float, y_end: float,
) -> list[float]:
    """Even spacing along lateral run (15–95 %), holes toward the media face."""
    if n_orf <= 0:
        return [y_end]
    if n_orf == 1:
        return [y_start + 0.88 * (y_end - y_start)]
    ys = []
    for k in range(n_orf):
        frac = 0.15 + 0.80 * k / max(n_orf - 1, 1)
        ys.append(y_start + frac * (y_end - y_start))
    return ys


def build_collector_underdrain_figure(
    *,
    cyl_len_m: float,
    vessel_id_m: float,
    collector_hyd: dict[str, Any],
    inputs: dict[str, Any],
) -> "go.Figure | None":
    """
    Plan view: header, lateral pipes (DN), orifices (true Ø, min visible size), labels.
    """
    if not _PLOTLY_OK:
        return None

    L = max(0.5, float(cyl_len_m or 1.0))
    W = max(0.5, float(vessel_id_m or 1.0))
    profile = list(collector_hyd.get("profile") or [])
    n_lat = int(collector_hyd.get("n_laterals") or inputs.get("n_bw_laterals") or 1)
    geo = collector_hyd.get("geometry") or {}
    # Plan: across-vessel run to shell (horizontal), not inclined L_max from elevation.
    l_pipe = float(collector_hyd.get("lateral_length_m") or geo.get("lateral_length_max_m") or 0.45 * W)
    l_plan = float(
        collector_hyd.get("lateral_horiz_reach_m")
        or geo.get("lateral_horiz_reach_m")
        or 0.0
    )
    if l_plan <= 0:
        l_plan = min(l_pipe, W / 2.0 - 0.02)
    else:
        l_plan = min(l_plan, W / 2.0 - 0.02)
    r_shell = l_plan  # centreline → shell (geometry); lateral tees from header OD
    d_hdr_m = float(collector_hyd.get("collector_header_id_m") or inputs.get("collector_header_id_m") or 0.25)
    d_lat_m = float(collector_hyd.get("lateral_dn_mm") or inputs.get("lateral_dn_mm") or 50.0) / 1000.0
    d_orf_m = float(collector_hyd.get("lateral_orifice_d_mm") or inputs.get("lateral_orifice_d_mm") or 0.0) / 1000.0
    if d_orf_m <= 0:
        d_orf_m = float(inputs.get("np_bore_dia") or 50.0) / 1000.0
    n_orf = int(collector_hyd.get("n_orifices_per_lateral") or inputs.get("n_orifices_per_lateral") or 0)
    n_orf_total = int(collector_hyd.get("n_orifices_total") or n_orf * n_lat)
    n_noz_ref = int(collector_hyd.get("nozzle_plate_holes_ref") or 0)
    _max_drawn = 18

    d_hdr_mm = d_hdr_m * 1000.0
    d_lat_mm = d_lat_m * 1000.0
    d_orf_mm = d_orf_m * 1000.0
    _hdr_lbl = fmt(d_hdr_mm, "length_mm", 0)
    _lat_lbl = fmt(d_lat_mm, "length_mm", 0)
    _orf_lbl = fmt(d_orf_mm, "length_mm", 1)
    q_bw = float(collector_hyd.get("q_bw_m3h") or 0.0)
    mal = float(collector_hyd.get("maldistribution_factor_calc") or 1.0)
    imb = float(collector_hyd.get("flow_imbalance_pct") or 0.0)

    flows = [float(p.get("lateral_flow_m3h") or 0.0) for p in profile]
    q_max = max(flows) if flows else 1.0

    d_hdr_vis = _vis_diameter_m(d_hdr_m)
    d_lat_vis = _vis_diameter_m(d_lat_m, min_m=0.012)
    d_orf_vis = _vis_diameter_m(d_orf_m, min_m=0.008)

    fig = go.Figure()

    # Vessel envelope
    fig.add_shape(
        type="rect", x0=0, y0=-W / 2, x1=L, y1=W / 2,
        line=dict(color="#64748b", width=2),
        fillcolor="rgba(148,163,184,0.07)",
    )
    # Caption in upper freeboard of vessel envelope (clear of the blue header centreline)
    fig.add_annotation(
        x=L * 0.5,
        y=W / 2 - max(0.04 * W, 0.015 * L),
        text="<i>Vessel plan — media above this section</i>",
        showarrow=False,
        font=dict(size=9, color="#475569"),
        bgcolor="rgba(255,255,255,0.82)",
        borderwidth=0,
        borderpad=2,
    )

    # Header pipe (true width, min visible)
    fig.add_shape(
        type="rect",
        x0=0, y0=-d_hdr_vis / 2, x1=L, y1=d_hdr_vis / 2,
        line=dict(color="#0369a1", width=2),
        fillcolor="rgba(14,165,233,0.45)",
        layer="below",
    )
    fig.add_trace(go.Scatter(
        x=[None], y=[None], mode="lines",
        line=dict(color="#0ea5e9", width=8),
        name=f"Header Ø {_hdr_lbl}",
    ))

    # BW inlet
    fig.add_annotation(
        x=-0.06 * L, y=0, ax=0.1 * L, ay=0,
        xref="x", yref="y", axref="x", ayref="y",
        showarrow=True, arrowhead=2, arrowsize=1.3, arrowwidth=2.5, arrowcolor="#0369a1",
        text="BW inlet", font=dict(size=11, color="#0369a1"),
    )

    stations = profile if profile else [
        {
            "station_m": L * (i + 1) / (n_lat + 1),
            "lateral_flow_m3h": q_bw / max(n_lat, 1),
            "lateral_index": i + 1,
        }
        for i in range(n_lat)
    ]

    lat_legend_added = False
    orf_x: list[float] = []
    orf_y: list[float] = []
    orf_hover: list[str] = []
    orf_sizes: list[float] = []

    for i, pt in enumerate(stations):
        x = float(pt.get("station_m") or 0.0)
        q_lat = float(pt.get("lateral_flow_m3h") or 0.0)
        rel = q_lat / q_max if q_max > 1e-9 else 0.5
        side = 1.0 if i % 2 == 0 else -1.0
        y_tee = side * d_hdr_vis / 2.0
        y_shell = side * r_shell
        y0, y1 = (y_tee, y_shell) if side > 0 else (y_shell, y_tee)
        y_mid = (y0 + y1) / 2.0
        idx = int(pt.get("lateral_index", i + 1))

        # Lateral pipe (plan: DN width in x, run in y)
        fill_a = 0.25 + 0.45 * rel
        fig.add_shape(
            type="rect",
            x0=x - d_lat_vis / 2, x1=x + d_lat_vis / 2,
            y0=min(y0, y1), y1=max(y0, y1),
            line=dict(color="#15803d", width=1.5),
            fillcolor=f"rgba(34,197,94,{fill_a:.2f})",
            layer="above",
        )
        if not lat_legend_added:
            fig.add_trace(go.Scatter(
                x=[None], y=[None], mode="markers",
                marker=dict(size=10, color="rgba(34,197,94,0.8)", symbol="square"),
                name=f"Lateral DN {_lat_lbl}",
            ))
            lat_legend_added = True

        # Lateral ID label at tee — nudge L1 so orifice callout can sit clear on opposite side
        _lx = x + (-0.028 * L) if idx == 1 and side > 0 else x + (0.028 * L if idx == 1 and side < 0 else 0)
        fig.add_annotation(
            x=_lx, y=y_mid,
            text=f"<b>L{idx}</b><br>DN {_lat_lbl}",
            showarrow=False,
            font=dict(size=9, color="#14532d"),
            bgcolor="rgba(255,255,255,0.75)",
            bordercolor="#86efac",
            borderwidth=1,
        )

        # Perforations along lateral (schematic shows subset if N is large)
        n_draw = min(n_orf, _max_drawn) if n_orf > 0 else 1
        y_orfs = _orifice_positions_along_lateral(n_draw, y0, y1)
        for j, y_o in enumerate(y_orfs):
            orf_x.append(x)
            orf_y.append(y_o)
            v_o = pt.get("orifice_velocity_m_s", "—")
            v_txt = fmt(float(v_o), "velocity_m_s", 2) if isinstance(v_o, (int, float)) else str(v_o)
            orf_hover.append(
                f"Lateral {idx} · perforation {j + 1} (of {n_orf} on this lateral)<br>"
                f"Ø {_orf_lbl}<br>"
                f"y = {fmt(y_o, 'length_m', 2)} along lateral<br>"
                f"v ≈ {v_txt}"
            )
            # Diameter in plot data units (1:1 scale); floor for visibility
            orf_sizes.append(max(d_orf_vis, 0.012) * 2.0)

        # Flow arrow on lateral
        fig.add_annotation(
            x=x + side * d_lat_vis * 2.5,
            y=y_mid + side * abs(y_shell - y_tee) * 0.22,
            ax=x + side * d_lat_vis * 2.5,
            ay=y_mid - side * abs(y_shell - y_tee) * 0.15,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=2, arrowwidth=1.5,
            arrowcolor=f"rgba(21,128,61,{0.5 + 0.4 * rel:.2f})",
        )

        # Orifice callout: prefer 2nd lateral (1-indexed L2) so it does not sit on L1 label
        _orf_callout_i = 1 if n_lat > 1 else 0
        if i == _orf_callout_i and y_orfs:
            y_lab = float(sum(y_orfs) / len(y_orfs))
            x_out = x + side * (d_lat_vis * 0.55 + max(0.05 * W, 0.04 * L))
            _orf_callout = (
                f"Ø {_orf_lbl}<br>"
                f"<b>{n_orf} / lateral</b><br>"
                f"({n_orf_total} total)"
            )
            fig.add_annotation(
                x=x_out,
                y=y_lab,
                text=_orf_callout,
                showarrow=True,
                arrowhead=2,
                ax=x + side * d_lat_vis * 0.35,
                ay=y_lab,
                arrowcolor="#b45309",
                font=dict(size=9, color="#b45309"),
                bgcolor="rgba(255,251,235,0.95)",
                bordercolor="#fbbf24",
                borderpad=3,
            )

    if orf_x:
        fig.add_trace(go.Scatter(
            x=orf_x, y=orf_y,
            mode="markers",
            marker=dict(
                size=orf_sizes,
                sizemode="diameter",
                color="#f59e0b",
                line=dict(width=1.5, color="#92400e"),
                symbol="circle",
            ),
            name=f"Perforation Ø {_orf_lbl} (each lateral)",
            hovertemplate="%{customdata}<extra></extra>",
            customdata=orf_hover,
        ))

    # Longitudinal dimensions below vessel envelope (tiers at negative y)
    xs_lat = sorted(float(pt.get("station_m") or 0.0) for pt in stations)
    xs_lat = [x for x in xs_lat if 0 <= x <= L + 1e-6]

    # Header diameter callout — inlet end, below header (avoids floating mid-vessel)
    _hdr_ann_x = min(L * 0.22, max(L * 0.06, xs_lat[0] * 0.45)) if xs_lat else L * 0.12
    fig.add_annotation(
        x=_hdr_ann_x,
        y=-d_hdr_vis / 2 - max(0.045 * W, 0.02 * L),
        text=f"Header ID Ø {_hdr_lbl}",
        showarrow=False,
        xanchor="left",
        font=dict(size=10, color="#0369a1"),
        bgcolor="rgba(224,242,254,0.9)",
        bordercolor="#7dd3fc",
    )
    _tick = max(0.006 * L, 0.008 * W, 0.012)
    _y_bot = -W / 2
    _m = max(W, 0.5)
    _gap = max(0.11 * _m, 0.028 * L, 0.015 * n_lat * _m / max(n_lat, 1))
    _lbl_sep = max(_tick * 2.9, 0.018 * _m)
    _dim_summary = ""
    if len(xs_lat) >= 2:
        _s = xs_lat[1] - xs_lat[0]
        _y1 = _y_bot - _gap
        _add_plan_horizontal_dimension(
            fig,
            x0=xs_lat[0],
            x1=xs_lat[1],
            y_line=_y1,
            label_html=f"<b>Lateral spacing (c–c)</b><br>{fmt(_s, 'length_m', 3)}",
            tick_h=_tick,
            label_y=_y1 - _lbl_sep,
        )
        _dim_summary += f"Lateral c–c: {fmt(_s, 'length_m', 3)}"
    if xs_lat:
        _x_first = xs_lat[0]
        _x_last = xs_lat[-1]
        _inset_inlet = max(0.0, _x_first)
        _inset_far = max(0.0, L - _x_last)
        _y2 = _y_bot - 2.0 * _gap
        _add_plan_horizontal_dimension(
            fig,
            x0=0.0,
            x1=_x_first,
            y_line=_y2,
            label_html=f"<b>Inlet end → 1st lateral</b><br>{fmt(_inset_inlet, 'length_m', 3)}",
            tick_h=_tick,
            color="#0369a1",
            label_y=_y2 + _lbl_sep,
        )
        _y3 = _y_bot - 3.0 * _gap
        _add_plan_horizontal_dimension(
            fig,
            x0=_x_last,
            x1=L,
            y_line=_y3,
            label_html=f"<b>Last lateral → far head</b><br>{fmt(_inset_far, 'length_m', 3)}",
            tick_h=_tick,
            color="#0369a1",
            label_y=_y3 - _lbl_sep,
        )
        if _dim_summary:
            _dim_summary += " · "
        _dim_summary += (
            f"Inlet inset: {fmt(_inset_inlet, 'length_m', 3)} · "
            f"Far inset: {fmt(_inset_far, 'length_m', 3)}"
        )

    _dim_stack = 3.5 * _gap + _lbl_sep if xs_lat else 0.0
    _r_plot = max(W / 2, r_shell) * 1.15
    y_max = _r_plot
    y_min = -_r_plot - _dim_stack
    _x_pad = max(0.12 * L, 0.04 * n_lat * d_lat_vis)
    _b_margin = 148 if (n_lat >= 10 or len(_dim_summary) > 40) else 120
    fig.update_layout(
        title=dict(
            text=(
                f"Inlet feed / BW outlet collector — plan · Q<sub>BW</sub>={fmt(q_bw, 'flow_m3h', 0)} · "
                f"mal={mal:.2f} · imbalance={imb:.0f}%"
            ),
            font=dict(size=14),
        ),
        xaxis=dict(
            title=f"Along vessel length ({ulbl('length_m')})",
            range=[-_x_pad, L * 1.06],
        ),
        yaxis=dict(
            title=f"Across vessel ({ulbl('length_m')})",
            range=[y_min, y_max],
            scaleanchor="x",
            scaleratio=1,
        ),
        height=max(460, int(380 + 28 * min(n_lat, 12))),
        margin=dict(l=60, r=24, t=68, b=_b_margin),
        template="plotly_white",
        plot_bgcolor="#f8fafc",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            x=0.5,
            xanchor="center",
            font=dict(size=10),
        ),
    )
    _plan_caption = (
        f"<b>Plan view</b> — <b>{n_lat}</b> laterals · <b>{n_orf}</b> perforations<b>/lateral</b> "
        f"(<b>{n_orf_total}</b> total) · Ø {_orf_lbl}. "
        f"Lateral run <b>{fmt(max(r_shell - d_hdr_vis / 2, 0), 'length_m', 2)}</b>; "
        f"L<sub>max</sub> <b>{fmt(l_pipe, 'length_m', 2)}</b> (θ={float(collector_hyd.get('theta_deg') or geo.get('theta_deg') or 0):.1f}°). "
        f"Green ∝ Q; orange = wall perforations (≤{_max_drawn}/lateral drawn)."
    )
    if _dim_summary:
        fig.add_annotation(
            x=0.5, y=-0.09, xref="paper", yref="paper",
            xanchor="center", yanchor="top",
            showarrow=False,
            text=f"<b>Longitudinal</b> — {_dim_summary}",
            font=dict(size=10, color="#334155"),
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="#94a3b8",
            borderwidth=1,
            borderpad=4,
        )
    fig.add_annotation(
        x=0.5, y=-0.22 if _dim_summary else -0.12, xref="paper", yref="paper",
        xanchor="center", yanchor="top",
        showarrow=False, align="center",
        text=_plan_caption,
        font=dict(size=9, color="#475569"),
        bgcolor="rgba(248,250,252,0.92)",
        bordercolor="#e2e8f0",
        borderwidth=1,
    )
    return fig


_LAYER_FILL = (
    "#78716c", "#a8a29e", "#ca8a04", "#57534e", "#44403c",
    "#0d9488", "#0369a1", "#6b7280",
)


def build_collector_elevation_figure(
    *,
    vessel_id_m: float,
    collector_hyd: dict[str, Any],
    layers: list | None = None,
    bw_exp: dict | None = None,
) -> "go.Figure | None":
    """Elevation cross-section: media bed, expansion, θ, lateral L_max, collector height."""
    if not _PLOTLY_OK:
        return None

    geo = collector_hyd.get("geometry") or {}
    r = float(geo.get("vessel_radius_m") or vessel_id_m / 2.0)
    h_np = float(geo.get("underdrain_axis_h_m") or 0.0)
    h_col = float(geo.get("collector_h_m") or h_np)
    l_horiz = float(geo.get("lateral_horiz_reach_m") or 0.0)
    l_lat = float(geo.get("lateral_length_max_m") or collector_hyd.get("lateral_length_m") or 0.0)
    theta = float(geo.get("theta_deg") or collector_hyd.get("theta_deg") or 0.0)
    exp_layers = list((bw_exp or {}).get("layers") or [])
    media_layers = list(layers or [])
    total_exp_pct = float((bw_exp or {}).get("total_expansion_pct", 0.0) or 0.0)
    # Label columns outside the bed (left = media, right = expansion %)
    x_lbl_media = -r * 0.38
    x_lbl_exp_pct = r * 0.97
    lbl_gap_m = max(0.20, 0.075 * r)

    fig = go.Figure()
    theta_pts = [i * math.pi / 180.0 for i in range(181)]
    xs = [r * math.sin(t) for t in theta_pts]
    ys = [r - r * math.cos(t) for t in theta_pts]
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(color="#64748b", width=2), name="Shell"))

    fig.add_shape(type="line", x0=0, x1=0, y0=0, y1=2 * r, line=dict(color="#94a3b8", width=1, dash="dot"))

    # Media bed (settled) + per-layer expansion overlay
    curr_h = h_np
    media_anns: list[dict[str, Any]] = []
    exp_pct_anns: list[dict[str, Any]] = []
    for i, lyr in enumerate(media_layers):
        depth = float(lyr.get("Depth", 0.0) or 0.0)
        if depth <= 0:
            continue
        y0, y1 = curr_h, curr_h + depth
        fill = _LAYER_FILL[i % len(_LAYER_FILL)]
        mtype = str(lyr.get("Type", "Media"))
        fig.add_shape(
            type="rect", x0=0, x1=r * 0.96, y0=y0, y1=y1,
            line=dict(color="#57534e", width=0.8),
            fillcolor=fill,
            opacity=0.55,
            layer="below",
        )
        media_anns.append({
            "y": (y0 + y1) / 2,
            "y0": y0,
            "y1": y1,
            "text": f"{mtype}<br>{fmt(depth, 'length_m', 2)}",
        })
        if i < len(exp_layers):
            er = exp_layers[i]
            d_exp = float(er.get("depth_expanded_m", depth) or depth)
            exp_pct = float(er.get("expansion_pct", 0.0) or 0.0)
            if d_exp > depth + 1e-6 or exp_pct > 0.1:
                fig.add_shape(
                    type="rect", x0=0, x1=r * 0.96, y0=y0, y1=y0 + d_exp,
                    line=dict(color="#2563eb", width=1, dash="dash"),
                    fillcolor="rgba(96,165,250,0.22)",
                    layer="below",
                )
                if exp_pct > 0.5:
                    exp_pct_anns.append({
                        "y": y0 + d_exp * 0.5,
                        "text": f"+{exp_pct:.0f}%",
                    })
        curr_h += depth

    if media_anns:
        resolved = _resolve_label_ys([a["y"] for a in media_anns], lbl_gap_m)
        for ann, y_lbl in zip(media_anns, resolved):
            fig.add_annotation(
                x=x_lbl_media, y=y_lbl,
                text=ann["text"],
                showarrow=False, xanchor="right",
                font=dict(size=10, color="#1e293b"),
                bgcolor="rgba(255,255,255,0.82)",
                borderwidth=0,
            )
    if exp_pct_anns:
        resolved_exp = _resolve_label_ys([a["y"] for a in exp_pct_anns], lbl_gap_m * 0.85)
        for ann, y_lbl in zip(exp_pct_anns, resolved_exp):
            fig.add_annotation(
                x=x_lbl_exp_pct, y=y_lbl,
                text=ann["text"],
                showarrow=False, xanchor="left",
                font=dict(size=8, color="#1d4ed8"),
                bgcolor="rgba(219,234,254,0.75)",
                borderwidth=0,
            )

    bed_top_settled = curr_h
    bed_top_expanded = h_np + float((bw_exp or {}).get("total_expanded_m", bed_top_settled - h_np) or 0.0)
    if bw_exp and bed_top_expanded > bed_top_settled + 0.01:
        fig.add_shape(
            type="line", x0=0, x1=r, y0=bed_top_expanded, y1=bed_top_expanded,
            line=dict(color="#2563eb", width=1.5, dash="dash"),
        )
        _y_top_lbl = bed_top_expanded + 0.05 * r
        if exp_pct_anns:
            _last_exp_y = max(a["y"] for a in exp_pct_anns)
            if _y_top_lbl - _last_exp_y < lbl_gap_m:
                _y_top_lbl = _last_exp_y + lbl_gap_m
        fig.add_annotation(
            x=x_lbl_exp_pct, y=_y_top_lbl,
            text=f"Expanded top<br>net +{total_exp_pct:.1f}%",
            showarrow=False, xanchor="left", yanchor="bottom",
            font=dict(size=9, color="#1d4ed8"),
            bgcolor="rgba(219,234,254,0.9)",
        )

    # Nozzle plate — below bed labels, clear of gravel callout
    fig.add_shape(type="line", x0=0, x1=r, y0=h_np, y1=h_np, line=dict(color="#0369a1", width=1.5, dash="dash"))
    _y_nozzle = max(h_np - 0.20 * r, 0.06 * r)
    if media_anns:
        _lowest_media = min(_resolve_label_ys([a["y"] for a in media_anns], lbl_gap_m))
        if _y_nozzle + lbl_gap_m * 0.9 > _lowest_media:
            _y_nozzle = _lowest_media - lbl_gap_m * 0.9
    fig.add_annotation(
        x=x_lbl_media, y=_y_nozzle,
        text=f"Nozzle plate<br>{fmt(h_np, 'length_m', 2)}",
        showarrow=False, xanchor="right", yanchor="top",
        font=dict(size=9, color="#0369a1"),
        bgcolor="rgba(224,242,254,0.85)",
        borderwidth=0,
    )

    # BW outlet collector centreline (no text on lateral arrow)
    fig.add_shape(type="line", x0=0, x1=r, y0=h_col, y1=h_col, line=dict(color="#dc2626", width=2))

    fig.add_shape(
        type="line", x0=0, y0=h_np, x1=l_horiz, y1=h_col,
        line=dict(color="#16a34a", width=4),
    )
    # L_max / θ above bed, near collector end of lateral (clear of media stack)
    _x_geom = min(l_horiz + 0.10 * r, r * 0.98)
    _y_geom = min(h_col + 0.06 * r, 2.05 * r)
    fig.add_annotation(
        x=_x_geom, y=_y_geom,
        text=f"L<sub>max</sub>={fmt(l_lat, 'length_m', 2)}<br>θ={theta:.1f}°",
        showarrow=False, xanchor="left", yanchor="bottom",
        font=dict(size=10, color="#14532d"),
        bgcolor="rgba(220,252,231,0.95)", bordercolor="#86efac",
    )
    fig.add_trace(go.Scatter(
        x=[0, l_horiz], y=[h_np, h_col], mode="markers",
        marker=dict(size=[9, 11], color=["#0ea5e9", "#dc2626"]),
        name="Distributor → collector zone",
    ))

    fig.update_layout(
        title=dict(
            text="Elevation — media, expansion, lateral L<sub>max</sub> & collector",
            font=dict(size=12),
            xref="paper",
            x=0.5,
            xanchor="center",
            yref="paper",
            y=1.0,
            yanchor="top",
            pad=dict(b=6),
        ),
        xaxis=dict(title=f"Half-width ({ulbl('length_m')})", range=[-r * 0.46, r * 1.10]),
        yaxis=dict(
            title=f"Height from bottom ({ulbl('length_m')})",
            range=[-0.05 * r, 2.1 * r],
            scaleanchor="x",
            scaleratio=1,
        ),
        height=460,
        template="plotly_white",
        showlegend=False,
        title_automargin=True,
        margin=dict(l=88, r=24, t=64, b=72),
    )
    sp_max = float(geo.get("lateral_spacing_max_m") or collector_hyd.get("lateral_spacing_max_m") or 0)
    fig.add_annotation(
        x=0.02, y=0.02, xref="paper", yref="paper", xanchor="left", yanchor="bottom",
        showarrow=False, align="left",
        text=(
            f"Red line: BW outlet collector @ <b>{fmt(h_col, 'length_m', 2)}</b> · "
            f"θ = atan(Δh/L<sub>horiz</sub>) · L<sub>horiz</sub>={fmt(l_horiz, 'length_m', 2)} · "
            f"header spacing ≤ {fmt(sp_max, 'length_m', 2)}<br>"
            f"Hatched blue = expanded layer (Richardson–Zaki @ sidebar BW velocity). "
            f"Solids = settled bed on nozzle plate."
        ),
        font=dict(size=9, color="#475569"),
        bgcolor="rgba(255,255,255,0.92)",
    )
    return fig
