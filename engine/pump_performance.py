"""
engine/pump_performance.py
──────────────────────────
Pump / blower hydraulic power, BW philosophy comparison, and budgetary equipment
costing for AQUASIGHT™ MMF — feeds the **Pump Performance, Power & Costing** tab
and future economics hooks.

Scope: dry-installed end-suction / vertical in-line style pumps only (no
submersible / wet-pit turbine models).
"""
from __future__ import annotations

import math
from typing import Any

GRAVITY = 9.80665


def _pump_shaft_power_kw(
    q_m3h: float,
    head_mwc: float,
    rho_kg_m3: float,
    eta_pump: float,
) -> float:
    """Hydraulic shaft power [kW] (η_pump only — motor applied separately)."""
    if q_m3h <= 0 or head_mwc <= 0 or eta_pump <= 0:
        return 0.0
    q_m3s = float(q_m3h) / 3600.0
    return q_m3s * float(rho_kg_m3) * GRAVITY * float(head_mwc) / (float(eta_pump) * 1000.0)


def motor_electrical_kw(shaft_kw: float, motor_eta: float) -> float:
    if shaft_kw <= 0 or motor_eta <= 0:
        return 0.0
    return float(shaft_kw) / float(motor_eta)


def estimate_pump_hydraulic_efficiency(q_m3h: float, head_mwc: float) -> float:
    """
    Order-of-magnitude η_pump for end-suction centrifugal (not a catalogue curve).
    Bounded for UI / energy sanity checks.
    """
    q = max(float(q_m3h), 1e-6)
    h = max(float(head_mwc), 0.5)
    # Larger pumps + moderate head → slightly better η
    base = 0.62 + 0.06 * math.log10(q + 10.0) + 0.008 * math.log10(h + 1.0)
    return max(0.50, min(0.82, base))


def snap_iec_motor_kw(p_run_kw: float, *, service_factor: float = 1.15) -> float:
    """Next standard IEC motor frame (kW) at or above p_run × service_factor."""
    target = max(0.37, float(p_run_kw) * float(service_factor))
    std = (
        0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3.0, 4.0, 5.5, 7.5, 11.0, 15.0, 18.5, 22.0,
        30.0, 37.0, 45.0, 55.0, 75.0, 90.0, 110.0, 132.0, 160.0, 200.0, 250.0, 315.0,
        355.0, 400.0, 450.0, 500.0, 560.0, 630.0,
    )
    for s in std:
        if s >= target:
            return float(s)
    return float(std[-1])


def feed_bank_motor_electrical_kw(
    q_stream_m3h: float,
    n_parallel_pumps: int,
    head_mwc: float,
    rho_kg_m3: float,
    motor_eta: float,
    pump_eta_user_cap: float,
) -> float:
    """
    Electrical kW for **n** identical duty pumps in parallel on one stream header
    (each pump takes Q_stream / n at the same differential head).
    """
    n = max(1, int(n_parallel_pumps))
    q_stream = max(0.0, float(q_stream_m3h))
    q_each = q_stream / float(n)
    h = max(0.0, float(head_mwc))
    if q_each <= 0 or h <= 0:
        return 0.0
    eta_model = estimate_pump_hydraulic_efficiency(q_each, h)
    eta_p = max(0.50, min(float(pump_eta_user_cap), eta_model))
    p_sh_each = _pump_shaft_power_kw(q_each, h, rho_kg_m3, eta_p)
    return motor_electrical_kw(float(n) * p_sh_each, motor_eta)


def plant_filtration_motor_kw_parallel_feed(
    *,
    total_flow_m3h: float,
    streams: int,
    n_feed_pumps_parallel_per_stream: int,
    head_dirty_mwc: float,
    head_clean_mwc: float,
    rho_feed_kg_m3: float,
    motor_eta: float,
    pump_eta_user_cap: float,
) -> dict[str, float]:
    """Total plant filtration motor kW with **parallel feed pumps per stream**."""
    st = max(1, int(streams))
    q_stream = float(total_flow_m3h) / float(st)
    p_d = feed_bank_motor_electrical_kw(
        q_stream, n_feed_pumps_parallel_per_stream, head_dirty_mwc,
        rho_feed_kg_m3, motor_eta, pump_eta_user_cap,
    )
    p_c = feed_bank_motor_electrical_kw(
        q_stream, n_feed_pumps_parallel_per_stream, head_clean_mwc,
        rho_feed_kg_m3, motor_eta, pump_eta_user_cap,
    )
    p_avg = (p_d + p_c) / 2.0
    p_plant = float(st) * p_avg
    return {
        "p_filtration_plant_dirty_kw": round(float(st) * p_d, 3),
        "p_filtration_plant_clean_kw": round(float(st) * p_c, 3),
        "p_filtration_plant_avg_kw": round(p_plant, 3),
    }


def feed_bank_iec_motor_kw_each(
    *,
    q_stream_m3h: float,
    n_parallel_pumps: int,
    head_mwc: float,
    rho_kg_m3: float,
    motor_eta: float,
    pump_eta_user_cap: float,
) -> float:
    """IEC motor frame (kW) for **one** pump in a parallel feed bank."""
    n = max(1, int(n_parallel_pumps))
    q_stream = max(0.0, float(q_stream_m3h))
    q_each = q_stream / float(n)
    h = max(0.0, float(head_mwc))
    if q_each <= 0 or h <= 0:
        return 0.37
    eta_model = estimate_pump_hydraulic_efficiency(q_each, h)
    eta_p = max(0.50, min(float(pump_eta_user_cap), eta_model))
    p_sh = _pump_shaft_power_kw(q_each, h, rho_kg_m3, eta_p)
    p_e = motor_electrical_kw(p_sh, motor_eta)
    return snap_iec_motor_kw(p_e)


def economics_energy_from_pump_configuration(
    energy: dict[str, Any],
    pump_perf: dict[str, Any],
    hyd_prof: dict[str, Any],
    *,
    total_flow_m3h: float,
    streams: int,
    n_feed_pumps_parallel_per_stream: int,
    pump_eta_user: float,
    motor_eta_feed: float,
    rho_feed: float,
    bw_philosophy: str,
    blower_operating_mode: str,
    n_blowers_running: int,
) -> dict[str, Any]:
    """
    Rebuild annual kWh splits for OPEX / CO₂ when the user configures the **Pumps & power** tab.

    Filtration: scales legacy ``e_filt_kwh_yr`` by the ratio of **parallel feed bank** motor kW
    (per stream × streams) vs the implied legacy plant filtration kW (e_filt / hours).

    BW pump: selects DOL or VFD annual pump kWh from ``pump_perf['philosophy']``.

    Blower: default unchanged (single duty machine). ``twin_iso`` applies a centrifugal-style
    part-load factor for two machines each at ~50 % air flow (order-of-magnitude only).
    """
    op_h = max(1e-9, float(energy.get("op_hours_per_year") or 8400.0))
    e_f0 = float(energy.get("e_filt_kwh_yr") or 0.0)
    p_legacy_total = e_f0 / op_h

    hd = float(hyd_prof["dirty"]["total_mwc"])
    hc = float(hyd_prof["clean"]["total_mwc"])
    fp = plant_filtration_motor_kw_parallel_feed(
        total_flow_m3h=total_flow_m3h,
        streams=streams,
        n_feed_pumps_parallel_per_stream=max(1, int(n_feed_pumps_parallel_per_stream)),
        head_dirty_mwc=hd,
        head_clean_mwc=hc,
        rho_feed_kg_m3=float(rho_feed),
        motor_eta=float(motor_eta_feed),
        pump_eta_user_cap=float(pump_eta_user),
    )
    p_new_total = float(fp["p_filtration_plant_avg_kw"])
    r_f = p_new_total / max(p_legacy_total, 1e-9)
    e_f = round(e_f0 * r_f, 0)

    phil = pump_perf.get("philosophy") or {}
    if str(bw_philosophy).upper() == "VFD":
        e_b = float(phil.get("VFD", {}).get("kwh_bw_pump_yr") or energy.get("e_bw_pump_kwh_yr") or 0.0)
    else:
        e_b = float(phil.get("DOL", {}).get("kwh_bw_pump_yr") or energy.get("e_bw_pump_kwh_yr") or 0.0)

    e_l0 = float(energy.get("e_blower_kwh_yr") or 0.0)
    nbr = max(1, int(n_blowers_running))
    mode = str(blower_operating_mode or "single_duty").lower()
    if mode == "twin_50_iso" and nbr >= 2:
        # Two identical centrifugal blowers each at ~50 % flow → ~2×(½)³ = 0.25 of single at 100 %
        twin_factor = float(nbr) * ((1.0 / float(nbr)) ** 3)
        e_l = round(e_l0 * max(0.35, min(1.0, twin_factor)), 0)
    else:
        e_l = round(e_l0, 0)

    return {
        "energy_kwh_filtration_yr": e_f,
        "energy_kwh_bw_pump_yr": round(e_b, 0),
        "energy_kwh_blower_yr": e_l,
        "energy_kwh_yr": round(e_f + e_b + e_l, 0),
        "filtration_kw_scale": round(r_f, 4),
        "p_filtration_plant_avg_kw": fp["p_filtration_plant_avg_kw"],
        "bw_philosophy_used": str(bw_philosophy).upper(),
        "blower_mode_used": mode,
    }


def _classify_bw_step(
    water_rate_m_h: float,
    source: str,
    bw_velocity_setpoint_m_h: float,
) -> str:
    r = float(water_rate_m_h or 0.0)
    src = str(source or "")
    if r <= 1e-9:
        return "air_only" if "Air" in src else "idle"
    thr = max(8.0, 0.85 * float(bw_velocity_setpoint_m_h))
    if r >= thr - 1e-6:
        return "high_water"
    return "low_water"


def _dol_pumps_running(q_step_m3h: float, q_design_m3h: float) -> int:
    """2 × 50 % duty philosophy: need two pumps in parallel above half design."""
    if q_step_m3h <= 1e-9:
        return 0
    qd = max(float(q_design_m3h), 1e-6)
    if q_step_m3h <= 0.52 * qd + 1e-6:
        return 1
    return 2


def _affinity_power_ratio(q_part: float, q_rated: float) -> float:
    if q_rated <= 0:
        return 0.0
    r = max(0.0, min(1.15, float(q_part) / float(q_rated)))
    return r**3


def sequence_stage_table(
    steps: list[dict] | None,
    *,
    filter_area_m2: float,
    bw_velocity_m_h: float,
    q_bw_design_m3h: float,
    bw_head_mwc: float,
    rho_bw_kg_m3: float,
    eta_pump_bw: float,
    eta_motor_bw: float,
    p_blower_motor_kw: float,
) -> list[dict]:
    """Per-step hydraulic classification and instantaneous BW pump + blower power."""
    out: list[dict] = []
    if not steps or filter_area_m2 <= 0:
        return out
    qd = max(float(q_bw_design_m3h), 1e-6)
    for s in steps:
        try:
            da = float(s.get("Dur avg (min)", 0) or 0)
        except (TypeError, ValueError):
            da = 0.0
        try:
            rate = float(s.get("Water rate (m/h)", 0) or 0)
        except (TypeError, ValueError):
            rate = 0.0
        src = str(s.get("Source", "") or "")
        q_step = rate * float(filter_area_m2)
        cat = _classify_bw_step(rate, src, bw_velocity_m_h)
        n_p = _dol_pumps_running(q_step, qd)
        q_each = q_step / max(1, n_p) if n_p else 0.0
        p_pump = 0.0
        if n_p > 0 and q_step > 0:
            p_each = _pump_shaft_power_kw(
                q_each, bw_head_mwc, rho_bw_kg_m3, eta_pump_bw,
            )
            p_pump = motor_electrical_kw(n_p * p_each, eta_motor_bw)
        p_blow = float(p_blower_motor_kw) if ("Air" in src) else 0.0
        out.append({
            "Step": s.get("Step", "—"),
            "Category": cat,
            "t_min": round(da, 2),
            "Q_step (m³/h)": round(q_step, 2),
            "DOL pumps running": n_p,
            "P_BW pump (kW)": round(p_pump, 2),
            "P_Blower (kW)": round(p_blow, 2),
            "P_total (kW)": round(p_pump + p_blow, 2),
        })
    return out


def _cycle_energy_from_steps(
    steps: list[dict],
    *,
    filter_area_m2: float,
    philosophy: str,
    q_bw_design_m3h: float,
    bw_head_mwc: float,
    rho_bw: float,
    eta_p: float,
    eta_m: float,
    p_blower_motor_kw: float,
) -> tuple[float, float, float]:
    """Cleaner path: integrate power × time without fragile stage join."""
    e_p = e_b = 0.0
    qd = max(float(q_bw_design_m3h), 1e-6)
    p_rated = motor_electrical_kw(
        _pump_shaft_power_kw(qd, bw_head_mwc, rho_bw, eta_p),
        eta_m,
    )
    for s in steps:
        try:
            da = float(s.get("Dur avg (min)", 0) or 0)
        except (TypeError, ValueError):
            da = 0.0
        th = da / 60.0
        try:
            rate = float(s.get("Water rate (m/h)", 0) or 0)
        except (TypeError, ValueError):
            rate = 0.0
        src = str(s.get("Source", "") or "")
        q_step = rate * float(filter_area_m2)
        if philosophy.upper() == "DOL":
            n_p = _dol_pumps_running(q_step, qd)
            q_each = q_step / max(1, n_p) if n_p else 0.0
            p_sh = _pump_shaft_power_kw(q_each, bw_head_mwc, rho_bw, eta_p) * max(0, n_p)
            e_p += motor_electrical_kw(p_sh, eta_m) * th
        else:
            if q_step > 0:
                e_p += p_rated * _affinity_power_ratio(q_step, qd) * th
        if "Air" in src:
            e_b += float(p_blower_motor_kw) * th
    return round(e_p, 3), round(e_b, 3), round(e_p + e_b, 3)


def _budget_pump_skid_usd(
    rated_motor_kw: float,
    *,
    material_mult: float,
    standard_mult: float,
    seal_mult: float,
    vfd_mult: float,
    vertical_mult: float,
) -> dict[str, float]:
    """±25 % budgetary factors — equipment-only, not installed project CAPEX."""
    p = max(0.75, float(rated_motor_kw))
    pump_base = 650.0 * (p**0.82)
    motor_base = 110.0 * (p**0.88)
    vfd_base = 140.0 * (p**0.75) if vfd_mult > 1.01 else 0.0
    skid = 4500.0 + 180.0 * p
    pump_cost = pump_base * material_mult * standard_mult * seal_mult * vertical_mult
    motor_cost = motor_base * material_mult * 0.95
    vfd_cost = vfd_base * vfd_mult if vfd_mult > 1.01 else 0.0
    total = pump_cost + motor_cost + vfd_cost + skid
    return {
        "pump_usd": round(pump_cost, 0),
        "motor_usd": round(motor_cost, 0),
        "vfd_usd": round(vfd_cost, 0),
        "skid_base_usd": round(skid, 0),
        "total_equipment_usd": round(total, 0),
    }


def _philosophy_capex_bundle(
    *,
    bw_motor_iec_kw_dol_train: float,
    bw_motor_iec_kw_vfd_train: float,
    blower_motor_kw: float,
    feed_motor_kw_each: float,
    n_feed_pumps_total: int,
    n_bw_dol_trains: int,
    n_bw_vfd_trains: int,
    n_blower_units: int,
    feed_complex_mult: float,
    feed_vfd_budget_mult: float,
    bw_complex_mult: float,
    bw_vfd_train_budget_mult: float,
) -> dict[str, Any]:
    """Budgetary pump + blower + feed skid (USD) with explicit installed quantities."""
    dol_p = _budget_pump_skid_usd(
        bw_motor_iec_kw_dol_train,
        material_mult=bw_complex_mult,
        standard_mult=1.0,
        seal_mult=1.0,
        vfd_mult=1.0,
        vertical_mult=1.0,
    )
    dol_bw = dol_p["total_equipment_usd"] * max(1, int(n_bw_dol_trains))
    vfd_p = _budget_pump_skid_usd(
        bw_motor_iec_kw_vfd_train,
        material_mult=bw_complex_mult,
        standard_mult=1.0,
        seal_mult=1.0,
        vfd_mult=bw_vfd_train_budget_mult,
        vertical_mult=1.0,
    )
    vfd_bw = vfd_p["total_equipment_usd"] * max(1, int(n_bw_vfd_trains))
    blow = _budget_pump_skid_usd(
        blower_motor_kw,
        material_mult=1.0,
        standard_mult=1.0,
        seal_mult=1.0,
        vfd_mult=1.0,
        vertical_mult=1.0,
    )
    blow_total = blow["total_equipment_usd"] * max(1, int(n_blower_units))
    feed = _budget_pump_skid_usd(
        feed_motor_kw_each,
        material_mult=feed_complex_mult,
        standard_mult=1.0,
        seal_mult=1.0,
        vfd_mult=feed_vfd_budget_mult,
        vertical_mult=1.0,
    )
    feed_total = feed["total_equipment_usd"] * max(1, int(n_feed_pumps_total))
    return {
        "dol_bw_pump_train_usd": dol_p["total_equipment_usd"],
        "dol_bw_total_usd": round(dol_bw, 0),
        "vfd_bw_pump_train_usd": vfd_p["total_equipment_usd"],
        "vfd_bw_total_usd": round(vfd_bw, 0),
        "blower_package_unit_usd": blow["total_equipment_usd"],
        "blower_package_total_usd": round(blow_total, 0),
        "feed_pump_unit_usd": feed["total_equipment_usd"],
        "feed_pumps_all_usd": round(feed_total, 0),
        "dol_grand_total_usd": round(dol_bw + blow_total + feed_total, 0),
        "vfd_grand_total_usd": round(vfd_bw + blow_total + feed_total, 0),
    }


def apply_cost_multipliers(
    *,
    material: str,
    pump_standard: str,
    seal: str,
    use_vfd: bool,
    vertical: bool,
) -> dict[str, float]:
    mats = {
        "Cast iron": 1.0,
        "Carbon steel": 1.12,
        "SS316": 1.55,
        "Duplex": 2.05,
        "Super duplex": 2.65,
    }
    stds = {
        "Commercial": 1.0,
        "ISO 5199": 1.22,
        "API 610 OH2": 1.48,
    }
    seals = {
        "Packing": 0.92,
        "Single mechanical seal": 1.0,
        "Dual seal / API Plan 53": 1.38,
    }
    return {
        "material": mats.get(material, 1.0),
        "standard": stds.get(pump_standard, 1.0),
        "seal": seals.get(seal, 1.0),
        "vfd": 1.35 if use_vfd else 1.0,
        "vertical": 1.10 if vertical else 1.0,
    }


def build_engineering_notes(
    *,
    total_flow: float,
    bw_cycles_day: float,
    elec_tariff: float,
    savings_kwh: float,
    philosophy_prefer: str,
) -> list[str]:
    notes = []
    if total_flow < 3000:
        notes.append(
            "Smaller hydraulic footprint — fixed-speed DOL backwash trains are often "
            "favoured for CAPEX simplicity and operator familiarity."
        )
    if total_flow > 15000 and bw_cycles_day >= 4:
        notes.append(
            "High backwash frequency increases fractional BW energy — VFD staging merits "
            "lifecycle review against marginal grid / PPA cost."
        )
    if savings_kwh > 5000 and elec_tariff > 0.08:
        notes.append(
            f"At ~{savings_kwh:,.0f} kWh/yr avoided on BW pumps alone, VFD philosophy gains "
            f"visibility on OPEX (~USD {savings_kwh * elec_tariff:,.0f}/yr @ current tariff)."
        )
    notes.append(
        f"Screening preference this run: **{philosophy_prefer}** — confirm with electrical "
        "harmonics study, cable sizing, and vendor curve verification in detailed design."
    )
    return notes


def build_pump_performance_package(
    *,
    inputs: dict[str, Any],
    hyd_prof: dict[str, Any],
    energy: dict[str, Any],
    bw_hyd: dict[str, Any],
    bw_seq: dict[str, Any],
    bw_sizing: dict[str, Any],
    q_per_filter: float,
    avg_area: float,
    total_flow: float,
    streams: int,
    n_filters: int,
    hydraulic_assist: int,
    rho_feed: float,
    rho_bw: float,
    pump_eta: float,
    motor_eta: float,
    bw_pump_eta: float,
    bw_head_mwc: float,
    bw_velocity: float,
    bw_cycles_day: float,
) -> dict[str, Any]:
    """
    Assemble auto-imported hydraulic / energy figures plus philosophy comparison.
    """
    steps = list(bw_seq.get("steps") or [])
    q_bw_design = float(bw_hyd.get("q_bw_design_m3h") or 0.0)
    p_blower_motor = float(
        bw_sizing.get("p_blower_motor_kw") or bw_hyd.get("p_blower_est_kw") or 0.0
    )

    # Feed: one duty pump per stream (typical UF/MMF headering)
    n_duty_per_stream = max(1, int(n_filters) - int(hydraulic_assist))
    q_feed_pump = float(total_flow) / max(1, int(streams))
    h_dirty = float(hyd_prof["dirty"]["total_mwc"])
    h_clean = float(hyd_prof["clean"]["total_mwc"])
    h_design = h_dirty
    eta_p_est = estimate_pump_hydraulic_efficiency(q_feed_pump, h_design)
    p_shaft_feed = _pump_shaft_power_kw(q_feed_pump, h_design, rho_feed, eta_p_est)
    p_elec_feed_dirty = motor_electrical_kw(p_shaft_feed, motor_eta)
    p_shaft_clean = _pump_shaft_power_kw(q_feed_pump, h_clean, rho_feed, eta_p_est)
    p_elec_feed_clean = motor_electrical_kw(p_shaft_clean, motor_eta)
    feed_motor_snap = snap_iec_motor_kw(p_elec_feed_dirty)

    # BW rated (design) motor electrical
    p_bw_shaft = _pump_shaft_power_kw(q_bw_design, bw_head_mwc, rho_bw, bw_pump_eta)
    p_bw_elec_rated = motor_electrical_kw(p_bw_shaft, motor_eta)
    p_half_shaft = _pump_shaft_power_kw(0.5 * q_bw_design, bw_head_mwc, rho_bw, bw_pump_eta)
    p_half_elec = motor_electrical_kw(p_half_shaft, motor_eta)
    bw_motor_snap_dol = snap_iec_motor_kw(p_half_elec)
    bw_motor_snap_vfd = snap_iec_motor_kw(p_bw_elec_rated)

    st_rows = sequence_stage_table(
        steps,
        filter_area_m2=float(avg_area),
        bw_velocity_m_h=float(bw_velocity),
        q_bw_design_m3h=q_bw_design,
        bw_head_mwc=float(bw_head_mwc),
        rho_bw_kg_m3=float(rho_bw),
        eta_pump_bw=float(bw_pump_eta),
        eta_motor_bw=float(motor_eta),
        p_blower_motor_kw=p_blower_motor,
    )

    e_p_dol, e_b_dol, e_tot_dol = _cycle_energy_from_steps(
        steps,
        filter_area_m2=float(avg_area),
        philosophy="DOL",
        q_bw_design_m3h=q_bw_design,
        bw_head_mwc=float(bw_head_mwc),
        rho_bw=float(rho_bw),
        eta_p=float(bw_pump_eta),
        eta_m=float(motor_eta),
        p_blower_motor_kw=p_blower_motor,
    )
    e_p_vfd, e_b_vfd, e_tot_vfd = _cycle_energy_from_steps(
        steps,
        filter_area_m2=float(avg_area),
        philosophy="VFD",
        q_bw_design_m3h=q_bw_design,
        bw_head_mwc=float(bw_head_mwc),
        rho_bw=float(rho_bw),
        eta_p=float(bw_pump_eta),
        eta_m=float(motor_eta),
        p_blower_motor_kw=p_blower_motor,
    )

    n_total = max(1, int(streams) * int(n_filters))
    bw_events_yr = float(energy.get("bw_events_yr") or 0.0)
    op_h_yr = float(inputs.get("op_hours_yr") or 8400.0)
    annual_filtration_m3 = float(energy.get("total_flow_m3_yr") or 0.0)

    annual_bw_pump_dol = e_p_dol * bw_events_yr
    annual_bw_pump_vfd = e_p_vfd * bw_events_yr

    kwh_m3_filt = (
        float(energy.get("e_total_kwh_yr") or 0) / annual_filtration_m3
        if annual_filtration_m3 > 0
        else 0.0
    )
    kwh_per_bw_filter_cycle = e_tot_dol
    kwh_bw_plant_day_sequence = e_tot_dol * n_total * float(bw_cycles_day)
    peak_stage_kw = max((r["P_total (kW)"] for r in st_rows), default=0.0)

    # Comparison narrative scores (1–5)
    savings_pct = (
        (annual_bw_pump_dol - annual_bw_pump_vfd) / annual_bw_pump_dol * 100.0
        if annual_bw_pump_dol > 1e-6
        else 0.0
    )

    prefer = (
        "VFD variable-speed BW trains"
        if savings_pct > 12.0 and float(total_flow) > 10_000.0
        else "DOL multi-pump BW trains"
    )
    eng_notes = build_engineering_notes(
        total_flow=float(total_flow),
        bw_cycles_day=float(bw_cycles_day),
        elec_tariff=float(inputs.get("elec_tariff") or 0.1),
        savings_kwh=max(0.0, annual_bw_pump_dol - annual_bw_pump_vfd),
        philosophy_prefer=prefer,
    )
    _defm = apply_cost_multipliers(
        material="SS316",
        pump_standard="ISO 5199",
        seal="Single mechanical seal",
        use_vfd=False,
        vertical=False,
    )
    pump_mult = (
        _defm["material"] * _defm["standard"] * _defm["seal"] * _defm["vertical"]
    )
    capex_baseline = _philosophy_capex_bundle(
        bw_motor_iec_kw_dol_train=bw_motor_snap_dol,
        bw_motor_iec_kw_vfd_train=bw_motor_snap_vfd,
        blower_motor_kw=p_blower_motor,
        feed_motor_kw_each=feed_motor_snap,
        n_feed_pumps_total=int(streams),
        n_bw_dol_trains=3,
        n_bw_vfd_trains=2,
        n_blower_units=1,
        feed_complex_mult=pump_mult,
        feed_vfd_budget_mult=1.0,
        bw_complex_mult=pump_mult,
        bw_vfd_train_budget_mult=1.35,
    )

    return {
        "auto": {
            "total_flow_m3h": float(total_flow),
            "streams": int(streams),
            "n_filters": int(n_filters),
            "n_duty_filters_per_stream": n_duty_per_stream,
            "q_per_filter_m3h": float(q_per_filter),
            "q_feed_pump_m3h": round(q_feed_pump, 3),
            "filter_area_m2": round(float(avg_area), 3),
            "q_bw_design_m3h": round(q_bw_design, 2),
            "bw_head_mwc": round(float(bw_head_mwc), 2),
            "head_clean_mwc": round(h_clean, 2),
            "head_dirty_mwc": round(h_dirty, 2),
            "dp_residual_bar": float(inputs.get("p_residual", 2.5)),
            "rho_feed_kg_m3": round(float(rho_feed), 2),
            "rho_bw_kg_m3": round(float(rho_bw), 2),
            "q_air_design_m3h": float(bw_hyd.get("q_air_design_m3h") or 0.0),
            "q_air_design_nm3h": float(bw_hyd.get("q_air_design_nm3h") or 0.0),
            "p_blower_motor_kw": round(p_blower_motor, 2),
            "blower_pressure_ratio": float(bw_sizing.get("pressure_ratio") or 1.0),
            "bw_cycles_day": float(bw_cycles_day),
            "bw_events_yr": round(bw_events_yr, 0),
            "op_hours_yr": op_h_yr,
        },
        "feed_pump": {
            "eta_pump_est": round(eta_p_est, 3),
            "p_shaft_kw": round(p_shaft_feed, 2),
            "p_motor_elec_dirty_kw": round(p_elec_feed_dirty, 2),
            "p_motor_elec_clean_kw": round(p_elec_feed_clean, 2),
            "motor_iec_kw": feed_motor_snap,
            "p_installed_kw": round(feed_motor_snap, 2),
            "specific_energy_kwh_m3": round(
                float(energy.get("e_filt_kwh_yr") or 0) / annual_filtration_m3, 4
            )
            if annual_filtration_m3 > 0
            else 0.0,
        },
        "bw_pump": {
            "p_rated_elec_kw": round(p_bw_elec_rated, 2),
            "motor_iec_kw_dol_half": bw_motor_snap_dol,
            "motor_iec_kw_vfd_full": bw_motor_snap_vfd,
        },
        "blower": {
            "q_air_design_m3h": round(float(bw_hyd.get("q_air_design_m3h") or 0.0), 2),
            "q_air_design_nm3h": round(float(bw_hyd.get("q_air_design_nm3h") or 0.0), 2),
            "p_motor_kw": round(p_blower_motor, 2),
            "technology_hint": (
                "Positive displacement (lobe) typical below ~2 000 **Nm³/h** (0 °C, 1 atm) @ total ΔP **0.2–0.9 bar**."
                if float(bw_hyd.get("q_air_design_nm3h") or bw_hyd.get("q_air_design_m3h") or 0) < 2000
                else "Centrifugal multistage or high-speed turbo blower often competitive at high air duty."
            ),
            "detail": {
                "h_submergence_m": bw_sizing.get("h_submergence_m"),
                "dp_sub_bar": bw_sizing.get("dp_sub_bar"),
                "blower_air_delta_p_bar": bw_sizing.get("blower_air_delta_p_bar"),
                "dp_airside_bar": bw_sizing.get("dp_airside_bar"),
                "vessel_pressure_bar": bw_sizing.get("vessel_pressure_bar"),
                "blower_dp_warning": bw_sizing.get("blower_dp_warning"),
                "P1_pa": bw_sizing.get("P1_pa"),
                "P2_pa": bw_sizing.get("P2_pa"),
                "pressure_ratio": bw_sizing.get("pressure_ratio"),
                "rho_air_kg_m3": bw_sizing.get("rho_air_kg_m3"),
                "p_blower_ideal_kw": bw_sizing.get("p_blower_ideal_kw"),
                "p_blower_shaft_kw": bw_sizing.get("p_blower_shaft_kw"),
                "blower_eta": bw_sizing.get("blower_eta"),
            },
        },
        "sequence_stages": st_rows,
        "philosophy": {
            "DOL": {
                "description": "2 × 50 % duty + 1 × 50 % standby, DOL — parallel for high-rate.",
                "kwh_bw_pump_per_cycle": e_p_dol,
                "kwh_blower_per_cycle": e_b_dol,
                "kwh_total_per_cycle": e_tot_dol,
                "kwh_bw_pump_yr": round(annual_bw_pump_dol, 0),
                "installed_bw_motor_kw": round(3.0 * bw_motor_snap_dol, 1),
            },
            "VFD": {
                "description": "2 × 100 % VFD — one modulating for low/high stages; N+1 sparing.",
                "kwh_bw_pump_per_cycle": e_p_vfd,
                "kwh_blower_per_cycle": e_b_vfd,
                "kwh_total_per_cycle": e_tot_vfd,
                "kwh_bw_pump_yr": round(annual_bw_pump_vfd, 0),
                "installed_bw_motor_kw": round(2.0 * bw_motor_snap_vfd, 1),
            },
            "annual_bw_pump_savings_kwh": round(max(0.0, annual_bw_pump_dol - annual_bw_pump_vfd), 0),
            "annual_savings_pct_bw_pump": round(savings_pct, 1),
            "screening_preference": prefer,
        },
        "engineering_notes": eng_notes,
        "capex_baseline_usd": capex_baseline,
        "energy_bridge": {
            "e_filt_kwh_yr": float(energy.get("e_filt_kwh_yr") or 0),
            "e_bw_pump_kwh_yr_model": float(energy.get("e_bw_pump_kwh_yr") or 0),
            "e_blower_kwh_yr": float(energy.get("e_blower_kwh_yr") or 0),
            "kwh_per_m3_filtered": round(kwh_m3_filt, 4),
            "kwh_per_bw_filter_cycle": round(kwh_per_bw_filter_cycle, 3),
            "kwh_bw_plant_day_sequence": round(kwh_bw_plant_day_sequence, 1),
            "peak_bw_stage_kw": round(float(peak_stage_kw), 2),
        },
        "warnings": [
            *(["High filtration superficial velocity — confirm NPSH margin at suction."]
              if float(q_per_filter) / max(float(avg_area), 1e-6) > 18.0
              else []),
            *(["BW pump motor snap significantly above continuous rating — review oversizing."]
              if bw_motor_snap_vfd > p_bw_elec_rated * 1.35
              else []),
        ],
    }
