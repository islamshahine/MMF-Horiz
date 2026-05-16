"""
Spatial hydraulic distribution on nozzle plate — 2D plan screening (Voronoi / grid).

Lumped flow split by service area; not coupled 3D bed CFD.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

METHOD_ID = "voronoi_lumped_v1"
_GRID_N = 72


def _hole_points_from_network(
    hole_network: List[dict],
) -> Tuple[List[float], List[float], List[dict]]:
    xs: List[float] = []
    ys: List[float] = []
    holes: List[dict] = []
    for h in hole_network:
        x = h.get("station_m")
        y = h.get("y_plot_m")
        if x is None:
            x = h.get("x_m")
        if y is None:
            y = h.get("y_along_chord_m")
        if x is None or y is None:
            continue
        xs.append(float(x))
        ys.append(float(y))
        holes.append(h)
    return xs, ys, holes


def voronoi_service_areas_grid(
    xs: List[float],
    ys: List[float],
    *,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    nx: int = _GRID_N,
    ny: int = _GRID_N,
) -> List[float]:
    """Nearest-neighbour grid Voronoi — areas (m²) per hole index."""
    n = len(xs)
    if n == 0:
        return []
    if n == 1:
        return [(x1 - x0) * (y1 - y0)]

    pts = np.column_stack([np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)])
    gx = np.linspace(x0, x1, max(nx, 4))
    gy = np.linspace(y0, y1, max(ny, 4))
    cell_area = ((x1 - x0) / len(gx)) * ((y1 - y0) / len(gy))
    areas = np.zeros(n, dtype=float)

    for xc in gx:
        for yc in gy:
            d2 = np.sum((pts - np.array([xc, yc])) ** 2, axis=1)
            k = int(np.argmin(d2))
            areas[k] += cell_area
    return [float(a) for a in areas]


def _open_area_per_hole(hole: dict) -> float:
    d_mm = float(hole.get("orifice_d_mm", 0) or 0)
    if d_mm <= 0:
        return 0.0
    r = (d_mm / 1000.0) / 2.0
    return math.pi * r * r


def _dead_zone_heuristic(
    i: int,
    *,
    service_area: float,
    median_area: float,
    y_plot: float,
    y_half_span: float,
    pitch_m: float,
    loading_factor: float,
) -> float:
    p = 0.0
    if median_area > 0 and service_area > 2.0 * median_area:
        p += 0.35
    if pitch_m > 0 and y_half_span > 0:
        edge_dist = y_half_span - abs(y_plot)
        if edge_dist < 0.35 * pitch_m:
            p += 0.35
    if loading_factor > 1.25:
        p += 0.2
    if loading_factor < 0.75:
        p += 0.15
    return round(min(1.0, p), 3)


def build_spatial_distribution(
    inputs: dict,
    computed: dict,
    *,
    flow_basis: str = "backwash",
) -> Dict[str, Any]:
    """
    Build ``computed["spatial_distribution"]`` from ``collector_nozzle_plate`` layout.
    """
    if not bool(inputs.get("spatial_distribution_enable", True)):
        return {
            "enabled": False,
            "note": "Spatial distribution disabled in inputs.",
        }

    np_plate = computed.get("collector_nozzle_plate") or {}
    if not np_plate.get("active"):
        return {
            "enabled": False,
            "note": "Nozzle plate BW hydraulics inactive — no spatial map.",
        }

    hole_net = list(np_plate.get("hole_network") or [])
    xs, ys, holes = _hole_points_from_network(hole_net)
    if len(xs) < 2:
        return {
            "enabled": False,
            "note": "Fewer than two nozzle positions — spatial map skipped.",
        }

    x0 = float(np_plate.get("field_x_start_m") or min(xs))
    x1 = float(np_plate.get("field_x_end_m") or max(xs))
    y0 = float(np_plate.get("field_y_plot_start_m") or min(ys))
    y1 = float(np_plate.get("field_y_plot_end_m") or max(ys))
    if x1 <= x0:
        x0, x1 = min(xs) - 0.1, max(xs) + 0.1
    if y1 <= y0:
        y0, y1 = min(ys) - 0.1, max(ys) + 0.1

    areas = voronoi_service_areas_grid(xs, ys, x0=x0, x1=x1, y0=y0, y1=y1)
    area_sum = sum(areas) or 1.0

    if flow_basis == "filtration":
        q_basis_m3h = float(computed.get("q_per_filter") or 0.0)
        basis_note = "filtration q_per_filter"
    else:
        q_basis_m3h = float(
            np_plate.get("q_bw_m3h")
            or (computed.get("bw_hyd") or {}).get("q_bw_m3h")
            or 0.0
        )
        basis_note = "backwash q_bw"

    pitch_m = max(
        float(np_plate.get("pitch_long_mm") or 0) / 1000.0,
        float(np_plate.get("pitch_trans_mm") or 0) / 1000.0,
        0.05,
    )
    y_half = max(abs(y0), abs(y1), (float(np_plate.get("chord_m") or 0) / 2.0))

    median_area = float(np.median(areas)) if areas else 0.0
    local_v_m_h: List[float] = []
    loading: List[float] = []
    dead_z: List[float] = []
    open_areas: List[float] = []

    for i, h in enumerate(holes):
        if i >= len(areas):
            break
        a_svc = areas[i]
        a_open = _open_area_per_hole(h)
        open_areas.append(round(a_open, 8))
        q_i_m3h = q_basis_m3h * (a_svc / area_sum) if q_basis_m3h > 0 else 0.0
        v_m_h = (q_i_m3h / 3600.0) / a_open if a_open > 1e-12 else 0.0
        local_v_m_h.append(round(v_m_h, 4))

    v_mean = sum(local_v_m_h) / len(local_v_m_h) if local_v_m_h else 0.0
    for i, h in enumerate(holes):
        if i >= len(local_v_m_h):
            break
        lf = local_v_m_h[i] / v_mean if v_mean > 1e-9 else 1.0
        loading.append(round(lf, 4))
        yp = float(h.get("y_plot_m") or ys[i] if i < len(ys) else 0.0)
        dead_z.append(
            _dead_zone_heuristic(
                i,
                service_area=areas[i],
                median_area=median_area,
                y_plot=yp,
                y_half_span=y_half,
                pitch_m=pitch_m,
                loading_factor=lf,
            )
        )

    lf_arr = np.asarray(loading, dtype=float)
    if lf_arr.size and np.mean(lf_arr) > 1e-9:
        uniformity = float(max(0.0, min(1.0, 1.0 - np.std(lf_arr) / np.mean(lf_arr))))
    else:
        uniformity = 1.0

    flags: List[str] = []
    if uniformity < 0.85:
        flags.append("low_hydraulic_uniformity")
    if lf_arr.size and float(np.max(lf_arr)) > 1.2:
        flags.append("edge_nozzle_high_loading")
    if float(np.mean(dead_z)) > 0.25:
        flags.append("elevated_dead_zone_risk")

    return {
        "enabled": True,
        "method": METHOD_ID,
        "flow_basis": flow_basis,
        "flow_basis_note": basis_note,
        "q_basis_m3h": round(q_basis_m3h, 4),
        "layout_revision": np_plate.get("layout_revision"),
        "n_nozzles": len(holes),
        "bounds_m": {
            "x0": round(x0, 4),
            "x1": round(x1, 4),
            "y0": round(y0, 4),
            "y1": round(y1, 4),
        },
        "nozzle_xy_m": [[round(xs[i], 4), round(ys[i], 4)] for i in range(len(xs))],
        "nozzle_service_area_m2": [round(a, 6) for a in areas],
        "nozzle_open_area_m2": open_areas,
        "nozzle_local_velocity_m_h": local_v_m_h,
        "nozzle_loading_factor": loading,
        "dead_zone_probability": dead_z,
        "hydraulic_uniformity_index": round(uniformity, 4),
        "max_loading_factor": round(float(np.max(lf_arr)) if lf_arr.size else 1.0, 4),
        "min_loading_factor": round(float(np.min(lf_arr)) if lf_arr.size else 1.0, 4),
        "advisory_flags": flags,
        "assumption_ids": ["ASM-SPATIAL-001", "ASM-SPATIAL-002"],
        "note": (
            "2D plan Voronoi (grid) service areas; lumped Q split. "
            "Not RTD or media channeling model."
        ),
    }


def enrich_hole_network_with_spatial(
    hole_network: List[dict],
    spatial: dict,
) -> List[dict]:
    """Attach service area / local velocity to hole rows for CFD CSV export."""
    if not spatial.get("enabled"):
        return hole_network
    areas = spatial.get("nozzle_service_area_m2") or []
    vels = spatial.get("nozzle_local_velocity_m_h") or []
    load = spatial.get("nozzle_loading_factor") or []
    out: List[dict] = []
    for i, row in enumerate(hole_network):
        r = dict(row)
        if i < len(areas):
            r["service_area_m2"] = areas[i]
        if i < len(vels):
            r["local_velocity_m_h"] = vels[i]
        if i < len(load):
            r["loading_factor"] = load[i]
        out.append(r)
    return out
