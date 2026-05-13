"""ui/helpers.py — Shared UI helper functions for AQUASIGHT™ MMF."""
import streamlit as st


def fmt(si_val, quantity: str, decimals: int = 2) -> str:
    """
    Format SI value in the current unit system.
    Reads unit_system from st.session_state (defaults to 'metric').
    Usage: fmt(computed["q_per_filter"], "flow_m3h", 1)
    """
    from engine.units import format_value
    system = st.session_state.get("unit_system", "metric")
    return format_value(si_val, quantity, system, decimals)


def ulbl(quantity: str) -> str:
    """
    Return unit label for the current unit system.
    Usage: ulbl("flow_m3h") → "m³/h" or "gpm"
    """
    from engine.units import unit_label
    system = st.session_state.get("unit_system", "metric")
    return unit_label(quantity, system)


def dv(si_val, quantity: str):
    """
    Convert SI value to display value for the current unit system.
    Usage: dv(1312.5, "flow_m3h")
    """
    from engine.units import display_value
    system = st.session_state.get("unit_system", "metric")
    return display_value(si_val, quantity, system)


def pressure_drop_layers_display_frames(rows: list) -> tuple:
    """
    Convert pressure_drop()['layers'] rows (SI) to display-unit DataFrames.

    Returns (full_breakdown_df, clogging_subset_df) for the current unit_system.
    Solid volume per area (m³/m²) is shown as an equivalent depth (length_m).
    """
    import pandas as pd

    if not rows:
        return pd.DataFrame(), pd.DataFrame()

    full_records: list = []
    clog_records: list = []

    for r in rows:
        sol_si = float(r["Solid load (kg/m²)"])
        svol_si = float(r["Solid vol (m³/m²)"])
        depth_si = float(r["Depth (m)"])
        lv_si = float(r["LV (m/h)"])
        dp_c_si = float(r["ΔP clean (bar)"])
        dp_cm_si = float(r["Cake ΔP mod (bar)"])
        dp_cd_si = float(r["Cake ΔP dirty (bar)"])
        dp_mt_si = float(r["ΔP mod total (bar)"])
        dp_dt_si = float(r["ΔP dirty total (bar)"])

        full = {
            "Media": r["Media"],
            "Support": r["Support"],
            "Capture (%)": r["Capture (%)"],
            f"Solid load ({ulbl('loading_kg_m2')})": round(
                dv(sol_si, "loading_kg_m2"), 4),
            f"Solid vol ({ulbl('length_m')})": round(
                dv(svol_si, "length_m"), 6),
            "ΔεF": r["ΔεF"],
            "Clogging (%)": r["Clogging (%)"],
            f"Depth ({ulbl('length_m')})": round(dv(depth_si, "length_m"), 3),
            f"LV ({ulbl('velocity_m_h')})": round(dv(lv_si, "velocity_m_h"), 2),
            "ε clean": r["ε clean"],
            f"ΔP clean ({ulbl('pressure_bar')})": round(
                dv(dp_c_si, "pressure_bar"), 5),
            f"Cake ΔP mod ({ulbl('pressure_bar')})": round(
                dv(dp_cm_si, "pressure_bar"), 5),
            f"Cake ΔP dirty ({ulbl('pressure_bar')})": round(
                dv(dp_cd_si, "pressure_bar"), 5),
            f"ΔP mod total ({ulbl('pressure_bar')})": round(
                dv(dp_mt_si, "pressure_bar"), 5),
            f"ΔP dirty total ({ulbl('pressure_bar')})": round(
                dv(dp_dt_si, "pressure_bar"), 5),
        }
        full_records.append(full)

        clog = {
            "Media": r["Media"],
            "Support": r["Support"],
            "Capture (%)": r["Capture (%)"],
            f"Solid load ({ulbl('loading_kg_m2')})": full[f"Solid load ({ulbl('loading_kg_m2')})"],
            f"Solid vol ({ulbl('length_m')})": full[f"Solid vol ({ulbl('length_m')})"],
            "ΔεF": r["ΔεF"],
            "Clogging (%)": r["Clogging (%)"],
            "ε clean": r["ε clean"],
            f"Cake ΔP mod ({ulbl('pressure_bar')})": full[f"Cake ΔP mod ({ulbl('pressure_bar')})"],
            f"Cake ΔP dirty ({ulbl('pressure_bar')})": full[f"Cake ΔP dirty ({ulbl('pressure_bar')})"],
        }
        clog_records.append(clog)

    return pd.DataFrame(full_records), pd.DataFrame(clog_records)


def cycle_matrix_temp_title(temp_key: str, temp_si_c: float) -> str:
    """Column title for filtration-cycle matrix (current unit_system)."""
    prefixes = {"temp_min": "Min", "temp_design": "Design", "temp_max": "Max"}
    return f"{prefixes[temp_key]} — {fmt(temp_si_c, 'temperature_c', 0)}"


def cycle_matrix_tss_row_title(tss_key: str, tss_mg_l: float) -> str:
    """Row label for filtration-cycle matrix Feed TSS (current unit_system)."""
    prefixes = {"tss_low": "Low", "tss_avg": "Avg", "tss_high": "High"}
    return f"{prefixes[tss_key]} — {fmt(tss_mg_l, 'concentration_mg_l', 0)}"


def fmt_bar_mwc(bar_si: float, mwc_si: float, bar_decimals: int = 4,
                mwc_decimals: int = 2) -> str:
    """Single cell: filtration ΔP as bar (or psi) + head as mWC (or ft WC)."""
    return f"{fmt(bar_si, 'pressure_bar', bar_decimals)} / {fmt(mwc_si, 'pressure_mwc', mwc_decimals)}"


def fmt_annual_flow_volume(annual_m3: float, decimals: int = 2) -> str:
    """Format total annual throughput (Mm³/yr vs Mft³/yr)."""
    system = st.session_state.get("unit_system", "metric")
    if system == "metric":
        return format(annual_m3 / 1e6, f",.{decimals}f") + " Mm³/yr"
    from engine.units import display_value
    mft3 = display_value(annual_m3, "volume_m3", "imperial") / 1e6
    return format(mft3, f",.{decimals}f") + " Mft³/yr"


def geo_volumes_display_rows(geo_rows: list) -> "tuple[list, list[str]]":
    """
    Convert compute geo_rows (SI column values) to display records + column names.

    Each geo row: [label, depth_m, area_m2, v_cyl, v_ends, v_tot].
    Returns (list of dicts, list of column keys in order).
    """
    cols = (
        "Item",
        f"Depth ({ulbl('length_m')})",
        f"Avg area ({ulbl('area_m2')})",
        f"V_cyl ({ulbl('volume_m3')})",
        f"V_ends ({ulbl('volume_m3')})",
        f"Total vol ({ulbl('volume_m3')})",
    )
    out = []
    for row in geo_rows:
        if len(row) < 6:
            continue
        label, d_m, a_m2, vc, ve, vt = row[0], float(row[1]), float(row[2]), float(row[3]), float(
            row[4]), float(row[5])
        out.append({
            cols[0]: label,
            cols[1]: round(dv(d_m, "length_m"), 3),
            cols[2]: round(dv(a_m2, "area_m2"), 4),
            cols[3]: round(dv(vc, "volume_m3"), 4),
            cols[4]: round(dv(ve, "volume_m3"), 4),
            cols[5]: round(dv(vt, "volume_m3"), 4),
        })
    return out, list(cols)


def media_properties_display_df(base: list) -> "object":
    """Media property table from compute `base` rows in display units."""
    import pandas as pd

    if not base:
        return pd.DataFrame()
    recs = []
    for b in base:
        recs.append({
            "Media": b["Type"],
            f"Depth ({ulbl('length_m')})": round(dv(float(b["Depth"]), "length_m"), 3),
            f"Vol ({ulbl('volume_m3')})": round(dv(float(b["Vol"]), "volume_m3"), 4),
            f"Avg area ({ulbl('area_m2')})": round(dv(float(b["Area"]), "area_m2"), 4),
            f"ρp,eff ({ulbl('density_kg_m3')})": round(dv(float(b["rho_p_eff"]), "density_kg_m3"), 0),
            "ε₀": b.get("epsilon0", 0),
            "d10 (mm)": round(float(b["d10"]), 2),
            "CU": round(float(b["cu"]), 2),
        })
    return pd.DataFrame(recs)


def operating_media_rows_display_df(rows: list) -> "object":
    """wt_oper['media_rows'] from mechanical — SI → display."""
    import pandas as pd

    if not rows:
        return pd.DataFrame()
    recs = []
    for r in rows:
        recs.append({
            "Media": r["Media"],
            "Support layer": r["Support layer"],
            f"Depth ({ulbl('length_m')})": round(dv(float(r["Depth (m)"]), "length_m"), 3),
            f"Area ({ulbl('area_m2')})": round(dv(float(r["Area (m²)"]), "area_m2"), 2),
            f"V bulk ({ulbl('volume_m3')})": round(dv(float(r["V bulk (m³)"]), "volume_m3"), 3),
            "ε₀": r["ε₀"],
            f"ρ particle ({ulbl('density_kg_m3')})": round(
                dv(float(r["ρ particle (kg/m³)"]), "density_kg_m3"), 0),
            f"V solid ({ulbl('volume_m3')})": round(dv(float(r["V solid (m³)"]), "volume_m3"), 4),
            f"Dry mass ({ulbl('mass_kg')})": round(dv(float(r["Dry mass (kg)"]), "mass_kg"), 1),
        })
    return pd.DataFrame(recs)


def backwash_sequence_steps_display_df(steps: list) -> "object":
    """Convert bw_seq['steps'] rows (SI) to display-unit DataFrame."""
    import pandas as pd

    if not steps:
        return pd.DataFrame()
    recs = []
    for s in steps:
        recs.append({
            "Step": s["Step"],
            "Dur low (min)": s["Dur low (min)"],
            "Dur avg (min)": s["Dur avg (min)"],
            "Dur high (min)": s["Dur high (min)"],
            f"Water rate ({ulbl('velocity_m_h')})": round(
                dv(float(s["Water rate (m/h)"]), "velocity_m_h"), 2),
            "Source": s["Source"],
            f"Flow ({ulbl('flow_m3h')})": round(dv(float(s["Flow (m³/h)"]), "flow_m3h"), 1),
            f"Vol low ({ulbl('volume_m3')})": round(dv(float(s["Vol low (m³)"]), "volume_m3"), 1),
            f"Vol avg ({ulbl('volume_m3')})": round(dv(float(s["Vol avg (m³)"]), "volume_m3"), 1),
            f"Vol high ({ulbl('volume_m3')})": round(dv(float(s["Vol high (m³)"]), "volume_m3"), 1),
        })
    return pd.DataFrame(recs)


def fmt_si_range(
    lo_si: float,
    hi_si: float,
    quantity: str,
    lo_decimals: int = 2,
    hi_decimals: int = 2,
) -> str:
    """Format an SI numeric interval for the active unit system (single trailing unit label)."""
    lo_d = dv(lo_si, quantity)
    hi_d = dv(hi_si, quantity)
    lbl = ulbl(quantity)
    return f"{lo_d:.{lo_decimals}f}–{hi_d:.{hi_decimals}f} {lbl}"


def saddle_catalogue_display_df(rows: list) -> "object":
    """Saddle catalogue_rows (SI) → display-unit DataFrame."""
    import pandas as pd

    if not rows:
        return pd.DataFrame()
    recs = []
    for r in rows:
        recs.append({
            f"Capacity ({ulbl('mass_t')})": round(
                dv(float(r["Capacity (t)"]), "mass_t"), 3),
            "Section": r["Section"],
            f"Mass / len ({ulbl('linear_density_kg_m')})": round(
                dv(float(r["kg/m"]), "linear_density_kg_m"), 2),
            f"Piece L ({ulbl('length_m')})": round(
                dv(float(r["Piece L (m)"]), "length_m"), 3),
            f"Piece wt ({ulbl('mass_kg')})": round(
                dv(float(r["Piece wt (kg)"]), "mass_kg"), 1),
            "Ribs/saddle": r["Ribs/saddle"],
            f"Struct. wt/saddle ({ulbl('mass_kg')})": round(
                dv(float(r["Struct. wt/saddle (kg)"]), "mass_kg"), 1),
            f"Paint ({ulbl('area_m2')}) / piece": round(
                dv(float(r["Paint m²/piece"]), "area_m2"), 2),
            "Selected": r.get("Selected", ""),
        })
    return pd.DataFrame(recs)


def saddle_alternatives_display_df(rows: list) -> "object":
    """wt_saddle['alternatives'] rows (SI) → display DataFrame."""
    import pandas as pd

    if not rows:
        return pd.DataFrame()
    recs = []
    for a in rows:
        cap = a["capacity_t"]
        cap_disp = (
            round(dv(float(cap), "mass_t"), 3)
            if isinstance(cap, (int, float)) else cap
        )
        recs.append({
            "Supports": a["n_saddles"],
            f"Reaction/saddle ({ulbl('mass_t')})": round(
                dv(float(a["reaction_t"]), "mass_t"), 3),
            "Section": a["section"],
            f"Capacity ({ulbl('mass_t')})": cap_disp,
            "Status": (
                "▶ current" if a["is_current"] else (
                    "✅ fits" if a["fits_catalogue"] else "❌ exceeds max")),
            f"Struct. wt/saddle ({ulbl('mass_kg')})": round(
                dv(float(a["struct_wt_ea_kg"]), "mass_kg"), 1),
            f"Total struct. wt ({ulbl('mass_kg')})": round(
                dv(float(a["struct_wt_total_kg"]), "mass_kg"), 1),
        })
    return pd.DataFrame(recs)


def nozzle_schedule_display_df(sched_rows: list) -> tuple:
    """
    Nozzle schedule rows from engine (SI) for st.data_editor in display units.

    DN stays **integer mm** (ISO 6708) for schedule lookups; flow, velocity,
    stub length, wall thickness are read-only in the editor. Weights are editable
    in the active mass unit; totals are converted back to kg via si_value when summing.

    Returns (DataFrame, dict of stable internal keys → column labels).
    """
    import pandas as pd

    keys = {
        "service": "Service",
        "flow": f"Flow ({ulbl('flow_m3h')})",
        "dn": "DN (mm)",
        "schedule": "Schedule",
        "rating": "Rating",
        "velocity": f"Velocity ({ulbl('velocity_m_s')})",
        "qty": "Qty",
        "stub_l": f"Stub L ({ulbl('length_mm')})",
        "t_wall": f"t wall ({ulbl('length_mm')})",
        "wt_ea": f"Wt/nozzle ({ulbl('mass_kg')})",
        "wt_tot": f"Total wt ({ulbl('mass_kg')})",
        "notes": "Notes",
    }
    if not sched_rows:
        return pd.DataFrame(), keys
    recs = []
    for r in sched_rows:
        recs.append({
            keys["service"]: r["Service"],
            keys["flow"]: round(dv(float(r["Flow (m³/h)"]), "flow_m3h"), 2),
            keys["dn"]: int(r["DN (mm)"]),
            keys["schedule"]: r["Schedule"],
            keys["rating"]: r["Rating"],
            keys["velocity"]: round(dv(float(r["Velocity (m/s)"]), "velocity_m_s"), 2),
            keys["qty"]: r["Qty"],
            keys["stub_l"]: round(dv(float(r["Stub L (mm)"]), "length_mm"), 2),
            keys["t_wall"]: round(dv(float(r["t wall (mm)"]), "length_mm"), 3),
            keys["wt_ea"]: round(dv(float(r["Wt/nozzle (kg)"]), "mass_kg"), 2),
            keys["wt_tot"]: round(dv(float(r["Total wt (kg)"]), "mass_kg"), 1),
            keys["notes"]: r.get("Notes", ""),
        })
    return pd.DataFrame(recs), keys


def nozzle_schedule_total_weight_kg(edited_df: "object", total_wt_col: str) -> float:
    """Sum total nozzle weight column back to SI kg."""
    from engine.units import si_value

    if edited_df is None or total_wt_col not in edited_df.columns:
        return 0.0
    system = st.session_state.get("unit_system", "metric")
    s = 0.0
    for v in edited_df[total_wt_col]:
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if fv != fv:
            continue
        s += si_value(fv, "mass_kg", system)
    return s


def filtration_dp_curve_display_df(rows: list):
    """Convert filtration_cycle()['dp_curve'] rows from SI to display units."""
    import pandas as pd

    if not rows:
        return pd.DataFrame()
    recs = []
    for r in rows:
        m_si = float(r["M (kg/m²)"])
        dpc = float(r["ΔP cake (bar)"])
        dpt = float(r["ΔP total (bar)"])
        recs.append({
            f"M ({ulbl('loading_kg_m2')})": round(dv(m_si, "loading_kg_m2"), 4),
            f"ΔP cake ({ulbl('pressure_bar')})": round(dv(dpc, "pressure_bar"), 4),
            f"ΔP total ({ulbl('pressure_bar')})": round(dv(dpt, "pressure_bar"), 4),
        })
    return pd.DataFrame(recs)


def show_alert(level: str, title: str, message: str) -> None:
    """Render a severity-coloured alert box using inline CSS."""
    _styles = {
        "info":     {"bg": "#0a1628", "border": "#1e40af", "icon": "ℹ️"},
        "advisory": {"bg": "#1a1500", "border": "#b8860b", "icon": "⚠️"},
        "warning":  {"bg": "#1a0a00", "border": "#cc5500", "icon": "🟠"},
        "critical": {"bg": "#1a0000", "border": "#cc0000", "icon": "🔴"},
    }
    s = _styles.get(level, _styles["info"])
    st.markdown(
        f"""<div style="
            background:{s['bg']}; border-left:4px solid {s['border']};
            border-radius:4px; padding:10px 14px; margin:6px 0;">
        <strong>{s['icon']} {title}</strong><br>{message}
        </div>""",
        unsafe_allow_html=True,
    )
