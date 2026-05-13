"""
engine/drawing.py
─────────────────
Dynamic vessel cross-section elevation figure for the AQUASIGHT™ MMF Calculator.

Produces a side-elevation (longitudinal theoretical section) of the
horizontal multi-media filter showing:
  • Vessel hull (cylinder + elliptic end caps)
  • Nozzle plate with symbolic strainer nozzles
  • Media layers (coloured per layer type — legend matches bed fill)
  • Expanded-bed overlay (optional)
  • Dimension arrows on the left side
  • Collector / freeboard annotation
  • ID and L (T/T) annotation
  • Optional right-hand fabrication panel (nozzle schedule N1…, shell/lining,
    saddles, nozzle-plate notes)
"""

from __future__ import annotations

import datetime as _dt_tb
from typing import Any

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

# ── Layer colours ──────────────────────────────────────────────────────────
LAYER_COLORS = {
    "Gravel":            "#d5c9b0",
    "Coarse sand":       "#ead9a0",
    "Fine sand":         "#f2e6a5",
    "Fine sand (extra)": "#f0d870",
    "Anthracite":        "#6e6e6e",
    "Garnet":            "#6b3d5c",
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
    "Garnet":            "ga",
    "MnO₂":         "mn",
    "Medium GAC":        "gac",
    "Biodagene":         "bio",
    "Schist":            "sch",
    "Limestone":         "ls",
    "Pumice":            "pu",
    "FILTRALITE clay":   "fl",
    "Custom":            "m",
}


def _media_layer_facecolor(lyr: dict) -> str:
    """Bed fill colour; kept in sync with the elevation legend swatches."""
    return LAYER_COLORS.get(str(lyr.get("Type", "")), _DEFAULT_COLOR)


# Layer types drawn with a dark fill — use a light label colour for contrast.
_MEDIA_DARK_FILL_TYPES = frozenset({"Anthracite", "Medium GAC", "MnO₂"})


# Process nozzle rows shown on the elevation (order = N1, N2, …)
_ELEVATION_SERVICES = (
    "Feed inlet",
    "Filtrate outlet",
    "Backwash inlet",
    "Backwash outlet",
    "Vent",
    "Drain",
)


def _schedule_row_for_service(schedule: list[dict] | None, service: str) -> dict | None:
    if not schedule:
        return None
    for row in schedule:
        if row.get("Service") == service:
            return row
    return None


def _truncate(s: str, max_len: int) -> str:
    s = str(s).strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def _flange_type_display(dn: int, rating: str) -> str:
    """
    Typical flange face / family for GA — vendor to confirm.
    PN / EN ratings often paired with flat-face options on utilities.
    """
    r = str(rating).upper()
    is_pn = "PN" in r or "EN" in r
    if dn <= 50:
        return "SOFF" if is_pn else "SORF"
    if dn <= 100:
        return "WN RF" if is_pn else "SORF"
    return "WN RF"


def _elevation_nozzle_table_rows(
    schedule: list[dict] | None,
) -> tuple[list[list[str]], list[str]]:
    """Build cell rows and column headers for the elevation nozzle table."""
    cols = ["Tag", "Service", "DN", "Sch", "Rating", "Flange"]
    rows: list[list[str]] = []
    for i, svc in enumerate(_ELEVATION_SERVICES, start=1):
        row = _schedule_row_for_service(schedule, svc)
        tag = f"N{i}"
        if row is None:
            rows.append([tag, _truncate(svc, 18), "—", "—", "—", "—"])
            continue
        dn = int(row.get("DN (mm)", 0) or 0)
        sch = str(row.get("Schedule", "—"))
        rat = str(row.get("Rating", "—"))
        rows.append([
            tag,
            _truncate(str(row.get("Service", svc)), 18),
            str(dn),
            _truncate(sch, 8),
            _truncate(rat, 10),
            _flange_type_display(dn, rat),
        ])
    return rows, cols


def _lining_interior_text(
    protection_type: str | None,
    lining_result: dict | None,
) -> str:
    if not protection_type or protection_type == "None":
        return "None (CA only)"
    lr = lining_result or {}
    t_mm = lr.get("thickness_mm")
    if t_mm is not None and float(t_mm) > 0:
        return f"{protection_type}  ({float(t_mm):.1f} mm eff.)"
    return str(protection_type)


def _shell_table_rows(
    mech: dict | None,
    end_geometry: str,
    material_name: str,
    protection_type: str | None,
    lining_result: dict | None,
    external_note: str,
    real_id_m: float | None,
) -> tuple[list[list[str]], list[str]]:
    cols = ["Item", "Value"]
    rows: list[list[str]] = []
    if material_name:
        rows.append(["Shell / head material", _truncate(material_name, 28)])
    if mech:
        rows.append([
            "Shell",
            f"t = {mech.get('t_shell_design_mm', '—')} mm  (design)",
        ])
        rows.append([
            "Dish ends (×2)",
            f"{_truncate(end_geometry, 22)}  ·  t = {mech.get('t_head_design_mm', '—')} mm",
        ])
    else:
        rows.append(["Shell / heads", "—"])
    if real_id_m is not None:
        rows.append(["Hydraulic ID (lined)", f"{float(real_id_m) * 1000:.0f} mm"])
    rows.append(["Internal surface", _lining_interior_text(protection_type, lining_result)])
    rows.append(["External surface", _truncate(external_note, 32)])
    return rows, cols


def _add_fabrication_panel(
    rax: plt.Axes,
    *,
    nozzle_schedule: list[dict] | None,
    mech: dict | None,
    end_geometry: str,
    material_name: str,
    protection_type: str | None,
    lining_result: dict | None,
    wt_np: dict | None,
    wt_saddle: dict | None,
    project_name: str,
    doc_number: str,
    revision: str,
    engineer: str,
    external_coating_note: str,
    real_id_m: float | None,
) -> None:
    rax.axis("off")
    rax.set_xlim(0, 1)
    rax.set_ylim(0, 1)

    y = 0.99
    rax.text(
        0.0, y, "AQUASIGHT™ MMF — fabrication notes",
        ha="left", va="top", fontsize=8, fontweight="bold", color="#000000",
        transform=rax.transAxes,
    )
    y -= 0.045
    _today = _dt_tb.date.today().strftime("%d-%b-%Y")
    rax.text(
        0.0, y,
        f"Project: {_truncate(project_name or '—', 26)}   Doc: {_truncate(doc_number or '—', 14)}   Rev: {revision or 'A'}\n"
        f"By: {_truncate(engineer or '—', 22)}   Date: {_today}   Scale: NTS",
        ha="left", va="top", fontsize=6.2, color="#222222",
        transform=rax.transAxes, linespacing=1.35,
    )
    y -= 0.095

    # ── Nozzle table ─────────────────────────────────────────────────────
    nz_rows, nz_cols = _elevation_nozzle_table_rows(nozzle_schedule)
    rax.text(0.0, y, "Nozzle schedule (elevation)", ha="left", va="top",
             fontsize=7, fontweight="bold", transform=rax.transAxes)
    y -= 0.028
    tbl_n = rax.table(
        cellText=nz_rows,
        colLabels=nz_cols,
        cellLoc="left",
        loc="upper left",
        bbox=[0.0, y - 0.36, 1.0, 0.34],
    )
    tbl_n.auto_set_font_size(False)
    tbl_n.set_fontsize(5.5)
    for key, cell in tbl_n.get_celld().items():
        row, _col = key
        cell.set_edgecolor("#333333")
        cell.set_linewidth(0.4)
        if row == 0:
            cell.set_facecolor("#e8e8e8")
            cell.get_text().set_fontweight("bold")
        else:
            cell.set_facecolor("#ffffff")
    y -= 0.38

    # ── Shell / lining table ───────────────────────────────────────────────
    s_rows, s_cols = _shell_table_rows(
        mech, end_geometry, material_name,
        protection_type, lining_result, external_coating_note,
        real_id_m,
    )
    rax.text(0.0, y, "Shell, heads & linings", ha="left", va="top",
             fontsize=7, fontweight="bold", transform=rax.transAxes)
    y -= 0.028
    tbl_s = rax.table(
        cellText=s_rows,
        colLabels=s_cols,
        cellLoc="left",
        loc="upper left",
        bbox=[0.0, y - 0.22, 1.0, 0.20],
    )
    tbl_s.auto_set_font_size(False)
    tbl_s.set_fontsize(5.5)
    for key, cell in tbl_s.get_celld().items():
        row, _col = key
        cell.set_edgecolor("#333333")
        cell.set_linewidth(0.4)
        if row == 0:
            cell.set_facecolor("#e8e8e8")
            cell.get_text().set_fontweight("bold")
        else:
            cell.set_facecolor("#ffffff")
    y -= 0.24

    # ── Nozzle plate & saddles (free text) ────────────────────────────────
    np_lines: list[str] = []
    if wt_np:
        np_lines.append(
            f"Nozzle plate: t = {wt_np.get('t_used_mm', '—')} mm  ·  "
            f"{wt_np.get('n_bores', '—')} × Ø{wt_np.get('bore_diameter_mm', '—')} mm bores  ·  "
            f"beams {wt_np.get('beam_section', '—')} @ {wt_np.get('beam_spacing_mm', '—')} mm"
        )
    else:
        np_lines.append("Nozzle plate: see mechanical calculation print-out.")

    if wt_saddle:
        th = int(wt_saddle.get("contact_angle_deg", 120) or 120)
        pos = wt_saddle.get("saddle_positions_m") or []
        if not pos:
            pos = [wt_saddle.get("saddle_1_from_left_m"), wt_saddle.get("saddle_2_from_left_m")]
        pos_txt = ", ".join(str(p) for p in pos if p is not None)
        esc = " (auto-escalated from requested count)" if wt_saddle.get("auto_escalated_saddles") else ""
        sp = wt_saddle.get("saddle_spacings_m") or []
        sp_txt = " / ".join(f"{s*1000:.0f} mm" for s in sp) if sp else "—"
        np_lines.append(
            f"Saddles: {wt_saddle.get('n_saddles', len(pos))} off{esc}  ·  "
            f"chainage from L tangent: {pos_txt} m  ·  "
            f"centre-to-centre spacings: {sp_txt}  ·  "
            f"θ ≈ {th}° wrap  ·  axes ⊥ vessel centreline."
        )
    else:
        np_lines.append(
            "Saddles: positions per structural calculation; "
            "support centrelines normal to vessel longitudinal axis."
        )

    note_block = "\n".join(np_lines)
    rax.text(
        0.0, y, note_block,
        ha="left", va="top", fontsize=5.8, color="#111111",
        transform=rax.transAxes, linespacing=1.45,
        bbox=dict(boxstyle="square,pad=0.35", facecolor="#f5f5f5",
                   edgecolor="#888888", linewidth=0.6),
    )


def _draw_saddle_symbols(
    ax: plt.Axes,
    wt_saddle: dict,
    *,
    shell_len: float,
    R: float,
    h_d: float,
) -> float:
    """
    Schematic saddle blocks under the cylindrical shell + chainage dimensions.
    Returns the lowest y used (for ylim adjustment).
    """
    positions = wt_saddle.get("saddle_positions_m")
    if not positions:
        positions = [
            wt_saddle.get("saddle_1_from_left_m"),
            wt_saddle.get("saddle_2_from_left_m"),
        ]
    xs: list[float] = []
    for xc in positions:
        try:
            xf = float(xc)
        except (TypeError, ValueError):
            continue
        if 0 <= xf <= shell_len:
            xs.append(xf)
    if not xs:
        return -R * 0.12

    half_w = max(R * 0.22, shell_len * 0.02)
    drop = max(R * 0.12, 0.08)
    for xf in xs:
        trap = mpatches.Polygon(
            [
                (xf - half_w * 0.55, 0.0),
                (xf + half_w * 0.55, 0.0),
                (xf + half_w, -drop),
                (xf - half_w, -drop),
            ],
            closed=True,
            facecolor="#d0d0d0",
            edgecolor="#000000",
            linewidth=0.9,
            zorder=5,
        )
        ax.add_patch(trap)
        ax.plot(
            [xf, xf], [0.0, -drop * 0.35],
            color="#000000", linewidth=0.55, linestyle=(0, (2, 2)), zorder=6,
        )

    _dc = "#000000"
    _akw = dict(arrowstyle="<->", color=_dc, lw=0.75, mutation_scale=6)
    spacings = list(wt_saddle.get("saddle_spacings_m") or [])
    if not spacings and len(xs) >= 2:
        spacings = [round(xs[i + 1] - xs[i], 4) for i in range(len(xs) - 1)]
    ly_dim = -drop - R * 0.18
    for i, gap in enumerate(spacings):
        if i + 1 >= len(xs):
            break
        x0, x1 = xs[i], xs[i + 1]
        yy = ly_dim - (i % 2) * R * 0.07
        ax.annotate("", xy=(x0, yy), xytext=(x1, yy), arrowprops=_akw, zorder=8)
        ax.plot([x0, x0], [yy - R*0.03, yy + R*0.03], color=_dc, lw=0.55, zorder=8)
        ax.plot([x1, x1], [yy - R*0.03, yy + R*0.03], color=_dc, lw=0.55, zorder=8)
        ax.text((x0 + x1) / 2, yy - R * 0.06,
                f"{gap * 1000:.0f} mm",
                ha="center", va="top", fontsize=7.0, color="#000080", zorder=8)

    ax.text(
        shell_len * 0.5, ly_dim - R * 0.14 - (len(spacings) % 2) * R * 0.05,
        "Supports (saddles) — dimensions centre-to-centre; verify with structural GA",
        ha="center", va="top", fontsize=6.2, color="#000000", zorder=7,
    )
    return ly_dim - R * 0.28


def _draw_manholes_schematic(
    ax: plt.Axes,
    manhole_layout: dict | None,
    *,
    shell_len: float,
    ID: float,
    R: float,
) -> None:
    """Manway / inspection openings on shell crown (schematic)."""
    if not manhole_layout:
        return
    n = int(manhole_layout.get("n_user", 0) or 0)
    xs = manhole_layout.get("positions_shell_m") or []
    if n <= 0 or not xs:
        return
    mw = max(shell_len * 0.018, 0.12)
    for i, x in enumerate(xs):
        try:
            xf = float(x)
        except (TypeError, ValueError):
            continue
        if xf < 0 or xf > shell_len:
            continue
        ell = mpatches.Ellipse(
            (xf, ID - mw * 0.15), mw, mw * 0.55, angle=0.0,
            facecolor="#f8f8f8", edgecolor="#000000",
            linewidth=1.0, linestyle="--", zorder=12,
        )
        ax.add_patch(ell)
        ax.text(
            xf, ID + R * 0.035, f"MH{i + 1}",
            ha="center", va="bottom", fontsize=6.5, color="#000000", zorder=13,
        )


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
    cyl_len: float | None = None,
    real_id: float | None = None,
    end_geometry: str = "Elliptic 2:1",
    project_name: str = "",
    doc_number: str = "",
    revision: str = "",
    engineer: str = "",
    # ── Optional fabrication / GA data (right panel) ─────────────────────
    nozzle_schedule: list[dict] | None = None,
    mech: dict[str, Any] | None = None,
    wt_np: dict[str, Any] | None = None,
    wt_saddle: dict[str, Any] | None = None,
    protection_type: str | None = None,
    lining_result: dict[str, Any] | None = None,
    material_name: str = "",
    external_coating_note: str = "Shop primer + external coating per project spec",
    manhole_layout: dict[str, Any] | None = None,
    show_fabrication_panel: bool = False,
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
    show_fabrication_panel
                      : When True, reserve a right column for nozzle N1…,
                        shell/lining table, and saddle / plate notes.
    """
    ID = vessel_id_m
    L = total_length_m
    h_d = h_dish_m
    R = ID / 2.0

    use_panel = bool(show_fabrication_panel)

    if figsize is None:
        aspect = L / ID
        w_main = min(20, max(12, aspect * 5.0))
        if use_panel:
            figsize = (w_main + 4.2, 6.4)
        else:
            figsize = (w_main, 5.8)

    if use_panel:
        fig = plt.figure(figsize=figsize, facecolor="#ffffff")
        gs = GridSpec(
            1, 2, figure=fig,
            width_ratios=[2.45, 1.05], wspace=0.06,
            left=0.05, right=0.98, top=0.90, bottom=0.08,
        )
        ax = fig.add_subplot(gs[0, 0])
        rax = fig.add_subplot(gs[0, 1])
    else:
        fig, ax = plt.subplots(figsize=figsize)
        rax = None

    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

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
        linewidth=1.65,
        zorder=1,
    )
    ax.add_patch(hull)

    # Centreline — ISO 128 dash-dot-dash, extends beyond each head
    _cl_ext = max(h_d * 0.5, 0.15)
    ax.plot([-h_d - _cl_ext, L + h_d + _cl_ext], [R, R],
            color="#888888", linewidth=0.8,
            linestyle=(0, (12, 4, 2, 4)), zorder=2)
    ax.text(L + h_d + _cl_ext + R * 0.05, R, "℄",
            ha="left", va="center", fontsize=9, color="#888888", zorder=2)

    # ── Nozzle plate (thick line + symbolic strainer nozzles) ─────────────
    ax.plot([0, L], [nozzle_plate_h_m] * 2,
            color="#000000", linewidth=3.5, solid_capstyle="butt", zorder=6)
    _np_cap = f"Nozzle plate  h = {nozzle_plate_h_m:.2f} m"
    if wt_np:
        _np_cap += (
            f"  ·  t = {wt_np.get('t_used_mm', '—')} mm  ·  "
            f"{wt_np.get('n_bores', '—')} × Ø{wt_np.get('bore_diameter_mm', '—')} mm"
        )
    ax.text(L * 0.02, nozzle_plate_h_m + R * 0.04,
            _np_cap,
            ha="left", va="bottom", fontsize=7.5, color="#000000", zorder=7)

    if wt_np and wt_np.get("n_bores"):
        n_noz = int(max(5, min(40, wt_np["n_bores"])))
    else:
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
        _fill = _media_layer_facecolor(lyr)
        _edge = "#4a4a4a" if lyr.get("is_support") else "#555555"
        rect = mpatches.Rectangle(
            (0, curr_h), L, depth,
            facecolor=_fill, edgecolor=_edge, linewidth=0.55,
            zorder=3,
        )
        ax.add_patch(rect)
        ax.fill_between(
            [0, L], curr_h, curr_h + depth,
            hatch="////" if lyr.get("is_support") else "...",
            facecolor="none", edgecolor="#6a6a6a", linewidth=0.28, zorder=4,
        )
        ax.text(
            L * 0.98, curr_h + depth / 2,
            f"{lyr['Type']}  {depth:.2f} m",
            ha="right", va="center", fontsize=9,
            color="#f4f4f4" if lyr.get("Type") in _MEDIA_DARK_FILL_TYPES else "#222222",
            zorder=7,
        )

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
    dx0 = -h_d * 0.35
    dx1 = -h_d * 0.70

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
    _id_note = f"ID\n{vessel_id_m * 1000:.0f} mm"
    if real_id is not None and abs(real_id - vessel_id_m) > 1e-6:
        _id_note += f"\n(real {real_id * 1000:.0f} mm)"
    ax.text(id_x + 0.06, R,
            _id_note,
            ha="left", va="center",
            fontsize=9, fontweight="bold", color="#1a3a5c", zorder=8)

    # ── Right side: distance from crown annotations ───────────────────────
    ann_x = L * 0.96

    if ID > collector_h_m:
        dist_c = (ID - collector_h_m) * 1000
        ax.annotate("", xy=(ann_x, ID), xytext=(ann_x, collector_h_m),
                    arrowprops=dict(arrowstyle="<->", color="#777",
                                   lw=0.8, mutation_scale=7), zorder=7)
        ax.text(ann_x + 0.06, (ID + collector_h_m) / 2,
                f"{dist_c:.0f} mm",
                ha="left", va="center", fontsize=7, color="#777", zorder=7)

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

    ly2 = ly1 - R * 0.40
    _x0, _x1 = -h_d, _shell_len + h_d
    ax.annotate("", xy=(_x0, ly2), xytext=(_x1, ly2),
                arrowprops=_akw, zorder=8)
    ax.annotate("", xy=(_x1, ly2), xytext=(_x0, ly2),
                arrowprops=_akw, zorder=8)
    for tx in (_x0, _x1):
        ax.plot([tx, tx], [ly2 - R*0.07, ly2 + R*0.07], color=_dc, lw=0.6, zorder=8)
    _total_oo = _shell_len + 2 * h_d
    ax.text((_x0 + _x1) / 2, ly2 - R * 0.10,
            f"Total (O/O)  {_total_oo:.2f} m",
            ha="center", va="top", fontsize=8.5, color="#000000", zorder=8)

    _ysad = -R * 1.40
    for tx in (0, _shell_len):
        ax.plot([tx, tx], [-R * 0.12, 0], color=_dc, lw=0.6, zorder=5)

    if wt_saddle:
        _ysad = _draw_saddle_symbols(ax, wt_saddle, shell_len=_shell_len, R=R, h_d=h_d)

    # ── Nozzle stubs (ISO schematic) + N-tags ────────────────────────────
    _sw = L * 0.028
    _sh = R * 0.20
    _nkw = dict(facecolor="white", edgecolor="#000000", linewidth=1.2, zorder=9)
    _nlkw = dict(fontsize=7.5, color="#000000", zorder=10)
    _nk_tag = dict(fontsize=6.5, color="#1a3a5c", fontweight="bold", zorder=11)

    _noz_defs = [
        (L / 2,   "top",   "Feed\ninlet",   "Feed inlet"),
        (L / 2,   "bot",   "Filtrate\noutlet", "Filtrate outlet"),
        (0,       "left",  "BW\ninlet",     "Backwash inlet"),
        (L,       "right", "BW\noutlet",    "Backwash outlet"),
        (L * 0.2, "top",   "Vent",          "Vent"),
        (L * 0.72, "bot",   "Drain",         "Drain"),
    ]
    for idx, (_xp, _side, _lbl, _) in enumerate(_noz_defs, start=1):
        tag = f"N{idx}"
        if _side == "top":
            ax.add_patch(mpatches.Rectangle(
                (_xp - _sw/2, ID), _sw, _sh, **_nkw))
            ax.text(_xp, ID + _sh + R*0.02, tag, ha="center", va="bottom", **_nk_tag)
            ax.text(_xp, ID + _sh + R*0.085, _lbl,
                    ha="center", va="bottom", **_nlkw)
        elif _side == "bot":
            ax.add_patch(mpatches.Rectangle(
                (_xp - _sw/2, -_sh), _sw, _sh, **_nkw))
            ax.text(_xp, -_sh - R*0.02, tag, ha="center", va="top", **_nk_tag)
            ax.text(_xp, -_sh - R*0.085, _lbl,
                    ha="center", va="top", **_nlkw)
        elif _side == "left":
            ax.add_patch(mpatches.Rectangle(
                (-_sh, R - _sw/2), _sh, _sw, **_nkw))
            ax.text(-_sh - R*0.02, R, tag, ha="right", va="center", **_nk_tag)
            ax.text(-_sh - R*0.09, R, _lbl,
                    ha="right", va="center", **_nlkw)
        else:
            ax.add_patch(mpatches.Rectangle(
                (L, R - _sw/2), _sh, _sw, **_nkw))
            ax.text(L + _sh + R*0.02, R, tag, ha="left", va="center", **_nk_tag)
            ax.text(L + _sh + R*0.09, R, _lbl,
                    ha="left", va="center", **_nlkw)

    _draw_manholes_schematic(ax, manhole_layout, shell_len=L, ID=ID, R=R)

    # ── Colour legend ─────────────────────────────────────────────────────
    legend_handles = []
    for lyr in layers:
        patch = mpatches.Patch(
            facecolor=_media_layer_facecolor(lyr),
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
        title="Media (settled bed)",
    )

    ax.text(
        0.015, 0.012,
        "Vertical filter fab drawings are for notation / title-block style reference only — "
        "this geometry is horizontal.",
        transform=ax.transAxes,
        fontsize=5.9,
        color="#444444",
        ha="left",
        va="bottom",
        style="italic",
        linespacing=1.15,
        zorder=20,
    )

    _sl = cyl_len if cyl_len is not None else total_length_m
    ax.set_xlim(-h_d * 4.0, _sl + h_d * 3.5)
    ax.set_ylim(min(-R * 1.40, _ysad - R * 0.06), ID + R * 0.65)
    ax.set_aspect("equal", adjustable="datalim")
    ax.axis("off")

    ax.set_title(
        "Horizontal Multi-Media Filter — Theoretical Elevation Section\n"
        f"ID {vessel_id_m * 1000:.0f} mm  ·  L(T/T) {_sl:.2f} m  ·  "
        f"Hₙₚ {nozzle_plate_h_m * 1000:.0f} mm  ·  "
        f"{len(layers)}-layer bed",
        fontsize=9.5, pad=6, fontweight="bold", color="#000000",
    )

    if use_panel and rax is not None:
        _add_fabrication_panel(
            rax,
            nozzle_schedule=nozzle_schedule,
            mech=mech,
            end_geometry=end_geometry,
            material_name=material_name,
            protection_type=protection_type,
            lining_result=lining_result,
            wt_np=wt_np,
            wt_saddle=wt_saddle,
            project_name=project_name,
            doc_number=doc_number,
            revision=revision,
            engineer=engineer,
            external_coating_note=external_coating_note,
            real_id_m=real_id,
        )
    else:
        _today_tb = _dt_tb.date.today().strftime("%d-%b-%Y")
        _tb = (
            "AQUASIGHT™ MMF\n"
            + "─" * 38 + "\n"
            + f"Project:      {project_name or '—'}\n"
            + f"Doc No:       {doc_number or '—'}   Rev: {revision or 'A'}\n"
            + f"Prepared by:  {engineer or '—'}   Date: {_today_tb}\n"
            + "─" * 38 + "\n"
            + "Scale: NTS    Units: m/mm   Sheet: 1/1"
        )
        fig.text(
            0.75, 0.02, _tb,
            ha="left", va="bottom", fontsize=7,
            fontfamily="monospace", color="#000000",
            transform=fig.transFigure,
            bbox=dict(boxstyle="square,pad=0.6",
                      facecolor="white", edgecolor="#000000", linewidth=1.0),
        )
        fig.tight_layout(pad=1.0)

    return fig
