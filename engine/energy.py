"""
engine/energy.py
────────────────
Energy & hydraulic budget for horizontal MMF systems.

Hydraulic profile — real filter flow path (filtration direction):

  Pump → inlet piping (valves/fittings) → inlet distributor
       → media bed (clean or dirty)
       → strainer nozzle plate
       → outlet piping (valves/fittings) → residual pressure downstream

  P_pump = P_residual + ΔP_outlet_pipe + ΔP_np_filt + ΔP_media
         + ΔP_distributor + ΔP_inlet_pipe + ρg·ΔZ_static

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
    # Media
    dp_media_clean_bar: float,
    dp_media_dirty_bar: float,
    # Strainer nozzle plate (filtration direction, orifice ΔP)
    np_dp_filt_bar: float,
    # Inlet distribution header / laterals
    distributor_dp_bar: float  = 0.02,
    # Inlet piping: feed nozzle + pipe + valves + flow meter
    dp_inlet_pipe_bar: float   = 0.30,
    # Outlet piping: outlet nozzle + pipe + valves
    dp_outlet_pipe_bar: float  = 0.20,
    # Required residual pressure at downstream tie-in point
    p_residual_bar: float      = 2.50,
    # Static head: filter elevation above pump datum (positive = pump pumps up)
    static_head_m: float       = 0.0,
    rho_feed_kg_m3: float      = 1025.0,
) -> dict:
    """
    Full hydraulic head budget for the filtration feed pump.

    Flow path (all resistances add to pump duty):

      [Pump] ──► inlet piping ──► distributor ──► media ──► NP ──► outlet piping ──► [P_residual]

    P_pump = P_residual + ΔP_outlet_pipe + ΔP_np + ΔP_media
           + ΔP_distributor + ΔP_inlet_pipe + ρg·ΔZ

    Parameters
    ----------
    dp_media_clean_bar  : Clean-bed ΔP, Ergun (bar)
    dp_media_dirty_bar  : Dirty-bed ΔP at M_max, Ergun + cake (bar)
    np_dp_filt_bar      : Strainer nozzle plate orifice ΔP at filtration flow (bar)
    distributor_dp_bar  : Inlet distribution header/laterals ΔP (bar); default 0.02
    dp_inlet_pipe_bar   : Inlet piping losses — nozzle, pipe, valves, flow meter (bar)
    dp_outlet_pipe_bar  : Outlet piping losses — pipe, valves, outlet nozzle (bar)
    p_residual_bar      : Required downstream pressure (barg); default 2.5
    static_head_m       : Elevation of filter above pump datum (m)
    rho_feed_kg_m3      : Feed water density (kg/m³)

    Returns
    -------
    dict — itemised head budget for clean and dirty bed, in bar and mWC
    """
    stat_bar = _mwc_to_bar(static_head_m, rho_feed_kg_m3)

    def _budget(media_bar: float) -> dict:
        items = {
            "Inlet piping (valves/fittings)": dp_inlet_pipe_bar,
            "Inlet distributor":              distributor_dp_bar,
            "Media bed":                      media_bar,
            "Strainer nozzle plate":          np_dp_filt_bar,
            "Outlet piping (valves/fittings)":dp_outlet_pipe_bar,
            "Downstream residual pressure":   p_residual_bar,
            "Static head":                    stat_bar,
        }
        total_bar = sum(items.values())
        return {
            "items_bar":   {k: round(v, 4) for k, v in items.items()},
            "items_mwc":   {k: round(_bar_to_mwc(v, rho_feed_kg_m3), 2)
                            for k, v in items.items()},
            "total_bar":   round(total_bar, 4),
            "total_mwc":   round(_bar_to_mwc(total_bar, rho_feed_kg_m3), 2),
            # quick-access keys
            "media_bar":   round(media_bar,        4),
            "np_bar":      round(np_dp_filt_bar,   4),
            "media_mwc":   round(_bar_to_mwc(media_bar,      rho_feed_kg_m3), 2),
            "np_mwc":      round(_bar_to_mwc(np_dp_filt_bar, rho_feed_kg_m3), 2),
        }

    return {
        "clean":               _budget(dp_media_clean_bar),
        "dirty":               _budget(dp_media_dirty_bar),
        "np_dp_filt_bar":      round(np_dp_filt_bar,    4),
        "distributor_dp_bar":  round(distributor_dp_bar, 4),
        "dp_inlet_pipe_bar":   round(dp_inlet_pipe_bar,  4),
        "dp_outlet_pipe_bar":  round(dp_outlet_pipe_bar, 4),
        "p_residual_bar":      round(p_residual_bar,     4),
        "static_head_m":       static_head_m,
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
