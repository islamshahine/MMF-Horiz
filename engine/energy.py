"""
engine/energy.py
────────────────
Energy & hydraulic budget for horizontal MMF systems.

Hydraulic profile (head budget):
  H_total = H_media + H_nozzle_plate + H_piping + H_static_delivery

Energy consumers:
  1. Filtration feed pump  (continuous)
  2. BW pump               (intermittent — per BW event)
  3. Air-scour blower      (intermittent — per BW event)
"""

GRAVITY = 9.81   # m/s²


# ── helpers ────────────────────────────────────────────────────────────────

def _mwc_to_bar(mwc: float, rho: float = 1025.0) -> float:
    return mwc * rho * GRAVITY / 1e5


def _bar_to_mwc(bar: float, rho: float = 1025.0) -> float:
    return bar * 1e5 / (rho * GRAVITY)


def _pump_power_kw(flow_m3h: float, head_mwc: float,
                   rho_kg_m3: float, eta: float) -> float:
    """Shaft power in kW for a centrifugal pump."""
    if eta <= 0 or flow_m3h <= 0:
        return 0.0
    q_m3s = flow_m3h / 3600.0
    return q_m3s * rho_kg_m3 * GRAVITY * head_mwc / (eta * 1000.0)


# ═══════════════════════════════════════════════════════════════════════════
# 1. HYDRAULIC PROFILE
# ═══════════════════════════════════════════════════════════════════════════

def hydraulic_profile(
    dp_media_clean_bar: float,
    dp_media_dirty_bar: float,
    np_dp_bar: float,
    pipe_loss_pct: float   = 15.0,
    static_head_m: float   = 0.0,
    rho_feed_kg_m3: float  = 1025.0,
) -> dict:
    """
    Build the filtration pump head budget.

    Parameters
    ----------
    dp_media_clean_bar  : Ergun clean-bed ΔP (bar)
    dp_media_dirty_bar  : Cake model dirty-bed ΔP at M_max (bar)
    np_dp_bar           : Nozzle-plate hydraulic ΔP (bar)
    pipe_loss_pct       : Piping friction as % of (media + NP) ΔP
    static_head_m       : Elevation / delivery static head (m)
    rho_feed_kg_m3      : Feed water density (kg/m³)

    Returns
    -------
    dict — head budget (clean & dirty) in both bar and mWC
    """
    def _budget(media_bar):
        np_bar    = np_dp_bar
        sub_bar   = media_bar + np_bar
        pipe_bar  = sub_bar * pipe_loss_pct / 100.0
        stat_bar  = _mwc_to_bar(static_head_m, rho_feed_kg_m3)
        total_bar = sub_bar + pipe_bar + stat_bar
        return {
            "media_bar":      round(media_bar,  4),
            "np_bar":         round(np_bar,     4),
            "pipe_bar":       round(pipe_bar,   4),
            "static_bar":     round(stat_bar,   4),
            "total_bar":      round(total_bar,  4),
            "media_mwc":      round(_bar_to_mwc(media_bar,  rho_feed_kg_m3), 2),
            "np_mwc":         round(_bar_to_mwc(np_bar,     rho_feed_kg_m3), 2),
            "pipe_mwc":       round(_bar_to_mwc(pipe_bar,   rho_feed_kg_m3), 2),
            "static_mwc":     round(static_head_m, 2),
            "total_mwc":      round(_bar_to_mwc(total_bar,  rho_feed_kg_m3), 2),
        }

    return {
        "clean": _budget(dp_media_clean_bar),
        "dirty": _budget(dp_media_dirty_bar),
        "pipe_loss_pct":    pipe_loss_pct,
        "static_head_m":    static_head_m,
        "np_dp_bar":        round(np_dp_bar, 4),
    }


# ═══════════════════════════════════════════════════════════════════════════
# 2. ENERGY SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

def energy_summary(
    # Filtration pump
    q_filter_m3h: float,
    n_filters_total: int,
    filt_head_dirty_mwc: float,
    filt_head_clean_mwc: float,
    pump_eta: float          = 0.75,
    motor_eta: float         = 0.95,
    rho_feed_kg_m3: float    = 1025.0,
    # BW pump
    q_bw_m3h: float          = 0.0,
    bw_head_mwc: float       = 15.0,
    bw_pump_eta: float       = 0.72,
    bw_motor_eta: float      = 0.95,
    rho_bw_kg_m3: float      = 1025.0,
    # Air blower
    p_blower_kw: float       = 0.0,
    blower_motor_eta: float  = 0.95,
    # BW scheduling
    bw_duration_h: float     = 0.633,
    bw_per_day_design: float = 3.6,
    availability_pct: float  = 90.0,
    # Economics
    elec_tariff_usd_kwh: float = 0.10,
    # Operation hours
    op_hours_per_year: float = 8_400.0,
) -> dict:
    """
    Annual energy and cost summary for the MMF system.

    Filtration pump:
        Runs continuously; uses dirty-bed head for design (worst case).
        Consumed = P_dirty × op_hours × n_filters_total

    BW pump + blower:
        Intermittent; runs bw_per_day_design times per filter × bw_duration_h.
        Consumed = P_bw × bw_duration_h × bw_per_day_design × 365 × n_filters_total

    Returns
    -------
    dict — power, energy, and cost breakdown
    """
    # Filtration pump
    p_filt_dirty_kw  = _pump_power_kw(q_filter_m3h, filt_head_dirty_mwc,
                                       rho_feed_kg_m3, pump_eta * motor_eta)
    p_filt_clean_kw  = _pump_power_kw(q_filter_m3h, filt_head_clean_mwc,
                                       rho_feed_kg_m3, pump_eta * motor_eta)

    # Annual filtration energy: all filters run op_hours, use avg of clean/dirty
    p_filt_avg_kw    = (p_filt_clean_kw + p_filt_dirty_kw) / 2.0
    e_filt_kwh_yr    = p_filt_avg_kw * n_filters_total * op_hours_per_year

    # BW pump
    p_bw_kw          = _pump_power_kw(q_bw_m3h, bw_head_mwc,
                                       rho_bw_kg_m3, bw_pump_eta * bw_motor_eta)
    bw_events_yr     = bw_per_day_design * 365.0 * n_filters_total
    e_bw_pump_kwh_yr = p_bw_kw * bw_duration_h * bw_events_yr

    # Air blower
    p_blower_shaft_kw = p_blower_kw / blower_motor_eta  # shaft → electrical
    e_blower_kwh_yr   = p_blower_shaft_kw * bw_duration_h * bw_events_yr

    # Totals
    e_total_kwh_yr    = e_filt_kwh_yr + e_bw_pump_kwh_yr + e_blower_kwh_yr
    total_flow_yr_m3  = (q_filter_m3h * n_filters_total
                         * (availability_pct / 100.0) * op_hours_per_year)
    kwh_per_m3        = e_total_kwh_yr / total_flow_yr_m3 if total_flow_yr_m3 > 0 else 0.0
    cost_usd_yr       = e_total_kwh_yr * elec_tariff_usd_kwh

    return {
        # Filtration pump
        "p_filt_dirty_kw":     round(p_filt_dirty_kw,   2),
        "p_filt_clean_kw":     round(p_filt_clean_kw,   2),
        "p_filt_avg_kw":       round(p_filt_avg_kw,     2),
        "e_filt_kwh_yr":       round(e_filt_kwh_yr,     0),
        # BW pump
        "p_bw_kw":             round(p_bw_kw,           2),
        "e_bw_pump_kwh_yr":    round(e_bw_pump_kwh_yr,  0),
        # Blower
        "p_blower_elec_kw":    round(p_blower_shaft_kw, 2),
        "e_blower_kwh_yr":     round(e_blower_kwh_yr,   0),
        # Totals
        "e_total_kwh_yr":      round(e_total_kwh_yr,    0),
        "total_flow_m3_yr":    round(total_flow_yr_m3,  0),
        "kwh_per_m3":          round(kwh_per_m3,        4),
        "cost_usd_yr":         round(cost_usd_yr,       0),
        # Inputs echoed
        "pump_eta":            pump_eta,
        "motor_eta":           motor_eta,
        "bw_pump_eta":         bw_pump_eta,
        "elec_tariff_usd_kwh": elec_tariff_usd_kwh,
        "op_hours_per_year":   op_hours_per_year,
        "bw_per_day_design":   round(bw_per_day_design, 2),
        "bw_events_yr":        round(bw_events_yr,      0),
    }
