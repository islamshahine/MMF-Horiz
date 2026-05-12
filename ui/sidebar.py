"""ui/sidebar.py — Sidebar input rendering for AQUASIGHT™ MMF."""
import streamlit as st
from engine.water import water_properties, FEED_PRESETS, BW_PRESETS
from engine.media import get_media_names, get_media, get_lv_range, get_ebct_range, get_gac_note

# ── Constants mirrored from app.py (kept here so sidebar is self-contained) ──
_DEFAULT_MEDIA_PRESETS = {
    "Gravel":            {"d10": 6.0,  "cu": 1.0, "epsilon0": 0.46, "psi": 0.90,
                          "rho_p_eff": 2600, "d60": 6.00, "is_porous": False, "default_depth": 0.20},
    "Coarse sand":       {"d10": 1.35, "cu": 1.5, "epsilon0": 0.44, "psi": 0.85,
                          "rho_p_eff": 2650, "d60": 2.03, "is_porous": False, "default_depth": 0.60},
    "Fine sand":         {"d10": 0.80, "cu": 1.3, "epsilon0": 0.42, "psi": 0.80,
                          "rho_p_eff": 2650, "d60": 1.04, "is_porous": False, "default_depth": 0.80},
    "Fine sand (extra)": {"d10": 0.50, "cu": 1.3, "epsilon0": 0.41, "psi": 0.75,
                          "rho_p_eff": 2650, "d60": 0.65, "is_porous": False, "default_depth": 0.70},
    "Anthracite":        {"d10": 1.30, "cu": 1.5, "epsilon0": 0.48, "psi": 0.70,
                          "rho_p_eff": 1450, "d60": 2.25, "is_porous": False, "default_depth": 0.80},
    "Garnet":            {"d10": 0.30, "cu": 1.3, "epsilon0": 0.38, "psi": 0.80,
                          "rho_p_eff": 4100, "d60": 0.39, "is_porous": False, "default_depth": 0.10},
    "MnO₂":             {"d10": 1.00, "cu": 2.4, "epsilon0": 0.50, "psi": 0.65,
                          "rho_p_eff": 4200, "d60": 2.40, "is_porous": False, "default_depth": 0.40},
    "Medium GAC":        {"d10": 1.00, "cu": 1.6, "epsilon0": 0.55, "psi": 0.65,
                          "rho_p_eff": 1000, "d60": 1.44, "is_porous": True,  "default_depth": 1.00},
    "Biodagene":         {"d10": 2.50, "cu": 1.4, "epsilon0": 0.42, "psi": 0.80,
                          "rho_p_eff": 1600, "d60": 3.50, "is_porous": False, "default_depth": 0.60},
    "Schist":            {"d10": 3.30, "cu": 1.5, "epsilon0": 0.47, "psi": 0.65,
                          "rho_p_eff": 1300, "d60": 4.95, "is_porous": False, "default_depth": 0.30},
    "Limestone":         {"d10": 3.00, "cu": 1.4, "epsilon0": 0.55, "psi": 0.60,
                          "rho_p_eff": 2700, "d60": 4.20, "is_porous": False, "default_depth": 0.50},
    "Pumice":            {"d10": 1.50, "cu": 1.3, "epsilon0": 0.55, "psi": 0.55,
                          "rho_p_eff":  900, "d60": 1.56, "is_porous": True,  "default_depth": 0.60},
    "FILTRALITE clay":   {"d10": 1.20, "cu": 1.5, "epsilon0": 0.48, "psi": 0.50,
                          "rho_p_eff": 1250, "d60": 1.80, "is_porous": True,  "default_depth": 0.80},
    "Custom":            {"d10": 0.0,  "cu": 1.5, "epsilon0": 0.42, "psi": 0.80,
                          "rho_p_eff": 2650, "d60": 0.0,  "is_porous": False, "default_depth": 0.50},
}

_GAC_MEDIA_NAMES = {"Medium GAC"}


def _eps0_from_psi(psi: float) -> float:
    return round(0.4 + 0.1 * (1.0 - psi) / max(psi, 0.01), 3)


def _rho_eff_porous(rho_dry: float, eps_p: float, rho_water: float = 1025.0) -> float:
    return rho_dry + rho_water * eps_p


def _ensure_presets():
    if ("media_presets" not in st.session_state or
            set(st.session_state.media_presets.keys()) != set(_DEFAULT_MEDIA_PRESETS.keys())):
        st.session_state.media_presets = _DEFAULT_MEDIA_PRESETS.copy()


def render_sidebar(
    MATERIALS, RADIOGRAPHY_OPTIONS, JOINT_EFFICIENCY, PROTECTION_TYPES,
    RUBBER_TYPES, EPOXY_TYPES, CERAMIC_TYPES,
    DEFAULT_LABOR_RUBBER_M2, DEFAULT_LABOR_EPOXY_M2, DEFAULT_LABOR_CERAMIC_M2,
    STEEL_DENSITY_KG_M3, FLANGE_RATINGS, STRAINER_WEIGHT_KG, MANHOLE_WEIGHT_KG,
    SUPPORT_TYPES, NOZZLE_DENSITY_DEFAULT, NOZZLE_DENSITY_MIN, NOZZLE_DENSITY_MAX,
    ELEMENT_SIZE_LABELS, RATING_UM_OPTIONS, HOUSING_CAPACITY_OPTIONS,
    DEFAULT_ELEMENTS_PER_HOUSING, SAFETY_FACTOR_CIP, SAFETY_FACTOR_STD,
) -> dict:
    """Render all sidebar input tabs. Returns dict of every input value."""
    _ensure_presets()
    out = {}

    proc_tab, vessel_tab, media_tab, bw_tab, econ_tab = st.tabs([
        "⚙️ Process", "🏗️ Vessel", "🧱 Media", "🔄 BW", "💰 Econ"
    ])

    # ── Tab 1: Process ────────────────────────────────────────────────────
    with proc_tab:
        st.markdown("**Project**")
        out["project_name"] = st.text_input("Project",     value="NPC SWRO 60 000 m³/d", key="project_name")
        out["doc_number"]   = st.text_input("Doc. No.",    value="EXXXX-VWT-PCS-CAL-2001", key="doc_number")
        out["revision"]     = st.text_input("Revision",    value="A1",             key="revision")
        out["client"]       = st.text_input("Client",      value="",               key="client")
        out["engineer"]     = st.text_input("Prepared by", value="Islam Shahine",  key="engineer")

        st.markdown("**Filter configuration**")
        out["total_flow"] = st.number_input("Total plant flow (m³/h)", value=21000.0, step=100.0, key="total_flow")
        out["streams"]    = int(st.number_input("Streams", value=1, min_value=1, key="streams"))
        out["n_filters"]  = int(st.number_input("Filters / stream", value=16, min_value=1, key="n_filters"))
        out["redundancy"] = int(st.selectbox("Redundancy (per stream)", [0,1,2,3,4], index=1, key="redundancy"))
        q_n = out["total_flow"] / out["streams"] / out["n_filters"]
        st.caption(
            f"Flow / filter (N): **{q_n:.1f} m³/h**  \n"
            f"Redundancy = {out['redundancy']} standby filter(s) per stream  \n"
            f"Total active filters (N scenario): **{out['streams'] * out['n_filters']} plant-wide**"
        )

        st.markdown("**Water quality — feed**")
        feed_preset = st.selectbox("Feed preset", list(FEED_PRESETS.keys()), index=2, key="feed_pre")
        fp = FEED_PRESETS[feed_preset]
        out["feed_sal"]  = st.number_input("Feed salinity (ppt)",    value=fp["salinity_ppt"], step=0.5, key="f_sal")
        out["feed_temp"] = st.number_input("Feed temp — avg (°C)",   value=fp["temp_c"],        step=1.0, key="f_tmp")
        out["temp_low"]  = st.number_input("Feed temp — min (°C)",   value=15.0, step=1.0, key="t_low")
        out["temp_high"] = st.number_input("Feed temp — max (°C)",   value=35.0, step=1.0, key="t_high")
        out["tss_low"]   = st.number_input("Feed TSS — low (mg/L)",  value=5.0,  step=1.0, key="tss_low")
        out["tss_avg"]   = st.number_input("Feed TSS — avg (mg/L)",  value=10.0, step=1.0, key="tss_avg")
        out["tss_high"]  = st.number_input("Feed TSS — high (mg/L)", value=20.0, step=1.0, key="tss_high")

        st.markdown("**Water quality — backwash**")
        bw_preset = st.selectbox("BW preset", list(BW_PRESETS.keys()), index=0, key="bw_pre")
        bp = BW_PRESETS[bw_preset] or fp
        out["bw_sal"]  = st.number_input("BW salinity (ppt)", value=bp["salinity_ppt"], step=0.5, key="b_sal")
        out["bw_temp"] = st.number_input("BW temp (°C)",      value=bp["temp_c"],       step=1.0, key="b_tmp")

        st.markdown("**Performance thresholds**")
        out["velocity_threshold"] = st.number_input("Max LV (m/h)",   value=12.0, key="velocity_threshold")
        out["ebct_threshold"]     = st.number_input("Min EBCT (min)", value=5.0,  key="ebct_threshold")

        st.markdown("**Cartridge filter**")
        out["cart_flow"]   = st.number_input("Design flow (m³/h)", value=float(out["total_flow"]),
                                              step=100.0, key="cart_flow")
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
        _cf_inlet_max  = float(out["tss_avg"])
        _cf_outlet_max = round(0.15 * out["tss_avg"], 2)
        out["cf_inlet_tss"]  = st.number_input("CF inlet TSS (mg/L)", min_value=0.0,
                                                max_value=_cf_inlet_max,
                                                value=min(2.0, _cf_inlet_max), step=0.1,
                                                format="%.2f", key="cf_inlet_tss")
        out["cf_outlet_tss"] = st.number_input("CF outlet TSS — target (mg/L)", min_value=0.0,
                                                max_value=_cf_outlet_max,
                                                value=min(0.5, _cf_outlet_max), step=0.05,
                                                format="%.2f", key="cf_outlet_tss")

    # ── Tab 2: Vessel ─────────────────────────────────────────────────────
    with vessel_tab:
        st.markdown("**Vessel geometry**")
        out["nominal_id"]   = st.number_input("Nominal internal diameter (m)", value=5.5, step=0.1, key="nominal_id")
        out["total_length"] = st.number_input("Total length T/T (m)", value=24.3, step=0.1, key="total_length")
        out["end_geometry"] = st.selectbox("End geometry", ["Elliptic 2:1", "Torispherical 10%"], key="end_geometry")

        st.markdown("**Mechanical (ASME)**")
        out["material_name"]   = st.selectbox("Material", list(MATERIALS.keys()), index=3, key="material_name")
        mat_info               = MATERIALS[out["material_name"]]
        out["mat_info"]        = mat_info
        st.caption(f"*{mat_info['description']}*")
        out["design_pressure"] = st.number_input("Design pressure (bar)", value=7.0, step=0.5, key="design_pressure")
        out["design_temp"]     = st.number_input("Design temperature (°C)", value=50.0, step=5.0, key="design_temp")
        out["corrosion"]       = st.number_input("Corrosion allowance (mm)", value=1.5, step=0.5, key="corrosion")
        st.markdown("*Radiography (ASME UW-11)*")
        rc1, rc2 = st.columns(2)
        with rc1:
            out["shell_radio"] = st.selectbox("Shell", RADIOGRAPHY_OPTIONS, index=2, key="sh_r")
            st.caption(f"E = {JOINT_EFFICIENCY[out['shell_radio']]:.2f}")
        with rc2:
            out["head_radio"]  = st.selectbox("Head",  RADIOGRAPHY_OPTIONS, index=2, key="hd_r")
            st.caption(f"E = {JOINT_EFFICIENCY[out['head_radio']]:.2f}")
        st.markdown("*Thickness overrides* (0 = use calculated)")
        out["ov_shell"]     = st.number_input("Shell t override (mm)", value=0.0, step=1.0, key="ov_sh")
        out["ov_head"]      = st.number_input("Head t override (mm)",  value=0.0, step=1.0, key="ov_hd")
        out["steel_density"]= st.number_input("Steel density (kg/m³)", value=STEEL_DENSITY_KG_M3, key="steel_density")

        st.markdown("**Internal protection**")
        out["protection_type"] = st.selectbox("Protection type", PROTECTION_TYPES, index=1, key="prot_type")

        if out["protection_type"] == "Rubber lining":
            out["rubber_type_sel"] = st.selectbox("Rubber type", list(RUBBER_TYPES.keys()), index=1, key="rub_type")
            out["lining_mm"]       = st.number_input("Rubber thickness / layer (mm)", value=4.0, step=0.5,
                                                      min_value=0.5, key="rub_t")
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

    # ── Tab 3: Media ──────────────────────────────────────────────────────
    with media_tab:
        st.markdown("**Nozzle plate**")
        out["nozzle_plate_h"] = st.number_input("Nozzle plate height (m)", value=1.0, step=0.05, key="nozzle_plate_h")
        out["np_bore_dia"]    = st.number_input("Bore diameter (mm)", value=50.0,
                                                 step=5.0, min_value=10.0, key="np_bd")
        out["np_density"]     = st.number_input("Nozzle density (/m²)", value=NOZZLE_DENSITY_DEFAULT,
                                                 min_value=NOZZLE_DENSITY_MIN, max_value=NOZZLE_DENSITY_MAX,
                                                 step=1.0, key="np_den")
        out["np_beam_sp"]     = st.number_input("Beam spacing (mm)", value=500.0,
                                                 step=50.0, key="np_bs")
        out["np_override_t"]  = st.number_input("Override plate t (mm) — 0=calc",
                                                  value=0.0, step=1.0, key="np_ov")

        st.markdown("**Media layers**")
        out["n_layers"] = int(st.selectbox("Layers", [1, 2, 3, 4, 5, 6], index=2, key="n_layers"))
        _rho_water_sb   = water_properties(out["feed_temp"], out["feed_sal"])["density_kg_m3"]
        layers = []
        default_types = ["Gravel", "Fine sand", "Anthracite"]
        for i in range(out["n_layers"]):
            st.markdown(f"**Layer {i+1}** (bottom → top)")
            def_type = default_types[i] if i < 3 else "Custom"
            preset_keys = list(st.session_state.media_presets.keys())
            m_type = st.selectbox("Type", preset_keys,
                                  index=preset_keys.index(def_type),
                                  key=f"lt_{i}")
            preset = st.session_state.media_presets[m_type]
            depth  = st.number_input("Depth (m)", value=preset["default_depth"],
                                     step=0.05, key=f"ld_{i}")
            is_sup = st.checkbox("Support media (no clogging)",
                                 value=(m_type == "Gravel"), key=f"sup_{i}")
            if not is_sup:
                cap_raw  = st.number_input("Capture weight", value=round(depth * 100, 0),
                                           step=5.0, min_value=0.0, key=f"cap_{i}")
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
                        f"Envelope — LV: {_lv_lo}–{_lv_hi} m/h · "
                        f"EBCT: {_eb_lo}–{_eb_hi} min"
                    )

            data = preset.copy()
            if m_type == "Custom":
                _c1, _c2 = st.columns(2)
                _d10  = _c1.number_input("d10 (mm)", value=1.0, step=0.05,
                                         min_value=0.01, key=f"d10_{i}")
                _cu   = _c2.number_input("CU (d60/d10)", value=1.5, step=0.05,
                                         min_value=1.0, key=f"cu_{i}")
                _psi  = _c1.number_input("Sphericity ψ", value=0.80, step=0.05,
                                         min_value=0.3, max_value=1.0, key=f"psi_{i}")
                _eps0_est = _eps0_from_psi(_psi)
                _eps0 = _c2.number_input("Voidage ε₀", value=_eps0_est, step=0.01,
                                         min_value=0.25, max_value=0.70, key=f"ep_{i}")
                _is_por = st.checkbox("Porous media (water fills particle pores)",
                                      value=False, key=f"por_{i}")
                if _is_por:
                    _p1, _p2 = st.columns(2)
                    _rho_dry = _p1.number_input("Dry apparent density (kg/m³)",
                                                 value=500.0, step=50.0, min_value=100.0, key=f"rhd_{i}")
                    _eps_p   = _p2.number_input("Particle internal porosity εₚ", value=0.50,
                                                 step=0.05, min_value=0.0, max_value=0.95, key=f"epp_{i}")
                    _rho_eff = _rho_eff_porous(_rho_dry, _eps_p, _rho_water_sb)
                    st.caption(f"ρ_eff = {_rho_eff:.0f} kg/m³")
                else:
                    _rho_eff = st.number_input("Particle density (kg/m³)",
                                                value=2650.0, step=50.0, min_value=100.0, key=f"rh_{i}")
                data["d10"]       = _d10
                data["cu"]        = _cu
                data["d60"]       = round(_d10 * _cu, 3)
                data["epsilon0"]  = _eps0
                data["psi"]       = _psi
                data["is_porous"] = _is_por
                data["rho_p_eff"] = round(_rho_eff, 1)
            layers.append({**data, "Type": m_type, "Depth": depth,
                           "is_support": is_sup, "capture_frac": cap_frac,
                           "gac_mode": gac_mode})
        out["layers"] = layers

        st.markdown("**Filtration performance**")
        out["solid_loading"]          = st.number_input("Solid loading before BW (kg/m²)", value=1.5, step=0.1, key="solid_loading")
        out["captured_solids_density"]= st.number_input("Captured solids density (kg/m³)", value=1020.0, step=10.0, key="captured_solids_density")
        alpha_9 = st.number_input("Specific cake resistance α (× 10⁹ m/kg)",
                                   value=0.0, step=5.0, min_value=0.0, key="alpha_res")
        out["alpha_specific"] = alpha_9 * 1e9

    # ── Tab 4: BW ─────────────────────────────────────────────────────────
    with bw_tab:
        st.markdown("**BW hydraulics**")
        out["collector_h"]    = st.number_input("BW outlet collector height (m)", value=4.2, step=0.1, key="collector_h")
        out["freeboard_mm"]   = st.number_input("Min. freeboard (mm)", value=200, step=50,
                                                  min_value=50, key="fb_mm")
        out["bw_velocity"]    = st.number_input("Proposed BW velocity (m/h)", value=30.0, step=5.0, key="bw_velocity")
        out["air_scour_rate"] = st.number_input("Air scour rate (m/h)", value=55.0, step=5.0, key="air_scour_rate")

        st.markdown("**BW sequence**")
        out["bw_cycles_day"]  = int(st.number_input("BW cycles / filter / day", value=1, min_value=1, key="bw_cycles_day"))
        out["dp_trigger_bar"] = st.number_input("BW initiation ΔP setpoint (bar)", value=1.0,
                                                  step=0.1, min_value=0.01, key="dp_trig")
        out["bw_s_drain"]  = st.number_input("① Gravity drain (min)",       value=10, step=1, min_value=0, key="bws1")
        out["bw_s_air"]    = st.number_input("② Air scour only (min)",       value=1,  step=1, min_value=0, key="bws2")
        out["bw_s_airw"]   = st.number_input("③ Air + low-rate water (min)", value=5,  step=1, min_value=0, key="bws3")
        out["bw_s_hw"]     = st.number_input("④ High-rate water flush (min)",value=10, step=1, min_value=0, key="bws4")
        out["bw_s_settle"] = st.number_input("⑤ Settling (min)",             value=2,  step=1, min_value=0, key="bws5")
        out["bw_s_fill"]   = st.number_input("⑥ Fill & rinse (min)",         value=10, step=1, min_value=0, key="bws6")
        out["bw_total_min"] = (out["bw_s_drain"] + out["bw_s_air"] + out["bw_s_airw"]
                               + out["bw_s_hw"] + out["bw_s_settle"] + out["bw_s_fill"])
        st.metric("Total BW duration", f"{out['bw_total_min']} min")

        st.markdown("**Equipment sizing**")
        out["vessel_pressure_bar"]  = st.number_input("Vessel operating pressure (bar g)",
                                                        value=2.0, step=0.5, min_value=0.0, key="ves_press")
        out["blower_eta"]           = st.number_input("Blower isentropic efficiency", value=0.70,
                                                        step=0.01, min_value=0.30, max_value=0.95, key="blower_eta")
        out["blower_inlet_temp_c"]  = st.number_input("Blower inlet air temperature (°C)", value=30.0,
                                                        step=5.0, min_value=-10.0, max_value=60.0, key="blower_t")
        out["tank_sf"]              = st.number_input("BW tank safety factor", value=1.5,
                                                        step=0.1, min_value=1.0, max_value=3.0, key="tank_sf")
        out["bw_head_mwc"]          = st.number_input("BW pump total head (mWC)", value=15.0,
                                                        step=1.0, min_value=1.0, key="bw_hd")

        st.markdown("**Nozzles & supports**")
        out["default_rating"]  = st.selectbox("Flange rating", FLANGE_RATINGS, index=1, key="default_rating")
        out["nozzle_stub_len"] = st.number_input("Nozzle stub length (mm)", value=350, step=50, key="nozzle_stub_len")
        out["strainer_mat"]    = st.selectbox("Strainer material", list(STRAINER_WEIGHT_KG.keys()), index=0, key="strainer_mat")
        out["air_header_dn"]   = st.number_input("Air scour header DN (mm)", value=200, step=50, key="ah_dn")
        out["manhole_dn"]      = st.selectbox("Manhole size", list(MANHOLE_WEIGHT_KG.keys()), index=0, key="manhole_dn")
        out["n_manholes"]      = int(st.number_input("No. of manholes", value=1, min_value=0, step=1, key="n_manholes"))
        out["support_type"]    = st.selectbox("Support type", SUPPORT_TYPES, key="sup_t")
        if "Saddle" in out["support_type"]:
            out["saddle_h"]             = st.number_input("Saddle height (m)", value=0.8, step=0.05, key="sad_h")
            out["base_plate_t"]         = st.number_input("Base plate t (mm)", value=20.0, step=2.0, key="sad_bp")
            out["gusset_t"]             = st.number_input("Gusset t (mm)", value=12.0, step=2.0, key="sad_gt")
            out["saddle_contact_angle"] = st.number_input("Saddle contact angle (°)", value=120.0,
                                                           step=15.0, min_value=90.0, max_value=180.0, key="sad_ang")
            out["leg_h"] = 1.2; out["leg_section"] = 150.0
        else:
            out["leg_h"]                = st.number_input("Leg height (m)", value=1.2, step=0.1, key="leg_h")
            out["leg_section"]          = st.number_input("Leg section (mm)", value=150.0, step=25.0, key="leg_s")
            out["base_plate_t"]         = st.number_input("Base plate t (mm)", value=20.0, step=2.0, key="leg_bp")
            out["gusset_t"]             = st.number_input("Gusset t (mm)", value=12.0, step=2.0, key="leg_gt")
            out["saddle_h"] = 0.8; out["saddle_contact_angle"] = 120.0

    # ── Tab 5: Econ ───────────────────────────────────────────────────────
    with econ_tab:
        st.markdown("**Pump hydraulics**")
        out["np_slot_dp"]     = st.number_input("Strainer nozzle plate ΔP at design LV (bar)",
                                                  value=0.02, step=0.005, min_value=0.0,
                                                  format="%.3f", key="np_slot")
        out["p_residual"]     = st.number_input("Required downstream pressure (barg)",
                                                  value=2.50, step=0.25, min_value=0.0, key="p_res")
        out["dp_inlet_pipe"]  = st.number_input("Inlet piping losses (bar)", value=0.30,
                                                  step=0.05, min_value=0.0, key="dp_in")
        out["dp_dist"]        = st.number_input("Inlet distributor ΔP (bar)", value=0.02,
                                                  step=0.01, min_value=0.0, key="dp_dist")
        out["dp_outlet_pipe"] = st.number_input("Outlet piping losses (bar)", value=0.20,
                                                  step=0.05, min_value=0.0, key="dp_out")
        out["static_head"]    = st.number_input("Static elevation head (m)", value=0.0,
                                                  step=0.5, key="stat_h")

        st.markdown("**Efficiencies**")
        out["pump_eta"]    = st.number_input("Filtration pump η", value=0.75, step=0.01,
                                              min_value=0.30, max_value=0.95, key="pump_e")
        out["bw_pump_eta"] = st.number_input("BW pump η", value=0.72, step=0.01,
                                              min_value=0.30, max_value=0.95, key="bwp_e")
        out["motor_eta"]   = st.number_input("Motor η (all motors)", value=0.95, step=0.01,
                                              min_value=0.70, max_value=0.99, key="mot_e")

        st.markdown("**Energy economics**")
        out["elec_tariff"] = st.number_input("Electricity tariff (USD/kWh)", value=0.10,
                                              step=0.01, min_value=0.01, key="elec_t")
        out["op_hours_yr"] = st.number_input("Operating hours / year", value=8400,
                                              step=100, min_value=1000, key="op_hr")

        st.markdown("**CAPEX inputs**")
        out["design_life_years"]         = st.number_input("Design life (years)", value=20, step=1, min_value=5, key="des_life")
        out["discount_rate"]             = st.number_input("Discount rate (%)", value=5.0, step=0.5, min_value=0.0, key="disc_rate")
        out["currency"]                  = st.selectbox("Currency", ["USD","EUR","GBP","SAR","AED"], key="currency")
        out["steel_cost_usd_kg"]         = st.number_input("Steel cost (USD/kg)", value=3.5, step=0.1, key="st_cost")
        out["erection_usd_vessel"]       = st.number_input("Erection cost (USD/vessel)", value=50000.0, step=5000.0, key="erect_usd")
        out["piping_usd_vessel"]         = st.number_input("Piping cost (USD/vessel)", value=80000.0, step=5000.0, key="pip_usd")
        out["instrumentation_usd_vessel"]= st.number_input("Instrumentation (USD/vessel)", value=30000.0, step=5000.0, key="instr_usd")
        out["civil_usd_vessel"]          = st.number_input("Civil works (USD/vessel)", value=40000.0, step=5000.0, key="civil_usd")
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
        out["chemical_cost_m3"]      = st.number_input("Chemical cost (USD/m³ treated)", value=0.005,
                                                        step=0.001, format="%.3f", key="chem_m3")

        st.markdown("**Carbon footprint**")
        out["grid_intensity"]       = st.number_input("Grid intensity (kgCO₂/kWh)", value=0.45, step=0.01, key="grid_co2")
        out["steel_carbon_kg"]      = st.number_input("Steel embodied carbon (kgCO₂/kg)", value=1.85, step=0.05, key="st_co2")
        out["concrete_carbon_kg"]   = st.number_input("Concrete embodied carbon (kgCO₂/kg)", value=0.13, step=0.01, key="con_co2")
        out["media_co2_gravel"]     = st.number_input("Gravel carbon (kgCO₂/kg)", value=0.004, step=0.001, format="%.3f", key="mco_gr")
        out["media_co2_sand"]       = st.number_input("Sand carbon (kgCO₂/kg)", value=0.006, step=0.001, format="%.3f", key="mco_sd")
        out["media_co2_anthracite"] = st.number_input("Anthracite carbon (kgCO₂/kg)", value=0.15, step=0.01, key="mco_an")

    return out
