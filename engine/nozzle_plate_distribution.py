"""
Triangular (staggered) nozzle-plate distribution — density-driven, full-plate coverage.

Plan coordinates: x along vessel length (m), y across chord centred on 0 (m).
"""
from __future__ import annotations

import math
from typing import Any

_SQRT3 = math.sqrt(3.0)
_TRIANGULAR_AREA_FACTOR = _SQRT3 / 2.0  # A_cell = (√3/2) P²


def pitch_from_density(
    *,
    plate_area_m2: float,
    n_total: int,
    bore_d_m: float,
) -> dict[str, Any]:
    """Steps 1–2: target count and triangular pitch P (m)."""
    a_plate = max(1e-6, float(plate_area_m2))
    n_target = max(1, int(n_total))
    d_m = max(1e-6, float(bore_d_m))
    p_min = max(2.5 * d_m, d_m + 0.05)

    a_nozzle = a_plate / n_target
    p_ideal = math.sqrt(a_nozzle / _TRIANGULAR_AREA_FACTOR)
    density_exceeded = p_ideal < p_min - 1e-12
    p_use = max(p_ideal, p_min)
    n_achievable_at_pmin = (
        int(a_plate / (_TRIANGULAR_AREA_FACTOR * p_min * p_min))
        if density_exceeded
        else n_target
    )
    advisories: list[str] = []
    if density_exceeded:
        advisories.append(
            "Requested nozzle density exceeds practical spacing — "
            f"pitch clamped to minimum ({p_min * 1000:.1f} mm); "
            f"achievable ≈ {n_achievable_at_pmin:,} holes on this plate area."
        )
    return {
        "n_target": n_target,
        "pitch_m": p_use,
        "pitch_ideal_m": p_ideal,
        "pitch_min_m": p_min,
        "area_per_nozzle_m2": a_nozzle,
        "density_spacing_exceeded": density_exceeded,
        "n_achievable_at_pmin": n_achievable_at_pmin,
        "advisories": advisories,
    }


def _point_inside_plate(
    x: float,
    y: float,
    *,
    h_plate_m: float,
    vessel_radius_m: float,
    h_dish_m: float,
    straight_cyl_len_m: float,
    edge_clear_m: float,
) -> bool:
    from engine.collector_nozzle_plate import chord_at_axial_x

    w_local = chord_at_axial_x(
        x,
        h_plate_m=h_plate_m,
        vessel_radius_m=vessel_radius_m,
        h_dish_m=h_dish_m,
        straight_cyl_len_m=straight_cyl_len_m,
    )
    if w_local < 2.0 * edge_clear_m + 1e-9:
        return False
    edge_y = min(edge_clear_m, w_local * 0.12)
    return abs(y) <= w_local / 2.0 - edge_y + 1e-9


def generate_triangular_candidates(
    *,
    total_length_m: float,
    chord_width_m: float,
    pitch_m: float,
    bore_d_m: float,
    h_plate_m: float,
    vessel_radius_m: float,
    h_dish_m: float,
    straight_cyl_len_m: float,
) -> list[tuple[float, float, int, int, bool]]:
    """Step 3–4: full-plate triangular candidate grid inside vessel contour."""
    l_plate = max(0.1, float(total_length_m))
    w = max(0.1, float(chord_width_m))
    p = max(1e-4, float(pitch_m))
    d_m = max(1e-6, float(bore_d_m))
    edge = max(0.5 * p, 1.5 * d_m)

    dy = p * _SQRT3 / 2.0
    y0 = -w / 2.0 + edge
    y1 = w / 2.0 - edge
    x0 = edge
    x1 = l_plate - edge

    out: list[tuple[float, float, int, int, bool]] = []
    row_idx = 0
    y = y0
    while y <= y1 + 1e-9:
        stagger = row_idx % 2 == 1
        x_start = x0 + (p / 2.0 if stagger else 0.0)
        col = 0
        x = x_start
        while x <= x1 + 1e-9:
            if _point_inside_plate(
                x,
                y,
                h_plate_m=h_plate_m,
                vessel_radius_m=vessel_radius_m,
                h_dish_m=h_dish_m,
                straight_cyl_len_m=straight_cyl_len_m,
                edge_clear_m=edge,
            ):
                out.append(
                    (
                        round(x, 4),
                        round(y, 4),
                        row_idx + 1,
                        col + 1,
                        stagger,
                    )
                )
            x += p
            col += 1
        y += dy
        row_idx += 1
    return out


def _subsample_even(
    candidates: list[tuple[float, float, int, int, bool]],
    n_keep: int,
) -> list[tuple[float, float, int, int, bool]]:
    n = len(candidates)
    if n <= n_keep:
        return candidates
    step = n / max(1, n_keep)
    idx = sorted({min(n - 1, int(i * step)) for i in range(n_keep)})
    return [candidates[i] for i in idx]


def build_triangular_nozzle_layout(
    *,
    plate_area_m2: float,
    chord_width_m: float,
    total_length_m: float,
    straight_cyl_len_m: float,
    vessel_id_m: float,
    nozzle_plate_h_m: float,
    h_dish_m: float,
    bore_d_mm: float,
    n_holes_total: int,
    np_density_per_m2: float = 0.0,
    max_pitch_iterations: int = 50,
) -> dict[str, Any]:
    """
    Full triangular distribution per AQUASIGHT spec (steps 1–5).

    Returns holes_xy and layout metadata for ``staggered_plate_layout`` consumers.
    """
    h_d = max(0.0, float(h_dish_m))
    l_total = max(0.1, float(total_length_m))
    l_straight = max(
        0.1,
        float(straight_cyl_len_m) if straight_cyl_len_m > 0 else max(0.1, l_total - 2.0 * h_d),
    )
    if l_total < l_straight + 1e-6:
        l_total = l_straight + 2.0 * h_d

    w = max(0.1, float(chord_width_m))
    r = max(0.01, float(vessel_id_m) / 2.0) if vessel_id_m > 0 else w / 2.0
    h_plate = max(0.01, float(nozzle_plate_h_m)) if nozzle_plate_h_m > 0 else 0.5
    d_m = max(0.001, float(bore_d_mm) / 1000.0)
    a_plate = max(1e-6, float(plate_area_m2))

    dens = max(0.0, float(np_density_per_m2))
    if dens > 0:
        n_target = max(1, int(round(dens * a_plate)))
    else:
        n_target = max(1, int(n_holes_total))

    pitch_info = pitch_from_density(
        plate_area_m2=a_plate, n_total=n_target, bore_d_m=d_m,
    )
    p = float(pitch_info["pitch_m"])
    advisories = list(pitch_info["advisories"])
    p_min = float(pitch_info["pitch_min_m"])

    candidates: list[tuple[float, float, int, int, bool]] = []
    for _ in range(max(1, int(max_pitch_iterations))):
        candidates = generate_triangular_candidates(
            total_length_m=l_total,
            chord_width_m=w,
            pitch_m=p,
            bore_d_m=d_m,
            h_plate_m=h_plate,
            vessel_radius_m=r,
            h_dish_m=h_d,
            straight_cyl_len_m=l_straight,
        )
        if len(candidates) >= n_target:
            break
        p_nxt = p * 0.98
        if p_nxt < p_min:
            break
        p = p_nxt

    n_generated = len(candidates)
    if n_generated > n_target:
        holes_xy = _subsample_even(candidates, n_target)
    else:
        holes_xy = candidates
        if n_generated < n_target and n_generated > 0:
            shortfall = 100.0 * (1.0 - n_generated / n_target)
            advisories.append(
                f"Plate geometry / minimum spacing limit placement — "
                f"**{n_generated:,}** of **{n_target:,}** target holes "
                f"({shortfall:.1f} % shortfall). Reduce density or bore size."
            )

    n_placed = len(holes_xy)
    x_cyl0 = h_d
    x_cyl1 = h_d + l_straight
    n_in_dish = sum(1 for x, *_ in holes_xy if x < x_cyl0 - 0.01 or x > x_cyl1 + 0.01)
    edge = max(0.5 * p, 1.5 * d_m)

    xs_all = [h[0] for h in holes_xy]
    ys_all = [h[1] for h in holes_xy]
    field_x0 = min(xs_all) if xs_all else edge
    field_x1 = max(xs_all) if xs_all else l_total - edge

    axial_span = max(1e-6, l_total - 2.0 * edge)
    axial_util = (field_x1 - field_x0) / axial_span if xs_all else 0.0

    row_indices = {h[2] for h in holes_xy}
    n_rows = len(row_indices) if row_indices else 0
    staggered_rows = sum(1 for h in holes_xy if h[4])

    return {
        "holes_xy": holes_xy,
        "n_target": n_target,
        "n_placed": n_placed,
        "n_generated": n_generated,
        "pitch_m": round(p, 6),
        "pitch_mm": round(p * 1000.0, 2),
        "pitch_row_spacing_m": round(p * _SQRT3 / 2.0, 6),
        "edge_clearance_m": round(edge, 6),
        "density_per_m2_target": round(dens if dens > 0 else n_target / a_plate, 4),
        "density_per_m2_actual": round(n_placed / a_plate, 4),
        "axial_utilization": round(axial_util, 4),
        "n_rows_across_chord": n_rows,
        "n_staggered_rows": staggered_rows,
        "x_cyl_start_m": round(x_cyl0, 4),
        "x_cyl_end_m": round(x_cyl1, 4),
        "total_length_m": round(l_total, 4),
        "straight_cyl_len_m": round(l_straight, 4),
        "chord_m": w,
        "plate_area_m2": round(a_plate, 4),
        "n_holes_in_dish_zones": n_in_dish,
        "n_holes_in_cyl_zone": n_placed - n_in_dish,
        "field_x_start_m": round(field_x0, 4),
        "field_x_end_m": round(field_x1, 4),
        "field_y_plot_start_m": round(min(ys_all) if ys_all else -w / 2, 4),
        "field_y_plot_end_m": round(max(ys_all) if ys_all else w / 2, 4),
        "advisories": advisories,
        "pitch_info": pitch_info,
    }
