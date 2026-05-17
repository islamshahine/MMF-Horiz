"""ui/sidebar.py — Sidebar input rendering for AQUASIGHT™ MMF."""
import streamlit as st
from engine.water import water_properties, FEED_PRESETS, BW_PRESETS
from engine.media import get_media_names, get_media, get_lv_range, get_ebct_range, get_gac_note
from engine.units import (
    UNIT_SYSTEMS, display_value, si_value,
    unit_label, convert_inputs, format_value,
    SESSION_WIDGET_QUANTITIES, transpose_display_value,
)
from ui.compare_units import reconvert_compare_b_widgets
from ui.feed_pump_context_inputs import merge_feed_hydraulics_into_out
from ui.fouling_workflow import render_fouling_guided_workflow
from ui.scroll_markers import inject_anchor
from engine.default_media_presets import (
    DEFAULT_MEDIA_PRESETS,
    eps0_from_psi,
    rho_eff_porous,
)
from engine.project_io import AB_RFQ_SESSION_TO_QUANTITY

_GAC_MEDIA_NAMES = {"Medium GAC"}

def _reconvert_session_units(old: str, new: str) -> None:
    """Re-express unitised widget values when unit_system changes (same SI physics)."""
    if old == new:
        return
    for wkey, qty in SESSION_WIDGET_QUANTITIES.items():
        if wkey not in st.session_state:
            continue
        v = st.session_state[wkey]
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        nv = transpose_display_value(fv, qty, old, new)
        st.session_state[wkey] = int(round(nv)) if wkey == "fb_mm" else nv
    for wkey, qty in AB_RFQ_SESSION_TO_QUANTITY.items():
        if wkey not in st.session_state:
            continue
        v = st.session_state[wkey]
        if not isinstance(v, (int, float)):
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        st.session_state[wkey] = transpose_display_value(fv, qty, old, new)
    for wkey in list(st.session_state.keys()):
        if not isinstance(wkey, str):
            continue
        if wkey.startswith("ld_") and wkey[3:].isdigit():
            qty = "length_m"
        elif wkey.startswith("d10_") and wkey[4:].isdigit():
            qty = "length_mm"
        elif wkey.startswith("rhd_") and wkey[4:].isdigit():
            qty = "density_kg_m3"
        elif wkey.startswith("rh_") and wkey[3:].isdigit():
            qty = "density_kg_m3"
        else:
            continue
        if wkey not in st.session_state:
            continue
        v = st.session_state[wkey]
        if not isinstance(v, (int, float)):
            continue
        st.session_state[wkey] = transpose_display_value(float(v), qty, old, new)
    reconvert_compare_b_widgets(old, new)


def _apply_fouling_suggested_solid_loading() -> None:
    """Runs before the rest of the script on button click — safe to set solid_loading."""
    v = st.session_state.get("_fouling_last_sugg_disp")
    if v is not None:
        st.session_state["solid_loading"] = float(v)


def _clamp_layer_widget_session_mins(unit_system: str) -> None:
    """Streamlit keys override ``value=`` — clamp stale session_state before number_input."""
    _min_d10 = float(display_value(0.01, "length_mm", unit_system))
    _min_rho = float(display_value(100.0, "density_kg_m3", unit_system))
    for wkey in list(st.session_state.keys()):
        if not isinstance(wkey, str):
            continue
        v = st.session_state.get(wkey)
        if not isinstance(v, (int, float)):
            continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        if wkey.startswith("d10_") and wkey[4:].isdigit():
            st.session_state[wkey] = max(_min_d10, fv)
        elif wkey.startswith("rhd_") and wkey[4:].isdigit():
            st.session_state[wkey] = max(_min_rho, fv)
        elif wkey.startswith("rh_") and wkey[3:].isdigit():
            st.session_state[wkey] = max(_min_rho, fv)


def _ensure_presets():
    if ("media_presets" not in st.session_state or
            set(st.session_state.media_presets.keys()) != set(DEFAULT_MEDIA_PRESETS.keys())):
        st.session_state.media_presets = DEFAULT_MEDIA_PRESETS.copy()


def render_sidebar(
    MATERIALS, RADIOGRAPHY_OPTIONS, JOINT_EFFICIENCY, PROTECTION_TYPES,
    RUBBER_TYPES, EPOXY_TYPES, CERAMIC_TYPES,
    DEFAULT_LABOR_RUBBER_M2, DEFAULT_LABOR_EPOXY_M2, DEFAULT_LABOR_CERAMIC_M2,
    STEEL_DENSITY_KG_M3, FLANGE_RATINGS, STRAINER_WEIGHT_KG, MANHOLE_WEIGHT_KG,
    SUPPORT_TYPES, NOZZLE_DENSITY_DEFAULT,
    ELEMENT_SIZE_LABELS, RATING_UM_OPTIONS, HOUSING_CAPACITY_OPTIONS,
    DEFAULT_ELEMENTS_PER_HOUSING, SAFETY_FACTOR_CIP, SAFETY_FACTOR_STD,
    *,
    lightweight_duty_refresh: bool = False,
) -> dict:
    """Render all sidebar input tabs. Returns dict of every input value in SI."""
    _ensure_presets()
    out = {}

    if lightweight_duty_refresh:
        from ui.bw_duty_form import render_bw_duty_chart_form

        unit_system = st.session_state.get("unit_system", "metric")
        st.caption(
            "⚡ **Fast duty-chart refresh** — only settings below are active. "
            "Plant inputs are frozen until you change them elsewhere."
        )
        out = dict(st.session_state.get("mmf_last_inputs") or {})
        if not out:
            st.warning("No saved inputs — run a full pass with the input column visible first.")
        render_bw_duty_chart_form(out)
        merge_feed_hydraulics_into_out(out, unit_system)
        out = convert_inputs(out, unit_system)
        out["unit_system"] = unit_system
        return out

    # ── Unit system toggle ─────────────────────────────────────────────────
    _us_radio = st.session_state.get("unit_system")
    _unit_radio_idx = UNIT_SYSTEMS.index(_us_radio) if _us_radio in UNIT_SYSTEMS else 0
    unit_system = st.radio(
        "Unit system",
        UNIT_SYSTEMS,
        index=_unit_radio_idx,
        horizontal=True,
        key="unit_system",
        help="Metric: m³/h, bar, m, kg, °C  |  "
             "Imperial: gpm, psi, ft, lb, °F\n"
             "All internal calculations remain in SI.",
    )
    _prev_units = st.session_state.get("_prev_unit_system", unit_system)
    if unit_system != _prev_units:
        _reconvert_session_units(_prev_units, unit_system)
    st.session_state["_prev_unit_system"] = unit_system
    st.divider()
    st.caption(
        "**Sidebar = inputs** (what you change before **Apply**). **Main tabs** = **Filtration · Backwash · "
        "Mechanical · Media** = read-only **results** from the same inputs — edit here, review there."
    )

    proc_tab, vessel_tab, media_tab, bw_tab, econ_tab = st.tabs(
        ["⚙️ Process", "🏗️ Vessel", "🧱 Media", "🔄 BW", "💰 Econ"],
        key="mmf_sidebar_tabs",
    )

    # ── Tab 1: Process ────────────────────────────────────────────────────
    with proc_tab:
        inject_anchor("mmf-anchor-sb-process")
        st.caption(
            "**Process** — plant duty, water quality, **cartridge/CF** (below). **LV/EBCT** limits: **🧱 Media** tab. "
            "**Hydraulics & ΔP curves:** **💧 Filtration** & **🧱 Media** (main)."
        )
        st.markdown("**Project**")
        out["project_name"] = st.text_input("Project",     value="NPC SWRO 60 000 m³/d", key="project_name")
        out["doc_number"]   = st.text_input("Doc. No.",    value="EXXXX-VWT-PCS-CAL-2001", key="doc_number")
        out["revision"]     = st.text_input("Revision",    value="A1",             key="revision")
        out["client"]       = st.text_input("Client",      value="",               key="client")
        out["engineer"]     = st.text_input("Prepared by", value="Islam Shahine",  key="engineer")

        st.markdown("**Filter configuration**")
        _lbl_flow = f"Total plant flow ({unit_label('flow_m3h', unit_system)})"
        _def_flow = display_value(21000.0, "flow_m3h", unit_system)
        _stp_flow = display_value(100.0, "flow_m3h", unit_system)
        out["total_flow"] = st.number_input(_lbl_flow, value=_def_flow, step=_stp_flow, key="total_flow")
        out["streams"]    = int(st.number_input("Streams", value=1, min_value=1, key="streams"))
        out["n_filters"]  = int(st.number_input(
            "Total physical number of filters / stream",
            value=16,
            min_value=1,
            key="n_filters",
        ))
        if "hydraulic_assist" not in st.session_state:
            st.session_state["hydraulic_assist"] = 0
        out["hydraulic_assist"] = int(st.selectbox(
            "Standby filters (physical / stream)",
            options=[0, 1, 2, 3, 4],
            format_func=lambda k: (
                "0 — no spare (all installed in hydraulic N)"
                if k == 0
                else f"{k} spare(s) — design N = installed − {k} (N+{k} bank)"
            ),
            key="hydraulic_assist",
        ))
        _n_design_raw = int(out["n_filters"]) - int(out["hydraulic_assist"])
        # Drive display from session_state: fixed key + value= is stale after first run.
        st.session_state["sidebar_n_design_display"] = str(_n_design_raw)
        st.text_input(
            "Calculated N filters / stream",
            disabled=True,
            key="sidebar_n_design_display",
            help=(
                "Total physical number of filters / stream minus "
                "Standby filters (physical / stream). "
                "This is design **N** for flow / filter (hydraulics use max(1, N) if invalid)."
            ),
        )
        out["redundancy"] = int(st.selectbox(
            "Outage depth modelled (per stream)",
            [0, 1, 2, 3, 4],
            index=1,
            key="redundancy",
            help="Hydraulic rows N, N-1, … for this many **extra** installed units offline "
            "(beyond standby). Standby filters are excluded from design N but remain on the BW chart.",
        ))
        _tf_si = si_value(out["total_flow"], "flow_m3h", unit_system)
        _n_design = max(1, out["n_filters"] - out["hydraulic_assist"])
        q_n_si = _tf_si / out["streams"] / max(_n_design, 1)
        q_n_disp = display_value(q_n_si, "flow_m3h", unit_system)
        st.caption(
            f"Flow / filter (**design N** = **{_n_design}** paths/stream): **{q_n_disp:.1f} "
            f"{unit_label('flow_m3h', unit_system)}**  \n"
            f"Physical installed / stream: **{out['n_filters']}** (BW duty chart rows)  \n"
            f"Standby (not in hydraulic N): **{out['hydraulic_assist']}** · "
            f"outage levels modelled: **{out['redundancy']}**  \n"
            f"Total physical plant-wide: **{out['streams'] * out['n_filters']}**"
        )

        st.markdown("**Water quality — feed**")
        feed_preset = st.selectbox("Feed preset", list(FEED_PRESETS.keys()), index=2, key="feed_pre")
        fp = FEED_PRESETS[feed_preset]
        out["feed_sal"]  = st.number_input("Feed salinity (ppt)",    value=fp["salinity_ppt"], step=0.5, key="f_sal")
        _lbl_ft = f"Feed temp — avg ({unit_label('temperature_c', unit_system)})"
        _def_ft = display_value(fp["temp_c"], "temperature_c", unit_system)
        out["feed_temp"] = st.number_input(_lbl_ft, value=_def_ft, step=1.0, key="f_tmp")
        _lbl_tlo = f"Feed temp — min ({unit_label('temperature_c', unit_system)})"
        _def_tlo = display_value(15.0, "temperature_c", unit_system)
        out["temp_low"]  = st.number_input(_lbl_tlo, value=_def_tlo, step=1.0, key="t_low")
        _lbl_thi = f"Feed temp — max ({unit_label('temperature_c', unit_system)})"
        _def_thi = display_value(35.0, "temperature_c", unit_system)
        out["temp_high"] = st.number_input(_lbl_thi, value=_def_thi, step=1.0, key="t_high")
        out["tss_low"]   = st.number_input("Feed TSS — low (mg/L)",  value=5.0,  step=1.0, key="tss_low")
        out["tss_avg"]   = st.number_input("Feed TSS — avg (mg/L)",  value=10.0, step=1.0, key="tss_avg")
        out["tss_high"]  = st.number_input("Feed TSS — high (mg/L)", value=20.0, step=1.0, key="tss_high")

        st.markdown("**Water quality — backwash**")
        bw_preset = st.selectbox("BW preset", list(BW_PRESETS.keys()), index=0, key="bw_pre")
        bp = BW_PRESETS[bw_preset] or fp
        out["bw_sal"]  = st.number_input("BW salinity (ppt)", value=bp["salinity_ppt"], step=0.5, key="b_sal")
        _lbl_bwt = f"BW temp ({unit_label('temperature_c', unit_system)})"
        _def_bwt = display_value(bp["temp_c"], "temperature_c", unit_system)
        out["bw_temp"] = st.number_input(_lbl_bwt, value=_def_bwt, step=1.0, key="b_tmp")

        st.markdown("**Performance thresholds**")
        st.caption(
            "**Max LV** and **min EBCT** setpoints are defined **per media layer** "
            "in the **Media** tab (with each layer). Support layers show read-only N/A."
        )
        inject_anchor("mmf-anchor-sb-process-cartridge")
        with st.expander("Cartridge & solids calibration", expanded=False):
            out["cart_flow"]   = st.number_input(
                f"Design flow ({unit_label('flow_m3h', unit_system)})",
                value=float(out["total_flow"]),
                step=_stp_flow, key="cart_flow",
            )
            out["cart_size"]   = st.selectbox("Element length", ELEMENT_SIZE_LABELS, index=2, key="cart_size")
            out["cart_rating"] = st.selectbox("Rating (μm absolute)", RATING_UM_OPTIONS, index=1, key="cart_rating")
            out["cart_cip"]    = st.toggle("CIP system (SS 316L elements)", value=False, key="cart_cip")
            _hsg_options     = [str(r) for r in HOUSING_CAPACITY_OPTIONS] + ["Custom…"]
            _hsg_default_idx = HOUSING_CAPACITY_OPTIONS.index(DEFAULT_ELEMENTS_PER_HOUSING)
            cart_hsg_sel = st.selectbox("Elements per housing", _hsg_options, index=_hsg_default_idx, key="cart_hsg_sel")
            if cart_hsg_sel == "Custom…":
                out["cart_housing"] = st.number_input("Custom elements per housing",
                                                       min_value=1, max_value=500, value=100, step=1, key="cart_hsg_custom")
            else:
                out["cart_housing"] = int(cart_hsg_sel)
            _use_vendor_dhc = st.toggle(
                "Vendor DHC override (g/element)",
                value=False,
                key="cart_dhc_vendor",
                help=(
                    "By default, element life uses the built-in **g/TIE × rating** curve. "
                    "Enable to enter **total dirt-hold per element** from a supplier datasheet; "
                    "clean/EOL ΔP still follows the vendor quadratic flow curves."
                ),
            )
            if _use_vendor_dhc:
                out["cart_dhc_override_g"] = float(st.number_input(
                    "DHC per element (g)",
                    min_value=1.0, max_value=8000.0, value=180.0, step=5.0, format="%.0f",
                    key="cart_dhc_override_g",
                ))
            else:
                out["cart_dhc_override_g"] = 0.0
            _tss_lo = float(out["tss_low"])
            _tss_md = float(out["tss_avg"])
            _tss_hi = max(_tss_lo, _tss_md, float(out["tss_high"]))
            out["cf_sync_feed_tss"] = st.toggle(
                "Sync CF inlet TSS from MMF feed scenario",
                value=False,
                key="cf_sync_feed_tss",
                help=(
                    "When enabled, CF inlet (MMF effluent basis for cartridge loading) follows the "
                    "same **low / average / high** feed TSS band as the BW solids scenarios. "
                    "Turn off to enter CF inlet manually (still capped at the highest feed TSS)."
                ),
            )
            _band_opts = ("low", "avg", "high")
            _band_fmt = {"low": "Low", "avg": "Average", "high": "High"}
            if out["cf_sync_feed_tss"]:
                _sb0 = str(st.session_state.get("cf_sync_tss_band", "avg"))
                if _sb0 not in _band_opts:
                    _sb0 = "avg"
                out["cf_sync_tss_band"] = st.radio(
                    "CF inlet matches feed TSS",
                    options=_band_opts,
                    format_func=lambda k: _band_fmt[str(k)],
                    index=_band_opts.index(_sb0),
                    horizontal=True,
                    key="cf_sync_tss_band",
                )
                _bind = float(out[f"tss_{out['cf_sync_tss_band']}"])
                out["cf_inlet_tss"] = _bind
                _cf_inlet_max = _bind
                _cf_outlet_max = round(0.15 * _bind, 4)
                st.caption(
                    f"CF inlet = **{_bind:.2f} mg/L** (feed {_band_fmt[out['cf_sync_tss_band']].lower()}). "
                    f"Outlet target ≤ **{_cf_outlet_max:.2f} mg/L** (15 % of that inlet)."
                )
                if "cf_outlet_tss" in st.session_state:
                    st.session_state["cf_outlet_tss"] = min(
                        float(st.session_state["cf_outlet_tss"]), float(_cf_outlet_max),
                    )
                out["cf_outlet_tss"] = st.number_input(
                    "CF outlet TSS — target (mg/L)", min_value=0.0,
                    max_value=float(_cf_outlet_max),
                    value=min(0.5, float(_cf_outlet_max)), step=0.05,
                    format="%.2f", key="cf_outlet_tss",
                )
            else:
                out["cf_sync_tss_band"] = str(st.session_state.get("cf_sync_tss_band", "avg"))
                if out["cf_sync_tss_band"] not in _band_opts:
                    out["cf_sync_tss_band"] = "avg"
                _cf_inlet_max = _tss_hi
                _cf_outlet_max = round(0.15 * _cf_inlet_max, 4)
                if "cf_inlet_tss" in st.session_state:
                    st.session_state["cf_inlet_tss"] = min(
                        float(st.session_state["cf_inlet_tss"]), float(_cf_inlet_max),
                    )
                if "cf_outlet_tss" in st.session_state:
                    st.session_state["cf_outlet_tss"] = min(
                        float(st.session_state["cf_outlet_tss"]), float(_cf_outlet_max),
                    )
                out["cf_inlet_tss"] = st.number_input(
                    "CF inlet TSS (mg/L)", min_value=0.0,
                    max_value=float(_cf_inlet_max),
                    value=min(2.0, float(_cf_inlet_max)), step=0.1,
                    format="%.2f", key="cf_inlet_tss",
                    help="MMF effluent basis — capped at the **highest** of low / avg / high feed TSS.",
                )
                out["cf_outlet_tss"] = st.number_input(
                    "CF outlet TSS — target (mg/L)", min_value=0.0,
                    max_value=float(_cf_outlet_max),
                    value=min(0.5, float(_cf_outlet_max)), step=0.05,
                    format="%.2f", key="cf_outlet_tss",
                )

    # ── Tab 2: Vessel ─────────────────────────────────────────────────────
    with vessel_tab:
        inject_anchor("mmf-anchor-sb-vessel")
        st.caption(
            "**Vessel** — geometry, ASME design, lining, environment. **Thicknesses, weights, nozzles, drawing:** "
            "main **⚙️ Mechanical** tab (read-only from these inputs)."
        )
        st.markdown("**Vessel geometry**")
        _lbl_id = f"Nominal internal diameter ({unit_label('length_m', unit_system)})"
        _def_id = display_value(5.5, "length_m", unit_system)
        _stp_id = display_value(0.1, "length_m", unit_system)
        out["nominal_id"]   = st.number_input(_lbl_id, value=_def_id, step=_stp_id, key="nominal_id")
        _lbl_tl = f"Total length T/T ({unit_label('length_m', unit_system)})"
        _def_tl = display_value(24.3, "length_m", unit_system)
        out["total_length"] = st.number_input(_lbl_tl, value=_def_tl, step=_stp_id, key="total_length")
        out["end_geometry"] = st.selectbox("End geometry", ["Elliptic 2:1", "Torispherical 10%"], key="end_geometry")

        st.markdown("**Mechanical (ASME)**")
        out["material_name"]   = st.selectbox("Material", list(MATERIALS.keys()), index=3, key="material_name")
        mat_info               = MATERIALS[out["material_name"]]
        out["mat_info"]        = mat_info
        st.caption(f"*{mat_info['description']}*")
        _lbl_dp = f"Design pressure ({unit_label('pressure_bar', unit_system)})"
        _def_dp = display_value(7.0, "pressure_bar", unit_system)
        _stp_dp = display_value(0.5, "pressure_bar", unit_system)
        out["design_pressure"] = st.number_input(_lbl_dp, value=_def_dp, step=_stp_dp, key="design_pressure")
        _lbl_dt = f"Design temperature ({unit_label('temperature_c', unit_system)})"
        _def_dt = display_value(50.0, "temperature_c", unit_system)
        out["design_temp"]     = st.number_input(_lbl_dt, value=_def_dt, step=5.0, key="design_temp")
        _lbl_ca = f"Corrosion allowance ({unit_label('length_mm', unit_system)})"
        _def_ca = display_value(1.5, "length_mm", unit_system)
        _stp_ca = display_value(0.5, "length_mm", unit_system)
        out["corrosion"]       = st.number_input(_lbl_ca, value=_def_ca, step=_stp_ca, key="corrosion")
        st.markdown("*Radiography (ASME UW-11)*")
        rc1, rc2 = st.columns(2)
        with rc1:
            out["shell_radio"] = st.selectbox("Shell", RADIOGRAPHY_OPTIONS, index=2, key="sh_r")
            st.caption(f"E = {JOINT_EFFICIENCY[out['shell_radio']]:.2f}")
        with rc2:
            out["head_radio"]  = st.selectbox("Head",  RADIOGRAPHY_OPTIONS, index=2, key="hd_r")
            st.caption(f"E = {JOINT_EFFICIENCY[out['head_radio']]:.2f}")
        st.markdown("*Thickness overrides* (**0** = use ASME-calculated thickness)")
        _lbl_ov_sh = f"Shell t override ({unit_label('length_mm', unit_system)})"
        _def_ov = float(display_value(0.0, "length_mm", unit_system))
        _stp_ov = float(display_value(1.0, "length_mm", unit_system))
        out["ov_shell"]     = st.number_input(
            _lbl_ov_sh,
            value=_def_ov,
            step=_stp_ov,
            key="ov_sh",
            help=(
                "0 — use calculated shell thickness from ASME VIII-1. Non-zero — force this thickness "
                f"({unit_label('length_mm', unit_system)})."
            ),
        )
        _lbl_ov_hd = f"Head t override ({unit_label('length_mm', unit_system)})"
        out["ov_head"]      = st.number_input(
            _lbl_ov_hd,
            value=_def_ov,
            step=_stp_ov,
            key="ov_hd",
            help=(
                "0 — use calculated head thickness from ASME VIII-1. Non-zero — force this thickness "
                f"({unit_label('length_mm', unit_system)})."
            ),
        )
        _lbl_sd = f"Steel density ({unit_label('density_kg_m3', unit_system)})"
        _def_sd = display_value(float(STEEL_DENSITY_KG_M3), "density_kg_m3", unit_system)
        out["steel_density"]= st.number_input(_lbl_sd, value=_def_sd, key="steel_density")

        st.markdown("**Internal protection**")
        out["protection_type"] = st.selectbox("Protection type", PROTECTION_TYPES, index=1, key="prot_type")

        if out["protection_type"] == "Rubber lining":
            out["rubber_type_sel"] = st.selectbox("Rubber type", list(RUBBER_TYPES.keys()), index=1, key="rub_type")
            _lbl_rub = f"Rubber thickness / layer ({unit_label('length_mm', unit_system)})"
            _def_rub = display_value(4.0, "length_mm", unit_system)
            _stp_rub = display_value(0.5, "length_mm", unit_system)
            out["lining_mm"]       = st.number_input(_lbl_rub, value=_def_rub, step=_stp_rub,
                                                      min_value=float(display_value(0.5, "length_mm", unit_system)), key="rub_t")
            out["rubber_layers"]   = st.number_input("Layers", value=2, min_value=1, max_value=6, key="rub_lay")
            _rub_def_cost          = RUBBER_TYPES[out["rubber_type_sel"]]["default_cost_m2"]
            out["rubber_cost_m2"]  = st.number_input("Rubber material cost (USD/m²)", value=float(_rub_def_cost),
                                                      step=5.0, key="rub_cost")
            out["rubber_labor_m2"] = st.number_input("Application labour (USD/m²)", value=DEFAULT_LABOR_RUBBER_M2,
                                                      step=5.0, key="rub_lab")
        else:
            out["lining_mm"] = 0.0; out["rubber_type_sel"] = "EPDM"; out["rubber_layers"] = 2
            out["rubber_cost_m2"] = 0.0; out["rubber_labor_m2"] = DEFAULT_LABOR_RUBBER_M2

        if out["protection_type"] == "Epoxy coating":
            out["epoxy_type_sel"]  = st.selectbox("Epoxy type", list(EPOXY_TYPES.keys()), index=1, key="epx_type")
            _epx_cat               = EPOXY_TYPES[out["epoxy_type_sel"]]
            out["epoxy_dft_um"]    = st.number_input("DFT per coat (µm)", value=float(_epx_cat["default_dft_um"]),
                                                      step=25.0, min_value=50.0, key="epx_dft")
            out["epoxy_coats"]     = st.number_input("Number of coats", value=_epx_cat["default_coats"],
                                                      min_value=1, max_value=6, key="epx_coats")
            out["epoxy_cost_m2"]   = st.number_input("Epoxy material cost (USD/m²)",
                                                      value=float(_epx_cat["default_cost_m2"]),
                                                      step=2.0, key="epx_cost")
            out["epoxy_labor_m2"]  = st.number_input("Application labour (USD/m²)",
                                                      value=DEFAULT_LABOR_EPOXY_M2, step=2.0, key="epx_lab")
        else:
            out["epoxy_type_sel"] = "High-build epoxy"; out["epoxy_dft_um"] = 350.0
            out["epoxy_coats"] = 2; out["epoxy_cost_m2"] = 0.0; out["epoxy_labor_m2"] = DEFAULT_LABOR_EPOXY_M2

        if out["protection_type"] == "Ceramic coating":
            out["ceramic_type_sel"]  = st.selectbox("Ceramic type", list(CERAMIC_TYPES.keys()), index=0, key="cer_type")
            _cer_cat                 = CERAMIC_TYPES[out["ceramic_type_sel"]]
            cc1, cc2                 = st.columns(2)
            out["ceramic_dft_um"]    = cc1.number_input("DFT / coat (µm)", value=float(_cer_cat["default_dft_um"]),
                                                         step=50.0, min_value=100.0, key="cer_dft")
            out["ceramic_coats"]     = int(cc2.number_input("Coats", value=int(_cer_cat["default_coats"]),
                                                              step=1, min_value=1, max_value=6, key="cer_coats"))
            out["ceramic_cost_m2"]   = st.number_input("Ceramic material cost (USD/m²)",
                                                        value=float(_cer_cat["default_cost_m2"]),
                                                        step=10.0, key="cer_cost")
            out["ceramic_labor_m2"]  = st.number_input("Application labour (USD/m²)",
                                                        value=DEFAULT_LABOR_CERAMIC_M2, step=5.0, key="cer_lab")
        else:
            out["ceramic_type_sel"] = "Ceramic-filled epoxy"
            out["ceramic_dft_um"] = 500.0; out["ceramic_coats"] = 2
            out["ceramic_cost_m2"] = 0.0; out["ceramic_labor_m2"] = DEFAULT_LABOR_CERAMIC_M2

        st.markdown("**External environment & structural loads**")
        out["external_environment"] = st.selectbox(
            "External atmosphere (outside painting)",
            [
                "Non-marine (industrial / inland)",
                "Marine / coastal (aggressive external)",
            ],
            index=0,
            key="ext_env",
        )
        st.caption(
            "Sets the **external** paint philosophy (ISO 12944 corrosivity band). "
            "Internal protection remains under *Internal protection* above."
        )
        eq1, eq2 = st.columns(2)
        with eq1:
            out["seismic_design_category"] = st.selectbox(
                "Seismic design category (SDC)",
                [
                    "Not evaluated",
                    "SDC A",
                    "SDC B",
                    "SDC C",
                    "SDC D",
                    "SDC E",
                    "SDC F",
                ],
                index=0,
                key="sdc_sel",
            )
            out["seismic_importance_factor"] = st.number_input(
                "Seismic importance factor Ie",
                min_value=0.5,
                max_value=1.5,
                value=1.0,
                step=0.05,
                format="%.2f",
                key="Ie_seismic",
                help="Per IBC risk category (Table 1.5-2). Typical Category II → Ie = 1.0.",
            )
        with eq2:
            out["spectral_accel_sds"] = st.number_input(
                "S_DS (short-period spectral accel., g)",
                min_value=0.0,
                max_value=3.0,
                value=0.0,
                step=0.05,
                format="%.2f",
                key="sds_inp",
                help="From site hazard / geotech; leave 0 if seismic not in scope.",
            )
            out["site_class_asce"] = st.selectbox(
                "Site class (ASCE 7)",
                ["A", "B", "C", "D", "E", "F"],
                index=1,
                key="site_cl",
            )
        wn1, wn2 = st.columns(2)
        with wn1:
            _lbl_wv = f"Basic wind speed — 3 s gust ({unit_label('velocity_m_s', unit_system)})"
            _def_wv = display_value(40.0, "velocity_m_s", unit_system)
            _stp_wv = display_value(2.0, "velocity_m_s", unit_system)
            out["basic_wind_ms"] = st.number_input(
                _lbl_wv,
                value=_def_wv,
                step=_stp_wv,
                min_value=0.0,
                key="basic_wind_ms",
                help="Ultimate wind speed for structural loads; use 0 to omit from summary.",
            )
        with wn2:
            out["wind_exposure"] = st.selectbox(
                "Wind exposure category (ASCE 7)",
                ["B", "C", "D"],
                index=1,
                key="wind_exp",
                help="B — urban/suburban, C — open, D — flat/coastal open.",
            )

    # ── Tab 3: Media ──────────────────────────────────────────────────────
    with media_tab:
        inject_anchor("mmf-anchor-sb-media")
        st.caption(
            "**Media** — nozzle plate, **layer stack** (bottom→top), **M_max / α / fouling** (below). "
            "**Volumes, ΔP tables, inventory:** main **🧱 Media** tab. **Filtration cycles & scenarios:** **💧 Filtration**."
        )
        inject_anchor("mmf-anchor-sb-media-nozzle")
        from ui.nozzle_catalogue_ui import render_underdrain_media_sidebar

        out = render_underdrain_media_sidebar(
            out, unit_system, nozzle_density_default=NOZZLE_DENSITY_DEFAULT,
        )

        inject_anchor("mmf-anchor-sb-media-layers")
        st.markdown("**Media layers**")
        out["n_layers"] = int(st.selectbox("Layers", [1, 2, 3, 4, 5, 6], index=2, key="n_layers"))
        # Normalize capture weights on the *next* run only, and only before cap_* widgets
        # exist — Streamlit forbids assigning session_state keys that are already bound to
        # widgets instantiated earlier in the same script run.
        if st.session_state.pop("_pending_normalize_cap_weights", False):
            _nl = out["n_layers"]

            def _layer_is_support_sb(idx: int) -> bool:
                if f"sup_{idx}" in st.session_state:
                    return bool(st.session_state[f"sup_{idx}"])
                return str(st.session_state.get(f"lt_{idx}", "")).strip() == "Gravel"

            _idx_ns = [i for i in range(_nl) if not _layer_is_support_sb(i)]
            _raw = [float(st.session_state.get(f"cap_{i}", 0.0)) for i in _idx_ns]
            _tot = sum(_raw) or 1.0
            for i, v in zip(_idx_ns, _raw):
                st.session_state[f"cap_{i}"] = round(
                    max(0.0, min(100.0, v / _tot * 100.0)), 2
                )
        # Convert feed_temp display value back to SI for internal engine call
        _feed_temp_si   = si_value(out["feed_temp"], "temperature_c", unit_system)
        _rho_water_sb   = water_properties(_feed_temp_si, out["feed_sal"])["density_kg_m3"]
        layers = []
        default_types = ["Gravel", "Fine sand", "Anthracite"]
        _clamp_layer_widget_session_mins(unit_system)
        # dp_trigger can be 0 in stale session_state while min is > 0 in display units
        if "dp_trig" in st.session_state and isinstance(st.session_state["dp_trig"], (int, float)):
            _min_dp = float(display_value(0.01, "pressure_bar", unit_system))
            st.session_state["dp_trig"] = max(_min_dp, float(st.session_state["dp_trig"]))
        for i in range(out["n_layers"]):
            st.markdown(f"**Layer {i+1}** (bottom → top)")
            def_type = default_types[i] if i < 3 else "Custom"
            preset_keys = list(st.session_state.media_presets.keys())
            m_type = st.selectbox("Type", preset_keys,
                                  index=preset_keys.index(def_type),
                                  key=f"lt_{i}")
            preset = st.session_state.media_presets[m_type]
            _lbl_dep = f"Depth ({unit_label('length_m', unit_system)})"
            _def_dep = display_value(preset["default_depth"], "length_m", unit_system)
            _stp_dep = display_value(0.05, "length_m", unit_system)
            depth  = st.number_input(_lbl_dep, value=_def_dep, step=_stp_dep, key=f"ld_{i}")
            _depth_si = si_value(depth, "length_m", unit_system)
            is_sup = st.checkbox("Support media (no clogging)",
                                 value=(m_type == "Gravel"), key=f"sup_{i}")
            if not is_sup:
                cap_raw  = st.number_input(
                    "Capture weight (% of filterable total)",
                    value=round(_depth_si * 100, 0),
                    step=5.0, min_value=0.0, max_value=100.0, key=f"cap_{i}",
                    help="Share of **filterable** (non-support) cake load for this layer. "
                         "All filterable layers should sum to **100%**.",
                )
                cap_frac = cap_raw / 100.0
            else:
                cap_frac = 0.0

            # GAC mode selectbox for GAC media
            gac_mode = None
            if m_type in _GAC_MEDIA_NAMES:
                _db_entry = get_media(m_type)
                if _db_entry.get("gac_modes"):
                    gac_mode = st.selectbox("GAC operating mode",
                                            list(_db_entry["gac_modes"].keys()),
                                            key=f"gac_mode_{i}")
                    _note = get_gac_note(m_type, gac_mode)
                    if _note:
                        st.caption(f"ℹ️ {_note}")

            # Engineering guidance envelope caption for non-support layers
            if not is_sup:
                _lv_lo, _lv_hi = get_lv_range(m_type, gac_mode)
                _eb_lo, _eb_hi = get_ebct_range(m_type, gac_mode)
                if _lv_lo is not None:
                    st.caption(
                        f"Envelope — LV: "
                        f"{format_value(float(_lv_lo), 'velocity_m_h', unit_system, 1)}–"
                        f"{format_value(float(_lv_hi), 'velocity_m_h', unit_system, 1)} · "
                        f"EBCT: {_eb_lo}–{_eb_hi} min"
                    )
                _thr_c1, _thr_c2 = st.columns(2)
                _def_lv_thr = float(_lv_hi) if _lv_hi is not None else 12.0
                _def_eb_thr = float(_eb_lo) if _eb_lo is not None else 5.0
                _lbl_lv_thr = f"Max LV setpoint ({unit_label('velocity_m_h', unit_system)})"
                _lbl_eb_thr = "Min EBCT setpoint (min)"
                _stp_lv_thr = display_value(0.5, "velocity_m_h", unit_system)
                with _thr_c1:
                    _lv_thr_disp = st.number_input(
                        _lbl_lv_thr,
                        value=display_value(_def_lv_thr, "velocity_m_h", unit_system),
                        step=float(_stp_lv_thr),
                        min_value=0.0,
                        key=f"lv_thr_{i}",
                        help="Upper limit for superficial velocity in this layer (envelope check).",
                    )
                with _thr_c2:
                    _eb_thr_disp = st.number_input(
                        _lbl_eb_thr,
                        value=_def_eb_thr,
                        step=0.25,
                        min_value=0.0,
                        key=f"ebct_thr_{i}",
                        help="Lower limit for EBCT in this layer (minutes).",
                    )
                _lv_thr_val, _eb_thr_val = _lv_thr_disp, _eb_thr_disp
            else:
                _thr_c1, _thr_c2 = st.columns(2)
                with _thr_c1:
                    st.text_input(
                        f"Max LV setpoint ({unit_label('velocity_m_h', unit_system)})",
                        value="— support layer (N/A)",
                        disabled=True,
                        key=f"lv_thr_sup_{i}",
                    )
                with _thr_c2:
                    st.text_input(
                        "Min EBCT setpoint (min)",
                        value="— support layer (N/A)",
                        disabled=True,
                        key=f"ebct_thr_sup_{i}",
                    )
                _lv_thr_val, _eb_thr_val = None, None

            data = preset.copy()
            if m_type == "Custom":
                _c1, _c2 = st.columns(2)
                _lbl_d10 = f"d10 ({unit_label('length_mm', unit_system)})"
                _d10_disp = _c1.number_input(
                    _lbl_d10,
                    value=float(display_value(float(preset.get("d10", 1.0)), "length_mm", unit_system)),
                    step=float(display_value(0.05, "length_mm", unit_system)),
                    min_value=float(display_value(0.01, "length_mm", unit_system)),
                    key=f"d10_{i}",
                )
                _cu   = _c2.number_input("CU (d60/d10)", value=1.5, step=0.05,
                                         min_value=1.0, key=f"cu_{i}")
                _psi  = _c1.number_input("Sphericity ψ", value=0.80, step=0.05,
                                         min_value=0.3, max_value=1.0, key=f"psi_{i}")
                _eps0_est = eps0_from_psi(_psi)
                _eps0 = _c2.number_input("Voidage ε₀", value=_eps0_est, step=0.01,
                                         min_value=0.25, max_value=0.70, key=f"ep_{i}")
                _is_por = st.checkbox("Porous media (water fills particle pores)",
                                      value=False, key=f"por_{i}")
                if _is_por:
                    _p1, _p2 = st.columns(2)
                    _lbl_rho_dry = f"Dry apparent density ({unit_label('density_kg_m3', unit_system)})"
                    _rho_dry_disp = _p1.number_input(
                        _lbl_rho_dry,
                        value=float(display_value(500.0, "density_kg_m3", unit_system)),
                        step=float(display_value(50.0, "density_kg_m3", unit_system)),
                        min_value=float(display_value(100.0, "density_kg_m3", unit_system)),
                        key=f"rhd_{i}",
                    )
                    _rho_dry_si = float(si_value(_rho_dry_disp, "density_kg_m3", unit_system))
                    _eps_p   = _p2.number_input("Particle internal porosity εₚ", value=0.50,
                                                 step=0.05, min_value=0.0, max_value=0.95, key=f"epp_{i}")
                    _rho_eff = rho_eff_porous(_rho_dry_si, _eps_p, _rho_water_sb)
                    st.caption(f"ρ_eff = {format_value(_rho_eff, 'density_kg_m3', unit_system, 0)}")
                else:
                    _lbl_rho_p = f"Particle density ({unit_label('density_kg_m3', unit_system)})"
                    _rho_disp = st.number_input(
                        _lbl_rho_p,
                        value=float(display_value(2650.0, "density_kg_m3", unit_system)),
                        step=float(display_value(50.0, "density_kg_m3", unit_system)),
                        min_value=float(display_value(100.0, "density_kg_m3", unit_system)),
                        key=f"rh_{i}",
                    )
                    _rho_eff = float(si_value(_rho_disp, "density_kg_m3", unit_system))
                data["d10"]       = float(si_value(_d10_disp, "length_mm", unit_system))
                data["cu"]        = _cu
                data["d60"]       = round(data["d10"] * _cu, 3)
                data["epsilon0"]  = _eps0
                data["psi"]       = _psi
                data["is_porous"] = _is_por
                data["rho_p_eff"] = round(_rho_eff, 1)
            layers.append({**data, "Type": m_type, "Depth": depth,
                           "is_support": is_sup, "capture_frac": cap_frac,
                           "gac_mode": gac_mode,
                           "lv_threshold_m_h": _lv_thr_val,
                           "ebct_threshold_min": _eb_thr_val})
        out["layers"] = layers

        _cap_sum_pct = sum(
            float(l.get("capture_frac", 0.0) or 0.0) * 100.0
            for l in layers if not l.get("is_support")
        )
        if any(not l.get("is_support") for l in layers):
            st.caption(
                f"**Filterable capture weights Σ = {_cap_sum_pct:.1f}%** — target **100%** "
                "for a literal percentage split on cake ΔP distribution."
            )
            if abs(_cap_sum_pct - 100.0) > 0.51:
                st.warning(
                    f"Capture weights sum to **{_cap_sum_pct:.1f}%**, not 100%. "
                    "The engine **normalises** to relative weights for ΔP/cake. "
                    "Use **Normalize to 100%** to scale filterable entries proportionally."
                )
            if st.button("Normalize capture weights to 100%", type="secondary", key="norm_cap_weights"):
                st.session_state["_pending_normalize_cap_weights"] = True
                st.rerun()

        inject_anchor("mmf-anchor-sb-media-mmax")
        st.markdown("**Filtration performance**")
        _lbl_sl = f"Solid loading before BW ({unit_label('loading_kg_m2', unit_system)})"
        _def_sl = display_value(1.5, "loading_kg_m2", unit_system)
        _stp_sl = display_value(0.1, "loading_kg_m2", unit_system)
        out["solid_loading"]          = st.number_input(_lbl_sl, value=_def_sl, step=_stp_sl, key="solid_loading")

        with st.expander("Monte Carlo lite (optional)", expanded=False):
            st.caption(
                "Enable sampling and view the histogram on the **💧 Filtration** tab → "
                "*Monte Carlo lite — optional cycle sampling*. Press **Apply** after toggling."
            )

        with st.expander("Calibration, fouling assistant & cake resistance (α)", expanded=False):
            with st.expander("Advanced — pilot / field calibration factors", expanded=False):
                st.caption(
                    "**M_max scale** scales the solids inventory used in ΔP dirty and BW trigger math "
                    "(not the label value above). **Maldistribution (≥1)** inflates superficial velocity for "
                    "Ergun + cake (distributor / wall effects). **α factor** scales cake resistance after "
                    "auto or user α. **TSS capture** is the fraction of feed TSS assumed to deposit for cycle-time "
                    "estimates. **Expansion scale** adjusts R–Z expanded bed height increment (pilot vs correlation)."
                )
                _c1a, _c2a = st.columns(2)
                with _c1a:
                    out["solid_loading_scale"] = st.number_input(
                        "M_max scale (−)", value=1.0, min_value=0.5, max_value=1.5, step=0.05,
                        key="solid_loading_scale",
                    )
                    out["use_calculated_maldistribution"] = st.checkbox(
                        "Link filtration mal factor to 1D underdrain distribution",
                        value=bool(st.session_state.get("use_calculated_maldistribution", False)),
                        key="use_calculated_maldistribution",
                        help=(
                            "When enabled, **filtration** Ergun / cake use the **1D distribution factor** "
                            "(max/mean flow) from the 1D screening solve. "
                            "Your **nozzle plate** is defined in **🧱 Media**; this link is approximate until "
                            "nozzle-plate hydraulics are added. Not §4 shell BW/air nozzles."
                        ),
                    )
                    out["maldistribution_factor"] = st.number_input(
                        "Filtration maldistribution factor (≥1) — manual",
                        value=1.0, min_value=1.0, max_value=2.0, step=0.05,
                        key="maldistribution_factor",
                        disabled=bool(out.get("use_calculated_maldistribution")),
                        help="Plant-wide fouling velocity multiplier. Ignored when linked to 1D underdrain distribution.",
                    )
                with _c2a:
                    out["alpha_calibration_factor"] = st.number_input(
                        "α calibration factor (−)", value=1.0, min_value=0.3, max_value=3.0, step=0.05,
                        key="alpha_calibration_factor",
                    )
                    out["tss_capture_efficiency"] = st.number_input(
                        "TSS capture efficiency (0–1)", value=1.0, min_value=0.0, max_value=1.0, step=0.05,
                        key="tss_capture_efficiency",
                    )
                out["expansion_calibration_scale"] = st.number_input(
                    "BW expansion increment scale (0.5–1.5)", value=1.0, min_value=0.5, max_value=1.5, step=0.05,
                    key="expansion_calibration_scale",
                    help="Scales only the **expanded height increment** above settled depth per layer (1 = model).",
                )
            with st.expander("Fouling assistant — guided workflow (SDI / MFI → M_max)", expanded=False):
                render_fouling_guided_workflow(
                    out,
                    unit_system,
                    computed=st.session_state.get("mmf_last_computed") or {},
                    on_apply_solid_loading=_apply_fouling_suggested_solid_loading,
                )

            _lbl_csd = f"Captured solids density ({unit_label('density_kg_m3', unit_system)})"
            _def_csd = display_value(1020.0, "density_kg_m3", unit_system)
            _stp_csd = display_value(10.0, "density_kg_m3", unit_system)
            out["captured_solids_density"]= st.number_input(_lbl_csd, value=_def_csd, step=_stp_csd, key="captured_solids_density")
            alpha_9 = st.number_input(
                "Specific cake resistance α (× 10⁹ m/kg)",
                value=0.0, step=5.0, min_value=0.0, key="alpha_res",
                help="0 — auto-calibrate α so dirty-bed ΔP matches the BW initiation setpoint at M_max solid loading. "
                     "Non-zero — fixed α for the Ruth cake model (ΔP tables, filtration cycles).",
            )
            out["alpha_specific"] = alpha_9 * 1e9
            st.caption(
                "**0** — auto-calibrate α from the BW ΔP setpoint and **M_max** solid loading. "
                "**> 0** — your α (×10⁹ m/kg). "
                "*Same pattern:* shell/head thickness **0** = ASME-calculated (Vessel tab); nozzle-plate override **0** = calculated."
            )

    # ── Tab 4: BW ─────────────────────────────────────────────────────────
    with bw_tab:
        inject_anchor("mmf-anchor-sb-bw")
        st.caption(
            "**Inputs** for backwash duty (plant), **underdrain / nozzle plate (1D screening)**, and optional studies. "
            "**Charts & advisories:** main **🔄 Backwash** tab — plant block first, then section 6."
        )
        st.markdown("### Backwash duty (plant)")
        st.caption(
            "Bed elevation, **BW velocity**, **air scour**, step times, blower/pump head, and timeline — "
            "not nozzle-plate / underdrain detail (see **Underdrain / nozzle plate (1D)** below)."
        )
        st.markdown("**Bed & BW hydraulics**")
        from engine.collector_geometry import max_collector_centerline_height_m
        from ui.nozzle_header_sync import linked_collector_header_id_si, user_nozzle_schedule

        _sched = user_nozzle_schedule()
        _q_pf = float(st.session_state.get("mmf_last_q_per_filter") or 0.0)
        _area = float(st.session_state.get("mmf_last_avg_area") or 0.0)
        _bwv_si = si_value(
            float(out.get("bw_velocity") or st.session_state.get("bw_velocity", display_value(30.0, "velocity_m_h", unit_system))),
            "velocity_m_h", unit_system,
        )
        _flow_kw = dict(
            q_filter_m3h=_q_pf,
            bw_velocity_m_h=_bwv_si,
            area_filter_m2=_area if _area > 0 else 25.0,
            default_rating=str(st.session_state.get("default_rating", "PN 16")),
            air_scour_rate_m_h=si_value(
                float(st.session_state.get("air_scour_rate", display_value(55.0, "velocity_m_h", unit_system))),
                "velocity_m_h", unit_system,
            ),
        )
        _hdr_si_sug, _hdr_link_note = linked_collector_header_id_si(**_flow_kw)
        _hdr_disp_sug = display_value(_hdr_si_sug, "length_m", unit_system)
        out["collector_header_id_linked"] = st.checkbox(
            "Link internal header ID to §4 Backwash outlet DN",
            value=bool(st.session_state.get("collector_header_id_linked", True)),
            key="collector_header_id_linked",
            help=(
                "Sets collector header ID = calculated internal diameter of §4 Backwash inlet "
                "and outlet (same DN, OD − 2× wall — not filtrate / nominal DN). "
                "Edit DN in **Mechanical → §4 Nozzle schedule**."
            ),
        )
        if out["collector_header_id_linked"]:
            st.session_state.pop("collector_header_id_m", None)
            st.session_state["_collector_header_id_linked_disp"] = _hdr_disp_sug
            from engine.nozzles import nozzle_dn_mm_for_service, nozzle_row_for_service
            _bw_out = nozzle_row_for_service(_sched, "Backwash outlet")
            _dn = nozzle_dn_mm_for_service(_sched, "Backwash outlet")
            st.caption(
                f"{_hdr_link_note} → **{format_value(_hdr_si_sug, 'length_m', unit_system)}** "
                f"(BW DN **{_dn or '—'}** mm, calculated ID **{_bw_out.get('ID (mm)', '—') if _bw_out else '—'}** mm)."
            )

        _lbl_ch = f"BW outlet collector height ({unit_label('length_m', unit_system)})"
        _stp_ch = display_value(0.1, "length_m", unit_system)
        _nid_si = si_value(
            float(out.get("nominal_id") or st.session_state.get("nominal_id", display_value(5.5, "length_m", unit_system))),
            "length_m", unit_system,
        )
        _hdr_si = _hdr_si_sug if out["collector_header_id_linked"] else si_value(
            float(st.session_state.get("collector_header_id_manual", _hdr_disp_sug)),
            "length_m", unit_system,
        )
        if out["collector_header_id_linked"]:
            out["collector_header_id_m"] = _hdr_disp_sug
        _np_si = si_value(
            float(out.get("nozzle_plate_h") or st.session_state.get("nozzle_plate_h", display_value(1.0, "length_m", unit_system))),
            "length_m", unit_system,
        )
        _max_ch_si = max_collector_centerline_height_m(_nid_si, _hdr_si)
        _min_ch_si = max(_np_si + 0.01, 0.1)
        _max_ch_disp = display_value(_max_ch_si, "length_m", unit_system)
        _min_ch_disp = display_value(_min_ch_si, "length_m", unit_system)
        if _max_ch_disp < _min_ch_disp:
            _max_ch_disp = _min_ch_disp
        _def_ch = display_value(4.2, "length_m", unit_system)
        _sess_ch = float(st.session_state.get("collector_h", _def_ch))
        _def_ch = min(max(_sess_ch, _min_ch_disp), _max_ch_disp)
        out["collector_h"] = st.number_input(
            _lbl_ch, value=_def_ch, step=_stp_ch,
            min_value=_min_ch_disp, max_value=_max_ch_disp,
            key="collector_h",
            help=(
                f"Centreline height from vessel bottom. Max ≈ vessel ID − 100 mm − header ID/2 "
                f"({format_value(_max_ch_si, 'length_m', unit_system)} with current vessel & header)."
            ),
        )
        st.caption(
            f"Collector height limit: **{format_value(_max_ch_si, 'length_m', unit_system)}** "
            f"(ID {format_value(_nid_si, 'length_m', unit_system)} − 100 mm − "
            f"header Ø {format_value(_hdr_si, 'length_m', unit_system)}/2)."
        )
        out["freeboard_mm"]   = st.number_input(
            f"Min. freeboard ({unit_label('length_mm', unit_system)})",
            value=int(round(display_value(200.0, "length_mm", unit_system))),
            step=int(round(display_value(50.0, "length_mm", unit_system))),
            min_value=int(round(display_value(50.0, "length_mm", unit_system))), key="fb_mm")
        _lbl_bwv = f"Proposed BW velocity ({unit_label('velocity_m_h', unit_system)})"
        _def_bwv = display_value(30.0, "velocity_m_h", unit_system)
        _stp_bwv = display_value(5.0, "velocity_m_h", unit_system)
        out["bw_velocity"]    = st.number_input(_lbl_bwv, value=_def_bwv, step=_stp_bwv, key="bw_velocity")

        _lbl_aw = f"③ Air + low-rate water — superficial water ({unit_label('velocity_m_h', unit_system)})"
        _def_aw = display_value(12.5, "velocity_m_h", unit_system)
        out["airwater_step_water_m_h"] = st.number_input(
            _lbl_aw,
            value=_def_aw,
            step=_stp_bwv,
            min_value=0.0,
            key="airwater_step_water_m_h",
            help="Fixed water leg during the air+water step. Auto air-scour sizing solves the **air** "
                 "equivalent for target expansion at (this rate + air).",
        )

        out["air_scour_mode"] = st.radio(
            "Air scour sizing",
            options=["manual", "auto_expansion"],
            format_func=lambda m: (
                "Manual air scour rate (m³/m²·h)"
                if m == "manual"
                else "Auto — target net bed expansion (%)"
            ),
            horizontal=True,
            key="air_scour_mode_sel",
        )
        if out["air_scour_mode"] == "auto_expansion":
            out["air_scour_target_expansion_pct"] = float(st.number_input(
                "Target net bed expansion (air scour surrogate) (%)",
                value=20.0,
                min_value=0.0, max_value=80.0, step=1.0,
                key="air_scour_target_expansion_pct",
                help="Engine solves equivalent superficial velocity using the same Richardson–Zaki stack "
                     "as the combined-phase table on the Backwash tab (not CFD).",
            ))
            st.caption(
                "Solver picks the **minimum** air-equivalent rate that meets the target "
                "(minimum screening blower kW at fixed ΔP/η). Blower sizing uses that rate."
            )
        else:
            out["air_scour_target_expansion_pct"] = float(
                st.session_state.get("air_scour_target_expansion_pct", 20.0)
            )

        _manual_air_disabled = out["air_scour_mode"] == "auto_expansion"
        _lbl_asr = f"Air scour rate ({unit_label('velocity_m_h', unit_system)})"
        _def_asr = display_value(55.0, "velocity_m_h", unit_system)
        out["air_scour_rate"] = st.number_input(
            _lbl_asr,
            value=_def_asr,
            step=_stp_bwv,
            key="air_scour_rate",
            disabled=_manual_air_disabled,
            help=(
                "Ignored while Auto expansion is selected — rate comes from the solver."
                if _manual_air_disabled else None
            ),
        )

        st.markdown("**BW sequence & equipment**")
        out["bw_cycles_day"]  = int(st.number_input("BW cycles / filter / day", value=1, min_value=1, key="bw_cycles_day"))
        out["dp_trigger_bar"] = st.number_input(
            f"BW initiation ΔP setpoint ({unit_label('pressure_bar', unit_system)})", value=1.0,
            step=float(display_value(0.1, "pressure_bar", unit_system)),
            min_value=float(display_value(0.01, "pressure_bar", unit_system)), key="dp_trig")
        out["bw_s_drain"]  = st.number_input("① Gravity drain (min)",       value=10, step=1, min_value=0, key="bws1")
        out["bw_s_air"]    = st.number_input("② Air scour only (min)",       value=1,  step=1, min_value=0, key="bws2")
        out["bw_s_airw"]   = st.number_input("③ Air + low-rate water (min)", value=5,  step=1, min_value=0, key="bws3")
        out["bw_s_hw"]     = st.number_input("④ High-rate water flush (min)",value=10, step=1, min_value=0, key="bws4")
        out["bw_s_settle"] = st.number_input("⑤ Settling (min)",             value=2,  step=1, min_value=0, key="bws5")
        out["bw_s_fill"]   = st.number_input("⑥ Fill & rinse (min)",         value=10, step=1, min_value=0, key="bws6")
        out["bw_total_min"] = (out["bw_s_drain"] + out["bw_s_air"] + out["bw_s_airw"]
                               + out["bw_s_hw"] + out["bw_s_settle"] + out["bw_s_fill"])
        st.metric("Total BW duration", f"{out['bw_total_min']} min")
        from ui.bw_duty_form import render_bw_duty_chart_form

        render_bw_duty_chart_form(out)

        st.markdown("**Equipment sizing**")
        out["vessel_pressure_bar"]  = st.number_input(
            f"Vessel operating pressure ({unit_label('pressure_bar', unit_system)} g)",
            value=2.0, step=float(display_value(0.5, "pressure_bar", unit_system)),
            min_value=0.0, key="ves_press")
        st.caption(
            "Used for **Nm³/h ↔ in-situ air volume** conversion only — **not** blower discharge pressure."
        )
        out["blower_air_delta_p_bar"] = st.number_input(
            f"Air scour blower ΔP — air side ({unit_label('pressure_bar', unit_system)} g)",
            value=float(display_value(0.15, "pressure_bar", unit_system)),
            step=float(display_value(0.02, "pressure_bar", unit_system)),
            min_value=0.0,
            max_value=float(display_value(1.2, "pressure_bar", unit_system)),
            key="blower_air_dp",
            help=(
                "**Beyond** the hydrostatic column (submergence). Covers sparger, distribution, "
                "and piping losses — **not** the liquid filtration operating gauge. "
                "Typical MMF air scour: **~"
                f"{format_value(0.1, 'pressure_bar', unit_system, 2)}–"
                f"{format_value(0.25, 'pressure_bar', unit_system, 2)}**; "
                "lobe PD blowers rarely exceed **~"
                f"{format_value(0.9, 'pressure_bar', unit_system, 2)}** total ΔP."
            ),
        )
        out["blower_eta"]           = st.number_input("Blower isentropic efficiency", value=0.70,
                                                        step=0.01, min_value=0.30, max_value=0.95, key="blower_eta")
        _lbl_blowt = f"Blower inlet air temperature ({unit_label('temperature_c', unit_system)})"
        _def_blowt = display_value(30.0, "temperature_c", unit_system)
        out["blower_inlet_temp_c"]  = st.number_input(_lbl_blowt, value=_def_blowt,
                                                        step=5.0, min_value=float(display_value(-10.0, "temperature_c", unit_system)),
                                                        max_value=float(display_value(60.0, "temperature_c", unit_system)), key="blower_t")
        out["tank_sf"]              = st.number_input("BW tank safety factor", value=1.5,
                                                        step=0.1, min_value=1.0, max_value=3.0, key="tank_sf")
        _lbl_bwh = f"BW pump total head ({unit_label('pressure_mwc', unit_system)})"
        _def_bwh = display_value(15.0, "pressure_mwc", unit_system)
        _stp_bwh = display_value(1.0, "pressure_mwc", unit_system)
        out["bw_head_mwc"]          = st.number_input(_lbl_bwh, value=_def_bwh,
                                                        step=_stp_bwh, min_value=float(display_value(1.0, "pressure_mwc", unit_system)), key="bw_hd")

        st.markdown("**Nozzles & supports**")
        out["default_rating"]  = st.selectbox("Flange rating", FLANGE_RATINGS, index=1, key="default_rating")
        _lbl_nstub = f"Nozzle stub length ({unit_label('length_mm', unit_system)})"
        out["nozzle_stub_len"] = int(round(st.number_input(
            _lbl_nstub,
            value=float(display_value(350.0, "length_mm", unit_system)),
            step=float(display_value(50.0, "length_mm", unit_system)),
            key="nozzle_stub_len",
        )))
        from engine.strainer_materials import strainer_material_label

        _str_mat = str(out.get("strainer_mat") or st.session_state.get("strainer_mat") or "—")
        st.caption(
            f"**Strainer material** is set on **🧱 Media** (with nozzle catalogue): "
            f"**{strainer_material_label(_str_mat) if _str_mat != '—' else '—'}**. "
            "Internals weight uses this alloy."
        )
        _lbl_ahdn = f"Air scour header DN ({unit_label('length_mm', unit_system)})"
        out["air_header_dn"]   = int(round(st.number_input(
            _lbl_ahdn,
            value=float(display_value(200.0, "length_mm", unit_system)),
            step=float(display_value(50.0, "length_mm", unit_system)),
            key="ah_dn",
        )))
        out["manhole_dn"]      = st.selectbox("Manhole size", list(MANHOLE_WEIGHT_KG.keys()), index=0, key="manhole_dn")
        out["n_manholes"]      = int(st.number_input("No. of manholes", value=1, min_value=0, step=1, key="n_manholes"))
        _mh_span = format_value(7.5, "length_m", unit_system, 1)
        st.caption(
            f"Rule of thumb: **one manhole per ~{_mh_span}** of cylindrical shell for access; "
            "the Mechanical tab shows a recommended count from the computed shell length."
        )
        out["support_type"]    = st.selectbox("Support type", SUPPORT_TYPES, key="sup_t")
        if "Saddle" in out["support_type"]:
            _lbl_sh = f"Saddle height ({unit_label('length_m', unit_system)})"
            _def_sh = display_value(0.8, "length_m", unit_system)
            _stp_sh = display_value(0.05, "length_m", unit_system)
            out["saddle_h"]             = st.number_input(_lbl_sh, value=_def_sh, step=_stp_sh, key="sad_h")
            out["base_plate_t"]         = st.number_input(
                f"Base plate t ({unit_label('length_mm', unit_system)})",
                value=float(display_value(20.0, "length_mm", unit_system)),
                step=float(display_value(2.0, "length_mm", unit_system)),
                key="sad_bp",
            )
            out["gusset_t"]             = st.number_input(
                f"Gusset t ({unit_label('length_mm', unit_system)})",
                value=float(display_value(12.0, "length_mm", unit_system)),
                step=float(display_value(2.0, "length_mm", unit_system)),
                key="sad_gt",
            )
            out["saddle_contact_angle"] = st.number_input("Saddle contact angle (°)", value=120.0,
                                                           step=15.0, min_value=90.0, max_value=180.0, key="sad_ang")
            out["leg_h"] = 1.2; out["leg_section"] = 150.0
        else:
            _lbl_lh = f"Leg height ({unit_label('length_m', unit_system)})"
            _def_lh = display_value(1.2, "length_m", unit_system)
            _stp_lh = display_value(0.1, "length_m", unit_system)
            out["leg_h"]                = st.number_input(_lbl_lh, value=_def_lh, step=_stp_lh, key="leg_h")
            out["leg_section"]          = st.number_input(
                f"Leg section ({unit_label('length_mm', unit_system)})",
                value=float(display_value(150.0, "length_mm", unit_system)),
                step=float(display_value(25.0, "length_mm", unit_system)),
                key="leg_s",
            )
            out["base_plate_t"]         = st.number_input(
                f"Base plate t ({unit_label('length_mm', unit_system)})",
                value=float(display_value(20.0, "length_mm", unit_system)),
                step=float(display_value(2.0, "length_mm", unit_system)),
                key="leg_bp",
            )
            out["gusset_t"]             = st.number_input(
                f"Gusset t ({unit_label('length_mm', unit_system)})",
                value=float(display_value(12.0, "length_mm", unit_system)),
                step=float(display_value(2.0, "length_mm", unit_system)),
                key="leg_gt",
            )
            out["saddle_h"] = 0.8; out["saddle_contact_angle"] = 120.0

        st.divider()
        st.markdown("### Underdrain / nozzle plate (1D screening)")
        _q_pf_si = float(st.session_state.get("mmf_last_q_per_filter") or 0.0)
        if _q_pf_si <= 0 and float(out.get("total_flow", 0) or 0) > 0:
            _n_hyd_paths = max(
                1, int(out.get("n_filters", 1)) - int(out.get("hydraulic_assist", 0)),
            )
            _q_pf_si = float(out["total_flow"]) / max(1, int(out.get("streams", 1))) / _n_hyd_paths
        _area_si = float(st.session_state.get("mmf_last_avg_area") or 0.0)
        _bwv_si = si_value(float(out.get("bw_velocity", 30)), "velocity_m_h", unit_system)
        _q_bw_si = _bwv_si * _area_si if _area_si > 0 else 0.0
        _q_pf_txt = (
            f"**{format_value(_q_pf_si, 'flow_m3h', unit_system, 1)}**"
            if _q_pf_si > 0
            else "— (run model)"
        )
        _q_bw_txt = (
            f"**{format_value(_q_bw_si, 'flow_m3h', unit_system, 1)}**"
            if _q_bw_si > 0
            else "— (set BW velocity + media area)"
        )
        st.caption(
            "**Your design (today):** **nozzle plate** underdrain — perforated or slotted plate under the media "
            "(**🧱 Media** → nozzle plate bore, density, open area). **No lateral pipes** in this project yet. "
            "**This 1D block** is a **screening surrogate**: feed **header/manifold** plus equivalent **orifice "
            "stations** along the drum (not a full nozzle-plate network). **Backwash flow only** — uses BW flow "
            f"{_q_bw_txt}, **not** filtration feed {_q_pf_txt} (Filtration tab). "
            "Other underdrain types may be added later. **Not** §4 shell BW in / out / air nozzles."
        )
        with st.expander(
            "Sizes, material & optimization",
            expanded=False,
        ):
            st.caption(
                "Header DN may link to §4 BW inlet/outlet nozzle pipe ID. "
                "Optional: link **filtration maldistribution factor** to the 1D distribution factor under "
                "**🧱 Media** (sidebar) → *Calibration…* → *Advanced — pilot / field calibration*."
            )
            st.markdown("**Sizes & hydraulics**")
            _lbl_chid = f"Header internal diameter ({unit_label('length_m', unit_system)})"
            if out.get("collector_header_id_linked"):
                st.metric(
                    _lbl_chid,
                    format_value(_hdr_si_sug, "length_m", unit_system),
                    help="Linked to §4 Backwash inlet/outlet calculated ID (OD − 2× wall). Uncheck link above to edit.",
                )
            else:
                _def_chid = float(st.session_state.get("collector_header_id_manual", _hdr_disp_sug))
                out["collector_header_id_m"] = st.number_input(
                    _lbl_chid,
                    value=_def_chid,
                    step=float(display_value(0.05, "length_m", unit_system)),
                    min_value=float(display_value(0.05, "length_m", unit_system)),
                    key="collector_header_id_manual",
                )
            out["collector_header_feed_mode"] = st.radio(
                "Header feed (1B+ manifold)",
                options=["one_end", "dual_end"],
                format_func=lambda x: (
                    "One end (standard 1B)"
                    if x == "one_end"
                    else "Dual end (centre-fed, 1B+ screening)"
                ),
                horizontal=True,
                key="collector_header_feed_mode_sel",
                help="Dual-end uses a split-header balance — screening only, not CFD.",
            )
            out["collector_tee_loss_enable"] = st.checkbox(
                "Branch tee losses (K=1.5 per lateral)",
                value=bool(st.session_state.get("collector_tee_loss_enable", False)),
                key="collector_tee_loss_enable",
                help=(
                    "Adds local loss Δh = K·V_header²/(2g) at each lateral takeoff in the 1D "
                    "distribution solve (screening). Increases header–lateral distribution loss vs "
                    "pipe friction alone — not 3D tee CFD."
                ),
            )
            out["n_bw_laterals"] = int(st.number_input(
                "Equivalent lateral stations (1D collector)",
                value=int(st.session_state.get("n_bw_laterals", 4) or 4),
                min_value=1,
                max_value=80,
                step=1,
                key="n_bw_laterals",
                help=(
                    "Count of **equivalent orifice stations** along the internal BW collector "
                    "header (1D screening model) — **not** nozzle-plate rows. "
                    "For brick nozzle rows across the plate chord, use **🧱 Media → "
                    "Nozzle rows across chord**."
                ),
            ))
            out["lateral_dn_mm"] = st.number_input(
                f"Lateral pipe DN ({unit_label('length_mm', unit_system)})",
                value=float(display_value(50.0, "length_mm", unit_system)),
                step=float(display_value(5.0, "length_mm", unit_system)),
                min_value=float(display_value(15.0, "length_mm", unit_system)),
                key="lateral_dn_mm",
            )
            _lbl_lsp = f"Lateral spacing along header — 0 = auto ({unit_label('length_m', unit_system)})"
            out["lateral_spacing_m"] = st.number_input(
                _lbl_lsp, value=0.0,
                step=float(display_value(0.5, "length_m", unit_system)),
                min_value=0.0, key="lateral_spacing_m",
            )
            out["use_geometry_lateral"] = st.checkbox(
                "Auto lateral length & spacing from vessel θ (ID + collector height)",
                value=bool(st.session_state.get("use_geometry_lateral", True)),
                key="use_geometry_lateral",
                help=(
                    "L_max from cross-section: header at **nozzle-plate height** to shell at "
                    "**BW collector height**. Spacing capped by ~vessel ID."
                ),
            )
            _lbl_llen = f"Lateral run length — 0 = geometry L_max ({unit_label('length_m', unit_system)})"
            out["lateral_length_m"] = st.number_input(
                _lbl_llen, value=0.0,
                step=float(display_value(0.1, "length_m", unit_system)),
                min_value=0.0, key="lateral_length_m",
                disabled=bool(out.get("use_geometry_lateral")),
            )
            out["lateral_orifice_d_mm"] = st.number_input(
                f"Lateral perforation Ø — 0 = nozzle bore ({unit_label('length_mm', unit_system)})",
                value=0.0,
                step=float(display_value(2.0, "length_mm", unit_system)),
                min_value=0.0, key="lateral_orifice_d_mm",
                help="Hydraulic diameter of holes/slots in the **lateral pipe wall** (not the nozzle-plate bores).",
            )
            out["n_orifices_per_lateral"] = int(st.number_input(
                "Perforations per lateral — 0 = auto (~200 mm pitch along lateral)",
                value=0, min_value=0, max_value=500, step=1, key="n_orifices_per_lateral",
                help=(
                    "Count **on each** lateral branch. **Not** the nozzle-plate hole count "
                    "(Media → nozzle density). Total plant perforations = this × N laterals."
                ),
            ))
            out["lateral_discharge_cd"] = st.number_input(
                "Orifice discharge coefficient Cd (−)", value=0.62,
                min_value=0.3, max_value=0.95, step=0.02, key="lateral_discharge_cd",
            )

            st.markdown("**Construction & material**")
            from engine.collector_lateral_types import (
                LATERAL_CONSTRUCTION_OPTIONS,
                WEDGE_OPEN_AREA_TYPICAL_PCT,
                materials_for_construction,
                water_service_class,
                water_service_material_guidance,
            )
            from engine.collector_geometry import LATERAL_MATERIAL_OPEN_AREA

            _feed_sal_si = si_value(
                float(out.get("feed_sal") or st.session_state.get("f_sal", 35.0)),
                "salinity_ppt", unit_system,
            )
            _wsvc = water_service_class(_feed_sal_si)
            _lcon_default = str(st.session_state.get("lateral_construction", "Drilled perforated pipe"))
            if _lcon_default not in LATERAL_CONSTRUCTION_OPTIONS:
                _lcon_default = "Drilled perforated pipe"
            out["lateral_construction"] = st.selectbox(
                "Lateral construction type",
                options=list(LATERAL_CONSTRUCTION_OPTIONS),
                index=list(LATERAL_CONSTRUCTION_OPTIONS).index(_lcon_default),
                key="lateral_construction",
                help=(
                    "**Drilled pipe** — perforation % and ligament govern. "
                    "**Wedge wire** — slot screen; collapse / rod spacing / OEM data (20–60% open area). "
                    "**Coated CS** — drilled + lining holidays / abrasion review."
                ),
            )
            _mat_opts = list(materials_for_construction(out["lateral_construction"]))
            _mat_default = str(st.session_state.get("lateral_material", _mat_opts[0]))
            if _mat_default not in _mat_opts:
                _mat_default = _mat_opts[0]
            out["lateral_material"] = st.selectbox(
                "Lateral material / alloy",
                options=_mat_opts,
                index=_mat_opts.index(_mat_default),
                key="lateral_material",
            )
            _wm = water_service_material_guidance(
                salinity_ppt=_feed_sal_si,
                lateral_construction=out["lateral_construction"],
                lateral_material=out["lateral_material"],
            )
            st.caption(
                f"Feed water: **{_wsvc}** ({_feed_sal_si:.1f} ppt). "
                + " ".join(_wm.get("recommendations") or [])[:280]
            )
            if out["lateral_construction"] == "Wedge wire screen":
                st.caption(
                    f"Wedge wire typical open area **{WEDGE_OPEN_AREA_TYPICAL_PCT}** — "
                    "not drilled-hole ligament rules."
                )
                out["wedge_slot_width_mm"] = st.number_input(
                    f"Slot width ({unit_label('length_mm', unit_system)}) — 0 = advisory only",
                    value=float(st.session_state.get("wedge_slot_width_mm", 0.0)),
                    min_value=0.0,
                    step=float(display_value(0.1, "length_mm", unit_system)),
                    key="wedge_slot_width_mm",
                )
                out["wedge_open_area_fraction"] = st.number_input(
                    "Wedge wire open area (fraction) — 0 = default 35%",
                    value=float(st.session_state.get("wedge_open_area_fraction", 0.0)),
                    min_value=0.0, max_value=0.60, step=0.01,
                    key="wedge_open_area_fraction",
                )
                out["max_lateral_open_area_fraction"] = 0.0
            else:
                out["wedge_slot_width_mm"] = 0.0
                out["wedge_open_area_fraction"] = 0.0
                _mat_spec = LATERAL_MATERIAL_OPEN_AREA.get(
                    out["lateral_material"],
                    LATERAL_MATERIAL_OPEN_AREA.get("Stainless steel", {}),
                )
                if out["lateral_construction"] == "Coated carbon steel (drilled)":
                    st.caption(
                        "Coated CS: check **holidays**, **weld edges**, **BW/air scour abrasion**, repair strategy."
                    )
                else:
                    st.caption(
                        f"Drilled pipe max open area **{_mat_spec.get('open_area_range_pct', '—')}** "
                        f"(cap **{float(_mat_spec.get('open_area_max_fraction', 0.1)) * 100:.0f}%**)."
                    )
                _custom_cap = out["lateral_material"] == "Custom"
                out["max_lateral_open_area_fraction"] = st.number_input(
                    "Custom max open area (fraction) — 0 = use material table",
                    value=float(st.session_state.get("max_lateral_open_area_fraction", 0.0)),
                    min_value=0.0, max_value=0.40, step=0.01,
                    key="max_lateral_open_area_fraction",
                    disabled=not _custom_cap,
                )

            st.divider()
            st.markdown("**Re-optimize after edits**")
            st.caption(
                "Run when you change **lateral DN**, **perforation Ø**, **N laterals**, "
                "**construction**, or **material** (and header ID if not linked to §4). "
                "The solver picks N × DN × perforation count for the lowest 1D distribution factor; "
                "it does not change §4 vessel nozzles or a linked header diameter."
            )
            _opt_msg = st.session_state.pop("_collector_opt_message", None)
            if _opt_msg:
                st.success(_opt_msg)
            from ui.collector_optim_ui import run_collector_optimization_from_session

            st.button(
                "Run collector optimization solver",
                key="collector_run_optim_solver",
                type="primary",
                help=(
                    "Uses your current material, diameters, and BW flow. "
                    "Overwrites N laterals, lateral DN, and perforation count when a better layout is found."
                ),
                on_click=run_collector_optimization_from_session,
            )

        with st.expander(
            "Optional — collector studies (extra runtime)",
            expanded=False,
        ):
            st.caption(
                "Screening tools on top of the 1D model — not required for a basic BW sizing run."
            )
            st.markdown("**Optional — collector flow study (1D)**")
            out["collector_bw_envelope_enable"] = st.checkbox(
                "Compute BW-flow sweep vs imbalance / velocities",
                value=bool(st.session_state.get("collector_bw_envelope_enable", False)),
                key="collector_bw_envelope_enable",
                help=(
                    "Runs the 1D collector model several times at scaled total BW flow (same geometry). "
                    "For optioneering only; each sweep adds extra work to each compute_all run."
                ),
            )
            _env_dis = not out["collector_bw_envelope_enable"]
            _e1, _e2 = st.columns(2)
            with _e1:
                out["collector_bw_envelope_n_points"] = int(st.number_input(
                    "Sweep base points (3–25)",
                    value=int(st.session_state.get("collector_bw_envelope_n_points", 7)),
                    min_value=3,
                    max_value=25,
                    step=1,
                    key="collector_bw_envelope_n_points",
                    disabled=_env_dis,
                ))
            with _e2:
                out["collector_bw_envelope_q_low_frac"] = float(st.number_input(
                    "Low flow / design",
                    value=float(st.session_state.get("collector_bw_envelope_q_low_frac", 0.55)),
                    min_value=0.05,
                    max_value=0.98,
                    step=0.05,
                    format="%.2f",
                    key="collector_bw_envelope_q_low_frac",
                    disabled=_env_dis,
                ))
            out["collector_bw_envelope_q_high_frac"] = float(st.number_input(
                "High flow / design",
                value=float(st.session_state.get("collector_bw_envelope_q_high_frac", 1.15)),
                min_value=1.02,
                max_value=1.80,
                step=0.05,
                format="%.2f",
                key="collector_bw_envelope_q_high_frac",
                disabled=_env_dis,
            ))
            st.caption(
                "Design-point BW flow is always included. "
                "Feasible = converged distribution and imbalance ≤ 55% (screening cap)."
            )

            st.markdown("**Optional — perforation staging (advisory)**")
            _staged_opts = [0, 2, 3, 4]
            _prev_sg = st.session_state.get("collector_staged_orifice_groups_sel", 0)
            if _prev_sg not in _staged_opts:
                _prev_sg = 0
            _staged_idx = _staged_opts.index(int(_prev_sg))
            out["collector_staged_orifice_groups"] = st.selectbox(
                "Staged perforation Ø bands per lateral",
                options=_staged_opts,
                index=_staged_idx,
                format_func=lambda x: (
                    "Off"
                    if x == 0
                    else f"{x} contiguous Ø bands (drill schedule)"
                ),
                key="collector_staged_orifice_groups_sel",
                help=(
                    "Advisory drill table from frozen per-hole flows — does not re-run the 1B solver."
                ),
            )

    # ── Tab 5: Econ ───────────────────────────────────────────────────────
    with econ_tab:
        inject_anchor("mmf-anchor-sb-econ")
        st.caption(
            "**💰 Econ** sidebar = tariffs, intervals, financial knobs; main **Economics** tab = **results**."
        )
        st.markdown("**Economics inputs**")
        st.caption(
            "These values feed **compute** → results on the main **Economics** tab. "
            "**Feed path hydraulics** and **pump/motor η** are on **Pumps & power** → **1 · Hydraulics & plant configuration**."
        )
        st.caption(
            "**Media / nozzle intervals:** **OPEX inputs** below set **levelized** annual replacement cost in engineering OPEX; "
            "**Financial lifecycle** further down sets **discrete cash-event** years for the full cash-flow model (can match or differ)."
        )
        st.markdown("**Energy economics**")
        out["elec_tariff"] = st.number_input("Electricity tariff (USD/kWh)", value=0.10,
                                              step=0.01, min_value=0.01, key="elec_t")
        out["op_hours_yr"] = st.number_input("Operating hours / year", value=8400,
                                              step=100, min_value=1000, key="op_hr")

        st.markdown("**CAPEX inputs**")
        out["design_life_years"]         = st.number_input("Design life (years)", value=20, step=1, min_value=5, key="des_life")
        out["discount_rate"]             = st.number_input("Discount rate (%)", value=5.0, step=0.5, min_value=0.0, key="disc_rate")
        out["currency"]                  = st.selectbox("Currency", ["USD","EUR","GBP","SAR","AED"], key="currency")
        out["steel_cost_usd_kg"]         = st.number_input(
            f"Steel cost (USD/{unit_label('cost_usd_per_kg', unit_system)})",
            value=float(display_value(3.5, "cost_usd_per_kg", unit_system)),
            step=float(display_value(0.1, "cost_usd_per_kg", unit_system)),
            key="st_cost",
        )
        _per_kg = unit_label("cost_usd_per_kg", unit_system)
        out["erection_usd_per_kg_steel"] = st.number_input(
            f"Erection ({_per_kg} installed steel)",
            value=float(display_value(0.625, "cost_usd_per_kg", unit_system)),
            step=float(display_value(0.05, "cost_usd_per_kg", unit_system)),
            min_value=0.0,
            key="erect_usd_kg",
            help="Applied to **dry installed steel mass per vessel** (shell, heads, supports, nozzles, internals).",
        )
        out["labor_usd_per_kg_steel"] = st.number_input(
            f"Field construction labor ({_per_kg} installed steel)",
            value=float(display_value(0.25, "cost_usd_per_kg", unit_system)),
            step=float(display_value(0.05, "cost_usd_per_kg", unit_system)),
            min_value=0.0,
            key="labor_st_kg",
            help="Rigging / fit-up / alignment labor indexed to installed steel; set **0** if included in an all-in steel rate.",
        )
        out["piping_usd_vessel"]         = st.number_input("Piping cost (USD/vessel)", value=80000.0, step=5000.0, key="pip_usd")
        out["instrumentation_usd_vessel"]= st.number_input("Instrumentation (USD/vessel)", value=30000.0, step=5000.0, key="instr_usd")
        out["civil_usd_per_kg_working"] = st.number_input(
            f"Civil works ({_per_kg} operating weight)",
            value=float(display_value(0.10, "cost_usd_per_kg", unit_system)),
            step=float(display_value(0.01, "cost_usd_per_kg", unit_system)),
            min_value=0.0,
            key="civil_w_kg",
            help="Foundations, plinths, sumps, access — scaled by **operating weight** (water + media + steel + lining in service) per vessel.",
        )
        out["engineering_pct"]           = st.number_input("Engineering (%)", value=12.0, step=1.0, min_value=0.0, key="eng_pct")
        out["contingency_pct"]           = st.number_input("Contingency (%)", value=10.0, step=1.0, min_value=0.0, key="cont_pct")

        st.markdown("**OPEX inputs**")
        out["media_replace_years"]   = st.number_input("Media replacement interval (years)", value=7.0, step=1.0, key="med_int")
        out["econ_media_gravel"]     = st.number_input("Gravel cost (USD/t)", value=80.0, step=10.0, key="mc_gr")
        out["econ_media_sand"]       = st.number_input("Sand cost (USD/t)", value=150.0, step=10.0, key="mc_sd")
        out["econ_media_anthracite"] = st.number_input("Anthracite cost (USD/t)", value=400.0, step=25.0, key="mc_an")
        out["nozzle_replace_years"]  = st.number_input("Nozzle replacement interval (years)", value=10.0, step=1.0, key="noz_int")
        out["nozzle_unit_cost"]      = st.number_input("Nozzle unit cost (USD/nozzle)", value=15.0, step=1.0, key="noz_cost")
        out["labour_usd_filter_yr"]  = st.number_input("Labour (USD/filter/year)", value=5000.0, step=500.0, key="lab_usd")
        out["chemical_cost_m3"]      = st.number_input(
            f"Chemical cost (USD/{unit_label('cost_usd_per_m3', unit_system)} treated)",
            value=float(display_value(0.005, "cost_usd_per_m3", unit_system)),
            step=float(display_value(0.001, "cost_usd_per_m3", unit_system)),
            format="%.4f",
            key="chem_m3",
        )

        st.markdown("**Financial lifecycle (NPV · IRR · replacements)**")
        st.caption(
            "**Design life** (above) drives LCOW / simple NPV on the Economics tab; **project life** here is the "
            "cash-flow horizon (often the same, or longer for concessions). **Discount rate** applies to both views."
        )
        out["project_life_years"] = int(st.number_input(
            "Project life for cash flow (years)",
            value=int(out.get("design_life_years", 20)),
            step=1, min_value=5, max_value=60, key="proj_life",
            help="Often equals design life; extend for concession / contract horizon.",
        ))
        out["inflation_rate"] = st.number_input("General inflation (%/yr)", value=2.0, step=0.25, min_value=0.0, key="fin_infl")
        out["escalation_energy_pct"] = st.number_input(
            "Energy cost escalation (%/yr)", value=2.5, step=0.25, min_value=0.0, key="fin_esc_e",
        )
        out["escalation_maintenance_pct"] = st.number_input(
            "Maintenance escalation (%/yr)", value=3.0, step=0.25, min_value=0.0, key="fin_esc_m",
        )
        out["maintenance_pct_capex"] = st.number_input(
            "Scheduled maintenance (% of CAPEX / yr)", value=2.0, step=0.25, min_value=0.0, key="fin_maint_pct",
        )
        out["tax_rate"] = st.number_input(
            "Corporate tax rate (%, 0 = off)", value=0.0, step=1.0, min_value=0.0, max_value=50.0, key="fin_tax",
        )
        out["salvage_value_pct"] = st.number_input(
            "Salvage value (% of CAPEX, end of life)", value=5.0, step=0.5, min_value=0.0, key="fin_salv",
        )
        out["annual_benefit_usd"] = st.number_input(
            "Annual benefit / revenue proxy (USD/yr, 0 = cost-only)",
            value=0.0, step=100_000.0, min_value=0.0, key="fin_benefit",
            help="Optional uniform inflow for IRR / payback (e.g. avoided legacy OPEX or water sales).",
        )
        _dep_m = st.selectbox(
            "Depreciation method", ["straight_line", "declining_balance"], index=0, key="fin_dep_m",
        )
        out["depreciation_method"] = _dep_m
        out["depreciation_years"] = int(st.number_input(
            "Depreciation period (years)", value=20, step=1, min_value=1, max_value=60, key="fin_dep_y",
        ))
        out["replacement_interval_media"] = st.number_input(
            "Media replacement — cash events (years)", value=float(out["media_replace_years"]),
            step=1.0, min_value=1.0, key="fin_med_rep",
        )
        out["replacement_interval_nozzles"] = st.number_input(
            "Nozzle replacement — cash events (years)", value=float(out["nozzle_replace_years"]),
            step=1.0, min_value=1.0, key="fin_noz_rep",
        )
        out["replacement_interval_lining"] = st.number_input(
            "Lining replacement interval (years)", value=15.0, step=1.0, min_value=1.0, key="fin_lin_rep",
        )

        st.markdown("**Carbon footprint**")
        st.caption(
            "**Operational CO₂** = grid intensity (below) × annual electrical energy from the **Energy** "
            "model (filtration + backwash + auxiliaries in scope). **Construction CO₂** = factors × "
            "steel, concrete, and media masses. Use a project-specific grid factor (PEF / residual mix / "
            "PPA) where available — quick presets are indicative only."
        )
        _gp1, _gp2, _gp3, _gp4 = st.columns(4)
        with _gp1:
            if st.button("Grid 0.20", key="grid_preset_020", help="Indicative low-carbon / high-renewables"):
                st.session_state["grid_co2"] = 0.20
        with _gp2:
            if st.button("Grid 0.45", key="grid_preset_045", help="Indicative global average order-of-magnitude"):
                st.session_state["grid_co2"] = 0.45
        with _gp3:
            if st.button("Grid 0.70", key="grid_preset_070", help="Indicative fossil-intensive grid"):
                st.session_state["grid_co2"] = 0.70
        with _gp4:
            st.caption("Presets set the field →")
        out["grid_intensity"]       = st.number_input(
            f"Grid intensity ({unit_label('co2_kg_per_kwh', unit_system)})",
            value=0.45, step=0.01, key="grid_co2",
        )
        out["steel_carbon_kg"]      = st.number_input(
            f"Steel embodied carbon ({unit_label('co2_per_kg_material', unit_system)})",
            value=1.85, step=0.05, key="st_co2",
        )
        out["concrete_carbon_kg"]   = st.number_input(
            f"Concrete embodied carbon ({unit_label('co2_per_kg_material', unit_system)})",
            value=0.13, step=0.01, key="con_co2",
        )
        _CARBON_DEFAULTS = {
            "Gravel": 0.004, "Gravel (2–3 mm)": 0.004, "Gravel (2-3 mm)": 0.004,
            "Fine sand": 0.006, "Fine sand (extra)": 0.006,
            "Coarse sand": 0.006, "Anthracite": 0.150, "Garnet": 0.010,
            "MnO₂": 0.080, "MnO2": 0.080, "Limestone": 0.020,
            "Medium GAC": 2.500, "Biodagene": 0.020, "Schist": 0.010,
            "Pumice": 0.015, "FILTRALITE clay": 0.030, "Custom": 0.050,
        }
        st.markdown("**Media embodied carbon**")
        st.caption("One value per media type in the current layer selection.")
        _seen_media: list = []
        for _layer in layers:
            _mt = _layer.get("Type", "Custom")
            if _mt not in _seen_media:
                _seen_media.append(_mt)
        _media_co2: dict = {}
        for _mt in _seen_media:
            _media_co2[_mt] = st.number_input(
                f"{_mt} (kgCO₂/kg)",
                value=_CARBON_DEFAULTS.get(_mt, 0.050),
                min_value=0.0, step=0.001, format="%.3f",
                key=f"carbon_{_mt.replace(' ', '_')}",
            )
        out["media_co2"] = _media_co2

    merge_feed_hydraulics_into_out(out, unit_system)

    # ── Convert display-unit inputs back to SI before returning ───────────
    out = convert_inputs(out, unit_system)
    out["unit_system"] = unit_system
    return out
