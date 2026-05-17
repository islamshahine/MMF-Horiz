"""
Blower performance maps — vendor-style curves, VFD affinity, vs adiabatic screening.

Screening only: tabulated generic lobe / centrifugal maps for comparison with
``bw_system_sizing`` ideal-gas compression. Not a substitute for OEM datasheets.
"""
from __future__ import annotations

import csv
import io
import re
from typing import Any, Dict, List, Optional, Tuple

from engine.backwash import nm3h_to_actual_m3s_at_pt
from engine.blower_oem_catalog import OEM_MOTOR_POINTS, build_oem_motor_grid, interp_oem_motor_kw

# Market-style screening envelopes (Nm³/h per machine)
LOBE_Q_MAX_NM3H = 15_000.0
CENTRIFUGAL_Q_MAX_NM3H = 50_000.0

_CURVE_GRIDS: Dict[str, dict] = {}


def _interp_q_row(q_axis: List[float], row: List[float], q: float) -> float:
    if q <= q_axis[0]:
        if len(q_axis) < 2:
            return float(row[0])
        slope = (row[1] - row[0]) / max(q_axis[1] - q_axis[0], 1e-12)
        return float(row[0] + slope * (q - q_axis[0]))
    for i in range(len(q_axis) - 1):
        if q <= q_axis[i + 1]:
            t = (q - q_axis[i]) / max(q_axis[i + 1] - q_axis[i], 1e-12)
            return float(row[i] * (1 - t) + row[i + 1] * t)
    if len(q_axis) < 2:
        return float(row[-1])
    slope = (row[-1] - row[-2]) / max(q_axis[-1] - q_axis[-2], 1e-12)
    return float(row[-1] + slope * (q - q_axis[-1]))


def _extend_grid_q_axis(
    q_axis: List[float],
    dp_axis: List[float],
    shaft_kw: List[List[float]],
    q_max: float,
    *,
    n_points: int = 10,
) -> Tuple[List[float], List[float], List[List[float]]]:
    """Extend Q axis to ``q_max``; kW beyond old max uses last-segment slope per ΔP column."""
    q_lo = float(q_axis[0])
    q_hi = max(float(q_axis[-1]), q_lo + 1.0)
    q_max = max(float(q_max), q_hi)
    step = (q_max - q_lo) / max(n_points - 1, 1)
    new_q: List[float] = []
    x = q_lo
    while x < q_max - 1e-6:
        new_q.append(round(x, 1))
        x += step
    if not new_q or new_q[-1] < q_max - 1e-3:
        new_q.append(round(q_max, 1))

    new_grid: List[List[float]] = []
    for q in new_q:
        col_vals = []
        for j in range(len(dp_axis)):
            col = [shaft_kw[i][j] for i in range(len(q_axis))]
            col_vals.append(_interp_q_row(q_axis, col, q))
        new_grid.append(col_vals)
    return new_q, list(dp_axis), new_grid


def _seed_grids() -> None:
    """Populate generic catalogs (called at import)."""
    lobe_q = [300.0, 600.0, 900.0, 1200.0, 1500.0, 2000.0]
    lobe_dp = [0.20, 0.35, 0.50, 0.65, 0.80]
    lobe_kw = [
        [28, 48, 68, 88, 108],
        [52, 88, 124, 158, 192],
        [76, 128, 178, 228, 276],
        [98, 165, 230, 294, 356],
        [120, 200, 280, 358, 432],
        [158, 262, 368, 470, 568],
    ]
    lobe_q, lobe_dp, lobe_kw = _extend_grid_q_axis(
        lobe_q, lobe_dp, lobe_kw, LOBE_Q_MAX_NM3H, n_points=12,
    )

    cent_q = [800.0, 1200.0, 1600.0, 2200.0, 3000.0, 4000.0]
    cent_dp = [0.30, 0.45, 0.60, 0.75, 0.90]
    cent_kw = [
        [95, 130, 168, 210, 255],
        [140, 192, 248, 310, 375],
        [185, 255, 330, 412, 498],
        [260, 358, 462, 578, 698],
        [355, 488, 630, 788, 952],
        [480, 660, 852, 1065, 1285],
    ]
    cent_q, cent_dp, cent_kw = _extend_grid_q_axis(
        cent_q, cent_dp, cent_kw, CENTRIFUGAL_Q_MAX_NM3H, n_points=12,
    )

    _CURVE_GRIDS["roots_lobe_generic"] = {
        "label": "Generic roots / lobe PD (screening — legacy)",
        "blower_type": "positive_displacement",
        "affinity_exponent": 1.0,
        "power_basis": "shaft",
        "q_max_nm3h": LOBE_Q_MAX_NM3H,
        "q_nm3h": lobe_q,
        "dp_bar": lobe_dp,
        "shaft_kw": lobe_kw,
    }
    _CURVE_GRIDS["centrifugal_multistage_generic"] = {
        "label": "Generic centrifugal multistage (screening)",
        "blower_type": "centrifugal",
        "affinity_exponent": 3.0,
        "power_basis": "shaft",
        "q_max_nm3h": CENTRIFUGAL_Q_MAX_NM3H,
        "q_nm3h": cent_q,
        "dp_bar": cent_dp,
        "shaft_kw": cent_kw,
    }

    oem_grid = build_oem_motor_grid(OEM_MOTOR_POINTS)
    _CURVE_GRIDS["oem_vendor_motor"] = {
        "label": "OEM motor catalog — ROBOX / GRBS / package tables",
        "blower_type": "centrifugal",
        "affinity_exponent": 3.0,
        "power_basis": "motor",
        "oem_points": list(OEM_MOTOR_POINTS),
        **oem_grid,
    }


_seed_grids()

CURVE_IDS = tuple(_CURVE_GRIDS.keys())
OEM_VENDOR_CURVE_ID = "oem_vendor_motor"
ROOTS_LOBE_CURVE_ID = "roots_lobe_generic"
CENTRIFUGAL_CURVE_ID = "centrifugal_multistage_generic"
DEFAULT_BLOWER_CURVE_ID = OEM_VENDOR_CURVE_ID


def list_blower_curves() -> List[dict[str, Any]]:
    out = []
    for cid in _CURVE_GRIDS:
        spec = _CURVE_GRIDS[cid]
        out.append({
            "id": cid,
            "label": spec["label"],
            "type": spec["blower_type"],
            "q_max_nm3h": float(spec.get("q_max_nm3h") or spec["q_nm3h"][-1]),
        })
    return out


def blowers_map_split_count(inputs: dict) -> int:
    """
    Blowers sharing plant air flow for **map / per-machine** duty (§3 ``pp_n_blowers``).

    Q_per_machine = Q_plant / this count. If you have 3 installed blowers in parallel,
    set **Air blowers installed** = 3 — not controlled by annual-kWh operating mode.
    """
    return max(1, int(inputs.get("pp_n_blowers") or inputs.get("n_blowers_installed") or 1))


def blowers_energy_online_count(inputs: dict) -> int:
    """
    Blowers assumed online for **annual kWh** (``pp_blower_mode`` in §3).

    - ``single_duty``: one duty machine (spares idle).
    - ``twin_50_iso``: all installed machines @ split flow (rough centrifugal Q³).
    """
    installed = blowers_map_split_count(inputs)
    mode = str(inputs.get("pp_blower_mode") or inputs.get("blower_operating_mode") or "single_duty").lower()
    if mode == "twin_50_iso" and installed >= 2:
        return installed
    return 1


def blowers_on_duty_from_inputs(inputs: dict) -> int:
    """Blowers splitting plant Q on the performance map — equals installed count."""
    return blowers_map_split_count(inputs)


def blower_n_on_duty_from_inputs(inputs: dict) -> int:
    """Alias for ``blowers_on_duty_from_inputs``."""
    return blowers_on_duty_from_inputs(inputs)


def pick_curve_id(
    q_per_nm3h: float,
    user_curve_id: Optional[str] = None,
    *,
    auto: bool = True,
) -> Tuple[str, bool, Optional[str]]:
    """Return (curve_id, auto_switched, reason). Default auto → OEM motor catalog."""
    cid = str(user_curve_id or DEFAULT_BLOWER_CURVE_ID).strip()
    if not auto:
        return cid, False, None
    if cid in ("", ROOTS_LOBE_CURVE_ID, CENTRIFUGAL_CURVE_ID) or cid.startswith("roots_") or cid.startswith("centrifugal_multistage"):
        return (
            OEM_VENDOR_CURVE_ID,
            cid != OEM_VENDOR_CURVE_ID,
            f"Using **OEM motor catalog** (realistic nameplate kW) for Q ≈ {q_per_nm3h:,.0f} Nm³/h per machine.",
        )
    return cid, False, None


def _bilinear_grid(
    q_nm3h: float,
    dp_bar: float,
    q_axis: List[float],
    dp_axis: List[float],
    grid: List[List[float]],
) -> Tuple[float, bool, bool, Dict[str, bool]]:
    """
    Bilinear interpolate / linear extrapolate shaft kW.

    Returns (value, in_envelope, extrapolated, axis_flags).
    """
    q = max(0.0, float(q_nm3h))
    dp = max(0.0, float(dp_bar))
    q0, q1 = q_axis[0], q_axis[-1]
    d0, d1 = dp_axis[0], dp_axis[-1]
    in_env = (q0 <= q <= q1) and (d0 <= dp <= d1)
    extrap = not in_env
    flags = {
        "q_low": q < q0 - 1e-9,
        "q_high": q > q1 + 1e-9,
        "dp_low": dp < d0 - 1e-9,
        "dp_high": dp > d1 + 1e-9,
    }

    def _idx(axis: List[float], v: float) -> Tuple[int, int, float]:
        if v <= axis[0]:
            return 0, 0, 0.0
        for i in range(len(axis) - 1):
            if v <= axis[i + 1]:
                t = (v - axis[i]) / max(axis[i + 1] - axis[i], 1e-12)
                return i, i + 1, t
        return len(axis) - 2, len(axis) - 1, 1.0

    qi, qj, tq = _idx(q_axis, q)
    di, dj, td = _idx(dp_axis, dp)
    v00 = grid[qi][di]
    v01 = grid[qi][dj]
    v10 = grid[qj][di]
    v11 = grid[qj][dj]
    v0 = v00 * (1 - td) + v01 * td
    v1 = v10 * (1 - td) + v11 * td
    return float(v0 * (1 - tq) + v1 * tq), in_env, extrap, flags


def curve_map_power_kw(
    curve_id: str,
    q_nm3h: float,
    dp_bar: float,
) -> Tuple[float, bool, str, bool, Dict[str, bool], str, Optional[str]]:
    """
    Map power at (Q, ΔP).

    Returns (power_kw, in_envelope, blower_type, extrapolated, axis_flags, power_basis, oem_model_hint).
    """
    spec = _CURVE_GRIDS.get(str(curve_id or "").strip())
    if not spec:
        return 0.0, False, "unknown_curve", False, {}, "shaft", None

    basis = str(spec.get("power_basis") or "shaft")
    if basis == "motor" and spec.get("oem_points"):
        motor, tag = interp_oem_motor_kw(q_nm3h, dp_bar, spec["oem_points"])
        q_axis = spec["q_nm3h"]
        dp_axis = spec["dp_bar"]
        in_env = (
            q_axis[0] <= q_nm3h <= q_axis[-1] * 1.05
            and dp_axis[0] <= dp_bar <= dp_axis[-1] * 1.05
        )
        extrap = not in_env
        flags = {
            "q_low": q_nm3h < q_axis[0],
            "q_high": q_nm3h > q_axis[-1],
            "dp_low": dp_bar < dp_axis[0],
            "dp_high": dp_bar > dp_axis[-1],
        }
        return max(0.0, motor), in_env, spec["blower_type"], extrap, flags, "motor", tag

    kw, in_env, extrap, flags = _bilinear_grid(
        q_nm3h,
        dp_bar,
        spec["q_nm3h"],
        spec["dp_bar"],
        spec["shaft_kw"],
    )
    return max(0.0, kw), in_env, spec["blower_type"], extrap, flags, "shaft", None


def curve_shaft_kw(
    curve_id: str,
    q_nm3h: float,
    dp_bar: float,
) -> Tuple[float, bool, str, bool, Dict[str, bool]]:
    """Shaft kW from map (converts OEM motor rating when applicable)."""
    power, in_env, btype, extrap, flags, basis, _ = curve_map_power_kw(curve_id, q_nm3h, dp_bar)
    if basis == "motor":
        return power * 0.70 * 0.95, in_env, btype, extrap, flags
    return power, in_env, btype, extrap, flags


def adiabatic_blower_power_at_flow(
    q_nm3h: float,
    dp_total_bar: float,
    *,
    blower_eta: float = 0.70,
    motor_eta: float = 0.95,
    blower_inlet_temp_c: float = 20.0,
    gamma: float = 1.4,
) -> Dict[str, float]:
    """
    Ideal-gas adiabatic compression at (Q, ΔP_total) — same model as ``bw_system_sizing``.

    Shaft power scales linearly with mass flow at fixed pressure ratio.
    """
    q = max(0.0, float(q_nm3h))
    dp = max(0.0, float(dp_total_bar))
    if q <= 1e-9 or dp <= 1e-9:
        return {"ideal_kw": 0.0, "shaft_kw": 0.0, "motor_kw": 0.0}

    exponent = (gamma - 1.0) / gamma
    p1_pa = 101_325.0
    t1_k = float(blower_inlet_temp_c) + 273.15
    p2_pa = p1_pa + dp * 1e5
    q_m3s = nm3h_to_actual_m3s_at_pt(q, p1_pa, t1_k)
    p_ideal_kw = (
        (gamma / (gamma - 1.0))
        * p1_pa
        * q_m3s
        * ((p2_pa / p1_pa) ** exponent - 1.0)
        / 1000.0
    )
    eta_b = max(0.01, float(blower_eta))
    eta_m = max(0.01, float(motor_eta))
    shaft = p_ideal_kw / eta_b
    motor = shaft / eta_m
    return {
        "ideal_kw": round(p_ideal_kw, 2),
        "shaft_kw": round(shaft, 2),
        "motor_kw": round(motor, 2),
    }


def curve_motor_kw(shaft_kw: float, blower_eta: float, motor_eta: float) -> float:
    eta_b = max(0.01, float(blower_eta))
    eta_m = max(0.01, float(motor_eta))
    return float(shaft_kw) / eta_b / eta_m


def vfd_affinity_shaft_kw(
    shaft_kw_design: float,
    speed_frac: float,
    *,
    blower_type: str = "centrifugal",
    affinity_exponent: Optional[float] = None,
) -> float:
    """Scale shaft power with speed — exponent 3 centrifugal, ~1 for PD (flow ∝ speed)."""
    s = max(0.05, min(1.0, float(speed_frac)))
    if affinity_exponent is not None:
        exp = float(affinity_exponent)
    elif str(blower_type).lower() in ("positive_displacement", "pd", "roots", "lobe"):
        exp = 1.0
    else:
        exp = 3.0
    return float(shaft_kw_design) * (s ** exp)


def curve_envelope_plot_points(
    curve_id: str,
    dp_bar: float,
) -> List[dict[str, float]]:
    """Shaft kW vs Q at fixed ΔP for charting."""
    spec = _CURVE_GRIDS.get(str(curve_id or ""))
    if not spec:
        return []
    pts = []
    for i, q in enumerate(spec["q_nm3h"]):
        di = 0
        for j, d in enumerate(spec["dp_bar"]):
            if d >= dp_bar - 1e-9:
                di = j
                break
        else:
            di = len(spec["dp_bar"]) - 1
        if di > 0 and dp_bar < spec["dp_bar"][di]:
            j0, j1 = di - 1, di
            t = (dp_bar - spec["dp_bar"][j0]) / max(spec["dp_bar"][j1] - spec["dp_bar"][j0], 1e-12)
            kw = spec["shaft_kw"][i][j0] * (1 - t) + spec["shaft_kw"][i][j1] * t
        else:
            kw = spec["shaft_kw"][i][di]
        basis = str(spec.get("power_basis") or "shaft")
        if basis == "motor":
            m, _ = interp_oem_motor_kw(q, dp_bar, spec.get("oem_points") or [])
            pts.append({"q_nm3h": float(q), "shaft_kw": float(m), "motor_kw": float(m)})
        else:
            pts.append({"q_nm3h": float(q), "shaft_kw": float(kw)})
    return pts


def parse_vendor_curve_csv(
    text: str,
    *,
    delimiter: str = ",",
) -> Dict[str, Any]:
    """
    Parse vendor map CSV.

    Format A — header ``q_nm3h,0.30,0.45,...`` (col 1 = per-blower Nm³/h label;
    cols 2+ = ΔP in bar). Data rows: Q per machine, then shaft kW per ΔP column.
    Format B — row 1 = ΔP values only; col 1 of each data row = Q; body = shaft kW.

    Returns dict suitable for ``import_custom_curve_grid``.
    """
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Empty CSV")

    rows: List[List[str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append([c.strip() for c in next(csv.reader(io.StringIO(line), delimiter=delimiter))])

    if len(rows) < 2:
        raise ValueError("CSV needs at least a header and one data row")

    header = rows[0]
    h0 = header[0].lower().replace(" ", "")
    if h0 in ("q_nm3h", "q", "flow", "flow_nm3h", "nm3h"):
        dp_bar = [float(x) for x in header[1:]]
        q_nm3h = []
        shaft_kw: List[List[float]] = []
        for row in rows[1:]:
            if not row or not row[0]:
                continue
            q_nm3h.append(float(row[0]))
            shaft_kw.append([float(x) for x in row[1 : 1 + len(dp_bar)]])
    else:
        dp_bar = [float(x) for x in header]
        q_nm3h = []
        shaft_kw = []
        for row in rows:
            if not row:
                continue
            q_nm3h.append(float(row[0]))
            shaft_kw.append([float(x) for x in row[1 : 1 + len(dp_bar)]])

    if len(shaft_kw) != len(q_nm3h):
        raise ValueError("Row count mismatch")
    if any(len(r) != len(dp_bar) for r in shaft_kw):
        raise ValueError("shaft_kw columns must match dp_bar count")

    return {
        "q_nm3h": q_nm3h,
        "dp_bar": dp_bar,
        "shaft_kw": shaft_kw,
    }


def import_custom_curve_grid(
    curve_id: str,
    label: str,
    q_nm3h: List[float],
    dp_bar: List[float],
    shaft_kw: List[List[float]],
    *,
    blower_type: str = "positive_displacement",
    affinity_exponent: float = 1.0,
) -> None:
    """Register a user / vendor grid at runtime (e.g. from CSV in UI)."""
    if len(shaft_kw) != len(q_nm3h) or any(len(row) != len(dp_bar) for row in shaft_kw):
        raise ValueError("shaft_kw grid shape must match q_nm3h × dp_bar")
    cid = str(curve_id).strip()
    if not re.match(r"^[a-z][a-z0-9_]{2,48}$", cid):
        raise ValueError("curve_id must be lowercase slug (e.g. vendor_xyz_2024)")
    _CURVE_GRIDS[cid] = {
        "label": label,
        "blower_type": blower_type,
        "affinity_exponent": affinity_exponent,
        "power_basis": "shaft",
        "q_max_nm3h": float(max(q_nm3h)),
        "q_nm3h": list(q_nm3h),
        "dp_bar": list(dp_bar),
        "shaft_kw": shaft_kw,
    }


def import_custom_curve_from_csv(
    curve_id: str,
    label: str,
    csv_text: str,
    *,
    blower_type: str = "positive_displacement",
    affinity_exponent: float = 1.0,
) -> None:
    """Parse CSV and register curve in one step."""
    parsed = parse_vendor_curve_csv(csv_text)
    import_custom_curve_grid(
        curve_id,
        label,
        parsed["q_nm3h"],
        parsed["dp_bar"],
        parsed["shaft_kw"],
        blower_type=blower_type,
        affinity_exponent=affinity_exponent,
    )


def build_blower_map_analysis(
    inputs: dict,
    computed: dict,
    *,
    curve_id: Optional[str] = None,
    vfd_speed_frac: Optional[float] = None,
) -> Dict[str, Any]:
    """Compare adiabatic ``bw_sizing`` with tabulated blower map at operating point."""
    if not bool(inputs.get("blower_map_enable", True)):
        return {"enabled": False, "note": "Blower map disabled in inputs."}

    bw_sizing = computed.get("bw_sizing") or {}
    bw_hyd = computed.get("bw_hyd") or {}
    if not bw_sizing:
        return {"enabled": False, "note": "No bw_sizing — run compute first."}

    q_total = float(
        bw_sizing.get("q_air_design_nm3h")
        or bw_hyd.get("q_air_design_nm3h")
        or bw_hyd.get("q_air_design_m3h")
        or 0.0
    )
    dp_bar = float(bw_sizing.get("dp_total_bar") or 0.0)
    if q_total <= 1e-6 or dp_bar <= 1e-9:
        return {"enabled": False, "note": "Zero air duty — blower map skipped."}

    n_on = blower_n_on_duty_from_inputs(inputs)
    q_per = q_total / float(n_on)

    user_cid = str(curve_id or inputs.get("blower_curve_id") or DEFAULT_BLOWER_CURVE_ID).strip()
    auto = bool(inputs.get("blower_map_auto_curve", True))
    cid, auto_switched, auto_reason = pick_curve_id(q_per, user_cid, auto=auto)

    spec = _CURVE_GRIDS.get(cid)
    if not spec:
        return {"enabled": False, "note": f"Unknown blower curve id: {cid}"}

    blower_eta = float(bw_sizing.get("blower_eta") or inputs.get("blower_eta") or 0.70)
    motor_eta = float(inputs.get("motor_eta") or 0.95)
    blower_t_c = float(inputs.get("blower_inlet_temp_c") or 20.0)

    ad_fleet_shaft = float(bw_sizing.get("p_blower_shaft_kw") or 0.0)
    ad_fleet_motor = float(bw_sizing.get("p_blower_motor_kw") or 0.0)

    ad_per = adiabatic_blower_power_at_flow(
        q_per,
        dp_bar,
        blower_eta=blower_eta,
        motor_eta=motor_eta,
        blower_inlet_temp_c=blower_t_c,
    )
    ad_per_shaft = float(ad_per["shaft_kw"])
    ad_per_motor = float(ad_per["motor_kw"])

    map_pwr, in_env, btype, extrap, axis_flags, power_basis, oem_hint = curve_map_power_kw(
        cid, q_per, dp_bar,
    )
    if power_basis == "motor":
        map_motor_per = map_pwr
        map_shaft = map_pwr * blower_eta * motor_eta
    else:
        map_shaft = map_pwr
        map_motor_per = curve_motor_kw(map_shaft, blower_eta, motor_eta)
    map_shaft_fleet = map_shaft * n_on
    map_motor_fleet = map_motor_per * n_on

    speed = float(
        vfd_speed_frac
        if vfd_speed_frac is not None
        else inputs.get("blower_vfd_speed_frac", 1.0)
    )
    speed = max(0.05, min(1.0, speed))
    vfd_shaft = vfd_affinity_shaft_kw(
        map_shaft,
        speed,
        blower_type=btype,
        affinity_exponent=float(spec.get("affinity_exponent", 3.0)),
    )
    vfd_motor_per = curve_motor_kw(vfd_shaft, blower_eta, motor_eta)
    vfd_motor_fleet = vfd_motor_per * n_on

    ad_fleet_shaft_recon = round(ad_per_shaft * n_on, 2)
    ad_fleet_motor_recon = round(ad_per_motor * n_on, 2)

    delta_per_pct = (
        100.0 * (map_motor_per - ad_per_motor) / ad_per_motor
        if ad_per_motor > 1e-6
        else 0.0
    )
    delta_fleet_pct = (
        100.0 * (map_motor_fleet - ad_fleet_motor_recon) / ad_fleet_motor_recon
        if ad_fleet_motor_recon > 1e-6
        else 0.0
    )
    comparison_trustworthy = (
        power_basis == "motor"
        and not extrap
        and abs(delta_per_pct) <= 80.0
        and abs(delta_fleet_pct) <= 80.0
    )

    flags: List[str] = []
    if extrap:
        flags.append("map_extrapolated")
        if axis_flags.get("q_high"):
            flags.append("extrapolated_q_above_grid")
        if axis_flags.get("q_low"):
            flags.append("extrapolated_q_below_grid")
        if axis_flags.get("dp_high"):
            flags.append("extrapolated_dp_above_grid")
        if axis_flags.get("dp_low"):
            flags.append("extrapolated_dp_below_grid")
    if not in_env and not extrap:
        flags.append("outside_map_envelope")
    if auto_switched:
        flags.append("auto_curve_centrifugal")
    if abs(delta_per_pct) > 25.0:
        flags.append("large_adiabatic_vs_map_delta")
    if speed < 0.98 and btype == "centrifugal":
        flags.append("vfd_part_load_active")
    if n_on > 1:
        flags.append("fleet_duty_split")

    q_max_cat = float(spec.get("q_max_nm3h") or spec["q_nm3h"][-1])
    if q_per > q_max_cat + 1e-6:
        flags.append("per_machine_q_above_catalog_max")

    return {
        "enabled": True,
        "curve_id": cid,
        "curve_id_requested": user_cid,
        "curve_label": spec["label"],
        "blower_type": btype,
        "auto_curve_switched": auto_switched,
        "auto_curve_reason": auto_reason,
        "fleet": {
            "n_on_duty": n_on,
            "q_total_nm3h": round(q_total, 1),
            "q_per_machine_nm3h": round(q_per, 1),
        },
        "operating_point": {
            "q_nm3h": round(q_per, 1),
            "q_total_nm3h": round(q_total, 1),
            "dp_bar": round(dp_bar, 3),
            "speed_frac": round(speed, 3),
            "n_on_duty": n_on,
        },
        "adiabatic": {
            "shaft_kw": ad_per_shaft,
            "motor_kw": ad_per_motor,
            "shaft_kw_per_machine": ad_per_shaft,
            "motor_kw_per_machine": ad_per_motor,
            "shaft_kw_fleet": ad_fleet_shaft_recon,
            "motor_kw_fleet": ad_fleet_motor_recon,
            "shaft_kw_fleet_sizing": round(ad_fleet_shaft, 2),
            "motor_kw_fleet_sizing": round(ad_fleet_motor, 2),
            "q_nm3h_per_machine": round(q_per, 1),
            "method": "ideal_gas_gamma_1.4",
            "note": (
                "Fleet shaft/motor = per-machine × n installed (parallel duty). "
                "fleet_sizing_* = single bw_system_sizing pass at plant Q."
            ),
        },
        "comparison_trustworthy": comparison_trustworthy,
        "curve_map": {
            "shaft_kw": round(map_shaft, 2),
            "shaft_kw_fleet": round(map_shaft_fleet, 2),
            "motor_kw_per_machine": round(map_motor_per, 2),
            "motor_kw_fleet": round(map_motor_fleet, 2),
            "motor_kw": round(map_motor_fleet, 2),
            "power_basis": power_basis,
            "oem_model_hint": oem_hint,
            "in_envelope": in_env,
            "extrapolated": extrap,
            "extrapolation_axes": axis_flags,
        },
        "chart_points": {
            "per_machine": {
                "q_nm3h": round(q_per, 1),
                "map_shaft_kw": round(map_shaft, 2),
                "adiabatic_shaft_kw": ad_per_shaft,
            },
            "fleet_on_duty": {
                "q_nm3h": round(q_total, 1),
                "map_shaft_kw": round(map_shaft_fleet, 2),
                "adiabatic_shaft_kw": ad_fleet_shaft_recon,
                "n_on_duty": n_on,
            },
        },
        "vfd": {
            "shaft_kw": round(vfd_shaft, 2),
            "motor_kw_per_machine": round(vfd_motor_per, 2),
            "motor_kw_fleet": round(vfd_motor_fleet, 2),
            "motor_kw": round(vfd_motor_fleet, 2),
            "affinity_exponent": float(spec.get("affinity_exponent", 3.0)),
        },
        "delta_map_vs_adiabatic_motor_pct": round(delta_per_pct, 1),
        "delta_map_vs_adiabatic_fleet_pct": round(delta_fleet_pct, 1),
        "curve_plot": curve_envelope_plot_points(cid, dp_bar),
        "advisory_flags": flags,
        "assumption_ids": ["ASM-BLOWER-01"],
        "note": (
            "Map is indicative generic OEM grid — confirm with vendor datasheet. "
            "Per-machine Q = plant Q / n on duty. Adiabatic model remains primary in "
            "bw_system_sizing / energy."
        ),
    }
