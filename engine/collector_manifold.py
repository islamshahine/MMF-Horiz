"""
Collector 1B+ — dual-end header feed and per-orifice network detail.

Screening / scheduling aid only — not CFD or structural FEA. For external CFD,
use ``collector_cfd_export.build_collector_cfd_bundle``.
"""
from __future__ import annotations

import math
from typing import Any

from engine.collector_hydraulics import (
    GRAVITY,
    _MAX_DIST_ITER,
    _DIST_TOL_REL,
    _darcy_head_m,
)

_HEADER_FEED_MODES = frozenset({"one_end", "dual_end"})


def solve_lateral_distribution_one_end(
    *,
    q_total_m3_s: float,
    positions_m: list[float],
    segment_lengths_m: list[float],
    d_header_m: float,
    d_lat_m: float,
    l_lat_m: float,
    n_orifices: int,
    friction_factor: float,
    headloss_factor: float,
    rho: float,
    max_iter: int = _MAX_DIST_ITER,
    tol_rel: float = _DIST_TOL_REL,
) -> tuple[list[float], int, float, bool]:
    """
    Fixed-point lateral flow split for a header fed from the first station outward.

    ``segment_lengths_m[i]`` is header length before lateral ``i`` (same length as positions).
    """
    n = len(positions_m)
    if n < 1 or q_total_m3_s <= 1e-12:
        return [0.0] * max(n, 0), 0, 0.0, True

    f = max(0.008, min(0.08, float(friction_factor)))
    hl = max(0.5, float(headloss_factor))
    rho = max(800.0, float(rho))
    d_header = max(0.02, float(d_header_m))
    d_lat = max(0.01, float(d_lat_m))
    l_lat = max(0.01, float(l_lat_m))

    q_lat = [q_total_m3_s / n] * n
    dist_residual = 1.0
    dist_iter = 0
    dist_converged = False

    for dist_iter in range(max_iter):
        q_rem = q_total_m3_s
        p_drive: list[float] = []
        cum_dp = 0.0
        v_header_prev = 0.0
        for i in range(n):
            seg_len = max(0.01, float(segment_lengths_m[i]))
            v_header = q_rem / (math.pi * (d_header / 2.0) ** 2) if q_rem > 0 else 0.0
            v_seg = 0.5 * (v_header + v_header_prev)
            cum_dp += _darcy_head_m(f=f, length_m=seg_len, diameter_m=d_header, velocity_m_s=v_seg) * hl * rho * GRAVITY
            v_lat = q_lat[i] / (math.pi * (d_lat / 2.0) ** 2) if q_lat[i] > 0 else 0.0
            dp_lat = _darcy_head_m(f=f, length_m=l_lat, diameter_m=d_lat, velocity_m_s=v_lat) * hl * rho * GRAVITY
            p_drive.append(max(1.0, q_total_m3_s * rho * GRAVITY * 0.01 - cum_dp - dp_lat))
            q_rem = max(0.0, q_rem - q_lat[i])
            v_header_prev = v_header

        p_ref = max(p_drive) if p_drive else 1.0
        q_new = []
        for p_i in p_drive:
            scale = math.sqrt(max(0.0, p_i) / p_ref) if p_ref > 0 else 1.0
            q_new.append((q_total_m3_s / n) * scale)
        s_new = sum(q_new) or 1.0
        q_new = [q * q_total_m3_s / s_new for q in q_new]
        q_mean = q_total_m3_s / n
        if q_mean > 1e-12:
            dist_residual = max(abs(q_new[i] - q_lat[i]) / q_mean for i in range(n))
        else:
            dist_residual = 0.0
        q_lat = q_new
        if dist_residual < tol_rel:
            dist_converged = True
            break

    return q_lat, dist_iter + 1, dist_residual, dist_converged


def solve_lateral_distribution_dual_end(
    *,
    q_total_m3_s: float,
    positions_m: list[float],
    cyl_len_m: float,
    d_header_m: float,
    d_lat_m: float,
    l_lat_m: float,
    n_orifices: int,
    friction_factor: float,
    headloss_factor: float,
    rho: float,
) -> tuple[list[float], int, float, bool, dict[str, Any]]:
    """
    Dual-end header: left group fed from x=0, right group from x=L; balance split at centre.
    """
    n = len(positions_m)
    meta: dict[str, Any] = {"split_index": n // 2, "balance_iterations": 0}
    if n < 2 or q_total_m3_s <= 1e-12:
        q1, it, res, ok = solve_lateral_distribution_one_end(
            q_total_m3_s=q_total_m3_s,
            positions_m=positions_m,
            segment_lengths_m=_segment_lengths(positions_m, cyl_len_m),
            d_header_m=d_header_m,
            d_lat_m=d_lat_m,
            l_lat_m=l_lat_m,
            n_orifices=n_orifices,
            friction_factor=friction_factor,
            headloss_factor=headloss_factor,
            rho=rho,
        )
        meta["mode"] = "degenerate_one_end"
        return q1, it, res, ok, meta

    split = max(1, n // 2)
    meta["split_index"] = split
    left_idx = list(range(split))
    right_idx = list(range(split, n))
    L = max(float(cyl_len_m), positions_m[-1] if positions_m else 1.0)

    pos_l = [positions_m[i] for i in left_idx]
    seg_l = _segment_lengths(pos_l, L)
    pos_r_from_right = [L - positions_m[i] for i in right_idx]
    seg_r = _segment_lengths(pos_r_from_right, L)

    q_left = q_total_m3_s * len(left_idx) / n
    q_lat_l: list[float] = []
    q_lat_r: list[float] = []
    it_l = it_r = 0
    res_l = res_r = 1.0
    ok_l = ok_r = False

    for bal in range(24):
        meta["balance_iterations"] = bal + 1
        q_lat_l, it_l, res_l, ok_l = solve_lateral_distribution_one_end(
            q_total_m3_s=q_left,
            positions_m=pos_l,
            segment_lengths_m=seg_l,
            d_header_m=d_header_m,
            d_lat_m=d_lat_m,
            l_lat_m=l_lat_m,
            n_orifices=n_orifices,
            friction_factor=friction_factor,
            headloss_factor=headloss_factor,
            rho=rho,
        )
        q_lat_r, it_r, res_r, ok_r = solve_lateral_distribution_one_end(
            q_total_m3_s=max(0.0, q_total_m3_s - q_left),
            positions_m=pos_r_from_right,
            segment_lengths_m=seg_r,
            d_header_m=d_header_m,
            d_lat_m=d_lat_m,
            l_lat_m=l_lat_m,
            n_orifices=n_orifices,
            friction_factor=friction_factor,
            headloss_factor=headloss_factor,
            rho=rho,
        )
        q_mean_l = q_left / max(len(left_idx), 1)
        q_mean_r = (q_total_m3_s - q_left) / max(len(right_idx), 1)
        p_end_l = q_mean_l * rho * GRAVITY * 0.01 if q_mean_l > 0 else 0.0
        p_end_r = q_mean_r * rho * GRAVITY * 0.01 if q_mean_r > 0 else 0.0
        dp = p_end_l - p_end_r
        if abs(dp) < 50.0:
            break
        q_left = max(
            q_total_m3_s * 0.15,
            min(q_total_m3_s * 0.85, q_left + dp * 1e-7 * q_total_m3_s),
        )

    q_merged = [0.0] * n
    for j, i in enumerate(left_idx):
        q_merged[i] = q_lat_l[j]
    for j, i in enumerate(right_idx):
        q_merged[i] = q_lat_r[j]

    dist_iter = it_l + it_r
    dist_residual = max(res_l, res_r)
    dist_converged = ok_l and ok_r and dist_residual <= _DIST_TOL_REL
    meta.update({
        "q_split_left_m3_s": round(q_left, 6),
        "q_split_right_m3_s": round(q_total_m3_s - q_left, 6),
        "mode": "dual_end_balanced",
    })
    return q_merged, dist_iter, dist_residual, dist_converged, meta


def _segment_lengths(positions_m: list[float], cyl_len_m: float) -> list[float]:
    if not positions_m:
        return []
    sp = float(cyl_len_m) / (len(positions_m) + 1) if cyl_len_m > 0 else 1.0
    segs: list[float] = []
    prev = 0.0
    for x in positions_m:
        segs.append(max(0.01, float(x) - prev if x > prev else sp))
        prev = float(x)
    return segs


def build_orifice_network(
    *,
    positions_m: list[float],
    q_lat_m3_s: list[float],
    n_orifices: int,
    lateral_length_m: float,
    orifice_d_m: float,
    pitch_mm: float,
    lateral_construction: str,
) -> list[dict[str, Any]]:
    """Per-hole flows along each lateral (uniform split with mild end bias)."""
    n_orf = max(1, int(n_orifices))
    pitch_m = max(0.001, float(pitch_mm) / 1000.0)
    l_lat = max(0.01, float(lateral_length_m))
    d_orf = max(0.001, float(orifice_d_m))
    area = math.pi * (d_orf / 2.0) ** 2
    rows: list[dict[str, Any]] = []

    for i, (x_m, q_lat) in enumerate(zip(positions_m, q_lat_m3_s)):
        if q_lat <= 1e-12:
            continue
        q_base = q_lat / n_orf
        for j in range(n_orf):
            frac = 0.15 + 0.70 * (j / max(n_orf - 1, 1))
            y_m = frac * l_lat
            q_h = q_base * (0.92 + 0.16 * (j / max(n_orf - 1, 1)))
            v_m_s = q_h / area if area > 0 else 0.0
            rows.append({
                "lateral_index": i + 1,
                "hole_index": j + 1,
                "station_m": round(float(x_m), 4),
                "y_along_lateral_m": round(y_m, 4),
                "flow_m3h": round(q_h * 3600.0, 4),
                "velocity_m_s": round(v_m_s, 3),
                "orifice_d_mm": round(d_orf * 1000.0, 2),
                "construction": lateral_construction,
            })
    return rows


def normalize_header_feed_mode(mode: str | None) -> str:
    m = str(mode or "one_end").strip().lower()
    return m if m in _HEADER_FEED_MODES else "one_end"


def compare_feed_modes(
    q_lat_one_end: list[float],
    q_lat_dual: list[float],
) -> dict[str, Any]:
    """Imbalance metrics for one-end vs dual-end on the same lateral count."""
    def _stats(q: list[float]) -> dict[str, float]:
        if not q:
            return {"mal": 1.0, "imbalance_pct": 0.0}
        q_mean = sum(q) / len(q)
        q_max, q_min = max(q), min(q)
        mal = q_max / q_mean if q_mean > 1e-12 else 1.0
        imb = (q_max - q_min) / q_mean * 100.0 if q_mean > 1e-12 else 0.0
        return {"mal": mal, "imbalance_pct": imb}

    s1 = _stats(q_lat_one_end)
    s2 = _stats(q_lat_dual)
    return {
        "one_end": {k: round(v, 4) for k, v in s1.items()},
        "dual_end": {k: round(v, 4) for k, v in s2.items()},
        "imbalance_improvement_pct_pts": round(s1["imbalance_pct"] - s2["imbalance_pct"], 2),
    }
