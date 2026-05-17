"""
OEM blower motor ratings — ROBOX, GRBS-CRBS, and package tables (screening).

Values are **nameplate motor kW** at rated (Q, ΔP) from manufacturer tables — not shaft power.
"""
from __future__ import annotations

from typing import List, Tuple

# (q_m3h ≈ Nm³/h screening, dp_bar gauge, motor_kw, source tag)
OEM_MOTOR_POINTS: List[Tuple[float, float, float, str]] = [
    # ROBOX ES — max pressure (mbar(g) → bar)
    (270, 0.75, 5.5, "ROBOX ES15"),
    (270, 0.90, 11.0, "ROBOX ES15"),
    (340, 0.70, 11.0, "ROBOX ES25"),
    (530, 1.00, 15.0, "ROBOX ES35"),
    (530, 1.00, 22.0, "ROBOX ES35"),
    (750, 1.00, 30.0, "ROBOX ES45"),
    (1125, 0.70, 30.0, "ROBOX ES46"),
    (1070, 1.00, 45.0, "ROBOX ES55"),
    (1370, 1.00, 55.0, "ROBOX ES65"),
    (1600, 1.00, 75.0, "ROBOX ES75"),
    (2500, 1.00, 90.0, "ROBOX ES85"),
    (2590, 1.00, 90.0, "ROBOX ES95"),
    (3600, 1.00, 132.0, "ROBOX ES105"),
    (4900, 0.70, 132.0, "ROBOX ES106"),
    (4290, 1.00, 160.0, "ROBOX ES115"),
    (5500, 1.00, 200.0, "ROBOX ES125"),
    (5620, 0.70, 200.0, "ROBOX ES126"),
    (5900, 1.00, 200.0, "ROBOX ES135"),
    (7360, 0.70, 250.0, "ROBOX ES126"),
    (8000, 1.00, 315.0, "ROBOX ES145"),
    (10300, 0.50, 315.0, "ROBOX ES155"),
    # GRBS-CRBS — max pressure
    (10420, 1.00, 400.0, "GRBS 165"),
    (14420, 1.00, 550.0, "GRBS 175"),
    (16430, 1.00, 600.0, "GRBS 205"),
    (24870, 0.70, 650.0, "GRBS 225"),
    # Package line — volume vs motor (typical ~0.5–0.7 bar class)
    (250, 0.50, 7.5, "PD package"),
    (340, 0.50, 7.5, "PD package"),
    (520, 0.50, 11.0, "PD package"),
    (600, 0.50, 15.0, "PD package"),
    (730, 0.50, 15.0, "PD package"),
    (1080, 0.50, 22.0, "PD package"),
    (1510, 0.50, 30.0, "PD package"),
    (2120, 0.50, 45.0, "PD package"),
    (2420, 0.50, 55.0, "PD package"),
    # Large multistage package table
    (3640, 0.70, 75.0, "MS package"),
    (5150, 0.70, 110.0, "MS package"),
    (5600, 0.70, 110.0, "MS package"),
    (6600, 0.70, 132.0, "MS package"),
    (8070, 0.70, 160.0, "MS package"),
    (9700, 0.70, 200.0, "MS package"),
    (12800, 0.70, 250.0, "MS package"),
    (15000, 0.70, 315.0, "MS package"),
]


def interp_oem_motor_kw(
    q_nm3h: float,
    dp_bar: float,
    points: List[Tuple[float, float, float, str]],
    *,
    power_exp: float = 0.15,
) -> Tuple[float, str]:
    """
    Inverse-distance blend of OEM (Q, ΔP) → motor kW points.

    ``power_exp`` softens flow scaling above the nearest catalog point when extrapolating high Q.
    """
    q = max(0.0, float(q_nm3h))
    dp = max(0.05, float(dp_bar))
    if not points:
        return 0.0, ""

    best_d = 1e18
    best_m = 0.0
    best_tag = ""
    w_sum = 0.0
    m_sum = 0.0
    tags: List[str] = []

    for q0, d0, m0, tag in points:
        dq = (q - q0) / max(q0, 100.0)
        dd = (dp - d0) / max(d0, 0.05)
        dist = (dq * dq + dd * dd) ** 0.5
        if dist < best_d:
            best_d = dist
            best_m = m0
            best_tag = tag
        if dist < 1e-6:
            return float(m0), tag
        w = 1.0 / max(dist, 0.02) ** 2.0
        w_sum += w
        m_sum += w * m0
        tags.append(tag)

    blended = m_sum / max(w_sum, 1e-12)

    if q > max(p[0] for p in points) * 1.02:
        q_ref = max(p[0] for p in points if p[0] > 1e-6)
        m_ref = max(p[2] for p in points if abs(p[0] - q_ref) < 1.0) or best_m
        scale = (q / q_ref) ** power_exp
        blended = max(blended, m_ref * scale)

    return float(blended), best_tag


def build_oem_motor_grid(
    points: List[Tuple[float, float, float, str]],
    *,
    q_pad: float = 0.15,
) -> dict:
    """Build a regular Q × ΔP grid of motor kW from scattered OEM points."""
    qs = sorted({float(p[0]) for p in points})
    dps = sorted({round(float(p[1]), 2) for p in points})
    if len(dps) < 3:
        dps = sorted(set(dps) | {0.35, 0.50, 0.70, 1.00})

    q_lo, q_hi = qs[0] * (1.0 - q_pad), qs[-1] * (1.0 + q_pad)
    n_q = min(14, max(8, len(qs) + 4))
    q_axis = [round(q_lo + (q_hi - q_lo) * i / (n_q - 1), 0) for i in range(n_q)]

    shaft_kw: List[List[float]] = []
    for q in q_axis:
        row = []
        for dp in dps:
            m, _ = interp_oem_motor_kw(q, dp, points)
            row.append(round(m, 1))
        shaft_kw.append(row)

    return {
        "q_nm3h": q_axis,
        "dp_bar": dps,
        "shaft_kw": shaft_kw,
        "q_max_nm3h": float(q_axis[-1]),
    }
