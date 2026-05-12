"""
engine/drawing.py
─────────────────
Dynamic vessel cross-section elevation figure for the AQUASIGHT™ MMF Calculator.

Produces a side-elevation (longitudinal theoretical section) of the
horizontal multi-media filter showing:
  • Vessel hull (cylinder + elliptic end caps)
  • Nozzle plate with symbolic strainer nozzles
  • Media layers (coloured, labelled)
  • Expanded-bed overlay (optional)
  • Dimension arrows on the left side
  • Collector / freeboard annotation
  • ID and L (T/T) annotation
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Layer colours ──────────────────────────────────────────────────────────
LAYER_COLORS = {
    "Gravel":            "#d5c9b0",
    "Coarse sand":       "#ead9a0",
    "Fine sand":         "#f2e6a5",
    "Fine sand (extra)": "#f0d870",
    "Anthracite":        "#6e6e6e",
    "MnO₂":         "#8b3a1a",
    "Medium GAC":        "#3a3a3a",
    "Biodagene":         "#b0a030",
    "Schist":            "#9a9a9a",
    "Limestone":         "#e0cfa8",
    "Pumice":            "#c8b09a",
    "FILTRALITE clay":   "#a0c8a0",
    "Custom":            "#90b8d8",
}
_DEFAULT_COLOR = "#b8b8b8"

# ── Dimension label subscripts per media type ──────────────────────────────
_DIM_SUB = {
    "Gravel":            "gr",
    "Coarse sand":       "cs",
    "Fine sand":         "fs",
    "Fine sand (extra)": "sd",
    "Anthracite":        "an",
    "MnO₂":         "mn",
    "Medium GAC":        "gac",
    "Biodagene":         "bio",
    "Schist":            "sch",
    "Limestone":         "ls",
    "Pumice":            "pu",
    "FILTRALITE clay":   "fl",
    "Custom":            "m",
}


def vessel_section_elevation(
    vessel_id_m: float,
    total_length_m: float,
    h_dish_m: float,
    nozzle_plate_h_m: float,
    layers: list,
    collector_h_m: float,
    bw_exp: dict,
    show_expansion: bool = True,
    figsize=None,
    cyl_len: float = None,
    real_id: float = None,
    end_geometry: str = "Elliptic 2:1",
    project_name: str = "",
    doc_number: str = "",
    revision: str = "",
    engineer: str = "",
) -> plt.Figure:
    """
    Draw the horizontal MMF vessel theoretical elevation cross-section.

    Parameters
    ----------
    vessel_id_m       : Internal diameter [m]
    total_length_m    : Tangent-to-tangent length [m]
    h_dish_m          : Depth of one end dish [m]
    nozzle_plate_h_m  : Nozzle plate height from vessel bottom [m]
    layers            : List of layer dicts {Type, Depth, is_support, ...}
    collector_h_m     : BW outlet collector height from vessel bottom [m]
    bw_exp            : bed_expansion() result dict (has "layers" list)
    show_expansion    : Overlay expanded-bed zone when True
    figsize           : (w, h) inches; auto-computed from vessel aspect ratio
    """
    ID = vessel_id_m
    L  = total_length_m
    h_d = h_dish_m
    R   = ID / 2.0

    if figsize is None:
        aspect = L / ID
        w = min(20, max(12, aspect * 5.0))
        figsize = (w, 5.8)

    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#f8f8f8")

    # ── Vessel hull ────────────────────────────────────────────────────────
    n = 120
    theta_r = np.linspace(np.pi / 2, -np.pi / 2, n)
    theta_l = np.linspace(3 * np.pi / 2, np.pi / 2, n)

    xr = L + h_d * np.cos(theta_r)
    yr = R + R * np.sin(theta_r)
    xl = h_d * np.cos(theta_l)
    yl = R + R * np.sin(theta_l)

    x_hull = np.concatenate([[0, L], xr[1:-1], [L, 0], xl[1:-1]])
    y_hull = np.concatenate([[ID, ID], yr[1:-1], [0, 0], yl[1:-1]])

    hull = mpatches.Polygon(
        np.column_stack([x_hull, y_hull]),
        closed=True,
        facecolor="#ffffff",
        edgecolor="#000000",
        linewidth=2.5,
        zorder=1,
    )
    ax.add_patch(hull)

    # Centreline — ISO 128 dash-dot-dash, extends 15 px beyond each head
    _cl_ext = max(h_d * 0.5, 0.15)
    ax.plot([-h_d - _cl_ext, L + h_d + _cl_ext], [R, R],
            color="#888888", linewidth=0.8,
            linestyle=(0, (12, 4, 2, 4)), zorder=2)
    ax.text(L + h_d + _cl_ext + R * 0.05, R, "℄",
            ha="left", va="center", fontsize=9, color="#888888", zorder=2)

    # ── Nozzle plate (thick line + symbolic strainer nozzles) ─────────────
    ax.plot([0, L], [nozzle_plate_h_m] * 2,
            color="#000000", linewidth=3.5, solid_capstyle="butt", zorder=6)
    ax.text(L * 0.02, nozzle_plate_h_m + R*0.04,
            f"Nozzle Plate  h={nozzle_plate_h_m:.2f} m",
            ha="left", va="bottom", fontsize=8, color="#000000", zorder=7)

    n_noz = min(14, max(5, int(L / 1.8)))
    for k in range(n_noz):
        xi = L * (k + 0.5) / n_noz
        noz_h = 0.035 * ID
        ax.plot([xi, xi],
                [nozzle_plate_h_m - noz_h, nozzle_plate_h_m],
                color="#1a3a5c", linewidth=1.2, zorder=6)
        ax.plot(xi, nozzle_plate_h_m - noz_h * 1.15,
                marker="v", color="#1a3a5c", markersize=3.5, zorder=6)

    # ── Media layers ──────────────────────────────────────────────────────
    exp_by_idx = bw_exp.get("layers", [])   # same order as 'layers'

    curr_h = nozzle_plate_h_m
    for i, lyr in enumerate(layers):
        depth = lyr["Depth"]
        # ISO style: support = light hatch, media = grey bands
        _iso_fill = "#e0e0e0" if lyr.get("is_support") else "#e8e8e8"
        rect = mpatches.Rectangle(
            (0, curr_h), L, depth,
            facecolor=_iso_fill, edgecolor="#666666", linewidth=0.5,
            zorder=3,
        )
        ax.add_patch(rect)
        # ISO 45° hatching on all layers
        ax.fill_between(
            [0, L], curr_h, curr_h + depth,
            hatch="////" if lyr.get("is_support") else "...",
            facecolor="none", edgecolor="#aaaaaa", linewidth=0.3, zorder=4,
        )
        # Layer label right-aligned inside band
        ax.text(
            L * 0.98, curr_h + depth / 2,
            f"{lyr['Type']}  {depth:.2f} m",
            ha="right", va="center", fontsize=9,
            color="#333333", zorder=7,
        )

        # Expanded-bed overlay
        if show_expansion and i < len(exp_by_idx):
            exp = exp_by_idx[i]
            if exp.get("fluidised"):
                exp_h = exp["depth_expanded_m"]
                exp_rect = mpatches.Rectangle(
                    (0, curr_h), L, exp_h,
                    facecolor="#6699dd", edgecolor="#3366aa",
                    linewidth=0.6, linestyle="--", alpha=0.25, zorder=4,
                )
                ax.add_patch(exp_rect)

        curr_h += depth

    settled_top = curr_h

    # ── Expansion-max dashed line ─────────────────────────────────────────
    total_exp_h = None
    if show_expansion and exp_by_idx:
        raw_exp = bw_exp.get("total_expanded_m", 0.0)
        if raw_exp > 0:
            total_exp_h = raw_exp + nozzle_plate_h_m
            ax.plot([0, L], [total_exp_h] * 2,
                    color="#3366bb", linewidth=1.3, linestyle="--",
                    alpha=0.9, zorder=5)
            delta_mm = (total_exp_h - settled_top) * 1000
            ax.annotate(
                f"Expansion max  +{delta_mm:.0f} mm",
                xy=(L * 0.70, total_exp_h),
                xytext=(L * 0.72, total_exp_h + 0.09 * R),
                fontsize=7.5, color="#3366bb",
                arrowprops=dict(arrowstyle="-", color="#3366bb", lw=0.7),
                zorder=7,
            )

    # ── Collector level — dashed red (ISO hidden line style) ─────────────
    ax.plot([0, L], [collector_h_m] * 2,
            color="#cc0000", linewidth=0.8,
            linestyle=(0, (6, 3)), zorder=5)
    ax.text(L * 0.02, collector_h_m + 0.012 * ID,
            f"Collector  h={collector_h_m:.2f} m",
            ha="left", va="bottom", fontsize=8, color="#cc0000", zorder=7)

    # ── Dimension lines (left side) ───────────────────────────────────────
    dx0 = -h_d * 0.35    # arrow x
    dx1 = -h_d * 0.70    # label x

    def _dim(y0, y1, subscript):
        if abs(y1 - y0) < 1e-4:
            return
        val_mm = abs(y1 - y0) * 1000
        ymid = (y0 + y1) / 2.0

        ax.annotate(
            "", xy=(dx0, y1), xytext=(dx0, y0),
            arrowprops=dict(arrowstyle="<->", color="#1a3a5c",
                            lw=0.9, mutation_scale=7),
            zorder=8,
        )
        for yy in (y0, y1):
            ax.plot([dx0 - 0.04, dx0 + 0.04], [yy, yy],
                    color="#1a3a5c", lw=0.7, zorder=8)

        ax.text(dx1, ymid,
                f"$H_{{\\rm {subscript}}}$\n{val_mm:.0f} mm",
                ha="right", va="center", fontsize=7.5,
                color="#1a3a5c", linespacing=1.35, zorder=8)

    _dim(0, nozzle_plate_h_m, "NP")

    curr_h = nozzle_plate_h_m
    for lyr in layers:
        sub = _DIM_SUB.get(lyr["Type"], "m")
        _dim(curr_h, curr_h + lyr["Depth"], sub)
        curr_h += lyr["Depth"]

    if collector_h_m > settled_top + 0.01:
        _dim(settled_top, collector_h_m, "fn")

    # ── Right end: ID double arrow ────────────────────────────────────────
    id_x = L + h_d * 1.15
    ax.annotate("", xy=(id_x, ID), xytext=(id_x, 0),
                arrowprops=dict(arrowstyle="<->", color="#1a3a5c",
                                lw=1.2, mutation_scale=8), zorder=8)
    ax.text(id_x + 0.06, R,
            f"ID\n{vessel_id_m * 1000:.0f} mm",
            ha="left", va="center",
            fontsize=9, fontweight="bold", color="#1a3a5c", zorder=8)

    # ── Right side: distance from crown annotations ───────────────────────
    ann_x = L * 0.96

    # Collector to crown
    if ID > collector_h_m:
        dist_c = (ID - collector_h_m) * 1000
        ax.annotate("", xy=(ann_x, ID), xytext=(ann_x, collector_h_m),
                    arrowprops=dict(arrowstyle="<->", color="#777",
                                   lw=0.8, mutation_scale=7), zorder=7)
        ax.text(ann_x + 0.06, (ID + collector_h_m) / 2,
                f"{dist_c:.0f} mm",
                ha="left", va="center", fontsize=7, color="#777", zorder=7)

    # Expansion max to crown
    if total_exp_h is not None and ID > total_exp_h:
        dist_e = (ID - total_exp_h) * 1000
        ax.annotate("", xy=(ann_x - 0.28, ID), xytext=(ann_x - 0.28, total_exp_h),
                    arrowprops=dict(arrowstyle="<->", color="#3366bb",
                                   lw=0.8, mutation_scale=7), zorder=7)
        ax.text(ann_x - 0.22, (ID + total_exp_h) / 2,
                f"{dist_e:.0f} mm",
                ha="left", va="center", fontsize=7, color="#3366bb", zorder=7)

    # ── Dimension lines — Shell (T/T) and Total (O/O) ────────────────────
    _shell_len = cyl_len if cyl_len is not None else total_length_m
    _dc = "#333333"
    _akw = dict(arrowstyle="-|>", color=_dc, lw=0.6, mutation_scale=7)

    # Line 1 — Shell (T/T): tangent to tangent = cyl_len
    ly1 = -R * 0.42
    ax.annotate("", xy=(0, ly1), xytext=(_shell_len, ly1),
                arrowprops=_akw, zorder=8)
    ax.annotate("", xy=(_shell_len, ly1), xytext=(0, ly1),
                arrowprops=_akw, zorder=8)
    for tx in (0, _shell_len):
        ax.plot([tx, tx], [ly1 - R*0.07, ly1 + R*0.07], color=_dc, lw=0.6, zorder=8)
    ax.text(_shell_len / 2, ly1 - R * 0.10,
            f"Shell (T/T)  {_shell_len:.2f} m",
            ha="center", va="top", fontsize=8.5, color="#000000", zorder=8)

    # Line 2 — Total (O/O): outer face to outer face = total_length_m
    ly2 = ly1 - R * 0.40
    _x0, _x1 = -h_d, _shell_len + h_d
    ax.annotate("", xy=(_x0, ly2), xytext=(_x1, ly2),
                arrowprops=_akw, zorder=8)
    ax.annotate("", xy=(_x1, ly2), xytext=(_x0, ly2),
                arrowprops=_akw, zorder=8)
    for tx in (_x0, _x1):
        ax.plot([tx, tx], [ly2 - R*0.07, ly2 + R*0.07], color=_dc, lw=0.6, zorder=8)
    ax.text((_x0 + _x1) / 2, ly2 - R * 0.10,
            f"Total (O/O)  {total_length_m:.2f} m",
            ha="center", va="top", fontsize=8.5, color="#000000", zorder=8)

    # Tangent line tick markers
    for tx in (0, _shell_len):
        ax.plot([tx, tx], [-R * 0.12, 0], color=_dc, lw=0.6, zorder=5)

    # ── Nozzle stubs (ISO schematic style) ───────────────────────────────
    _sw = L * 0.028          # stub width
    _sh = R * 0.20           # stub length (protrusion)
    _nkw = dict(facecolor="white", edgecolor="#000000", linewidth=1.2, zorder=9)
    _nlkw = dict(fontsize=8, color="#000000", zorder=10)
    _noz_defs = [
        (L / 2,   "top",   "Feed\ninlet"),
        (L / 2,   "bot",   "Filtrate\noutlet"),
        (0,       "left",  "BW\ninlet"),
        (L,       "right", "BW\noutlet"),
        (L * 0.2, "top",   "Vent"),
        (L * 0.8, "bot",   "Drain"),
    ]
    for _xp, _side, _lbl in _noz_defs:
        if _side == "top":
            ax.add_patch(mpatches.Rectangle(
                (_xp - _sw/2, ID), _sw, _sh, **_nkw))
            ax.text(_xp, ID + _sh + R*0.04, _lbl,
                    ha="center", va="bottom", **_nlkw)
        elif _side == "bot":
            ax.add_patch(mpatches.Rectangle(
                (_xp - _sw/2, -_sh), _sw, _sh, **_nkw))
            ax.text(_xp, -_sh - R*0.04, _lbl,
                    ha="center", va="top", **_nlkw)
        elif _side == "left":
            ax.add_patch(mpatches.Rectangle(
                (-_sh, R - _sw/2), _sh, _sw, **_nkw))
            ax.text(-_sh - R*0.04, R, _lbl,
                    ha="right", va="center", **_nlkw)
        else:
            ax.add_patch(mpatches.Rectangle(
                (L, R - _sw/2), _sh, _sw, **_nkw))
            ax.text(L + _sh + R*0.04, R, _lbl,
                    ha="left", va="center", **_nlkw)

    # ── Colour legend ─────────────────────────────────────────────────────
    legend_handles = []
    for lyr in layers:
        patch = mpatches.Patch(
            facecolor=LAYER_COLORS.get(lyr["Type"], _DEFAULT_COLOR),
            edgecolor="#555", linewidth=0.6,
            label=f"{lyr['Type']}  ({lyr['Depth'] * 1000:.0f} mm)",
        )
        legend_handles.append(patch)
    if show_expansion and total_exp_h is not None:
        legend_handles.append(
            mpatches.Patch(
                facecolor="#6699dd", edgecolor="#3366aa",
                linewidth=0.6, alpha=0.55, linestyle="--",
                label="Expanded bed (BW)",
            )
        )
    ax.legend(
        handles=legend_handles,
        loc="upper left",
        bbox_to_anchor=(0.01, 0.99),
        fontsize=7.5,
        framealpha=0.85,
        edgecolor="#aaa",
        ncol=1,
    )

    # ── Title block (figure coordinates, bottom-right) ────────────────────
    import datetime as _dt_tb
    _today_tb = _dt_tb.date.today().strftime("%d-%b-%Y")
    _tb = (
        "AQUASIGHT™ MMF\n"
        "─" * 38 + "\n"
        f"Project:      {project_name or '—'}\n"
        f"Doc No:       {doc_number or '—'}   Rev: {revision or 'A'}\n"
        f"Prepared by:  {engineer or '—'}   Date: {_today_tb}\n"
        "Scale: NTS    Units: m/mm   Sheet: 1/1"
    )
    fig.text(
        0.75, 0.02, _tb,
        ha="left", va="bottom", fontsize=7,
        fontfamily="monospace", color="#000000",
        transform=fig.transFigure,
        bbox=dict(boxstyle="square,pad=0.6",
                  facecolor="white", edgecolor="#000000", linewidth=1.0),
    )

    # ── Title & layout ────────────────────────────────────────────────────
    _sl = cyl_len if cyl_len is not None else total_length_m
    ax.set_xlim(-h_d * 4.0, _sl + h_d * 3.5)
    ax.set_ylim(-R * 1.40, ID + R * 0.65)
    ax.set_aspect("equal", adjustable="datalim")
    ax.axis("off")

    ax.set_title(
        "Horizontal Multi-Media Filter — Theoretical Elevation Section\n"
        f"ID {vessel_id_m * 1000:.0f} mm  ·  L(T/T) {_sl:.2f} m  ·  "
        f"Hₙₚ {nozzle_plate_h_m * 1000:.0f} mm  ·  "
        f"{len(layers)}-layer bed",
        fontsize=9.5, pad=6, fontweight="bold", color="#000000",
    )

    fig.tight_layout(pad=1.0)
    return fig
