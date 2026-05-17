"""ui/helpers.py — Shared UI helper functions for AQUASIGHT™ MMF."""
from __future__ import annotations

import re
from typing import Any, Final

import pandas as pd
import streamlit as st

# Default layout for read-only `st.dataframe` tables (single place if Streamlit API evolves).
ST_DATAFRAME_KW: Final[dict[str, Any]] = {
    "use_container_width": True,
    "hide_index": True,
}


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


def _unit_system() -> str:
    return str(st.session_state.get("unit_system", "metric"))


def localize_engine_message(msg: str) -> str:
    """
    Rewrite embedded SI literals in engine-generated strings for imperial UI.

    Engine layers store SI; warnings from ``collector_hydraulics`` / ``collector_geometry``
    are formatted at display time so we do not duplicate physics strings.
    """
    if _unit_system() == "metric" or not msg:
        return msg
    from engine.units import format_value

    us = "imperial"
    out = str(msg)

    def _fv(m: re.Match, qty: str, dec: int) -> str:
        return format_value(float(m.group(1)), qty, us, dec)

    out = re.sub(
        r"([\d]+(?:\.[\d]+)?)\s*m³/h",
        lambda m: _fv(m, "flow_m3h", 1),
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"([\d]+(?:\.[\d]+)?)\s*m3/h",
        lambda m: _fv(m, "flow_m3h", 1),
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"([\d]+(?:\.[\d]+)?)\s*m/s",
        lambda m: _fv(m, "velocity_m_s", 2),
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"([\d]+(?:\.[\d]+)?)\s*m/h",
        lambda m: _fv(m, "velocity_m_h", 1),
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"([\d]+(?:\.[\d]+)?)\s*kPa",
        lambda m: _fv(m, "pressure_kpa", 2),
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"([\d]+(?:\.[\d]+)?)\s*mm\b",
        lambda m: _fv(m, "length_mm", 1),
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"([\d]+(?:\.[\d]+)?)\s*m\b",
        lambda m: _fv(m, "length_m", 2),
        out,
        flags=re.IGNORECASE,
    )
    return out


_COLLECTOR_PROFILE_FIELDS: Final[list[tuple[str, str, str, int]]] = [
    ("station_m", "Station", "length_m", 3),
    ("header_flow_m3h", "Header flow", "flow_m3h", 1),
    ("header_velocity_m_s", "Header velocity", "velocity_m_s", 2),
    ("lateral_flow_m3h", "Lateral flow", "flow_m3h", 1),
    ("lateral_velocity_m_s", "Lateral velocity", "velocity_m_s", 2),
    ("orifice_velocity_m_s", "Opening velocity", "velocity_m_s", 2),
    ("cumulative_header_loss_kpa", "Cumulative header loss", "pressure_kpa", 2),
]


def collector_hyd_profile_display_df(profile: list[dict[str, Any]]) -> pd.DataFrame:
    """Collector ladder profile table with unit labels for the active unit system."""
    rows: list[dict[str, Any]] = []
    for pt in profile:
        row: dict[str, Any] = {}
        for key, title, qty, dec in _COLLECTOR_PROFILE_FIELDS:
            val = pt.get(key)
            col = f"{title} ({ulbl(qty)})"
            if val is None:
                row[col] = "—"
            else:
                row[col] = fmt(val, qty, dec)
        if "lateral_index" in pt:
            row["Lateral #"] = pt["lateral_index"]
        rows.append(row)
    cols = ["Lateral #"] + [f"{t} ({ulbl(q)})" for _, t, q, _ in _COLLECTOR_PROFILE_FIELDS]
    df = pd.DataFrame(rows)
    return df[[c for c in cols if c in df.columns]]


_BW_TIMELINE_STAGGER_LABELS: Final[dict[str, str]] = {
    "feasibility_trains": "Feasibility BW trains (section 4)",
    "optimized_trains": "Optimized trains (scheduling aid)",
    "tariff_aware_v3": "Tariff-aware v3 (peak + tariff + blackouts)",
    "uniform": "Uniform stagger (legacy)",
}


_ORIFICE_NETWORK_FIELDS: Final[list[tuple[str, str, str, int]]] = [
    ("station_m", "Station along header", "length_m", 3),
    ("y_along_lateral_m", "Along lateral", "length_m", 3),
    ("flow_m3h", "Hole flow", "flow_m3h", 2),
    ("velocity_m_s", "Hole velocity", "velocity_m_s", 2),
    ("orifice_d_mm", "Opening size", "length_mm", 1),
]


def orifice_network_display_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Perforation network table with unit labels for the active unit system."""
    out_rows: list[dict[str, Any]] = []
    for r in rows:
        row: dict[str, Any] = {
            "Lateral #": r.get("lateral_index"),
            "Hole #": r.get("hole_index"),
        }
        for key, title, qty, dec in _ORIFICE_NETWORK_FIELDS:
            val = r.get(key)
            col = f"{title} ({ulbl(qty)})"
            if val is None:
                row[col] = "—"
            else:
                row[col] = fmt(val, qty, dec)
        if r.get("construction"):
            row["Construction"] = r.get("construction")
        out_rows.append(row)
    cols = (
        ["Lateral #", "Hole #"]
        + [f"{t} ({ulbl(q)})" for _, t, q, _ in _ORIFICE_NETWORK_FIELDS]
        + (["Construction"] if any(r.get("construction") for r in rows) else [])
    )
    df = pd.DataFrame(out_rows)
    return df[[c for c in cols if c in df.columns]]


def bw_timeline_stagger_label(stagger_model: str | None) -> str:
    """User-facing label for duty-chart stagger mode (not internal keys)."""
    key = str(stagger_model or "").strip().lower()
    return _BW_TIMELINE_STAGGER_LABELS.get(key, key.replace("_", " ").title() or "—")


def metric_explain_help(metric_id: str, inputs: dict, computed: dict) -> str:
    """Tooltip text for metrics (explainability registry)."""
    from engine.explainability import metric_help_text

    return metric_help_text(metric_id, inputs, computed)


def render_metric_explain_panel(
    inputs: dict,
    computed: dict,
    metric_ids: list[str],
    *,
    title: str = "How these numbers are built",
) -> None:
    """Expandable contributor breakdown for selected metrics."""
    import streamlit as st
    from engine.explainability import get_metric_explanation

    with st.expander(title, expanded=False):
        st.caption(
            "Deterministic contributors from **inputs** and **computed** — "
            "scheduling aid / design review only."
        )
        for mid in metric_ids:
            ex = get_metric_explanation(mid, inputs, computed)
            if not ex:
                continue
            st.markdown(f"**{ex['title']}**")
            st.caption(ex["equation"])
            for row in ex.get("contributors") or []:
                st.markdown(
                    f"- **{row['label']}:** {row['value']} — {row['role']}"
                )
            st.caption(f"Reference: {ex.get('doc_section', '')}")
            st.divider()


def bw_timeline_schedule_summary_html(bw_timeline: dict) -> str:
    """Compact scheduling summary for Backwash duty chart (all stagger modes)."""
    _tl = bw_timeline or {}
    _pk = _tl.get("peak_concurrent_bw", "—")
    _ktr = _tl.get("bw_trains")
    _ktr_s = str(_ktr) if _ktr is not None else "—"
    _cap_ok = _tl.get("meets_bw_trains_cap")
    if _cap_ok is True:
        _cap_txt = "Yes"
    elif _cap_ok is False:
        _cap_txt = "No — review BW trains / cycle"
    else:
        _cap_txt = "—"
    rows = [
        ("Peak filters in BW", f"<b>{_pk}</b>"),
        ("Rated BW trains (section 4)", f"<b>{_ktr_s}</b>"),
        ("Within BW-train cap", f"<b>{_cap_txt}</b>"),
    ]
    _opt = _tl.get("optimizer") or {}
    if str(_tl.get("stagger_model", "")).lower() in ("optimized_trains", "tariff_aware_v3") and _opt:
        rows.extend([
            ("Peak (feasibility spacing)", f"<b>{_opt.get('peak_feasibility_spacing', '—')}</b>"),
            ("Peak reduction (filters)", f"<b>{_opt.get('improvement_filters', 0)}</b>"),
        ])
    _tv3 = _tl.get("tariff_v3") or _opt.get("tariff_v3") or {}
    if str(_tl.get("stagger_model", "")).lower() == "tariff_aware_v3" and _tv3:
        rows.extend([
            ("BW filter-h in peak tariff", f"<b>{_tv3.get('peak_tariff_filter_h', '—')}</b>"),
            ("Blackout overlap (h)", f"<b>{_tv3.get('blackout_overlap_h', 0)}</b>"),
        ])
    _pt = _tl.get("peak_time_h") or _opt.get("peak_time_h")
    if _pt is not None:
        rows.append(("First peak at", f"<b>{float(_pt):.1f} h</b>"))
    _pw = _tl.get("peak_windows") or _opt.get("peak_windows") or []
    if _pw:
        _w0 = _pw[0]
        rows.append((
            "First peak overlap",
            f"<b>{float(_w0.get('t0_h', 0)):.1f}–{float(_w0.get('t1_h', 0)):.1f} h</b>",
        ))
    body = "".join(
        f"<tr><td>{lbl}</td><td style='text-align:right'>{val}</td></tr>"
        for lbl, val in rows
    )
    return (
        f"<table style='width:100%;font-size:0.78rem;line-height:1.5;border-collapse:collapse;'>"
        f"{body}</table>"
    )


def clogging_pct_display(val) -> str:
    """Arrow-safe display for support layers (—) vs filterable layers (numeric %)."""
    if val is None or val == "—":
        return "—"
    try:
        return f"{float(val):.1f}"
    except (TypeError, ValueError):
        return str(val)


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
            "Clogging (%)": clogging_pct_display(r["Clogging (%)"]),
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
            "Clogging (%)": clogging_pct_display(r["Clogging (%)"]),
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
            f"d10 ({ulbl('length_mm')})": round(dv(float(b["d10"]), "length_mm"), 2),
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


def data_editor_value_to_dataframe(editor_value: "object", base_df: "object" = None):
    """
    Normalize st.data_editor session value to a pandas DataFrame.

    Streamlit stores widget state as EditingState (edited_rows / added_rows /
    deleted_rows), not as a DataFrame. Pass the display table as base_df.
    """
    import pandas as pd

    if editor_value is None:
        return None
    if isinstance(editor_value, pd.DataFrame):
        return editor_value
    if hasattr(editor_value, "iloc"):
        return editor_value
    if not isinstance(editor_value, dict):
        return None
    if "edited_rows" in editor_value or "added_rows" in editor_value or "deleted_rows" in editor_value:
        if base_df is None:
            return None
        base = base_df.copy() if isinstance(base_df, pd.DataFrame) else pd.DataFrame(base_df)
        edited_rows = editor_value.get("edited_rows") or {}
        for row_idx, changes in edited_rows.items():
            i = int(row_idx)
            if i < 0 or i >= len(base):
                continue
            for col, val in (changes or {}).items():
                if col in base.columns:
                    base.at[base.index[i], col] = val
        for row_idx in sorted((editor_value.get("deleted_rows") or []), reverse=True):
            i = int(row_idx)
            if 0 <= i < len(base):
                base = base.drop(base.index[i])
        added = editor_value.get("added_rows") or []
        if added:
            base = pd.concat([base, pd.DataFrame(added)], ignore_index=True)
        return base.reset_index(drop=True)
    try:
        return pd.DataFrame(editor_value)
    except (ValueError, TypeError):
        return None


def nozzle_schedule_si_from_editor_df(
    edited_df: "object",
    keys: dict,
    base_rows: list,
    *,
    editor_base_df: "object" = None,
) -> list:
    """Map §4 data_editor back to engine schedule rows (SI); refresh ID & V when DN changes."""
    from engine.nozzles import refresh_nozzle_row_hydraulics
    from engine.units import si_value

    edited_df = data_editor_value_to_dataframe(edited_df, editor_base_df)
    if edited_df is None or not base_rows:
        return list(base_rows)
    system = st.session_state.get("unit_system", "metric")
    out_rows: list = []
    for i, base in enumerate(base_rows):
        row = dict(base)
        if i < len(edited_df):
            er = edited_df.iloc[i]
            try:
                row["DN (mm)"] = int(er[keys["dn"]])
            except (TypeError, ValueError):
                pass
            if keys["schedule"] in er:
                row["Schedule"] = str(er[keys["schedule"]])
            if keys["rating"] in er:
                row["Rating"] = str(er[keys["rating"]])
            if keys["qty"] in er:
                row["Qty"] = int(er[keys["qty"]])
        row = refresh_nozzle_row_hydraulics(row)
        out_rows.append(row)
    return out_rows


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


def _fmt_cycle_h(val: Any) -> str:
    if val is None:
        return "—"
    try:
        v = float(val)
        if v != v:
            return "—"
    except (TypeError, ValueError):
        return "—"
    return fmt(v, "time_h", 2)


def staged_orifice_bands_display_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Staged perforation bands table (advisory drill schedule)."""
    if not rows:
        return pd.DataFrame()
    _d = ulbl("length_mm")
    recs = []
    for r in rows:
        recs.append({
            "Lateral #": int(r.get("lateral_index", 0) or 0),
            "Hole from #": int(r.get("hole_index_from", 0) or 0),
            "Hole to #": int(r.get("hole_index_to", 0) or 0),
            "Band #": int(r.get("band_index", 0) or 0),
            f"Baseline Ø ({_d})": fmt(float(r.get("d_mm_baseline", 0)), "length_mm", 1),
            f"Ideal mean Ø in band ({_d})": fmt(
                float(r.get("d_mm_ideal_mean_in_band_mm", 0)), "length_mm", 1
            ),
            f"Recommended Ø ({_d})": fmt(float(r.get("d_mm_recommended", 0)), "length_mm", 1),
        })
    return pd.DataFrame(recs)


def staged_orifice_hole_display_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Per-hole staged perforation detail (advisory)."""
    if not rows:
        return pd.DataFrame()
    _d = ulbl("length_mm")
    _v = ulbl("velocity_m_s")
    _q = ulbl("flow_m3h")
    recs = []
    for r in rows:
        recs.append({
            "Lateral #": int(r.get("lateral_index", 0) or 0),
            "Hole #": int(r.get("hole_index", 0) or 0),
            f"Flow ({_q})": fmt(float(r.get("flow_m3h", 0)), "flow_m3h", 3),
            f"Baseline Ø ({_d})": fmt(float(r.get("d_mm_baseline", 0)), "length_mm", 1),
            f"Recommended Ø ({_d})": fmt(float(r.get("d_mm_recommended", 0)), "length_mm", 1),
            f"V baseline ({_v})": fmt(
                float(r.get("velocity_baseline_m_s", 0)), "velocity_m_s", 2
            ),
            f"V after snap ({_v})": fmt(
                float(r.get("velocity_estimated_after_snap_m_s", 0)), "velocity_m_s", 2
            ),
        })
    return pd.DataFrame(recs)


def nozzle_plate_hole_display_df(rows: list[dict[str, Any]]) -> pd.DataFrame:
    """Nozzle-plate hole network for Backwash §6 (display units)."""
    if not rows:
        return pd.DataFrame()
    recs = []
    for r in rows:
        recs.append({
            "Row (across chord)": int(r.get("lateral_index", 0) or 0),
            "Hole": int(r.get("hole_index", 0) or 0),
            f"Station ({ulbl('length_m')})": fmt(float(r.get("station_m", 0)), "length_m", 2),
            f"Flow ({ulbl('flow_m3h')})": fmt(float(r.get("flow_m3h", 0)), "flow_m3h", 3),
            f"Velocity ({ulbl('velocity_m_s')})": fmt(float(r.get("velocity_m_s", 0)), "velocity_m_s", 2),
            f"Ø ({ulbl('length_mm')})": fmt(float(r.get("orifice_d_mm", 0)), "length_mm", 1),
        })
    return pd.DataFrame(recs)


def cycle_driver_decomposition_display_df(drivers: list[dict[str, Any]]) -> pd.DataFrame:
    """Human-readable columns for cycle uncertainty driver decomposition."""
    if not drivers:
        return pd.DataFrame()
    _th = ulbl("time_h")
    recs = []
    for d in drivers:
        recs.append({
            "Driver": str(d.get("driver", "—")),
            f"Cycle — optimistic only ({_th})": _fmt_cycle_h(d.get("cycle_optimistic_only_h")),
            f"Cycle — conservative only ({_th})": _fmt_cycle_h(d.get("cycle_conservative_only_h")),
            f"Δ vs expected — optimistic ({_th})": _fmt_cycle_h(d.get("delta_optimistic_h")),
            f"Δ vs expected — conservative ({_th})": _fmt_cycle_h(d.get("delta_conservative_h")),
            f"Swing ({_th})": _fmt_cycle_h(d.get("swing_h")),
            f"Impact rank (|swing|, {_th})": _fmt_cycle_h(d.get("rank_metric")),
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
