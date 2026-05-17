"""
Nozzle-plate underdrain hydraulics at **backwash** flow (deterministic screening).

**Brick / staggered layout** (plan view):
  • **X** = along vessel length (drum axis), full L_plate
  • **Y** = across plate chord, centred on 0 in plots
  • Pitch from √(A_plate / N_total); min spacing 1.5× bore
  • Odd rows offset P_long/2; pattern centred on plate

Does **not** model filtration / raw-water feed through the plate.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any

from engine.collector_geometry import chord_half_width_m, lateral_geometry_from_vessel

GRAVITY = 9.81
_HOLE_V_WARN_M_S = 3.0
_OPEN_AREA_LIMIT_PCT = 60.0
_MAL_CAP = 2.0
_F_DARCY = 0.02
_HL_F = 1.0

_MIN_SPACING_BORE_MULT = 1.5
_LAYOUT_REVISION = 6  # triangular density grid — full plate coverage


def chord_at_axial_x(
    x_m: float,
    *,
    h_plate_m: float,
    vessel_radius_m: float,
    h_dish_m: float,
    straight_cyl_len_m: float,
) -> float:
    """Local nozzle-plate chord (m) at axial position x along total vessel length."""
    R = max(0.01, float(vessel_radius_m))
    h_d = max(0.0, float(h_dish_m))
    Ls = max(0.0, float(straight_cyl_len_m))
    x_cyl0 = h_d
    x_cyl1 = h_d + Ls

    def _chord_at_radius(Rz: float) -> float:
        hp = float(h_plate_m)
        if hp <= 0 or Rz <= 0 or hp >= 2 * Rz:
            return 0.0
        return 2.0 * math.sqrt(max(0.0, Rz**2 - (Rz - hp) ** 2))

    if x_cyl0 <= x_m <= x_cyl1:
        return _chord_at_radius(R)
    if h_d <= 0:
        return 0.0
    if x_m < x_cyl0:
        z = h_d - x_m
        if z < 0 or z > h_d:
            return 0.0
        Rz = R * math.sqrt(max(0.0, 1.0 - (z / h_d) ** 2))
        return _chord_at_radius(Rz)
    z = x_m - x_cyl1
    if z < 0 or z > h_d:
        return 0.0
    Rz = R * math.sqrt(max(0.0, 1.0 - (z / h_d) ** 2))
    return _chord_at_radius(Rz)


def plate_outline_samples(
    *,
    total_length_m: float,
    h_plate_m: float,
    vessel_radius_m: float,
    h_dish_m: float,
    straight_cyl_len_m: float,
    n_samples: int = 100,
) -> tuple[list[float], list[float], list[float]]:
    """Top/bottom plate edges for plan view (x, y_top, y_bot) in plot coordinates."""
    n = max(8, int(n_samples))
    xs = [i * total_length_m / (n - 1) for i in range(n)]
    y_top: list[float] = []
    y_bot: list[float] = []
    for x in xs:
        w = chord_at_axial_x(
            x,
            h_plate_m=h_plate_m,
            vessel_radius_m=vessel_radius_m,
            h_dish_m=h_dish_m,
            straight_cyl_len_m=straight_cyl_len_m,
        )
        y_top.append(w / 2.0)
        y_bot.append(-w / 2.0)
    return xs, y_top, y_bot


def plate_axial_extent_m(
    *,
    cyl_len_m: float,
    h_dish_m: float,
    pitch_m: float,
    edge_m: float,
) -> tuple[float, float, float]:
    """Usable drum axis (m) inset from dish zones — for plot head shading only."""
    cyl = max(0.1, float(cyl_len_m))
    h_dish = max(0.0, float(h_dish_m))
    pitch = max(0.001, float(pitch_m))
    edge = max(0.0, float(edge_m))
    inset = max(edge, pitch / 2.0, h_dish * 0.4, cyl * 0.015)
    inset = min(inset, max(0.05, cyl * 0.45))
    x0 = inset
    x1 = cyl - inset
    if x1 <= x0:
        x0, x1 = cyl * 0.05, cyl * 0.95
    return round(x0, 4), round(x1, 4), round(inset, 4)


def staggered_plate_layout(
    *,
    cyl_len_m: float,
    n_holes_total: int,
    chord_m: float,
    h_dish_m: float = 0.0,
    n_rows_override: int = 0,
    bore_d_mm: float = 50.0,
    pitch_chord_mm: float | None = None,
    edge_clearance_mm: float | None = None,
    total_length_m: float = 0.0,
    straight_cyl_len_m: float = 0.0,
    vessel_id_m: float = 0.0,
    nozzle_plate_h_m: float = 0.0,
    plate_area_total_m2: float = 0.0,
    area_cyl_m2: float = 0.0,
    area_one_dish_m2: float = 0.0,
    np_density_per_m2: float = 0.0,
) -> dict[str, Any]:
    """
    Triangular (staggered) nozzle grid — density × plate area, full vessel outline.

    See ``engine.nozzle_plate_distribution`` for pitch and coverage algorithm.
    """
    del pitch_chord_mm, edge_clearance_mm, n_rows_override

    from engine.nozzle_plate_distribution import build_triangular_nozzle_layout

    h_d = max(0.0, float(h_dish_m))
    l_total = max(0.1, float(total_length_m) if total_length_m > 0 else float(cyl_len_m))
    l_straight = max(
        0.1,
        float(straight_cyl_len_m) if straight_cyl_len_m > 0 else max(0.1, l_total - 2.0 * h_d),
    )
    if l_total < l_straight + 1e-6:
        l_total = l_straight + 2.0 * h_d

    w = max(0.1, float(chord_m))
    r = max(0.01, float(vessel_id_m) / 2.0) if vessel_id_m > 0 else w
    h_plate = max(0.01, float(nozzle_plate_h_m)) if nozzle_plate_h_m > 0 else 0.5
    d_m = max(0.001, float(bore_d_mm) / 1000.0)

    a_cyl = float(area_cyl_m2) if area_cyl_m2 > 0 else w * l_straight
    a_dish = float(area_one_dish_m2) if area_one_dish_m2 > 0 else 0.0
    a_plate = max(
        w * l_total,
        float(plate_area_total_m2) if plate_area_total_m2 > 0 else a_cyl + 2.0 * a_dish,
    )

    tri = build_triangular_nozzle_layout(
        plate_area_m2=a_plate,
        chord_width_m=w,
        total_length_m=l_total,
        straight_cyl_len_m=l_straight,
        vessel_id_m=float(vessel_id_m),
        nozzle_plate_h_m=h_plate,
        h_dish_m=h_d,
        bore_d_mm=float(bore_d_mm),
        n_holes_total=int(n_holes_total),
        np_density_per_m2=float(np_density_per_m2),
    )
    holes_xy = tri["holes_xy"]
    n_target = int(tri["n_target"])
    n_placed = int(tri["n_placed"])
    p = float(tri["pitch_m"])
    edge_x = float(tri["edge_clearance_m"])
    p_row = float(tri["pitch_row_spacing_m"])
    n_rows = int(tri["n_rows_across_chord"])
    x_cyl0 = float(tri["x_cyl_start_m"])
    x_cyl1 = float(tri["x_cyl_end_m"])
    n_in_dish = int(tri["n_holes_in_dish_zones"])
    n_in_cyl = int(tri["n_holes_in_cyl_zone"])

    ol_x, ol_top, ol_bot = plate_outline_samples(
        total_length_m=l_total,
        h_plate_m=h_plate,
        vessel_radius_m=r,
        h_dish_m=h_d,
        straight_cyl_len_m=l_straight,
    )

    plate_rows: list[dict[str, Any]] = []
    by_row: dict[int, list[tuple[float, float, int, int, bool]]] = {}
    for tup in holes_xy:
        by_row.setdefault(tup[2], []).append(tup)
    for ri in sorted(by_row.keys()):
        row_holes = by_row[ri]
        stagger = row_holes[0][4]
        xs = [h[0] for h in row_holes]
        y_plot = row_holes[0][1]
        plate_rows.append({
            "row_index": ri,
            "y_chord_m": round(y_plot + w / 2.0, 4),
            "y_plot_m": round(y_plot, 4),
            "staggered": stagger,
            "x_positions_m": xs,
            "n_holes": len(xs),
        })

    x_counts = Counter(h[0] for h in holes_xy)
    positions_m = sorted(x_counts.keys())
    holes_per_station = [x_counts[x] for x in positions_m]
    xs_all = [h[0] for h in holes_xy]
    ys_all = [h[1] for h in holes_xy]
    field_x0 = float(tri["field_x_start_m"])
    field_x1 = float(tri["field_x_end_m"])
    field_y0 = float(tri["field_y_plot_start_m"])
    field_y1 = float(tri["field_y_plot_end_m"])

    return {
        "layout_mode": "triangular_stagger",
        "layout_density_per_m2": float(tri["density_per_m2_actual"]),
        "layout_axial_utilization": float(tri["axial_utilization"]),
        "layout_advisories": list(tri.get("advisories") or []),
        "pitch_triangular_m": round(p, 6),
        "n_rows_across_chord": n_rows,
        "n_per_row_along_drum": len(positions_m),
        "n_columns": len(positions_m),
        "n_phys_rows": len(positions_m),
        "n_along_chord": n_rows,
        "holes_per_row": len(positions_m),
        "pitch_long_m": round(p, 4),
        "pitch_trans_m": round(p_row, 4),
        "pitch_chord_mm": round(p * 1000.0, 1),
        "pitch_long_mm": round(p * 1000.0, 1),
        "pitch_trans_mm": round(p_row * 1000.0, 1),
        "edge_clearance_mm": round(edge_x * 1000.0, 1),
        "min_spacing_mm": round(max(2.5 * d_m, d_m + 0.05) * 1000.0, 1),
        "column_pitch_m": round(
            (positions_m[1] - positions_m[0]) if len(positions_m) > 1 else p, 4
        ),
        "row_spacing_m": round(p_row, 4),
        "plate_x_start_m": 0.0,
        "plate_x_end_m": round(l_total, 4),
        "field_x_start_m": round(field_x0, 4),
        "field_x_end_m": round(field_x1, 4),
        "field_y_start_m": round(field_y0 + w / 2.0, 4),
        "field_y_end_m": round(field_y1 + w / 2.0, 4),
        "field_y_plot_start_m": round(field_y0, 4),
        "field_y_plot_end_m": round(field_y1, 4),
        "head_inset_m": round(h_d, 4),
        "h_dish_m": round(h_d, 4),
        "straight_cyl_len_m": round(l_straight, 4),
        "total_length_m": round(l_total, 4),
        "x_cyl_start_m": round(x_cyl0, 4),
        "x_cyl_end_m": round(x_cyl1, 4),
        "n_holes_in_dish_zones": n_in_dish,
        "n_holes_in_cyl_zone": n_in_cyl,
        "includes_dish_heads": h_d > 0.01,
        "plate_outline_x_m": [round(v, 4) for v in ol_x],
        "plate_outline_y_top_m": [round(v, 4) for v in ol_top],
        "plate_outline_y_bot_m": [round(v, 4) for v in ol_bot],
        "plate_area_total_m2": round(a_plate, 4),
        "plate_area_cyl_m2": round(a_cyl, 4),
        "plate_area_one_dish_m2": round(a_dish, 4),
        "cyl_len_m": round(l_total, 4),
        "chord_m": w,
        "plate_area_rect_m2": round(w * l_straight, 4),
        "positions_m": positions_m,
        "holes_per_phys_row": holes_per_station,
        "plate_rows": plate_rows,
        "holes_xy": holes_xy,
        "actual_holes_from_layout": n_placed,
        "target_holes": n_target,
        "edge_margin_x_m": round(edge_x, 4),
        "edge_margin_y_m": round(w / 2.0 - abs(field_y1), 4) if ys_all else 0.0,
    }


def build_staggered_nozzle_hole_network(
    *,
    holes_xy: list[tuple[float, float, int, int, bool]],
    q_by_x: dict[float, float],
    chord_m: float,
    orifice_d_m: float,
) -> list[dict[str, Any]]:
    """Build per-hole table from (x, y) layout and flow per x station."""
    d_orf = max(0.001, float(orifice_d_m))
    area = math.pi * (d_orf / 2.0) ** 2
    chord = max(0.1, float(chord_m))
    rows: list[dict[str, Any]] = []
    n_at_x_map = Counter(round(hx, 4) for hx, *_ in holes_xy)

    for x, y_plot, ri, hi, stagger in holes_xy:
        q_station = float(q_by_x.get(round(x, 4), 0.0) or 0.0)
        n_at_x = max(1, n_at_x_map.get(round(x, 4), 1))
        q = q_station / n_at_x
        v_m_s = q / area if area > 0 else 0.0
        y_chord = y_plot + chord / 2.0
        rows.append({
            "lateral_index": ri,
            "row_index": ri,
            "hole_index": hi,
            "column_index": hi,
            "sub_row": 2 if stagger else 1,
            "staggered": stagger,
            "station_m": round(float(x), 4),
            "y_along_chord_m": round(y_chord, 4),
            "y_along_lateral_m": round(y_chord, 4),
            "y_plot_m": round(float(y_plot), 4),
            "flow_m3h": round(q * 3600.0, 4),
            "velocity_m_s": round(v_m_s, 3),
            "orifice_d_mm": round(d_orf * 1000.0, 2),
            "construction": "Nozzle plate (brick rows)",
        })
    return rows


def compute_nozzle_plate_bw_hydraulics(
    *,
    q_bw_m3h: float,
    nozzle_plate_area_m2: float,
    cyl_len_m: float,
    nominal_id_m: float,
    np_bore_dia_mm: float,
    np_density_per_m2: float,
    n_holes_total: int = 0,
    chord_m: float = 0.0,
    straight_cyl_len_m: float = 0.0,
    area_cyl_m2: float = 0.0,
    area_one_dish_m2: float = 0.0,
    collector_header_id_m: float,
    nozzle_plate_h_m: float,
    collector_h_m: float = 0.0,
    n_rows_along_drum: int = 0,
    h_dish_m: float = 0.0,
    discharge_coefficient: float = 0.62,
    header_feed_mode: str = "one_end",
    k_tee_branch: float = 0.0,
    rho_water: float = 1000.0,
    friction_factor: float = _F_DARCY,
    media_avg_bed_area_m2: float = 0.0,
) -> dict[str, Any]:
    """BW nozzle-plate screening — brick row layout + 1D header along drum."""
    del discharge_coefficient, media_avg_bed_area_m2

    _inactive: dict[str, Any] = {
        "active": False,
        "underdrain_type": "nozzle_plate",
        "method": "nozzle_plate_bw",
        "note": None,
    }

    q_bw = max(0.0, float(q_bw_m3h))
    plate_area = max(0.01, float(nozzle_plate_area_m2))
    d_m = max(0.001, float(np_bore_dia_mm) / 1000.0)
    dens = max(0.1, float(np_density_per_m2))
    cyl = max(0.1, float(cyl_len_m))
    d_header = max(0.02, float(collector_header_id_m))

    # Hole count always from sidebar **Hole density (/m²)** × plate area (not a fixed constant).
    n_holes_target = max(1, int(round(dens * plate_area)))
    if int(n_holes_total) > 0 and abs(int(n_holes_total) - n_holes_target) > max(
        5, 0.02 * n_holes_target
    ):
        n_holes_target = max(1, int(n_holes_total))

    geo = lateral_geometry_from_vessel(
        vessel_id_m=nominal_id_m,
        nozzle_plate_h_m=float(nozzle_plate_h_m or 0.5),
        collector_h_m=float(collector_h_m or nozzle_plate_h_m or 0.5),
        cyl_len_m=cyl,
    )
    r = float(geo.get("vessel_radius_m") or nominal_id_m / 2.0)
    h_np = float(geo.get("underdrain_axis_h_m") or nozzle_plate_h_m)
    chord_plate = float(chord_m) if float(chord_m) > 0 else max(0.1, chord_half_width_m(r, h_np) * 2.0)

    h_d = float(h_dish_m)
    L_total = max(0.1, float(cyl_len_m))
    L_straight = (
        max(0.1, float(straight_cyl_len_m))
        if float(straight_cyl_len_m) > 0
        else (max(0.1, L_total - 2.0 * h_d) if h_d > 0 else L_total)
    )

    layout = staggered_plate_layout(
        cyl_len_m=L_total,
        total_length_m=L_total,
        straight_cyl_len_m=L_straight,
        vessel_id_m=float(nominal_id_m),
        nozzle_plate_h_m=float(nozzle_plate_h_m or h_np),
        n_holes_total=n_holes_target,
        chord_m=chord_plate,
        h_dish_m=h_d,
        plate_area_total_m2=plate_area,
        area_cyl_m2=float(area_cyl_m2),
        area_one_dish_m2=float(area_one_dish_m2),
        n_rows_override=int(n_rows_along_drum) if int(n_rows_along_drum) > 0 else 0,
        bore_d_mm=float(np_bore_dia_mm),
        np_density_per_m2=dens,
    )

    positions = layout["positions_m"]
    holes_per_phys = layout["holes_per_phys_row"]
    n_orf_header = max(holes_per_phys) if holes_per_phys else 1
    n_holes = int(layout["actual_holes_from_layout"])
    n_rows = layout["n_rows_across_chord"]
    n_per_row = layout["n_per_row_along_drum"]
    p_long = layout["pitch_long_m"]

    a_hole = math.pi * (d_m / 2.0) ** 2
    a_open = n_holes * a_hole
    q_m3s = q_bw / 3600.0
    v_uniform = q_m3s / a_open if a_open > 1e-12 else 0.0
    open_frac_pct = min(100.0, a_open / plate_area * 100.0) if plate_area > 0 else 0.0

    if q_m3s <= 1e-12:
        _inactive["note"] = "Zero BW flow — nozzle plate screening inactive."
        _inactive.update(_layout_summary(layout, n_holes_target, plate_area, dens, n_holes, open_frac_pct))
        return _inactive

    from engine.collector_manifold import (
        normalize_header_feed_mode,
        solve_lateral_distribution_dual_end,
        solve_lateral_distribution_one_end,
        _segment_lengths,
    )

    feed_mode = normalize_header_feed_mode(header_feed_mode)
    seg_lens = _segment_lengths(positions, cyl)
    n_phys = len(positions)

    _solve_kw = dict(
        q_total_m3_s=q_m3s,
        positions_m=positions,
        segment_lengths_m=seg_lens,
        d_header_m=d_header,
        d_lat_m=d_m,
        l_lat_m=max(0.05, p_long),
        n_orifices=n_orf_header,
        friction_factor=friction_factor,
        headloss_factor=_HL_F,
        rho=float(rho_water),
        k_tee_branch=max(0.0, float(k_tee_branch)),
    )

    dual_meta: dict[str, Any] = {}
    if feed_mode == "dual_end":
        q_lat, dist_iter, dist_res, dist_ok, dual_meta = solve_lateral_distribution_dual_end(
            q_total_m3_s=q_m3s,
            positions_m=positions,
            cyl_len_m=cyl,
            d_header_m=d_header,
            d_lat_m=d_m,
            l_lat_m=max(0.05, p_long),
            n_orifices=n_orf_header,
            friction_factor=friction_factor,
            headloss_factor=_HL_F,
            rho=float(rho_water),
            k_tee_branch=max(0.0, float(k_tee_branch)),
        )
    else:
        q_lat, dist_iter, dist_res, dist_ok = solve_lateral_distribution_one_end(**_solve_kw)

    q_by_x = {round(positions[i], 4): q_lat[i] for i in range(len(positions))}
    hole_net = build_staggered_nozzle_hole_network(
        holes_xy=layout["holes_xy"],
        q_by_x=q_by_x,
        chord_m=chord_plate,
        orifice_d_m=d_m,
    )

    vels = [float(h.get("velocity_m_s", 0) or 0) for h in hole_net if h.get("velocity_m_s")]
    v_max = max(vels) if vels else v_uniform
    v_min = min(vels) if vels else v_uniform

    q_mean = q_m3s / n_phys if n_phys > 0 else q_m3s
    q_max = max(q_lat) if q_lat else q_m3s
    q_min = min(q_lat) if q_lat else q_m3s
    mal = max(1.0, min(_MAL_CAP, q_max / q_mean if q_mean > 1e-12 else 1.0))
    imb_pct = (q_max - q_min) / q_mean * 100.0 if q_mean > 1e-12 else 0.0

    advisories = _build_advisories(
        n_holes, n_holes_target, layout, v_max, open_frac_pct, imb_pct,
    )
    for _msg in layout.get("layout_advisories") or []:
        advisories.append({
            "severity": "warning",
            "topic": "Nozzle layout",
            "detail": str(_msg),
        })

    return {
        "active": True,
        "underdrain_type": "nozzle_plate",
        "layout": str(layout.get("layout_mode", "triangular_stagger")),
        "layout_revision": _LAYOUT_REVISION,
        "method": (
            f"Nozzle plate (BW) — triangular stagger P={layout['pitch_long_mm']:.0f} mm "
            f"(row Δ={layout['pitch_trans_mm']:.0f} mm); "
            f"{'dual-end' if feed_mode == 'dual_end' else 'one-end'} header"
        ),
        "screening_note": (
            f"**Triangular layout:** **{n_holes:,}** holes · ρ **{dens:.0f}**/m² · "
            f"open area **{open_frac_pct:.1f} %** · "
            f"**{n_rows}** rows · **{layout.get('total_length_m', cyl):.2f} m** plate "
            f"(dish **{layout.get('n_holes_in_dish_zones', 0):,}** + cyl "
            f"**{layout.get('n_holes_in_cyl_zone', 0):,}**)."
        ),
        "q_bw_m3h": round(q_bw, 3),
        "hole_d_mm": round(d_m * 1000.0, 2),
        **_layout_summary(layout, n_holes_target, plate_area, dens, n_holes, open_frac_pct),
        "distribution_factor_calc": round(mal, 4),
        "flow_imbalance_pct": round(imb_pct, 2),
        "distribution_iterations": int(dist_iter),
        "distribution_residual_rel": round(float(dist_res), 5),
        "distribution_converged": bool(dist_ok),
        "header_feed_mode": feed_mode,
        "dual_end_meta": dual_meta,
        "collector_header_id_m": round(d_header, 4),
        "hole_network": hole_net,
        "orifice_velocity_uniform_m_s": round(v_uniform, 3),
        "orifice_velocity_max_m_s": round(v_max, 3),
        "orifice_velocity_min_m_s": round(v_min, 3),
        "open_area_limit_pct": _OPEN_AREA_LIMIT_PCT,
        "advisories": advisories,
    }


def _layout_summary(
    layout: dict[str, Any],
    n_target: int,
    plate_area: float,
    dens: float,
    n_holes: int,
    open_frac_pct: float,
) -> dict[str, Any]:
    return {
        "design_basis": _design_basis_text(layout, n_target, plate_area, dens),
        "cyl_len_m": layout["cyl_len_m"],
        "chord_m": layout["chord_m"],
        "nozzle_plate_area_m2": round(plate_area, 4),
        "plate_area_rect_m2": layout.get("plate_area_rect_m2"),
        "np_density_per_m2": dens,
        "n_holes_total": n_holes,
        "n_holes_target": n_target,
        "n_holes_placed": n_holes,
        "n_rows_across_chord": layout["n_rows_across_chord"],
        "n_per_row_along_drum": layout["n_per_row_along_drum"],
        "n_rows_along_drum": layout["n_rows_across_chord"],
        "n_columns": layout["n_columns"],
        "n_phys_rows": layout["n_phys_rows"],
        "n_along_chord": layout["n_rows_across_chord"],
        "holes_per_row": layout["holes_per_row"],
        "pitch_chord_mm": layout["pitch_chord_mm"],
        "pitch_long_mm": layout["pitch_long_mm"],
        "pitch_trans_mm": layout["pitch_trans_mm"],
        "edge_clearance_mm": layout["edge_clearance_mm"],
        "column_pitch_m": layout["column_pitch_m"],
        "row_spacing_m": layout["row_spacing_m"],
        "plate_x_start_m": layout["plate_x_start_m"],
        "plate_x_end_m": layout["plate_x_end_m"],
        "field_x_start_m": layout["field_x_start_m"],
        "field_x_end_m": layout["field_x_end_m"],
        "field_y_start_m": layout["field_y_start_m"],
        "field_y_end_m": layout["field_y_end_m"],
        "field_y_plot_start_m": layout.get("field_y_plot_start_m"),
        "field_y_plot_end_m": layout.get("field_y_plot_end_m"),
        "head_inset_m": layout["head_inset_m"],
        "open_area_fraction_pct": round(open_frac_pct, 2),
        "layout_revision": _LAYOUT_REVISION,
        "total_length_m": layout.get("total_length_m"),
        "straight_cyl_len_m": layout.get("straight_cyl_len_m"),
        "x_cyl_start_m": layout.get("x_cyl_start_m"),
        "x_cyl_end_m": layout.get("x_cyl_end_m"),
        "n_holes_in_dish_zones": layout.get("n_holes_in_dish_zones"),
        "n_holes_in_cyl_zone": layout.get("n_holes_in_cyl_zone"),
        "includes_dish_heads": layout.get("includes_dish_heads"),
        "plate_outline_x_m": layout.get("plate_outline_x_m"),
        "plate_outline_y_top_m": layout.get("plate_outline_y_top_m"),
        "plate_outline_y_bot_m": layout.get("plate_outline_y_bot_m"),
        "layout_advisories": list(layout.get("layout_advisories") or []),
        "layout_axial_utilization": layout.get("layout_axial_utilization"),
        "pitch_triangular_m": layout.get("pitch_triangular_m"),
        "layout_mode": layout.get("layout_mode"),
    }


def _design_basis_text(
    layout: dict[str, Any],
    n_target: int,
    plate_area: float,
    dens: float,
) -> str:
    n_act = int(layout.get("actual_holes_from_layout", 0))
    mode = str(layout.get("layout_mode", "triangular_stagger"))
    util = layout.get("layout_axial_utilization")
    util_s = f" · axial fill **{100.0 * float(util):.0f} %**" if isinstance(util, (int, float)) else ""
    return (
        f"**{mode}**: **{n_act:,}** placed (target **{n_target:,}**) · "
        f"P **{layout['pitch_long_mm']:.0f} mm** (Δrow **{layout['pitch_trans_mm']:.0f} mm**) · "
        f"**{layout['n_rows_across_chord']}** rows · "
        f"chord **{layout['chord_m']:.2f} m** × **{layout['cyl_len_m']:.2f} m** "
        f"(ρ **{dens:.0f}**/m² on **{plate_area:.1f} m²**){util_s}"
    )


def _build_advisories(
    n_holes: int,
    n_target: int,
    layout: dict[str, Any],
    v_max: float,
    open_frac_pct: float,
    imb_pct: float,
) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if abs(n_holes - n_target) > max(5, 0.05 * n_target):
        out.append({
            "severity": "advisory",
            "topic": "Hole count vs density",
            "detail": (
                f"Layout places **{n_holes:,}** holes vs target **{n_target:,}** — "
                "adjust density, bore, or vessel geometry."
            ),
        })
    if v_max > _HOLE_V_WARN_M_S:
        out.append({
            "severity": "warning",
            "topic": "Plate hole velocity",
            "detail": f"Peak **{v_max:.2f} m/s** > limit **{_HOLE_V_WARN_M_S:.1f} m/s**.",
        })
    if open_frac_pct > _OPEN_AREA_LIMIT_PCT:
        out.append({
            "severity": "advisory",
            "topic": "Open area",
            "detail": f"Open area **{open_frac_pct:.1f}%** of plate face.",
        })
    if imb_pct > 15.0:
        out.append({
            "severity": "warning",
            "topic": "Flow imbalance",
            "detail": f"Header station imbalance **{imb_pct:.1f}%**.",
        })
    return out
