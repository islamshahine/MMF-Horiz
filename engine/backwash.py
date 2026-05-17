"""
engine/backwash.py
──────────────────
Backwash and media expansion for horizontal multi-media filters.

Key exports
-----------
1. backwash_hydraulics   BW pump flow, air-scour blower capacity
2. bed_expansion         Richardson-Zaki fluidisation per layer
3. solve_equivalent_velocity_for_target_expansion_pct  — inverse (target % → m/h)
4. filter_bw_timeline_24h — idealised 24 h filter duty / BW Gantt data
5. pressure_drop         Ergun equation  — clean / moderate / dirty
6. bw_sequence           BW step schedule, waste volumes & TSS
"""

import math

GRAVITY         = 9.81       # m/s²
_RHO_WATER_DEF  = 1025.0     # kg/m³


# ═══════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def _viscosity(temp_c: float) -> float:
    """Dynamic viscosity of water, Pa·s  (Vogel equation)."""
    return 2.414e-5 * 10 ** (247.8 / (temp_c + 133.15))


def _archimedes(d_m: float, rho_p: float, rho_f: float, mu: float) -> float:
    """Archimedes number using particle diameter d_m."""
    if d_m <= 0:
        return 0.0
    return d_m**3 * rho_f * (rho_p - rho_f) * GRAVITY / mu**2


def _terminal_velocity(d_m: float, rho_p: float, rho_f: float, mu: float) -> float:
    """
    Terminal settling velocity, m/s.
    Stokes / Allen intermediate / Newton via Archimedes number.
    Returns 0 for degenerate inputs.
    """
    if d_m <= 0:
        return 0.0
    Ar = _archimedes(d_m, rho_p, rho_f, mu)
    if Ar < 36:
        return d_m**2 * (rho_p - rho_f) * GRAVITY / (18.0 * mu)
    elif Ar < 83_000:
        return (0.153 * d_m**1.14
                * ((rho_p - rho_f) * GRAVITY / rho_f) ** 0.714
                / (mu / rho_f) ** 0.428)
    else:
        return 1.74 * math.sqrt(d_m * (rho_p - rho_f) * GRAVITY / rho_f)


def _rz_exponent(Re_mf: float) -> float:
    """
    Richardson-Zaki n evaluated at Re_mf (Wen & Yu proxy).
    Calibrated to filter media expansion data.
    """
    if Re_mf < 0.2:   return 4.65
    if Re_mf < 1.0:   return 4.35 * Re_mf ** (-0.03)
    if Re_mf < 500.0: return 4.45 * Re_mf ** (-0.1)
    return 2.39


def _u_mf_wen_yu(d_m: float, rho_p: float, rho_f: float, mu: float) -> tuple:
    """
    Minimum fluidisation velocity — Wen & Yu (1966).
    Standard for granular filter media expansion design.

        Re_mf = sqrt(33.7^2 + 0.0408*Ar) - 33.7
        u_mf  = Re_mf * mu / (rho_f * d10)

    Returns (u_mf m/s, Re_mf, n_rz).
    """
    if d_m <= 0:
        return 0.0, 0.0, 4.65
    Ar    = _archimedes(d_m, rho_p, rho_f, mu)
    Re_mf = max(math.sqrt(33.7**2 + 0.0408 * Ar) - 33.7, 0.0)
    u_mf  = Re_mf * mu / (rho_f * d_m)
    n_rz  = _rz_exponent(Re_mf)
    return u_mf, Re_mf, n_rz


# Keep old _u_mf for Ergun pressure drop (different use case)
def _u_mf(d_m, rho_p, rho_f, mu, eps0, phi=0.85):
    """Ergun-based u_mf — used only for pressure drop cross-check."""
    if d_m <= 0 or eps0 <= 0:
        return 0.0
    A = 150 * mu * (1 - eps0)**2 / (phi**2 * d_m**2 * eps0**3)
    B = 1.75 * rho_f * (1 - eps0) / (phi * d_m * eps0**3)
    C = (rho_p - rho_f) * GRAVITY
    disc = A**2 + 4 * B * C
    if disc < 0 or B == 0:
        return 0.0
    return (-A + math.sqrt(disc)) / (2 * B)


# ═══════════════════════════════════════════════════════════════════════════
# 1. BACKWASH HYDRAULICS
# ═══════════════════════════════════════════════════════════════════════════

def backwash_hydraulics(
    filter_area_m2: float,
    bw_rate_m_h: float         = 30.0,
    air_scour_rate_m_h: float  = 55.0,
    filtration_flow_m3h: float = 0.0,
    bw_safety_factor: float    = 1.10,
) -> dict:
    """
    BW pump flow and air-scour blower capacity.

    BW flow = max(bw_rate × area,  2 × filtration_flow)
    Air flow = air_scour_rate × area  (volumetric, at vessel conditions)

    Blower power: isothermal compression, ΔP=0.5 bar, η=0.65.
    """
    q_bw_area = bw_rate_m_h * filter_area_m2
    q_bw_2x   = 2.0 * filtration_flow_m3h
    q_bw      = max(q_bw_area, q_bw_2x)
    governs   = "BW rate × area" if q_bw_area >= q_bw_2x else "2 × filtration flow"

    q_air     = air_scour_rate_m_h * filter_area_m2
    p_blower  = (q_air / 3600) * (0.5e5) / 0.65 / 1000   # kW

    return {
        "q_bw_from_rate_m3h":  round(q_bw_area, 2),
        "q_bw_from_2x_m3h":    round(q_bw_2x,   2),
        "q_bw_m3h":            round(q_bw,       2),
        "bw_governs":          governs,
        "bw_lv_actual_m_h":    round(q_bw / filter_area_m2, 2),
        "q_bw_design_m3h":     round(q_bw * bw_safety_factor, 2),
        "q_air_m3h":           round(q_air, 2),
        "q_air_design_m3h":    round(q_air * bw_safety_factor, 2),
        "p_blower_est_kw":     round(p_blower, 2),
        "bw_rate_m_h":         bw_rate_m_h,
        "air_scour_rate_m_h":  air_scour_rate_m_h,
        "filter_area_m2":      round(filter_area_m2, 3),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 2. BED EXPANSION  —  Richardson-Zaki
# ═══════════════════════════════════════════════════════════════════════════

def layer_expansion(
    depth_m: float,
    epsilon0: float,
    d10_mm: float,
    rho_p: float,
    bw_velocity_m_h: float,
    cu: float            = 1.0,
    water_temp_c: float  = 27.0,
    rho_water: float     = _RHO_WATER_DEF,
) -> dict:
    """
    Richardson-Zaki bed expansion for one media layer.

    Methodology (Wen & Yu 1966 / Dharmarajah & Cleasby 1986):
    1. Ar    = d10^3 * rho_f * (rho_p - rho_f) * g / mu^2
    2. Re_mf = sqrt(33.7^2 + 0.0408*Ar) - 33.7
    3. u_mf  = Re_mf * mu / (rho_f * d10)
    4. n     = R-Z at Re_mf  (proxy for Re_t, calibrated to filter media)
    5. u_t   = Allen formula with d50 = d10 * sqrt(CU)
    6. eps_f = (u_bw / u_t)^(1/n)
    7. Expansion: L_exp = L0*(1-eps0)/(1-eps_f) if eps_f > eps0 else L0
    """
    if d10_mm <= 0 or epsilon0 <= 0 or depth_m <= 0:
        return {
            "depth_settled_m": round(depth_m, 3), "epsilon0": epsilon0,
            "d10_mm": d10_mm, "d50_mm": 0.0, "Ar": 0.0, "Re_mf": 0.0,
            "mu_pa_s": 0.0, "u_mf_m_h": 0.0, "n_rz": 0.0,
            "u_t_m_h": 0.0, "u_bw_m_h": bw_velocity_m_h,
            "eps_f": 0.0, "fluidised": False, "elutriation_risk": False,
            "depth_expanded_m": round(depth_m, 3), "expansion_pct": 0.0,
            "warning": "Incomplete media data — d10, epsilon0, or depth is zero.",
        }

    mu  = _viscosity(water_temp_c)
    d10 = d10_mm / 1000.0

    # 1-4: Wen & Yu u_mf and n
    Ar    = _archimedes(d10, rho_p, rho_water, mu)
    Re_mf = math.sqrt(33.7**2 + 0.0408 * Ar) - 33.7
    Re_mf = max(Re_mf, 0.0)
    u_mf  = Re_mf * mu / (rho_water * d10)
    n_rz  = _rz_exponent(Re_mf)

    # 5: u_t with d50 = d10 * sqrt(CU)
    cu_safe = max(cu, 1.0)
    d50     = d10 * cu_safe ** 0.5
    u_t     = _terminal_velocity(d50, rho_p, rho_water, mu)

    # 6: voidage from R-Z
    u_bw  = bw_velocity_m_h / 3600.0
    eps_f = (u_bw / u_t) ** (1.0 / n_rz) if u_t > 0 else 0.0

    elutriation = u_bw >= u_t and u_t > 0
    fluidised   = eps_f > epsilon0 and not elutriation

    if elutriation:
        depth_exp     = depth_m
        expansion_pct = 0.0
        warning = "WARNING: u_bw >= u_t — elutriation risk! Reduce BW rate."
    elif fluidised:
        depth_exp     = depth_m * (1.0 - epsilon0) / (1.0 - eps_f)
        expansion_pct = (depth_exp / depth_m - 1.0) * 100.0
        warning = ""
    else:
        depth_exp     = depth_m
        expansion_pct = 0.0
        warning = "u_bw {:.1f} m/h < u_mf {:.1f} m/h — bed rests on plate.".format(
            bw_velocity_m_h, u_mf * 3600)

    return {
        "depth_settled_m":  round(depth_m,           3),
        "epsilon0":         round(epsilon0,           3),
        "d10_mm":           round(d10_mm,             2),
        "d50_mm":           round(d50 * 1000,         3),
        "Ar":               round(Ar,                 1),
        "Re_mf":            round(Re_mf,              4),
        "mu_pa_s":          round(mu,                 6),
        "u_mf_m_h":         round(u_mf * 3600,        2),
        "n_rz":             round(n_rz,               4),
        "u_t_m_h":          round(u_t * 3600,         1),
        "u_bw_m_h":         bw_velocity_m_h,
        "eps_f":            round(eps_f,              4),
        "fluidised":        fluidised,
        "elutriation_risk": elutriation,
        "depth_expanded_m": round(depth_exp,          3),
        "expansion_pct":    round(expansion_pct,      1),
        "warning":          warning,
    }


def bed_expansion(
    layers: list,
    bw_velocity_m_h: float,
    water_temp_c: float = 27.0,
    rho_water: float    = _RHO_WATER_DEF,
    expansion_calibration_scale: float = 1.0,
) -> dict:
    """Expand all layers; return per-layer results and totals."""
    results        = []
    total_settled  = 0.0
    total_expanded = 0.0
    scl = max(0.5, min(1.5, float(expansion_calibration_scale)))

    for L in layers:
        r = layer_expansion(
            depth_m=L.get("Depth",     0.5),
            epsilon0=L.get("epsilon0", 0.42),
            d10_mm=L.get("d10",        1.0),
            rho_p=L.get("rho_p_eff",   2650),
            bw_velocity_m_h=bw_velocity_m_h,
            cu=L.get("cu",             1.0),
            water_temp_c=water_temp_c,
            rho_water=rho_water,
        )
        d0 = float(L.get("Depth", 0.0))
        d_exp = float(r["depth_expanded_m"])
        if scl != 1.0 and d0 > 1e-9:
            inc = d_exp - d0
            d_adj = d0 + inc * scl
            r["depth_expanded_m"] = round(d_adj, 3)
            r["expansion_pct"] = round((d_adj / d0 - 1.0) * 100.0, 1)
        r["media_type"] = L.get("Type", "—")
        r["is_support"] = bool(L.get("is_support", False))
        results.append(r)
        total_settled  += d0
        total_expanded += float(r["depth_expanded_m"])

    exp_pct = (total_expanded / total_settled - 1) * 100 if total_settled > 0 else 0.0
    any_warn = any(r["warning"] for r in results)

    return {
        "layers":               results,
        "total_settled_m":      round(total_settled,  3),
        "total_expanded_m":     round(total_expanded, 3),
        "total_expansion_pct":  round(exp_pct,        1),
        "bw_velocity_m_h":      bw_velocity_m_h,
        "water_temp_c":         water_temp_c,
        "any_warning":          any_warn,
    }


def solve_equivalent_velocity_for_target_expansion_pct(
    layers: list,
    target_expansion_pct: float,
    water_temp_c: float = 27.0,
    rho_water: float = _RHO_WATER_DEF,
    u_scan_max_m_h: float = 200.0,
    scan_step_m_h: float = 1.0,
    low_rate_water_m_h: float = 0.0,
) -> dict:
    """
    Find **air-equivalent** superficial velocity (m/h) such that the R–Z stack
    matches the target net expansion at the **air + low-rate water** step.

    The combined superficial velocity passed to ``bed_expansion`` is::

        u_total = max(0, low_rate_water_m_h) + u_air_equivalent

    ``low_rate_water_m_h`` is the fixed water leg (step ③); the solver searches
    ``u_air_equivalent`` only.  This is still a single-phase surrogate, not CFD.

    Returns the **smallest** air-equivalent velocity that reaches the target
    (first crossing when scanning upward), then refines by bisection on the
    lower boundary.  For monotone expansion vs. ``u_air``, this is the
    **minimum** air rate — and at fixed blower ΔP/efficiency, the **minimum**
    screening mass flow / shaft power for that target expansion.
    """
    tgt = float(target_expansion_pct)
    u_w = max(0.0, float(low_rate_water_m_h))
    note = (
        "Air-equivalent superficial velocity from R–Z bed model (combined-phase "
        "surrogate: u_total = low-rate water + air equivalent); vendor air-grid data may differ."
    )

    def _exp_pct(u_air: float) -> float:
        return float(
            bed_expansion(
                layers, u_w + max(0.0, u_air), water_temp_c, rho_water,
            )["total_expansion_pct"]
        )

    e_water_only = float(
        bed_expansion(layers, u_w, water_temp_c, rho_water)["total_expansion_pct"]
    )

    if tgt <= 0.0:
        e0 = _exp_pct(0.0)
        return {
            "ok": True,
            "velocity_m_h": 0.0,
            "low_rate_water_m_h": round(u_w, 3),
            "combined_superficial_m_h": round(u_w, 3),
            "expansion_water_only_pct": round(e_water_only, 2),
            "expansion_increment_from_air_pct": round(e0 - e_water_only, 2),
            "expansion_at_velocity_pct": round(e0, 2),
            "target_expansion_pct": tgt,
            "bound_hit": "none",
            "note": note + " Target ≤ 0 — returning zero air-equivalent velocity.",
        }

    e0 = _exp_pct(0.0)
    if e0 >= tgt:
        return {
            "ok": True,
            "velocity_m_h": 0.0,
            "low_rate_water_m_h": round(u_w, 3),
            "combined_superficial_m_h": round(u_w, 3),
            "expansion_water_only_pct": round(e_water_only, 2),
            "expansion_increment_from_air_pct": round(e0 - e_water_only, 2),
            "expansion_at_velocity_pct": round(e0, 2),
            "target_expansion_pct": tgt,
            "bound_hit": "none",
            "note": note + " Target already met with low-rate water only (u_air = 0).",
        }

    prev_u, prev_e = 0.0, e0
    u_hi = None
    u = scan_step_m_h
    while u <= u_scan_max_m_h + 1e-9:
        e = _exp_pct(u)
        if e >= tgt:
            u_hi = u
            break
        prev_u, prev_e = u, e
        u += scan_step_m_h

    if u_hi is None:
        e_max = _exp_pct(u_scan_max_m_h)
        return {
            "ok": False,
            "velocity_m_h": round(u_scan_max_m_h, 2),
            "low_rate_water_m_h": round(u_w, 3),
            "combined_superficial_m_h": round(u_w + u_scan_max_m_h, 3),
            "expansion_water_only_pct": round(e_water_only, 2),
            "expansion_increment_from_air_pct": round(e_max - e_water_only, 2),
            "expansion_at_velocity_pct": round(e_max, 2),
            "target_expansion_pct": tgt,
            "bound_hit": "u_max",
            "note": note + f" Target not reached by {u_scan_max_m_h:g} m/h "
            f"(expansion {e_max:.1f} %).",
        }

    lo, hi = prev_u, u_hi
    for _ in range(55):
        mid = 0.5 * (lo + hi)
        if _exp_pct(mid) >= tgt:
            hi = mid
        else:
            lo = mid
    u_sol = round(0.5 * (lo + hi), 3)
    e_sol = _exp_pct(u_sol)

    return {
        "ok": True,
        "velocity_m_h": u_sol,
        "low_rate_water_m_h": round(u_w, 3),
        "combined_superficial_m_h": round(u_w + u_sol, 3),
        "expansion_water_only_pct": round(e_water_only, 2),
        "expansion_increment_from_air_pct": round(e_sol - e_water_only, 2),
        "expansion_at_velocity_pct": round(e_sol, 2),
        "target_expansion_pct": tgt,
        "bound_hit": "none",
        "note": note,
    }


def nm3h_to_actual_m3s_at_pt(q_nm3h: float, P_pa: float, T_K: float, *, R: float = 287.0) -> float:
    """
    Convert **normal** m³/h (dry air at **0 °C**, **101 325 Pa**) to **actual** m³/s
    at blower suction ``P_pa``, ``T_K`` (ideal gas, constant mass flow).
    """
    P_n = 101_325.0
    T_n = 273.15
    q_n_m3s = max(float(q_nm3h), 0.0) / 3600.0
    t_k = max(float(T_K), 200.0)
    p_pa = max(float(P_pa), 1000.0)
    mdot = P_n * q_n_m3s / (R * T_n)
    rho1 = p_pa / (R * t_k)
    return mdot / max(rho1, 1e-12)


def actual_m3m2h_to_nm3_m2h(
    q_m3_per_m2_h: float,
    temp_c: float,
    pressure_gauge_bar: float,
) -> float:
    """
    Ideal-gas correction: in-situ m³/(m²·h) → Nm³/(m²·h) at 0 °C, 1 atm.

    Uses absolute pressure = atmospheric + gauge (bar).
    """
    p_abs_bar = 1.01325 + max(float(pressure_gauge_bar), 0.0)
    t_k = max(float(temp_c) + 273.15, 200.0)
    t_n = 273.15
    p_n = 1.01325
    return float(q_m3_per_m2_h) * (t_n / t_k) * (p_abs_bar / p_n)


def filter_bw_timeline_24h(
    n_filters_total: int,
    t_cycle_h: float,
    bw_duration_h: float,
    horizon_h: float = 24.0,
    *,
    bw_trains: int | None = None,
    stagger_model: str = "feasibility_trains",
    sim_demand: float | None = None,
    n_streams: int = 1,
    scheduler_inputs: dict | None = None,
) -> dict:
    """
    Filter duty chart: operate vs backwash over ``horizon_h``.

    * ``stagger_model="uniform"`` — phases ``i/N`` of ``period`` (legacy smooth fiction).

    * ``stagger_model="feasibility_trains"`` — BW start spacing ``Δt_bw / bw_trains``
      so the **integer** ``bw_trains`` caps concurrent BW in the schematic (aligned with
      the feasibility matrix). If ``bw_trains < ceil(N·Δt_bw/T)``, a shortfall note is added.

    * ``stagger_model="optimized_trains"`` — **scheduling aid**: coordinate descent on
      per-filter phases (see ``engine/bw_scheduler.py``) to reduce peak concurrent BW
      over ``horizon_h`` while keeping the same cycle period.

    * ``stagger_model="tariff_aware_v3"`` — **B2**: v3 optimizer — peak trains + shift BW
      toward off-peak electricity windows + avoid maintenance blackouts (heuristic).
      Pass tariff/blackout settings via ``scheduler_inputs`` dict.

    * ``stagger_model="milp_lite"`` — **C5**: discrete-phase ILP (PuLP) minimizing peak,
      peak-tariff filter-hours, and blackout overlap; falls back to v3 if solver unavailable.
    """
    if n_filters_total < 1:
        return {
            "filters": [],
            "peak_concurrent_bw": 0,
            "horizon_h": horizon_h,
            "t_cycle_h": t_cycle_h,
            "bw_duration_h": bw_duration_h,
            "period_h": 0.0,
            "stagger_model": stagger_model,
            "bw_trains": bw_trains,
            "sim_demand": sim_demand,
            "note": "No filters — empty timeline.",
        }

    tc = float(t_cycle_h)
    if not math.isfinite(tc) or tc <= 0:
        tc = 24.0
    bd = float(bw_duration_h)
    if not math.isfinite(bd) or bd <= 0:
        bd = 0.05

    period = tc + bd
    if period <= 0:
        period = 24.0

    n_int = int(n_filters_total)
    K_raw = int(bw_trains) if bw_trains is not None else 1
    K = max(1, min(K_raw, n_int))
    min_k = int(math.ceil(n_int * bd / max(period, 1e-9)))
    notes: list[str] = []

    _sched_in = dict(scheduler_inputs or {})
    use_milp = (
        stagger_model == "milp_lite"
        and bw_trains is not None
        and K_raw >= 1
    )
    use_tariff_v3 = (
        not use_milp
        and stagger_model == "tariff_aware_v3"
        and bw_trains is not None
        and K_raw >= 1
    )
    use_optimized = (
        not use_milp
        and not use_tariff_v3
        and stagger_model == "optimized_trains"
        and bw_trains is not None
        and K_raw >= 1
    )
    use_uniform = (
        not use_milp
        and not use_optimized
        and (stagger_model == "uniform" or bw_trains is None or K_raw < 1)
    )
    train_shortfall = False
    opt_meta: dict = {}

    if use_milp:
        from engine.bw_scheduler_milp import build_bw_schedule_assessment_milp

        assess = build_bw_schedule_assessment_milp(
            n_int,
            period_h=period,
            bw_duration_h=bd,
            bw_trains=K,
            horizon_h=horizon_h,
            inputs=_sched_in,
            n_streams=max(1, int(n_streams)),
        )
        filters = assess["filters"]
        opt_meta = assess.get("optimizer") or {}
        peak = int(assess["peak_concurrent_bw"])
        notes.extend(assess.get("advisory_notes") or [])
        stagger_model_out = "milp_lite"
        bw_trains_out = K
        train_shortfall = K < min_k
        if sim_demand is not None and math.isfinite(float(sim_demand)):
            notes.append(f"Feasibility sim_demand ≈ {float(sim_demand):.2f}.")
        return {
            "filters": filters,
            "peak_concurrent_bw": peak,
            "horizon_h": horizon_h,
            "t_cycle_h": tc,
            "bw_duration_h": bd,
            "period_h": period,
            "stagger_model": stagger_model_out,
            "bw_trains": bw_trains_out,
            "sim_demand": sim_demand,
            "note": " ".join(notes),
            "optimizer": opt_meta,
            "peak_windows": assess.get("peak_windows") or [],
            "meets_bw_trains_cap": assess.get("meets_bw_trains_cap"),
        }

    if use_tariff_v3:
        from engine.bw_scheduler import build_bw_schedule_assessment_v3

        assess = build_bw_schedule_assessment_v3(
            n_int,
            period_h=period,
            bw_duration_h=bd,
            bw_trains=K,
            horizon_h=horizon_h,
            inputs=_sched_in,
            n_streams=max(1, int(n_streams)),
        )
        filters = assess["filters"]
        opt_meta = assess.get("optimizer") or {}
        peak = int(assess["peak_concurrent_bw"])
        notes.append(
            "Tariff-aware v3 stagger: minimizes peak concurrent BW, peak-tariff filter-hours, "
            "and maintenance blackout overlap (scheduling aid)."
        )
        if int(opt_meta.get("improvement_filters", 0) or 0) > 0:
            notes.append(
                f"v3 vs feasibility spacing: peak reduced by {opt_meta['improvement_filters']} filter(s)."
            )
        stagger_model_out = "tariff_aware_v3"
        bw_trains_out = K
        train_shortfall = K < min_k
        if train_shortfall:
            notes.append(
                f"⚠ bw_trains={K} < ceil(N·Δt_bw/T)={min_k} — demand may exceed this schematic."
            )
        if sim_demand is not None and math.isfinite(float(sim_demand)):
            notes.append(f"Feasibility sim_demand ≈ {float(sim_demand):.2f}.")

        return {
            "filters": filters,
            "peak_concurrent_bw": int(peak),
            "horizon_h": horizon_h,
            "t_cycle_h": round(tc, 3),
            "bw_duration_h": round(bd, 4),
            "period_h": round(period, 3),
            "stagger_model": stagger_model_out,
            "bw_trains": bw_trains_out,
            "sim_demand": None if sim_demand is None else round(float(sim_demand), 3),
            "min_bw_trains_theory": min_k,
            "train_shortfall": train_shortfall,
            "optimizer": opt_meta,
            "peak_time_h": assess.get("peak_time_h"),
            "peak_windows": assess.get("peak_windows"),
            "meets_bw_trains_cap": bool(assess.get("meets_bw_trains_cap", peak <= K)),
            "tariff_v3": assess.get("tariff_v3"),
            "advisory_notes": assess.get("advisory_notes"),
            "note": " ".join(notes),
        }

    if use_optimized:
        from engine.bw_scheduler import filters_from_phases, optimize_bw_phases, peak_concurrent_bw

        phases, opt_meta = optimize_bw_phases(
            n_int,
            period_h=period,
            bw_duration_h=bd,
            bw_trains=K,
            horizon_h=horizon_h,
            n_streams=max(1, int(n_streams)),
        )
        filters = filters_from_phases(
            n_int,
            phases,
            period_h=period,
            bw_duration_h=bd,
            horizon_h=horizon_h,
        )
        from engine.bw_scheduler import find_peak_bw_windows, peak_concurrent_bw_profile

        prof = peak_concurrent_bw_profile(filters, horizon_h=horizon_h)
        peak = int(prof["peak"])
        _peak_wins = find_peak_bw_windows(filters, horizon_h=horizon_h)
        opt_meta = {
            **opt_meta,
            "peak_time_h": prof["peak_time_h"],
            "peak_windows": _peak_wins,
        }
        notes.append(
            f"Optimized train stagger (scheduling aid): peak {opt_meta.get('peak_optimized')} "
            f"vs feasibility spacing peak {opt_meta.get('peak_feasibility_spacing')} "
            f"(target bw_trains={K})."
        )
        if int(opt_meta.get("improvement_filters", 0) or 0) > 0:
            notes.append(
                f"Optimizer lowered peak concurrent BW by "
                f"{opt_meta['improvement_filters']} filter(s) vs feasibility spacing."
            )
        stagger_model_out = "optimized_trains"
        bw_trains_out = K
        train_shortfall = K < min_k
        if train_shortfall:
            notes.append(
                f"⚠ bw_trains={K} < ceil(N·Δt_bw/T)={min_k} — demand may exceed this schematic."
            )
        if sim_demand is not None and math.isfinite(float(sim_demand)):
            notes.append(f"Feasibility sim_demand ≈ {float(sim_demand):.2f}.")

        return {
            "filters": filters,
            "peak_concurrent_bw": int(peak),
            "horizon_h": horizon_h,
            "t_cycle_h": round(tc, 3),
            "bw_duration_h": round(bd, 4),
            "period_h": round(period, 3),
            "stagger_model": stagger_model_out,
            "bw_trains": bw_trains_out,
            "sim_demand": None if sim_demand is None else round(float(sim_demand), 3),
            "min_bw_trains_theory": min_k,
            "train_shortfall": train_shortfall,
            "optimizer": opt_meta,
            "peak_time_h": prof["peak_time_h"],
            "peak_windows": _peak_wins,
            "meets_bw_trains_cap": bool(opt_meta.get("meets_bw_trains_cap", peak <= K)),
            "note": " ".join(notes),
        }

    if use_uniform:
        notes.append("Uniform stagger (i/N of period).")

        def _phi(i: int) -> float:
            return (i / float(n_int)) * period

        stagger_model_out = "uniform"
        bw_trains_out = None
    else:
        notes.append(
            f"Feasibility-train stagger: start spacing = Δt_bw / bw_trains "
            f"({bd:.3f} h / {K})."
        )

        def _phi(i: int) -> float:
            return (i * bd) / float(K)

        stagger_model_out = "feasibility_trains"
        bw_trains_out = K
        train_shortfall = K < min_k
        if train_shortfall:
            notes.append(
                f"⚠ bw_trains={K} < ceil(N·Δt_bw/T)={min_k} — demand may exceed this schematic."
            )

    if sim_demand is not None and math.isfinite(float(sim_demand)):
        notes.append(f"Feasibility sim_demand ≈ {float(sim_demand):.2f}.")

    filters: list[dict] = []
    for i in range(n_int):
        phi = _phi(i)
        bws: list[tuple[float, float]] = []
        k_lo = int(math.floor((0.0 - phi - bd) / period)) - 1
        k_hi = int(math.ceil((horizon_h - phi) / period)) + 2
        for k in range(k_lo, k_hi + 1):
            start = phi + k * period
            t0 = max(0.0, start)
            t1 = min(horizon_h, start + bd)
            if t0 + 1e-9 < t1:
                bws.append((t0, t1))
        bws.sort()
        merged: list[tuple[float, float]] = []
        for a, b in bws:
            if merged and a <= merged[-1][1] + 1e-9:
                merged[-1] = (merged[-1][0], max(merged[-1][1], b))
            else:
                merged.append((a, b))

        segs: list[dict[str, float | str]] = []
        cursor = 0.0
        for a, b in merged:
            if cursor + 1e-9 < a:
                segs.append({"state": "operate", "t0": cursor, "t1": a})
            segs.append({"state": "bw", "t0": a, "t1": b})
            cursor = b
        if cursor + 1e-9 < horizon_h:
            segs.append({"state": "operate", "t0": cursor, "t1": horizon_h})

        filters.append({"filter_index": i + 1, "segments": segs})

    from engine.bw_scheduler import find_peak_bw_windows, peak_concurrent_bw_profile

    prof = peak_concurrent_bw_profile(filters, horizon_h=horizon_h)
    peak = int(prof["peak"])
    _peak_wins = find_peak_bw_windows(filters, horizon_h=horizon_h)
    _k_cap = int(bw_trains_out) if bw_trains_out is not None else max(1, K)

    return {
        "filters": filters,
        "peak_concurrent_bw": peak,
        "peak_time_h": prof["peak_time_h"],
        "peak_windows": _peak_wins,
        "meets_bw_trains_cap": peak <= _k_cap,
        "horizon_h": horizon_h,
        "t_cycle_h": round(tc, 3),
        "bw_duration_h": round(bd, 4),
        "period_h": round(period, 3),
        "stagger_model": stagger_model_out,
        "bw_trains": bw_trains_out,
        "sim_demand": None if sim_demand is None else round(float(sim_demand), 3),
        "min_bw_trains_theory": min_k,
        "train_shortfall": train_shortfall,
        "note": " ".join(notes),
    }


def timeline_plant_operating_hours(
    filters: list[dict],
    *,
    horizon_h: float,
    n_design_online_total: int,
) -> dict:
    """
    Plant-wide hours in [0, horizon_h] where **not in BW** filter count is
    ≥ design N, exactly N−1, or below N−1.

    Also splits the **≥ N** bucket into **exactly N** (rated set fully online) vs
    **> N** (physical spare also in filtration — N+1 margin).

    ``filters`` is the ``bw_timeline["filters"]`` list (one entry per **physical**
    filter in the schematic). ``n_design_online_total`` is the total number of filters
    that should be **online** for rated **N** hydraulics (typically
    ``streams × (n_filters_per_stream − spares)``).
    """
    h = float(horizon_h)
    if not filters or h <= 0:
        return {
            "hours_operating_ge_design_n_h": 0.0,
            "hours_operating_eq_design_n_h": 0.0,
            "hours_operating_gt_design_n_h": 0.0,
            "hours_operating_eq_n_minus_1_h": 0.0,
            "hours_operating_below_n_minus_1_h": 0.0,
            "n_design_online_total": int(max(0, n_design_online_total)),
            "n_physical_timeline": 0,
        }
    n_phys = len(filters)
    n_des = max(0, int(n_design_online_total))
    times: set[float] = {0.0, h}
    for f in filters:
        for s in f.get("segments") or []:
            times.add(float(s["t0"]))
            times.add(float(s["t1"]))
    ts = sorted(times)
    h_ge = h_eq_n = h_gt_n = h_nm1 = h_lt = 0.0
    for i in range(len(ts) - 1):
        t0, t1 = ts[i], ts[i + 1]
        if t1 <= t0 + 1e-12:
            continue
        tm = 0.5 * (t0 + t1)
        n_bw = 0
        for f in filters:
            in_bw = False
            for s in f.get("segments") or []:
                if str(s.get("state")) == "bw":
                    a, b = float(s["t0"]), float(s["t1"])
                    if a - 1e-9 <= tm < b + 1e-9:
                        in_bw = True
                        break
            if in_bw:
                n_bw += 1
        n_op = n_phys - n_bw
        dt = t1 - t0
        if n_des <= 0:
            h_ge += dt
        elif n_op > n_des:
            h_ge += dt
            h_gt_n += dt
        elif n_op == n_des:
            h_ge += dt
            h_eq_n += dt
        elif n_op == n_des - 1:
            h_nm1 += dt
        else:
            h_lt += dt
    return {
        "hours_operating_ge_design_n_h": round(h_ge, 2),
        "hours_operating_eq_design_n_h": round(h_eq_n, 2),
        "hours_operating_gt_design_n_h": round(h_gt_n, 2),
        "hours_operating_eq_n_minus_1_h": round(h_nm1, 2),
        "hours_operating_below_n_minus_1_h": round(h_lt, 2),
        "n_design_online_total": n_des,
        "n_physical_timeline": n_phys,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 3. PRESSURE DROP  —  Ergun equation
# ═══════════════════════════════════════════════════════════════════════════

def _ergun_dp(depth_m, eps, d10_mm, cu, phi, u_m_h, rho_f, mu):
    u   = u_m_h / 3600
    d   = (d10_mm * cu if cu > 1.0 else d10_mm) / 1000   # m, use d60 for ΔP
    if d <= 0 or eps <= 0 or depth_m <= 0:
        return 0.0
    A   = 150 * mu * (1 - eps)**2 * u / (phi**2 * d**2 * eps**3)
    B   = 1.75 * rho_f * (1 - eps) * u**2 / (phi * d * eps**3)
    return (A + B) * depth_m   # Pa


def pressure_drop(
    layers: list,
    q_filter_m3h: float,
    avg_area_m2: float,
    solid_loading_kg_m2: float    = 1.5,
    captured_density_kg_m3: float = 1020.0,
    water_temp_c: float           = 27.0,
    rho_water: float              = _RHO_WATER_DEF,
    alpha_m_kg: float             = 0.0,
    dp_trigger_bar: float         = 1.0,
    layer_areas_m2: list[float] | None = None,
    maldistribution_factor: float = 1.0,
    alpha_calibration_factor: float = 1.0,
) -> dict:
    """
    Filtration ΔP: clean (Ergun) / moderate (50% loaded) / dirty (100% loaded).

    Clean ΔP uses Ergun equation on the virgin bed.
    Moderate and dirty add cake filtration (Ruth model):
        ΔP_cake = α × μ × LV × M   where M = solid loading [kg/m²]
    alpha_m_kg = 0 → auto-calibrated so dirty ΔP equals dp_trigger_bar at M_max.
    alpha_m_kg > 0 → user-specified value.

    When ``layer_areas_m2`` is provided with one entry per layer, each layer's Ergun
    term uses u_i = Q/A_i (chordal slice in a horizontal drum). Cake resistance still
    uses the reference superficial velocity u_ref = Q/avg_area × maldistribution_factor
    so M_max [kg/m²] stays on the same basis as the solid-loading input.

    Solid capture per layer:
    • is_support=True  → no clogging.
    • capture_frac key → explicit weight (auto-normalised across non-support layers).
    • Neither          → depth-proportional among non-support layers.
    """
    mu = _viscosity(water_temp_c)
    _mal = max(1.0, float(maldistribution_factor))
    _acf = max(0.05, min(3.0, float(alpha_calibration_factor)))

    u_ref_m_h = q_filter_m3h / max(avg_area_m2, 1e-9) * _mal
    use_local = (
        layer_areas_m2 is not None
        and len(layer_areas_m2) == len(layers)
    )

    # ── Resolve & normalise capture fractions ─────────────────────────────
    non_sup_depth = sum(
        L.get("Depth", 0) for L in layers if not L.get("is_support", False)
    )
    raw = []
    for L in layers:
        if L.get("is_support", False):
            raw.append(0.0)
        elif L.get("capture_frac") is not None:
            raw.append(float(L["capture_frac"]))
        else:
            d = L.get("Depth", 0)
            raw.append(d / non_sup_depth if non_sup_depth > 0 else 0.0)

    non_sup_sum = sum(f for f, L in zip(raw, layers)
                      if not L.get("is_support", False))
    fracs = [
        0.0 if L.get("is_support", False)
        else (f / non_sup_sum if non_sup_sum > 0 else 0.0)
        for f, L in zip(raw, layers)
    ]

    rows = []
    dp_c = 0.0

    for i, (L, frac) in enumerate(zip(layers, fracs)):
        depth  = L.get("Depth",    0.5)
        eps0   = L.get("epsilon0", 0.42)
        d10    = L.get("d10",      1.0)
        cu     = L.get("cu",       1.5)
        phi    = L.get("psi",      0.85)   # per-layer sphericity
        is_sup = L.get("is_support", False)

        if use_local:
            u_m_h = q_filter_m3h / max(float(layer_areas_m2[i]), 1e-9) * _mal
        else:
            u_m_h = u_ref_m_h

        sol     = solid_loading_kg_m2 * frac
        sol_vol = sol / captured_density_kg_m3 if captured_density_kg_m3 > 0 else 0.0
        d_eps   = sol_vol / depth if depth > 0 else 0.0
        clog    = sol_vol / (depth * eps0) * 100 if (depth * eps0) > 0 else 0.0

        c = _ergun_dp(depth, eps0, d10, cu, phi, u_m_h, rho_water, mu)
        dp_c += c

        rows.append({
            "Media":               L.get("Type", "—"),
            "Support":             "✓" if is_sup else "",
            "Capture (%)":         "—" if is_sup else f"{frac * 100:.1f}",
            "Solid load (kg/m²)":  round(sol,     3),
            "Solid vol (m³/m²)":   round(sol_vol, 5),
            "ΔεF":                 round(d_eps,   4),
            "Clogging (%)":        "—" if is_sup else round(clog, 1),
            "Depth (m)":           round(depth,   3),
            "LV (m/h)":            round(u_m_h,   2),
            "ε clean":             round(eps0,    3),
            "ΔP clean (bar)":      round(c / 1e5, 5),
            # cake columns filled after α is resolved (below)
            "_frac":               frac,
        })

    # ── Cake model: moderate (50% M_max) and dirty (100% M_max) ─────────────
    lv_ms  = u_ref_m_h / 3600.0
    M_max  = solid_loading_kg_m2
    dp_c_bar = dp_c / 1e5

    dp_avail_pa = max(dp_trigger_bar - dp_c_bar, 0.0) * 1e5
    if alpha_m_kg <= 0:
        if M_max > 0 and lv_ms > 0 and mu > 0:
            alpha_used = dp_avail_pa / (mu * lv_ms * M_max)
        else:
            alpha_used = 0.0
        alpha_src = "auto-calibrated"
    else:
        alpha_used = alpha_m_kg
        alpha_src  = "user-specified"

    alpha_used *= _acf

    cake_mod_pa  = alpha_used * mu * lv_ms * (0.5 * M_max)   # 50% loaded
    cake_dir_pa  = alpha_used * mu * lv_ms * M_max            # 100% loaded
    dp_m_pa      = dp_c + cake_mod_pa
    dp_d_pa      = dp_c + cake_dir_pa

    # Distribute cake ΔP to rows by capture fraction
    for row in rows:
        f = row.pop("_frac")
        row["Cake ΔP mod (bar)"]   = round(f * cake_mod_pa / 1e5, 5)
        row["Cake ΔP dirty (bar)"] = round(f * cake_dir_pa / 1e5, 5)
        row["ΔP mod total (bar)"]  = round(row["ΔP clean (bar)"] + row["Cake ΔP mod (bar)"],   5)
        row["ΔP dirty total (bar)"]= round(row["ΔP clean (bar)"] + row["Cake ΔP dirty (bar)"], 5)

    rg = rho_water * GRAVITY
    return {
        "layers":                rows,
        "fracs":                 fracs,
        "u_m_h":                 round(u_ref_m_h,     2),
        "ergun_local_areas":     use_local,
        "solid_loading":         solid_loading_kg_m2,
        "captured_density":      captured_density_kg_m3,
        "alpha_used_m_kg":       alpha_used,
        "alpha_source":          alpha_src,
        "dp_clean_bar":          round(dp_c_bar,         5),
        "dp_moderate_bar":       round(dp_m_pa / 1e5,    5),
        "dp_dirty_bar":          round(dp_d_pa / 1e5,    5),
        "dp_clean_mwc":          round(dp_c    / rg,     3),
        "dp_moderate_mwc":       round(dp_m_pa / rg,     3),
        "dp_dirty_mwc":          round(dp_d_pa / rg,     3),
        "dp_clean_kpa":          round(dp_c    / 1e3,    3),
        "dp_moderate_kpa":       round(dp_m_pa / 1e3,    3),
        "dp_dirty_kpa":          round(dp_d_pa / 1e3,    3),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 3b. FILTRATION CYCLE — cake filtration model
# ═══════════════════════════════════════════════════════════════════════════

def filtration_cycle(
    layers: list,
    q_filter_m3h: float,
    avg_area_m2: float,
    solid_loading_kg_m2: float    = 1.5,
    captured_density_kg_m3: float = 1020.0,
    water_temp_c: float           = 27.0,
    rho_water: float              = _RHO_WATER_DEF,
    dp_trigger_bar: float         = 1.0,
    alpha_m_kg: float             = 0.0,
    tss_mg_l_list: list           = None,
    layer_areas_m2: list[float] | None = None,
    maldistribution_factor: float = 1.0,
    alpha_calibration_factor: float = 1.0,
    tss_capture_efficiency: float = 1.0,
) -> dict:
    """
    Filtration cycle duration — cake filtration model (Ruth, 1935).

    Physical basis
    --------------
    TSS particles (5–50 µm) are far smaller than media grains (0.8–1.3 mm).
    They do NOT fill bulk voids — they deposit on grain surfaces and block pore
    throats, forming a surface cake.  The resistance scales linearly with
    deposited mass (unlike bulk voidage reduction which is negligible):

        ΔP_total(M) = ΔP_clean_Ergun  +  α × μ × LV_m_s × M

    where:
        ΔP_clean_Ergun  clean-bed Ergun pressure drop  [Pa]
        α               specific cake resistance        [m/kg]
        μ               dynamic viscosity of feed water [Pa·s]
        LV_m_s          superficial filtration velocity [m/s]
        M               accumulated solid loading       [kg/m²]

    Trigger condition (BW initiation):
        M* = (DP_trigger − DP_clean) / (α × μ × LV_m_s)   [kg/m²]
        → analytical solution, no iteration needed.

    If alpha_m_kg ≤ 0 (auto-calibrate):
        α is back-calculated so that M* = M_max (solid_loading_kg_m2),
        i.e. the filter reaches the trigger exactly when fully loaded.
        α_cal = (DP_trigger − DP_clean) / (μ × LV_m_s × M_max)

    Typical α ranges [m/kg]:
        coarse mineral / silt   1×10⁸ – 1×10¹⁰
        seawater mixed TSS      1×10¹⁰ – 5×10¹⁰   ← default calibration target
        organic-rich / algae    1×10¹¹ – 5×10¹¹
        clay / fine colloids    1×10¹² – 1×10¹³
    """
    if tss_mg_l_list is None:
        tss_mg_l_list = [5.0, 10.0, 20.0]

    _acf = max(0.05, min(3.0, float(alpha_calibration_factor)))
    _cap = max(0.0, min(1.0, float(tss_capture_efficiency)))

    dp_res   = pressure_drop(
        layers=layers,
        q_filter_m3h=q_filter_m3h,
        avg_area_m2=avg_area_m2,
        solid_loading_kg_m2=solid_loading_kg_m2,
        captured_density_kg_m3=captured_density_kg_m3,
        water_temp_c=water_temp_c,
        rho_water=rho_water,
        alpha_m_kg=alpha_m_kg,
        dp_trigger_bar=dp_trigger_bar,
        layer_areas_m2=layer_areas_m2,
        maldistribution_factor=maldistribution_factor,
        alpha_calibration_factor=alpha_calibration_factor,
    )
    dp_clean_bar = dp_res["dp_clean_bar"]
    lv_mh        = dp_res["u_m_h"]
    lv_ms        = lv_mh / 3600.0
    mu           = _viscosity(water_temp_c)

    dp_avail_pa = max(dp_trigger_bar - dp_clean_bar, 0.0) * 1e5   # Pa

    # ── Auto-calibrate α so M* = M_max ────────────────────────────────────
    denom_cal = mu * lv_ms * solid_loading_kg_m2
    alpha_cal = dp_avail_pa / denom_cal if denom_cal > 0 else 0.0

    if alpha_m_kg <= 0:
        alpha_used = alpha_cal
        alpha_src  = "auto-calibrated"
    else:
        alpha_used = alpha_m_kg
        alpha_src  = "user-specified"

    alpha_used *= _acf

    # ── Analytical M* ─────────────────────────────────────────────────────
    denom_trig = alpha_used * mu * lv_ms
    if denom_trig > 0 and dp_avail_pa > 0:
        m_trigger = min(dp_avail_pa / denom_trig, solid_loading_kg_m2)
    else:
        m_trigger = solid_loading_kg_m2

    if dp_avail_pa <= 0:
        note = "ΔP_clean ≥ trigger — check setpoint"
    elif m_trigger >= solid_loading_kg_m2 * 0.9999:
        note = "Trigger not reached by M_max — BW by schedule (α too low)"
    else:
        note = f"BW triggered by DP setpoint — cake model (α {alpha_src})"

    # ── ΔP vs solid loading curve (0 → M_max, 5 points) ──────────────────
    dp_curve = []
    for frac in [0.0, 0.25, 0.50, 0.75, 1.0]:
        m_pt          = solid_loading_kg_m2 * frac
        dp_cake_bar   = (alpha_used * mu * lv_ms * m_pt) / 1e5
        dp_total_bar  = dp_clean_bar + dp_cake_bar
        dp_curve.append({
            "M (kg/m²)":      round(m_pt,        3),
            "ΔP cake (bar)":  round(dp_cake_bar,  4),
            "ΔP total (bar)": round(dp_total_bar, 4),
        })

    # ── Per-TSS cycle durations ────────────────────────────────────────────
    tss_rows = []
    for tss in tss_mg_l_list:
        tss_eff    = tss * _cap
        acc_rate   = (tss_eff / 1000.0) * lv_mh    # kg/(m²·h)
        duration_h = m_trigger / acc_rate if acc_rate > 0 else float("inf")
        tss_rows.append({
            "TSS (mg/L)":              tss,
            "TSS deposited (mg/L)":    round(tss_eff, 3),
            "Acc. rate (kg/m²·h)":     round(acc_rate,   4),
            "Load @ trigger (kg/m²)":  round(m_trigger,  3),
            "Cycle duration (h)":      round(duration_h, 2),
        })

    return {
        "dp_clean_bar":              dp_clean_bar,
        "dp_trigger_bar":            dp_trigger_bar,
        "dp_avail_bar":              round(dp_avail_pa / 1e5, 5),
        "alpha_used_m_kg":           alpha_used,
        "alpha_calibrated_m_kg":     alpha_cal,
        "alpha_source":              alpha_src,
        "lv_m_h":                    lv_mh,
        "mu_pa_s":                   round(mu, 6),
        "loading_at_trigger_kg_m2":  round(m_trigger, 4),
        "solid_loading_kg_m2":       solid_loading_kg_m2,
        "note":                      note,
        "dp_curve":                  dp_curve,
        "tss_results":               tss_rows,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 3c. COLLECTOR HEIGHT CHECK — media loss guard
# ═══════════════════════════════════════════════════════════════════════════

def collector_check(
    layers: list,
    nozzle_plate_h_m: float,
    collector_h_m: float,
    bw_velocity_m_h: float,
    water_temp_c: float = 27.0,
    rho_water: float    = _RHO_WATER_DEF,
) -> dict:
    """
    Check whether the expanded media bed reaches the BW outlet collector.

    The BW outlet collector is positioned at a fixed height from the vessel
    bottom. If the top of the expanded bed reaches or exceeds the collector
    height, media will be carried out — a critical operational failure.

    The maximum safe BW velocity is found by binary search: the highest
    u_bw at which the expanded top-of-bed stays below the collector with
    at least 100mm freeboard.

    Parameters
    ----------
    layers          : Media layer list (same format as bed_expansion)
    nozzle_plate_h_m: Height of nozzle plate from vessel bottom, m
    collector_h_m   : Height of BW outlet collector from vessel bottom, m
    bw_velocity_m_h : Proposed BW velocity, m/h
    water_temp_c    : BW water temperature, °C
    rho_water       : BW water density, kg/m³

    Returns
    -------
    dict:
        expanded_top_m        top of expanded bed from vessel bottom, m
        collector_h_m         collector height, m
        freeboard_m           collector_h - expanded_top, m
        freeboard_pct         freeboard as % of settled bed depth
        media_loss_risk       True if expanded top >= collector
        max_safe_bw_m_h       maximum BW velocity with ≥100mm freeboard
        proposed_bw_m_h       the velocity that was checked
        status                "OK", "WARNING", or "CRITICAL"
        per_layer             expansion results per layer
    """
    # Compute expansion at proposed velocity
    exp = bed_expansion(layers, bw_velocity_m_h, water_temp_c, rho_water)

    total_settled  = exp["total_settled_m"]
    total_expanded = exp["total_expanded_m"]

    # Top of expanded bed = nozzle plate + expanded media
    expanded_top = nozzle_plate_h_m + total_expanded

    freeboard   = collector_h_m - expanded_top
    freq_pct    = freeboard / total_settled * 100 if total_settled > 0 else 0

    media_loss  = expanded_top >= collector_h_m
    warning     = freeboard < 0.15  # < 150mm freeboard

    # Binary search for max safe BW velocity (≥ 100mm freeboard)
    lo, hi = 0.0, 200.0
    for _ in range(40):
        mid = (lo + hi) / 2
        exp_test = bed_expansion(layers, mid, water_temp_c, rho_water)
        top_test = nozzle_plate_h_m + exp_test["total_expanded_m"]
        if collector_h_m - top_test >= 0.10:
            lo = mid
        else:
            hi = mid
    max_safe_bw = round(lo, 1)

    if media_loss:
        status = "CRITICAL — media loss risk"
    elif warning:
        status = "WARNING — freeboard < 150 mm"
    else:
        status = "OK"

    return {
        "nozzle_plate_h_m":   round(nozzle_plate_h_m, 3),
        "collector_h_m":      round(collector_h_m,     3),
        "settled_top_m":      round(nozzle_plate_h_m + total_settled,  3),
        "expanded_top_m":     round(expanded_top,      3),
        "freeboard_m":        round(freeboard,         3),
        "freeboard_pct":      round(freq_pct,          1),
        "media_loss_risk":    media_loss,
        "max_safe_bw_m_h":    max_safe_bw,
        "proposed_bw_m_h":    bw_velocity_m_h,
        "status":             status,
        "per_layer":          exp["layers"],
        "total_settled_m":    round(total_settled,     3),
        "total_expanded_m":   round(total_expanded,    3),
        "total_expansion_pct": exp["total_expansion_pct"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# 4. BACKWASH SEQUENCE  —  waste volumes & TSS
# ═══════════════════════════════════════════════════════════════════════════

# Each tuple: (step_name, dur_low_min, dur_avg_min, dur_high_min,
#              water_rate_m_h, source_label)
# water_rate_m_h = 0 for air-only steps.
DEFAULT_BW_SEQUENCE = [
    ("Partial drainage",      10, 10, 10,  5.0, "Filter drainage"),
    ("Air scour only",         1,  2,  3,  0.0, "Air"),
    ("Air + low water rate",   3,  5,  7, 12.5, "Air + brine"),
    ("High water rate",       10, 10, 10, 30.0, "Brine"),
    ("Rinse — raw water",     20, 20, 20, 12.5, "Raw water"),
]


def bw_sequence(
    filter_area_m2: float,
    tss_scenarios: list         = None,
    sequence: list              = None,
    n_filters_total: int        = 16,
    bw_per_day_per_filter: int  = 1,
    rho_water: float            = _RHO_WATER_DEF,
) -> dict:
    """
    BW step schedule: per-step volumes, daily plant waste, and TSS scenarios.

    Volume per step = water_rate_m_h × filter_area × duration_h.
    Air-only steps (water_rate = 0) contribute no water volume.
    Rinse volume is tracked separately (returned to process, not wasted).
    """
    if tss_scenarios is None:
        tss_scenarios = [5.0, 10.0, 20.0]
    if sequence is None:
        sequence = DEFAULT_BW_SEQUENCE

    tss_low, tss_avg, tss_high = tss_scenarios

    steps = []
    total_low = total_avg = total_high = 0.0
    rinse_vol = 0.0
    dur_total = 0

    for name, dl, da, dh, rate, source in sequence:
        q_m3h  = rate * filter_area_m2          # m³/h  (0 for air-only)
        vl = q_m3h * dl / 60
        va = q_m3h * da / 60
        vh = q_m3h * dh / 60

        total_low  += vl
        total_avg  += va
        total_high += vh
        dur_total  += da

        if "Rinse" in name:
            rinse_vol = va

        steps.append({
            "Step":                 name,
            "Dur low (min)":        dl,
            "Dur avg (min)":        da,
            "Dur high (min)":       dh,
            "Water rate (m/h)":     rate,
            "Source":               source,
            "Flow (m³/h)":          round(q_m3h, 1),
            "Vol low (m³)":         round(vl,    1),
            "Vol avg (m³)":         round(va,    1),
            "Vol high (m³)":        round(vh,    1),
        })

    waste_avg   = total_avg - rinse_vol
    waste_daily = waste_avg * n_filters_total * bw_per_day_per_filter
    rinse_daily = rinse_vol * n_filters_total * bw_per_day_per_filter

    # TSS of waste stream: approximate — show feed TSS scenarios
    # Detailed mass balance requires filtration run time (handled in app)
    # ── TSS mass balance ──────────────────────────────────────────────────
    # M_solids per filter per cycle = TSS × Q_filter × run_time
    # run_time = 24 / bw_per_day  (hours between BW cycles)
    # Waste TSS concentration = M_solids / waste_vol
    run_time_h = 24.0 / bw_per_day_per_filter if bw_per_day_per_filter > 0 else 24.0

    def tss_balance(tss_mg_l, q_filter_m3h):
        """Solids captured (kg) and waste concentration (mg/L) per filter per cycle."""
        if q_filter_m3h <= 0 or waste_avg <= 0:
            return 0.0, 0.0
        m_solids = tss_mg_l * q_filter_m3h * run_time_h / 1000.0  # kg
        waste_tss = (m_solids * 1e3) / waste_avg if waste_avg > 0 else 0.0
        return round(m_solids, 1), round(waste_tss, 0)

    # Placeholder — q_filter passed from app; store formula, fill in app
    # Store run_time for the app to use
    return {
        "steps":                  steps,
        "dur_total_avg_min":      dur_total,
        "run_time_h":             round(run_time_h, 2),
        # Per filter per cycle
        "total_vol_low_m3":       round(total_low,   1),
        "total_vol_avg_m3":       round(total_avg,   1),
        "total_vol_high_m3":      round(total_high,  1),
        "waste_vol_avg_m3":       round(waste_avg,   1),
        "rinse_vol_avg_m3":       round(rinse_vol,   1),
        # Plant daily
        "waste_vol_daily_m3":     round(waste_daily, 1),
        "rinse_vol_daily_m3":     round(rinse_daily, 1),
        "n_filters_total":        n_filters_total,
        "bw_per_day_per_filter":  bw_per_day_per_filter,
        # TSS scenarios
        "tss_low_mg_l":           tss_low,
        "tss_avg_mg_l":           tss_avg,
        "tss_high_mg_l":          tss_high,
        "filter_area_m2":         round(filter_area_m2, 3),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 5. BW SYSTEM EQUIPMENT DATA SHEET
# ═══════════════════════════════════════════════════════════════════════════

def bw_system_sizing(
    q_bw_design_m3h: float,
    bw_head_mwc: float,
    bw_pump_eta: float,
    motor_eta: float,
    q_air_design_m3h: float,
    vessel_pressure_bar: float,
    filter_id_m: float,
    blower_inlet_temp_c: float,
    blower_eta: float,
    bw_vol_per_cycle_m3: float,
    n_bw_systems: int,
    tank_sf: float = 1.5,
    rho_bw_kg_m3: float = 1025.0,
    *,
    blower_air_delta_p_bar: float = 0.15,
    q_air_design_nm3h: float | None = None,
) -> dict:
    """
    BW pump, air blower, and BW storage tank sizing.

    Pump
    ----
        P_shaft = rho × g × Q × H / eta_pump
        P_motor = P_shaft / eta_motor

    Blower (adiabatic compression, gamma = 1.4)
    -------------------------------------------
        **Discharge pressure** is *not* the liquid filtration operating gauge on the
        vessel nameplate. The air scour blower must overcome **hydrostatic head** of
        the water column above the sparger (≈ ID/2 here) plus **air-side** losses
        (distribution, piping, sparger) — typically **~0.15–0.35 bar** combined with
        submergence for MMF; positive-displacement lobes are rarely economical above
        **~0.9 bar** differential.

        P2_abs       = P_atm + dp_submergence + blower_air_delta_p_bar * 1e5
        Q1           = mass flow from **Nm³/h** (0 °C, 101 325 Pa) expanded to suction P1, T1
        Ideal power  = gamma/(gamma-1) × P1 × Q1 × [(P2/P1)^((gamma-1)/gamma) − 1]
        P_shaft      = ideal / blower_eta
        P_motor      = P_shaft / motor_eta

        ``vessel_pressure_bar`` is retained for **Nm³/h conversion** elsewhere (in-situ
        vs normal air volume); it is **not** added to P2 for thermodynamic sizing.

    Tank
    ----
        V_cycle  = bw_vol_per_cycle × n_simultaneous_systems × safety_factor
        V_10min  = Q_bw_design / 6   (10 min at design flow)
        V_tank   = max(V_cycle, V_10min)
    """
    g = GRAVITY

    # ── BW pump ──────────────────────────────────────────────────────────────
    q_bw_m3s       = q_bw_design_m3h / 3600.0
    p_pump_ideal_kw = rho_bw_kg_m3 * g * q_bw_m3s * bw_head_mwc / 1000.0
    p_pump_shaft_kw = p_pump_ideal_kw / max(bw_pump_eta, 0.01)
    p_pump_motor_kw = p_pump_shaft_kw / max(motor_eta,   0.01)

    # ── Air blower ────────────────────────────────────────────────────────────
    gamma       = 1.4
    exponent    = (gamma - 1.0) / gamma   # 0.2857
    P1_pa       = 101_325.0               # atmospheric (sea level)
    T1_K        = blower_inlet_temp_c + 273.15
    h_sub       = filter_id_m / 2.0       # submergence ≈ vessel radius
    dp_sub_pa   = rho_bw_kg_m3 * g * h_sub
    dp_airside_pa = max(0.0, float(blower_air_delta_p_bar)) * 1e5
    P2_pa       = P1_pa + dp_sub_pa + dp_airside_pa
    dp_total_bar = (P2_pa - P1_pa) / 1e5
    blower_dp_warning: str | None = None
    if dp_total_bar > 0.9 + 1e-6:
        blower_dp_warning = (
            f"Total blower ΔP is **{dp_total_bar:.2f} bar** — above a typical lobe PD "
            "practical envelope (~**0.9 bar**). Confirm technology (multistage centrifugal / turbo) "
            "or reduce **air-side ΔP** / submergence assumption."
        )

    rho_air_kg_m3 = P1_pa / (287.0 * T1_K)         # ideal gas, dry air
    if q_air_design_nm3h is not None and float(q_air_design_nm3h) > 0.0:
        q_air_m3s = nm3h_to_actual_m3s_at_pt(float(q_air_design_nm3h), P1_pa, T1_K)
    else:
        q_air_m3s = max(float(q_air_design_m3h), 0.0) / 3600.0

    p_ideal_kw  = (
        (gamma / (gamma - 1.0))
        * P1_pa * q_air_m3s
        * ((P2_pa / P1_pa) ** exponent - 1.0)
        / 1000.0
    )
    p_blower_shaft_kw = p_ideal_kw / max(blower_eta, 0.01)
    p_blower_motor_kw = p_blower_shaft_kw / max(motor_eta, 0.01)

    # ── BW tank ───────────────────────────────────────────────────────────────
    v_cycle_m3  = bw_vol_per_cycle_m3 * n_bw_systems * tank_sf
    v_10min_m3  = q_bw_design_m3h / 6.0     # 10 min at design flow
    v_tank_m3   = max(v_cycle_m3, v_10min_m3)
    tank_governs = "cycle-based" if v_cycle_m3 >= v_10min_m3 else "10-min rule"

    return {
        # Pump
        "q_bw_design_m3h":       round(q_bw_design_m3h,   1),
        "bw_head_mwc":           round(bw_head_mwc,        1),
        "bw_head_bar":           round(bw_head_mwc / 10.2, 3),
        "p_pump_ideal_kw":       round(p_pump_ideal_kw,    1),
        "p_pump_shaft_kw":       round(p_pump_shaft_kw,    1),
        "p_pump_motor_kw":       round(p_pump_motor_kw,    1),
        "bw_pump_eta":           bw_pump_eta,
        # Blower
        "q_air_design_m3h":      round(q_air_design_m3h,   1),
        "q_air_design_m3min":    round(q_air_design_m3h / 60.0, 2),
        "h_submergence_m":       round(h_sub,               2),
        "dp_sub_bar":            round(dp_sub_pa / 1e5,     3),
        "blower_air_delta_p_bar": round(max(0.0, float(blower_air_delta_p_bar)), 3),
        "dp_airside_bar":        round(dp_airside_pa / 1e5, 3),
        "vessel_pressure_bar":   vessel_pressure_bar,
        "P1_pa":                 round(P1_pa,               0),
        "P2_pa":                 round(P2_pa,               0),
        "pressure_ratio":        round(P2_pa / P1_pa,       3),
        "dp_total_bar":          round(dp_total_bar,        3),
        "blower_dp_warning":     blower_dp_warning,
        "rho_air_kg_m3":         round(rho_air_kg_m3,       4),
        "p_blower_ideal_kw":     round(p_ideal_kw,          1),
        "p_blower_shaft_kw":     round(p_blower_shaft_kw,   1),
        "p_blower_motor_kw":     round(p_blower_motor_kw,   1),
        "blower_eta":            blower_eta,
        # Tank
        "bw_vol_per_cycle_m3":   round(bw_vol_per_cycle_m3, 1),
        "n_bw_systems":          n_bw_systems,
        "tank_sf":               tank_sf,
        "v_cycle_m3":            round(v_cycle_m3,           0),
        "v_10min_m3":            round(v_10min_m3,           0),
        "v_tank_m3":             round(v_tank_m3,            0),
        "tank_governs":          tank_governs,
    }