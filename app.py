"""
AQUASIGHT™ MMF  —  Horizontal Multi-Media Filter Calculator
============================================================
Block flow (matches calculation dependency order):
  1  Process basis       → flow / filter per scenario
  2  Water properties    → density, viscosity (feed + BW, 3 scenarios)
  3  Vessel geometry     → real ID, volumes, cross-sections
     Mechanical          → ASME thickness, weight: body + nozzles + plate + supports
  4  Media design        → volumes, EBCT, LV, ΔP, inventory
  5  Backwash design     → collector check, expansion, pump/blower, sequence
  6  Weight summary      → consolidated empty weight
"""

import io
import math
import pandas as pd
import streamlit as st

try:
    from docx import Document as _DocxDocument
    from docx.shared import Pt as _Pt, Cm as _Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH as _WD_ALIGN
    _DOCX_OK = True
except ImportError:
    _DOCX_OK = False

from engine.geometry   import segment_area, dish_volume
from engine.process    import filter_loading
from engine.water      import water_properties, FEED_PRESETS, BW_PRESETS
from engine.mechanical import (
    thickness, apply_thickness_override, empty_weight,
    nozzle_plate_design, nozzle_plate_area, saddle_weight, internals_weight,
    MATERIALS, RADIOGRAPHY_OPTIONS, JOINT_EFFICIENCY,
    STEEL_DENSITY_KG_M3, SUPPORT_TYPES,
    NOZZLE_DENSITY_MIN, NOZZLE_DENSITY_MAX, NOZZLE_DENSITY_DEFAULT,
    STRAINER_WEIGHT_KG, MANHOLE_WEIGHT_KG,
)
from engine.nozzles import (
    estimate_nozzle_schedule,
    FLANGE_RATINGS, SCHEDULES, DN_SERIES,
)
from engine.backwash import (
    backwash_hydraulics, bed_expansion, pressure_drop,
    bw_sequence, filtration_cycle,
)
from engine.collector_ext import collector_check_ext
from engine.cartridge import (
    cartridge_design, cartridge_optimise,
    ELEMENT_SIZE_LABELS, RATING_UM_OPTIONS,
    HOUSING_CAPACITY_OPTIONS, DEFAULT_ELEMENTS_PER_HOUSING,
    MARKET_ROUNDS, DP_REPLACEMENT_BAR, DHC_G_PER_TIE,
    SAFETY_FACTOR_STD, SAFETY_FACTOR_CIP,
)
from engine.energy import hydraulic_profile, energy_summary

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="AQUASIGHT™ MMF", layout="wide",
                   initial_sidebar_state="collapsed")

# ══════════════════════════════════════════════════════════════════════════════
# MEDIA PRESETS  (default 3-layer: Gravel / Sand / Anthracite)
# ══════════════════════════════════════════════════════════════════════════════
DEFAULT_MEDIA_PRESETS = {
    "Gravel":      {"d10": 6.0,  "cu": 1.0, "epsilon0": 0.46,
                    "rho_p_eff": 2600, "d60": 6.0,  "default_depth": 0.20},
    "Fine Sand":   {"d10": 0.8,  "cu": 1.3, "epsilon0": 0.42,
                    "rho_p_eff": 2650, "d60": 1.04, "default_depth": 0.80},
    "Anthracite":  {"d10": 1.3,  "cu": 1.5, "epsilon0": 0.48,
                    "rho_p_eff": 1450, "d60": 1.95, "default_depth": 0.80},
    "Coarse Sand": {"d10": 1.35, "cu": 1.5, "epsilon0": 0.44,
                    "rho_p_eff": 2650, "d60": 2.03, "default_depth": 0.60},
    "Custom":      {"d10": 0.0,  "cu": 1.0, "epsilon0": 0.40,
                    "rho_p_eff": 2650, "d60": 0.0,  "default_depth": 0.50},
}

if "media_presets" not in st.session_state:
    st.session_state.media_presets = DEFAULT_MEDIA_PRESETS.copy()

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
h1, h2 = st.columns([3, 1])
with h1:
    st.markdown("## AQUASIGHT™ &nbsp; Horizontal Multi-Media Filter")
with h2:
    st.markdown(
        "<p style='text-align:right;color:grey;font-size:13px;margin-top:18px'>"
        "Islam Shahine · Process Expert</p>", unsafe_allow_html=True)
st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# LAYOUT: context column | content tabs
# ══════════════════════════════════════════════════════════════════════════════
ctx, main = st.columns([1, 4], gap="large")

# ─────────────────────────────────────────────────────────────────────────────
# CONTEXT PANEL
# ─────────────────────────────────────────────────────────────────────────────
with ctx:
    st.markdown("#### Inputs")

    # ── Block 1: Project ───────────────────────────────────────────────────
    with st.expander("📋 Project", expanded=True):
        project_name = st.text_input("Project",     value="NPC SWRO 60 000 m³/d")
        doc_number   = st.text_input("Doc. No.",    value="EXXXX-VWT-PCS-CAL-2001")
        revision     = st.text_input("Revision",    value="A1")
        client       = st.text_input("Client",      value="")
        engineer     = st.text_input("Prepared by", value="Islam Shahine")

    # ── Block 1: Process basis ─────────────────────────────────────────────
    with st.expander("💧 Process basis", expanded=True):
        total_flow = st.number_input("Total plant flow (m³/h)",
                                     value=21000.0, step=100.0)
        streams    = int(st.number_input("Streams", value=1, min_value=1))
        n_filters  = int(st.number_input("Filters / stream",
                                          value=16, min_value=1))
        redundancy = int(st.selectbox("Redundancy",
                                      [0, 1, 2, 3, 4], index=1))
        q_n = total_flow / streams / n_filters
        st.caption(f"Flow / filter (N): **{q_n:.1f} m³/h**")

    # ── Block 2: Water properties ──────────────────────────────────────────
    with st.expander("💧 Water properties", expanded=False):
        st.markdown("**Feed water**")
        feed_preset = st.selectbox("Feed preset", list(FEED_PRESETS.keys()),
                                   index=2, key="feed_pre")
        fp = FEED_PRESETS[feed_preset]
        feed_sal = st.number_input("Salinity (ppt)",   value=fp["salinity_ppt"],
                                   step=0.5, key="f_sal")
        feed_temp = st.number_input("Temperature (°C)", value=fp["temp_c"],
                                    step=1.0, key="f_tmp")

        st.markdown("**Backwash water**")
        bw_preset = st.selectbox("BW preset", list(BW_PRESETS.keys()),
                                 index=0, key="bw_pre")
        bp = BW_PRESETS[bw_preset] or fp
        bw_sal  = st.number_input("Salinity (ppt)",   value=bp["salinity_ppt"],
                                  step=0.5, key="b_sal")
        bw_temp = st.number_input("Temperature (°C)", value=bp["temp_c"],
                                  step=1.0, key="b_tmp")

    # ── Block 3: Vessel geometry ───────────────────────────────────────────
    with st.expander("🏗️ Vessel geometry", expanded=True):
        nominal_id   = st.number_input("Nominal internal diameter (m)",
                                       value=5.5, step=0.1,
                                       help="The ID the vessel is sized to. "
                                            "Lining reduces the hydraulic ID.")
        total_length = st.number_input("Total length T/T (m)",
                                       value=24.3, step=0.1)
        end_geometry = st.selectbox("End geometry",
                                    ["Elliptic 2:1", "Torispherical 10%"])

    # ── Block 3: Mechanical ────────────────────────────────────────────────
    with st.expander("⚙️ Mechanical", expanded=False):
        material_name   = st.selectbox("Material", list(MATERIALS.keys()), index=3)
        mat_info        = MATERIALS[material_name]
        st.caption(f"*{mat_info['description']}*")
        design_pressure = st.number_input("Design pressure (bar)", value=7.0, step=0.5)
        design_temp     = st.number_input("Design temperature (°C)", value=50.0, step=5.0)
        corrosion       = st.number_input("Corrosion allowance (mm)", value=1.5, step=0.5)
        lining_mm       = st.number_input("Rubber lining thickness (mm)", value=4.0,
                                          step=0.5,
                                          help="Subtracted from nominal ID to give "
                                               "hydraulic ID used in all calculations.")
        st.markdown("**Radiography (ASME UW-11)**")
        rc1, rc2 = st.columns(2)
        with rc1:
            shell_radio = st.selectbox("Shell", RADIOGRAPHY_OPTIONS, index=2,
                                       key="sh_r")
            st.caption(f"E = {JOINT_EFFICIENCY[shell_radio]:.2f}")
        with rc2:
            head_radio  = st.selectbox("Head",  RADIOGRAPHY_OPTIONS, index=2,
                                       key="hd_r")
            st.caption(f"E = {JOINT_EFFICIENCY[head_radio]:.2f}")

        st.markdown("**Thickness overrides** (0 = use calculated)")
        ov_shell = st.number_input("Shell t override (mm)", value=0.0, step=1.0,
                                   key="ov_sh",
                                   help="Must be ≥ t_min + CA. "
                                        "Enforced automatically.")
        ov_head  = st.number_input("Head t override (mm)",  value=0.0, step=1.0,
                                   key="ov_hd")
        steel_density = st.number_input("Steel density (kg/m³)",
                                        value=STEEL_DENSITY_KG_M3,
                                        help="7850 CS · 7900 SS 304/316")

    # ── Block 3: Nozzle plate ──────────────────────────────────────────────
    with st.expander("🟫 Nozzle plate", expanded=False):
        np_bore_dia    = st.number_input("Bore diameter (mm)", value=50.0,
                                         step=5.0, min_value=10.0, key="np_bd")
        np_density     = st.number_input(
            "Nozzle density (/m²)", value=NOZZLE_DENSITY_DEFAULT,
            min_value=NOZZLE_DENSITY_MIN, max_value=NOZZLE_DENSITY_MAX,
            step=1.0, key="np_den",
            help=f"{NOZZLE_DENSITY_MIN:.0f}–{NOZZLE_DENSITY_MAX:.0f} nozzles/m²")
        np_beam_sp     = st.number_input("Beam spacing (mm)", value=500.0,
                                         step=50.0, key="np_bs",
                                         help="Stiffener beam spacing — "
                                              "effective bending span")
        np_override_t  = st.number_input("Override plate t (mm) — 0=calc",
                                         value=0.0, step=1.0, key="np_ov")

    # ── Block 4: Media layers ──────────────────────────────────────────────
    with st.expander("🧱 Media layers", expanded=True):
        nozzle_plate_h = st.number_input("Nozzle plate height (m)",
                                         value=1.0, step=0.05)
        captured_solids_density = st.number_input(
            "Captured solids density (kg/m³)", value=1020.0, step=10.0,
            help="Density of TSS retained in media voids — typically 1010–1050 kg/m³")
        n_layers = int(st.selectbox("Layers", [1,2,3,4,5,6], index=2))
        layers = []
        default_types = ["Gravel", "Fine Sand", "Anthracite"]
        for i in range(n_layers):
            st.markdown(f"**Layer {i+1}** (bottom → top)")
            def_type = default_types[i] if i < 3 else "Custom"
            m_type = st.selectbox("Type",
                                  list(st.session_state.media_presets.keys()),
                                  index=list(st.session_state.media_presets.keys()
                                             ).index(def_type),
                                  key=f"lt_{i}")
            preset = st.session_state.media_presets[m_type]
            depth  = st.number_input("Depth (m)",
                                     value=preset["default_depth"],
                                     step=0.05, key=f"ld_{i}")
            default_sup = (m_type == "Gravel")
            is_sup = st.checkbox("Support media (no clogging)", value=default_sup,
                                 key=f"sup_{i}")
            if not is_sup:
                cap_raw = st.number_input(
                    "Capture weight", value=round(depth * 100, 0), step=5.0,
                    min_value=0.0, key=f"cap_{i}",
                    help="Relative TSS capture weight — auto-normalised across "
                         "non-support layers. E.g., 30 + 70 → 30 %/70 %.")
                cap_frac = cap_raw / 100.0
            else:
                cap_frac = 0.0
            data   = preset.copy()
            if m_type == "Custom":
                data["d10"]       = st.number_input("d10 (mm)",  value=1.0,
                                                    key=f"d10_{i}")
                data["cu"]        = st.number_input("CU",        value=1.3,
                                                    key=f"cu_{i}")
                data["epsilon0"]  = st.number_input("Voidage ε₀", value=0.42,
                                                    key=f"ep_{i}")
                data["rho_p_eff"] = st.number_input("Density (kg/m³)", value=2650,
                                                    key=f"rh_{i}")
            layers.append({**data, "Type": m_type, "Depth": depth,
                           "is_support": is_sup, "capture_frac": cap_frac})

    # ── Block 5: Backwash ──────────────────────────────────────────────────
    with st.expander("🔄 Backwash design", expanded=False):
        collector_h    = st.number_input(
            "BW outlet collector height (m)", value=4.2, step=0.1,
            help="Height from vessel bottom to BW outlet collector / trough")
        freeboard_mm   = st.number_input(
            "Min. freeboard (mm)", value=200, step=50, min_value=50,
            key="fb_mm",
            help="Minimum clearance required between expanded bed top and "
                 "collector. Governs max-safe-BW binary search.")
        bw_velocity    = st.number_input("Proposed BW velocity (m/h)",
                                         value=30.0, step=5.0)
        air_scour_rate = st.number_input("Air scour rate (m/h)",
                                         value=55.0, step=5.0)
        bw_cycles_day  = int(st.number_input("BW cycles / filter / day",
                                              value=1, min_value=1))
        solid_loading  = st.number_input("Solid loading before BW (kg/m²)",
                                         value=1.5, step=0.1)
        dp_trigger_bar = st.number_input(
            "BW initiation ΔP setpoint (bar)", value=1.0, step=0.1,
            min_value=0.01, key="dp_trig",
            help="Filter triggers BW when ΔP across media reaches this value")
        alpha_9 = st.number_input(
            "Specific cake resistance α (× 10⁹ m/kg)",
            value=0.0, step=5.0, min_value=0.0, key="alpha_res",
            help=(
                "Resistance of deposited TSS cake per unit mass (Ruth model). "
                "0 = auto-calibrate: α is set so that ΔP reaches the trigger "
                "exactly at M_max (solid loading input above). "
                "Typical ranges: coarse mineral / silt  0.1–10 · "
                "seawater mixed TSS  10–50 · "
                "organic-rich / algae  100–500 · "
                "clay / fine colloids  1 000–10 000  (all × 10⁹ m/kg)."
            ))
        alpha_specific = alpha_9 * 1e9   # m/kg
        tss_low  = st.number_input("Feed TSS — low (mg/L)",  value=5.0,  step=1.0)
        tss_avg  = st.number_input("Feed TSS — avg (mg/L)",  value=10.0, step=1.0)
        tss_high = st.number_input("Feed TSS — high (mg/L)", value=20.0, step=1.0)
        st.caption("Temperature range for filtration cycle matrix:")
        temp_low  = st.number_input("Feed temp — min (°C)", value=15.0, step=1.0, key="t_low")
        temp_high = st.number_input("Feed temp — max (°C)", value=35.0, step=1.0, key="t_high")
        st.caption("BW step durations (editable):")
        bw_s_drain  = st.number_input("① Gravity drain (min)",       value=10, step=1, min_value=0, key="bws1")
        bw_s_air    = st.number_input("② Air scour only (min)",       value=1,  step=1, min_value=0, key="bws2")
        bw_s_airw   = st.number_input("③ Air + low-rate water (min)", value=5,  step=1, min_value=0, key="bws3")
        bw_s_hw     = st.number_input("④ High-rate water flush (min)",value=10, step=1, min_value=0, key="bws4")
        bw_s_settle = st.number_input("⑤ Settling (min)",             value=2,  step=1, min_value=0, key="bws5")
        bw_s_fill   = st.number_input("⑥ Fill & rinse (min)",         value=10, step=1, min_value=0, key="bws6")
        bw_total_min = bw_s_drain + bw_s_air + bw_s_airw + bw_s_hw + bw_s_settle + bw_s_fill
        st.metric("Total BW duration", f"{bw_total_min} min")

    # ── Block 3+6: Supports & nozzles ─────────────────────────────────────
    with st.expander("🔩 Nozzles & supports", expanded=False):
        default_rating  = st.selectbox("Flange rating", FLANGE_RATINGS, index=1)
        nozzle_stub_len = st.number_input("Nozzle stub length (mm)",
                                          value=350, step=50)
        strainer_mat    = st.selectbox("Strainer material",
                                       list(STRAINER_WEIGHT_KG.keys()), index=0,
                                       help="SS316 seawater · HDPE/PP fresh/brackish")
        air_header_dn   = st.number_input("Air scour header DN (mm)",
                                          value=200, step=50, key="ah_dn")
        manhole_dn      = st.selectbox("Manhole size",
                                       list(MANHOLE_WEIGHT_KG.keys()), index=0)
        n_manholes      = int(st.number_input("No. of manholes",
                                               value=1, min_value=0, step=1))
        support_type    = st.selectbox("Support type", SUPPORT_TYPES, key="sup_t")
        if "Saddle" in support_type:
            saddle_h      = st.number_input("Saddle height (m)", value=0.8,
                                            step=0.05, key="sad_h")
            base_plate_t  = st.number_input("Base plate t (mm)", value=20.0,
                                            step=2.0, key="sad_bp")
            gusset_t      = st.number_input("Gusset t (mm)",     value=12.0,
                                            step=2.0, key="sad_gt")
            leg_h = 1.2; leg_section = 150.0
        else:
            leg_h         = st.number_input("Leg height (m)",   value=1.2,
                                            step=0.1, key="leg_h")
            leg_section   = st.number_input("Leg section (mm)", value=150.0,
                                            step=25.0, key="leg_s")
            base_plate_t  = st.number_input("Base plate t (mm)", value=20.0,
                                            step=2.0, key="leg_bp")
            gusset_t      = st.number_input("Gusset t (mm)",     value=12.0,
                                            step=2.0, key="leg_gt")
            saddle_h = 0.8

    # ── Energy & economics ─────────────────────────────────────────────────
    with st.expander("⚡ Energy & economics", expanded=False):
        st.caption("Hydraulic profile — filtration pump duty")
        np_slot_dp   = st.number_input(
            "Strainer nozzle plate ΔP at design LV (bar)", value=0.02,
            step=0.005, min_value=0.0, format="%.3f", key="np_slot",
            help=(
                "Hydraulic ΔP through the strainer nozzle slots at filtration flow. "
                "The 50 mm plate bore is for the nozzle body — ΔP is governed by "
                "the fine slots on the nozzle head (manufacturer data). "
                "Typical: 0.01–0.05 bar (0.1–0.5 mWC) at 8–12 m/h."
            ))
        p_residual   = st.number_input(
            "Required downstream pressure (barg)", value=2.50, step=0.25,
            min_value=0.0, key="p_res",
            help="Residual pressure at downstream tie-in (e.g. RO feed header). "
                 "Typically 2–4 barg for SWRO pre-treatment.")
        dp_inlet_pipe = st.number_input(
            "Inlet piping losses (bar)", value=0.30, step=0.05,
            min_value=0.0, key="dp_in",
            help="Feed nozzle + inlet pipe + isolation valve + flow meter + fittings. "
                 "Typical 0.2–0.5 bar depending on pipe sizing and layout.")
        dp_dist      = st.number_input(
            "Inlet distributor ΔP (bar)", value=0.02, step=0.01,
            min_value=0.0, key="dp_dist",
            help="Perforated header-lateral or distributor nozzles. Typical 0.01–0.05 bar.")
        dp_outlet_pipe= st.number_input(
            "Outlet piping losses (bar)", value=0.20, step=0.05,
            min_value=0.0, key="dp_out",
            help="Outlet nozzle + pipe + isolation valve + fittings. Typical 0.1–0.3 bar.")
        static_head  = st.number_input(
            "Static elevation head (m)", value=0.0, step=0.5, key="stat_h",
            help="Filter elevation above pump centre-line (positive = pumping uphill).")
        st.caption("Equipment efficiencies")
        pump_eta     = st.number_input(
            "Filtration pump η", value=0.75, step=0.01,
            min_value=0.30, max_value=0.95, key="pump_e")
        bw_pump_eta  = st.number_input(
            "BW pump η",         value=0.72, step=0.01,
            min_value=0.30, max_value=0.95, key="bwp_e")
        motor_eta    = st.number_input(
            "Motor η (all motors)", value=0.95, step=0.01,
            min_value=0.70, max_value=0.99, key="mot_e")
        bw_head_mwc  = st.number_input(
            "BW pump total head (mWC)", value=15.0, step=1.0,
            min_value=1.0, key="bw_hd",
            help="Typical 12–20 mWC; includes bed + nozzle plate + BW piping losses.")
        st.caption("Economics")
        elec_tariff  = st.number_input(
            "Electricity tariff (USD/kWh)", value=0.10, step=0.01,
            min_value=0.01, key="elec_t")
        op_hours_yr  = st.number_input(
            "Operating hours / year", value=8400, step=100,
            min_value=1000, key="op_hr")

    # ── Performance thresholds ─────────────────────────────────────────────
    with st.expander("⚠️ Thresholds", expanded=False):
        velocity_threshold = st.number_input("Max LV (m/h)",   value=12.0)
        ebct_threshold     = st.number_input("Min EBCT (min)", value=5.0)

    # ── Block 7: Cartridge filter ───────────────────────────────────────────
    with st.expander("🔷 Cartridge filter", expanded=False):
        cart_flow   = st.number_input(
            "Design flow (m³/h)", value=float(total_flow),
            step=100.0, key="cart_flow",
            help="Total flow to the cartridge station (usually = plant flow)")
        cart_size   = st.selectbox(
            "Element length", ELEMENT_SIZE_LABELS, index=2, key="cart_size",
            help="All elements are 2.5\" (63.5 mm) OD. "
                 "Longer elements = more TIEs = higher capacity per housing.")
        cart_rating = st.selectbox(
            "Rating (μm absolute)", RATING_UM_OPTIONS, index=1, key="cart_rating")

        cart_cip = st.toggle(
            "CIP system (SS 316L elements)",
            value=False, key="cart_cip",
            help="CIP (Clean-In-Place): regenerable stainless-steel 316L elements.  "
                 "Applies SF=1.2 (vs 1.5 for disposable polymer), higher DHC (45 g/TIE), "
                 "longer replacement interval, and SS 316L unit costs.")

        # Housing size: standard market rounds + optional custom value
        _hsg_options = [str(r) for r in HOUSING_CAPACITY_OPTIONS] + ["Custom…"]
        _hsg_default_idx = HOUSING_CAPACITY_OPTIONS.index(DEFAULT_ELEMENTS_PER_HOUSING)
        cart_hsg_sel = st.selectbox(
            "Elements per housing (market round)", _hsg_options,
            index=_hsg_default_idx, key="cart_hsg_sel",
            help="Standard market rounds: 1·3·5·7·12·18·21·28·36·52·75·100·160·200.  "
                 "Select 'Custom…' to enter any value up to 500.  "
                 "Use the optimisation table in the Cartridge tab to find the best fit.")
        if cart_hsg_sel == "Custom…":
            cart_housing = st.number_input(
                "Custom elements per housing", min_value=1, max_value=500,
                value=100, step=1, key="cart_hsg_custom",
                help="Enter a non-standard housing capacity (e.g. 120, 144, 180).")
        else:
            cart_housing = int(cart_hsg_sel)

        _sf_label = f"SF = {SAFETY_FACTOR_CIP}" if cart_cip else f"SF = {SAFETY_FACTOR_STD}"
        st.caption(
            f"{'🔩 SS 316L CIP mode — ' + _sf_label if cart_cip else '🔵 Polymer standard — ' + _sf_label}.  "
            "Capacity = TIE × BASE_FLOW_TIE / μ_feed.  "
            "Feed viscosity from temperature & salinity inputs.")

# ══════════════════════════════════════════════════════════════════════════════
# PRE-COMPUTE — all calculations in dependency order
# ══════════════════════════════════════════════════════════════════════════════

# ── Block 2: Water properties ──────────────────────────────────────────────
feed_wp = water_properties(feed_temp, feed_sal)
bw_wp   = water_properties(bw_temp,  bw_sal)

rho_feed = feed_wp["density_kg_m3"]
mu_feed  = feed_wp["viscosity_pa_s"]
rho_bw   = bw_wp["density_kg_m3"]
mu_bw    = bw_wp["viscosity_pa_s"]

# ── Block 3: Vessel geometry ───────────────────────────────────────────────
h_dish  = (nominal_id / 4) if end_geometry == "Elliptic 2:1" \
          else (0.2 * nominal_id)
cyl_len = total_length - 2 * h_dish

# Real hydraulic ID (nominal minus lining)
real_id = nominal_id - 2.0 * lining_mm / 1000.0

# ── Block 3: Mechanical ────────────────────────────────────────────────────
mech_base = thickness(
    diameter_m=nominal_id,
    design_pressure_bar=design_pressure,
    material_name=material_name,
    shell_radio=shell_radio,
    head_radio=head_radio,
    corrosion_mm=corrosion,
    internal_lining_mm=lining_mm,
)
mech = apply_thickness_override(
    mech_base,
    override_shell_mm=ov_shell,
    override_head_mm=ov_head,
    internal_lining_mm=lining_mm,
    nominal_id_m=nominal_id,
)
# Attach corrosion for override floor check
mech["corrosion_mm"] = corrosion

wt_body = empty_weight(
    diameter_m=real_id,
    straight_length_m=cyl_len,
    end_geometry=end_geometry,
    t_shell_mm=mech["t_shell_design_mm"],
    t_head_mm=mech["t_head_design_mm"],
    density_kg_m3=steel_density,
)

# ── Block 4: Media geometry (uses real_id) ─────────────────────────────────
geo_rows, base = [], []
curr_h = nozzle_plate_h

if nozzle_plate_h > 0:
    a0  = segment_area(0, real_id)
    a1  = segment_area(nozzle_plate_h, real_id)
    v_c = (a1 - a0) * cyl_len
    v_e = (dish_volume(nozzle_plate_h, real_id, h_dish, end_geometry) -
           dish_volume(0,              real_id, h_dish, end_geometry)) * 2
    tot = v_c + v_e
    geo_rows.append(["Nozzle Plate", nozzle_plate_h,
                     tot / nozzle_plate_h if nozzle_plate_h else 0,
                     v_c, v_e, tot])

for L in layers:
    h1, h2 = curr_h, curr_h + L["Depth"]
    v_c = (segment_area(h2, real_id) - segment_area(h1, real_id)) * cyl_len
    v_e = (dish_volume(h2, real_id, h_dish, end_geometry) -
           dish_volume(h1, real_id, h_dish, end_geometry)) * 2
    vol  = v_c + v_e
    area = vol / L["Depth"] if L["Depth"] > 0 else 0
    base.append({**L, "Vol": vol, "Area": area})
    geo_rows.append([L["Type"], L["Depth"], area, v_c, v_e, vol])
    curr_h = h2

avg_area     = sum(b["Area"] for b in base) / len(base) if base else 1.0
q_per_filter = (total_flow / streams) / n_filters

# ── Block 4: Pressure drop (Ergun) uses BW water properties ───────────────
bw_dp = pressure_drop(
    layers=layers,
    q_filter_m3h=q_per_filter,
    avg_area_m2=avg_area,
    solid_loading_kg_m2=solid_loading,
    captured_density_kg_m3=captured_solids_density,
    water_temp_c=feed_temp,
    rho_water=rho_feed,
    alpha_m_kg=alpha_specific,
    dp_trigger_bar=dp_trigger_bar,
)
# Use dirty ΔP as the nozzle plate design ΔP (auto-wired, no manual input needed)
np_dp_auto = bw_dp["dp_dirty_bar"]

# ── Block 3: Nozzle plate (uses dirty ΔP and real_id) ─────────────────────
wt_np = nozzle_plate_design(
    vessel_id_m=real_id,
    cyl_len_m=cyl_len,
    h_dish_m=h_dish,
    h_plate_m=nozzle_plate_h,
    design_dp_bar=np_dp_auto,
    media_layers=layers,
    water_density_kg_m3=rho_feed,
    nozzle_density_per_m2=np_density,
    bore_diameter_mm=np_bore_dia,
    beam_spacing_mm=np_beam_sp,
    allowable_stress_kgf_cm2=float(mech["allowable_stress"]),
    corrosion_allowance_mm=corrosion,
    density_kg_m3=steel_density,
    override_thickness_mm=np_override_t,
)

# ── Block 6: Nozzle schedule ───────────────────────────────────────────────
nozzle_sched = estimate_nozzle_schedule(
    q_filter_m3h=q_per_filter,
    bw_velocity_ms=bw_velocity,
    area_filter_m2=avg_area,
    default_rating=default_rating,
    stub_length_mm=float(nozzle_stub_len),
)

# ── Block 6: Supports ──────────────────────────────────────────────────────
wt_sup = saddle_weight(
    vessel_od_m=mech["od_m"],
    vessel_length_m=total_length,
    support_type=support_type,
    saddle_height_m=saddle_h,
    leg_height_m=leg_h,
    leg_section_mm=leg_section,
    base_plate_thickness_mm=base_plate_t,
    gusset_thickness_mm=gusset_t,
    density_kg_m3=steel_density,
)

# ── Block 5: Backwash ──────────────────────────────────────────────────────
bw_hyd = backwash_hydraulics(
    filter_area_m2=avg_area,
    bw_rate_m_h=bw_velocity,
    air_scour_rate_m_h=air_scour_rate,
    filtration_flow_m3h=q_per_filter,
)

bw_col = collector_check_ext(
    layers=layers,
    nozzle_plate_h_m=nozzle_plate_h,
    collector_h_m=collector_h,
    bw_velocity_m_h=bw_velocity,
    water_temp_c=bw_temp,
    rho_water=rho_bw,
    min_freeboard_m=freeboard_mm / 1000.0,
)

bw_exp = bed_expansion(
    layers=layers,
    bw_velocity_m_h=bw_velocity,
    water_temp_c=bw_temp,
    rho_water=rho_bw,
)

bw_seq = bw_sequence(
    filter_area_m2=avg_area,
    tss_scenarios=[tss_low, tss_avg, tss_high],
    n_filters_total=streams * n_filters,
    bw_per_day_per_filter=bw_cycles_day,
)

# ── Block 6: Internals weight ─────────────────────────────────────────────
wt_int = internals_weight(
    n_strainer_nozzles=wt_np.get("n_bores", 0),
    strainer_material=strainer_mat,
    air_header_dn_mm=int(air_header_dn),
    cyl_len_m=cyl_len,
    manhole_dn=manhole_dn,
    n_manholes=n_manholes,
    density_kg_m3=steel_density,
)

# ── TSS mass balance ────────────────────────────────────────────────────────
run_time_h = bw_seq.get("run_time_h", 24.0)
waste_vol   = bw_seq.get("waste_vol_avg_m3", 1.0)

def _tss_bal(tss_mg_l):
    m_sol = tss_mg_l * q_per_filter * run_time_h / 1000.0
    w_tss = (m_sol * 1e3) / waste_vol if waste_vol > 0 else 0.0
    m_day = m_sol * (streams * n_filters) * bw_cycles_day
    return round(m_sol, 1), round(w_tss, 0), round(m_day, 0)

m_sol_low,  w_tss_low,  m_daily_low  = _tss_bal(tss_low)
m_sol_avg,  w_tss_avg,  m_daily_avg  = _tss_bal(tss_avg)
m_sol_high, w_tss_high, m_daily_high = _tss_bal(tss_high)

# ── Filtration cycle (DP-trigger based, design temperature) ──────────────
_load_data_cyc = filter_loading(total_flow, streams, n_filters, redundancy)
filt_cycles: dict = {}
for _x, _nact, _q in _load_data_cyc:
    _sc = "N" if _x == 0 else f"N-{_x}"
    filt_cycles[_sc] = filtration_cycle(
        layers=layers,
        q_filter_m3h=_q,
        avg_area_m2=avg_area,
        solid_loading_kg_m2=solid_loading,
        captured_density_kg_m3=captured_solids_density,
        water_temp_c=feed_temp,
        rho_water=rho_feed,
        dp_trigger_bar=dp_trigger_bar,
        alpha_m_kg=alpha_specific,
        tss_mg_l_list=[tss_low, tss_avg, tss_high],
    )

# ── Filtration cycle matrix: TSS × temperature, α fixed at design value ──
# α is locked to the design-temperature calibration so that temperature
# variation reflects real viscosity effect on cycle duration.
_alpha_fixed  = filt_cycles["N"]["alpha_used_m_kg"] if filt_cycles else 0.0
_tss_labels   = [f"Low ({tss_low:.0f} mg/L)",
                 f"Avg ({tss_avg:.0f} mg/L)",
                 f"High ({tss_high:.0f} mg/L)"]
_tss_vals     = [tss_low, tss_avg, tss_high]
_temp_vals    = [temp_low, feed_temp, temp_high]
_temp_labels  = [f"Min ({temp_low:.0f}°C)",
                 f"Design ({feed_temp:.0f}°C)",
                 f"Max ({temp_high:.0f}°C)"]
# cycle_matrix[sc_label][temp_label] = filtration_cycle result
cycle_matrix: dict = {}
for _x, _nact, _q in _load_data_cyc:
    _sc = "N" if _x == 0 else f"N-{_x}"
    cycle_matrix[_sc] = {}
    for _tv, _tl in zip(_temp_vals, _temp_labels):
        cycle_matrix[_sc][_tl] = filtration_cycle(
            layers=layers,
            q_filter_m3h=_q,
            avg_area_m2=avg_area,
            solid_loading_kg_m2=solid_loading,
            captured_density_kg_m3=captured_solids_density,
            water_temp_c=_tv,
            rho_water=rho_feed,
            dp_trigger_bar=dp_trigger_bar,
            alpha_m_kg=_alpha_fixed,
            tss_mg_l_list=_tss_vals,
        )

# ── BW scheduling & feasibility ──────────────────────────────────────────
import math as _math
_bw_dur_h = bw_total_min / 60.0   # BW duration in hours

# feasibility_matrix[sc_label][temp_label][tss_label] = dict of KPIs
def _feas_kpis(t_cycle_h, bw_dur_h, n_active_filters):
    """Return operational KPIs for one (cycle_time, BW_duration, n_filters) set."""
    t_total   = t_cycle_h + bw_dur_h          # full filtration + BW period
    avail_pct = t_cycle_h / t_total * 100 if t_total > 0 else 0.0
    bw_per_day = 24.0 / t_total if t_total > 0 else 0.0
    # steady-state fraction of filters in BW at any moment
    sim_demand = n_active_filters * bw_dur_h / t_total if t_total > 0 else 0.0
    bw_trains  = max(1, _math.ceil(sim_demand))

    # Feasibility score
    if avail_pct >= 90 and bw_trains <= 1 and t_cycle_h >= 6:
        score, flag = "🟢 Good", "OK"
    elif avail_pct >= 80 and bw_trains <= 2 and t_cycle_h >= 3:
        score, flag = "🟡 Caution", "Review"
    else:
        score, flag = "🔴 Critical", "Redesign"

    return {
        "t_cycle_h":   round(t_cycle_h,   2),
        "avail_pct":   round(avail_pct,    1),
        "bw_per_day":  round(bw_per_day,   1),
        "sim_demand":  round(sim_demand,   2),
        "bw_trains":   bw_trains,
        "score":       score,
        "flag":        flag,
    }

feasibility_matrix: dict = {}
for _x, _nact, _q in _load_data_cyc:
    _sc = "N" if _x == 0 else f"N-{_x}"
    feasibility_matrix[_sc] = {}
    for _t_lbl in _temp_labels:
        feasibility_matrix[_sc][_t_lbl] = {}
        for _tss_lbl, _tss_v in zip(_tss_labels, _tss_vals):
            _cyc_t = cycle_matrix[_sc][_t_lbl]
            _tr    = next((r for r in _cyc_t["tss_results"]
                           if r["TSS (mg/L)"] == _tss_v), None)
            _t_cyc = _tr["Cycle duration (h)"] if _tr else 0.0
            feasibility_matrix[_sc][_t_lbl][_tss_lbl] = _feas_kpis(
                _t_cyc, _bw_dur_h, _nact
            )

# ── Cartridge design ──────────────────────────────────────────────────────
_cart_mu_cP = mu_feed * 1000.0   # Pa·s → cP

cart_result = cartridge_design(
    design_flow_m3h=cart_flow,
    element_size=cart_size,
    rating_um=cart_rating,
    mu_cP=_cart_mu_cP,
    n_elem_per_housing=cart_housing,
    is_CIP_system=cart_cip,
)

cart_optim = cartridge_optimise(
    design_flow_m3h=cart_flow,
    rating_um=cart_rating,
    mu_cP=_cart_mu_cP,
    is_CIP_system=cart_cip,
)

# ── Hydraulic profile & energy ────────────────────────────────────────────
# Strainer nozzle plate ΔP: user-specified at design LV (vendor data).
# The plate bore (50 mm) is the nozzle body hole — actual ΔP is set by
# the fine slots on the nozzle head, which vary by manufacturer.
_np_dp_bar = np_slot_dp
hyd_prof = hydraulic_profile(
    dp_media_clean_bar  = bw_dp["dp_clean_bar"],
    dp_media_dirty_bar  = bw_dp["dp_dirty_bar"],
    np_dp_filt_bar      = _np_dp_bar,
    distributor_dp_bar  = dp_dist,
    dp_inlet_pipe_bar   = dp_inlet_pipe,
    dp_outlet_pipe_bar  = dp_outlet_pipe,
    p_residual_bar      = p_residual,
    static_head_m       = static_head,
    rho_feed_kg_m3      = rho_feed,
)

# Design scenario N at design temp / avg TSS for energy basis
_n_feas = feasibility_matrix.get("N", {}).get(
    f"Design ({feed_temp:.0f}°C)", {}).get(
    f"Avg ({tss_avg:.0f} mg/L)", {})
_bw_per_day_design = _n_feas.get("bw_per_day", 24.0 / (bw_total_min/60.0 + 1.0))
_avail_design      = _n_feas.get("avail_pct",  90.0)
_n_total_filters   = streams * n_filters

energy = energy_summary(
    q_filter_m3h        = q_per_filter,
    n_filters_total     = _n_total_filters,
    filt_head_dirty_mwc = hyd_prof["dirty"]["total_mwc"],
    filt_head_clean_mwc = hyd_prof["clean"]["total_mwc"],
    pump_eta            = pump_eta,
    motor_eta           = motor_eta,
    rho_feed_kg_m3      = rho_feed,
    q_bw_m3h            = bw_hyd["q_bw_design_m3h"],
    bw_head_mwc         = bw_head_mwc,
    bw_pump_eta         = bw_pump_eta,
    bw_motor_eta        = motor_eta,
    rho_bw_kg_m3        = rho_bw,
    p_blower_kw         = bw_hyd["p_blower_est_kw"],
    blower_motor_eta    = motor_eta,
    bw_duration_h       = _bw_dur_h,
    bw_per_day_design   = _bw_per_day_design,
    availability_pct    = _avail_design,
    elec_tariff_usd_kwh = elec_tariff,
    op_hours_per_year   = float(op_hours_yr),
)

# ── Consolidated weight ────────────────────────────────────────────────────
nozzle_wt_total = sum(r.get("Total wt (kg)", 0) for r in nozzle_sched)
w_body  = wt_body["weight_body_kg"]
w_np    = wt_np["weight_total_kg"]
w_sup   = wt_sup["weight_all_supports_kg"]
w_noz   = nozzle_wt_total
w_int   = wt_int["weight_internals_kg"]
w_total = w_body + w_np + w_sup + w_noz + w_int

# ══════════════════════════════════════════════════════════════════════════════
# STATUS BADGES
# ══════════════════════════════════════════════════════════════════════════════
with ctx:
    st.divider()
    st.markdown("**Status**")
    for label, done in {
        "Project":    bool(project_name),
        "Process":    total_flow > 0 and n_filters > 0,
        "Water":      feed_sal >= 0 and feed_temp > 0,
        "Geometry":   nominal_id > 0 and total_length > 0,
        "Mechanical": design_pressure > 0,
        "Media":      len(layers) > 0 and all(L["Depth"]>0 for L in layers),
        "Backwash":   not bw_col["media_loss_risk"],
        "Weight":     w_total > 0,
    }.items():
        icon = "🟢" if done else ("🔴" if label=="Backwash" and
                                  bw_col["media_loss_risk"] else "⚪")
        st.markdown(f"{icon} &nbsp; {label}")

    if bw_col["media_loss_risk"]:
        st.error(f"⚠️ Media loss risk!\nMax safe BW: "
                 f"{bw_col['max_safe_bw_m_h']} m/h")

    st.divider()
    st.caption("AQUASIGHT™ | Proprietary Tool")

# ══════════════════════════════════════════════════════════════════════════════
# CONTENT TABS
# ══════════════════════════════════════════════════════════════════════════════
with main:
    (tab_proj, tab_proc, tab_water, tab_vessel,
     tab_media, tab_bw, tab_weight, tab_cart, tab_energy, tab_report) = st.tabs([
        "📋 Project",
        "💧 Process",
        "🌊 Water",
        "🏗️ Vessel",
        "🧱 Media",
        "🔄 Backwash",
        "⚖️ Weight",
        "🔷 Cartridge",
        "⚡ Energy",
        "📄 Report",
    ])

    # ─────────────────────────────────────────────────────────────────────
    # TAB 1 · PROJECT
    # ─────────────────────────────────────────────────────────────────────
    with tab_proj:
        st.subheader("Project information")
        c1, c2 = st.columns(2)
        with c1:
            st.table(pd.DataFrame([
                ["Project",     project_name],
                ["Document",    doc_number],
                ["Revision",    revision],
                ["Client",      client or "—"],
                ["Prepared by", engineer],
            ], columns=["Field", "Value"]))
        with c2:
            st.markdown("**Scope**")
            st.info(
                "1. Horizontal MMF process sizing\n"
                "2. Water properties — feed and BW\n"
                "3. Vessel geometry and ASME mechanical\n"
                "4. Media volumes, EBCT, LV, ΔP, inventory\n"
                "5. Backwash: collector check, expansion,\n"
                "   pump/blower, sequence, waste volumes\n"
                "6. Empty weight — complete vessel\n"
                "7. Report export *(pending)*"
            )

    # ─────────────────────────────────────────────────────────────────────
    # TAB 2 · PROCESS
    # ─────────────────────────────────────────────────────────────────────
    with tab_proc:
        st.subheader("Process — filter loading")

        load_data = filter_loading(total_flow, streams, n_filters, redundancy)

        # Comparison table across all scenarios
        st.markdown("#### Flow distribution by scenario")
        comp = []
        for x, a, q in load_data:
            lv = q / avg_area if avg_area > 0 else 0
            comp.append({
                "Scenario":            "N" if x == 0 else f"N-{x}",
                "Active filters":      a,
                "Flow / filter (m³/h)": round(q, 2),
                "LV (m/h)":            round(lv, 2),
                "LV status":           "✅" if lv <= velocity_threshold else "⚠️",
            })
        st.dataframe(pd.DataFrame(comp), use_container_width=True, hide_index=True)

        # EBCT per layer per scenario
        st.markdown("#### EBCT & LV per layer")
        for x, a, q in load_data:
            label = "N (normal)" if x == 0 else f"N-{x}"
            with st.expander(f"Scenario {label} — {q:.1f} m³/h / filter",
                             expanded=(x == 0)):
                rows, alerts = [], []
                for b in base:
                    vel  = q / b["Area"] if b["Area"] > 0 else 0
                    ebct = (b["Vol"] / q) * 60 if q > 0 else 0
                    rows.append({
                        "Layer":      b["Type"],
                        "Area (m²)":  round(b["Area"], 3),
                        "LV (m/h)":   round(vel, 2),
                        "LV ✓":       "✅" if vel <= velocity_threshold else "⚠️",
                        "EBCT (min)": round(ebct, 2),
                        "EBCT ✓":     "✅" if ebct >= ebct_threshold else "⚠️",
                    })
                    if vel > velocity_threshold:
                        alerts.append(f"⚠️ {b['Type']}: LV {vel:.2f} m/h "
                                      f"> max {velocity_threshold} m/h")
                    if ebct < ebct_threshold:
                        alerts.append(f"⚠️ {b['Type']}: EBCT {ebct:.2f} min "
                                      f"< min {ebct_threshold} min")
                st.dataframe(pd.DataFrame(rows),
                             use_container_width=True, hide_index=True)
                for msg in alerts:
                    st.warning(msg)

        st.divider()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("LV — N scenario",   f"{q_per_filter/avg_area:.2f} m/h")
        m2.metric("Flow / filter (N)", f"{q_per_filter:.1f} m³/h")
        m3.metric("Total filters",     f"{streams * n_filters}")
        m4.metric("Redundancy",        f"N to N-{redundancy}")

    # ─────────────────────────────────────────────────────────────────────
    # TAB 3 · WATER PROPERTIES
    # ─────────────────────────────────────────────────────────────────────
    with tab_water:
        st.subheader("Water properties — feed & backwash")

        w1, w2 = st.columns(2)
        with w1:
            st.markdown("**Feed water**")
            st.table(pd.DataFrame([
                ["Temperature",   f"{feed_wp['temp_c']:.1f} °C"],
                ["Salinity",      f"{feed_wp['salinity_ppt']:.2f} ppt"],
                ["Density",       f"{feed_wp['density_kg_m3']:.3f} kg/m³"],
                ["Viscosity",     f"{feed_wp['viscosity_cp']:.4f} cP"],
                ["TDS (approx.)", f"{feed_wp['tds_mg_l']:,.0f} mg/L"],
            ], columns=["Property", "Value"]))

        with w2:
            st.markdown("**Backwash water**")
            st.table(pd.DataFrame([
                ["Temperature",   f"{bw_wp['temp_c']:.1f} °C"],
                ["Salinity",      f"{bw_wp['salinity_ppt']:.2f} ppt"],
                ["Density",       f"{bw_wp['density_kg_m3']:.3f} kg/m³"],
                ["Viscosity",     f"{bw_wp['viscosity_cp']:.4f} cP"],
                ["TDS (approx.)", f"{bw_wp['tds_mg_l']:,.0f} mg/L"],
            ], columns=["Property", "Value"]))

        st.info(
            "Water properties feed directly into: terminal velocity (u_t), "
            "minimum fluidisation velocity (u_mf), Ergun pressure drop (ΔP), "
            "and nozzle velocity checks. "
            "BW water properties govern the expansion and collector check calculations."
        )

    # ─────────────────────────────────────────────────────────────────────
    # TAB 4 · VESSEL
    # ─────────────────────────────────────────────────────────────────────
    with tab_vessel:
        st.subheader("Vessel geometry & mechanical")

        # ── Geometry summary ──
        with st.expander("1 · Geometry", expanded=True):
            g1, g2, g3, g4, g5 = st.columns(5)
            g1.metric("Nominal ID",   f"{nominal_id:.3f} m")
            g2.metric("Lining",       f"{lining_mm:.1f} mm")
            g3.metric("Real hyd. ID", f"{real_id:.4f} m",
                      delta=f"−{lining_mm*2:.1f} mm", delta_color="off")
            g4.metric("Cyl. length",  f"{cyl_len:.3f} m")
            g5.metric("Dish depth",   f"{h_dish:.3f} m")
            st.caption(
                f"Real hydraulic ID = {nominal_id:.3f} m − "
                f"2 × {lining_mm:.1f} mm = **{real_id:.4f} m**. "
                "This ID is used in all hydraulic calculations below."
            )

        # ── Mechanical ──
        with st.expander("2 · ASME wall thickness", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Material & radiography**")
                st.table(pd.DataFrame([
                    ["Material",            material_name],
                    ["Standard",            mat_info["standard"]],
                    ["Allowable stress (S)", f"{mech['allowable_stress']} kg/cm²"],
                    ["Shell radiography",   f"{shell_radio}  →  E={mech['shell_E']:.2f}"],
                    ["Head radiography",    f"{head_radio}  →  E={mech['head_E']:.2f}"],
                ], columns=["Parameter", "Value"]))
            with c2:
                st.markdown("**Thickness results**")
                def fmt_t(t_min, t_des, overridden):
                    flag = " ✏️ overridden" if overridden else ""
                    return f"{t_des} mm{flag}  (t_min={t_min:.2f} mm)"
                st.table(pd.DataFrame([
                    ["Design pressure",
                     f"{design_pressure:.2f} bar ({mech['p_kgf_cm2']:.3f} kg/cm²)"],
                    ["Corrosion allowance",  f"{corrosion:.1f} mm"],
                    ["Shell t_min",          f"{mech['t_shell_min_mm']:.2f} mm"],
                    ["Shell t_design",
                     fmt_t(mech['t_shell_min_mm'], mech['t_shell_design_mm'],
                           mech.get('shell_overridden', False))],
                    ["Head t_min",           f"{mech['t_head_min_mm']:.2f} mm"],
                    ["Head t_design",
                     fmt_t(mech['t_head_min_mm'], mech['t_head_design_mm'],
                           mech.get('head_overridden', False))],
                    ["Nominal ID",           f"{mech['nominal_id_m']:.4f} m"],
                    ["Real hydraulic ID",    f"{real_id:.4f} m"],
                    ["Outside diameter",     f"{mech['od_m']:.4f} m"],
                ], columns=["Parameter", "Value"]))

        # ── Nozzle plate ──
        with st.expander("3 · Nozzle plate design", expanded=True):
            st.info(f"Design ΔP auto-wired from Ergun dirty-bed result: "
                    f"**{np_dp_auto:.5f} bar** "
                    f"({np_dp_auto*1e5/1000:.3f} kPa)")
            l1, l2, l3 = st.columns(3)
            l1.metric("ΔP hydraulic", f"{wt_np['q_dp_kpa']:.3f} kPa")
            l2.metric("Media load",   f"{wt_np['q_media_kpa']:.3f} kPa")
            l3.metric("Total load",   f"{wt_np['q_total_kpa']:.3f} kPa")

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Geometry & bore layout**")
                st.table(pd.DataFrame([
                    ["Plate height",      f"{wt_np['h_plate_m']:.3f} m"],
                    ["Chord at plate",    f"{wt_np['chord_m']:.4f} m"],
                    ["Angle θ",          f"{wt_np['theta_deg']:.2f}°"],
                    ["Cyl. plate area",   f"{wt_np['area_cyl_m2']:.4f} m²"],
                    ["Dish ends area",    f"{wt_np['area_both_dish_m2']:.4f} m²"],
                    ["Total plate area",  f"{wt_np['area_total_m2']:.4f} m²"],
                    ["Number of bores",   str(wt_np["n_bores"])],
                    ["Bore diameter",     f"{wt_np['bore_diameter_mm']:.0f} mm"],
                    ["Nozzle density",    f"{wt_np['actual_density_per_m2']:.1f} /m²"],
                    ["Open area ratio",   f"{wt_np['open_ratio_pct']:.1f} %"],
                ], columns=["Parameter", "Value"]))
            with c2:
                st.markdown("**Thickness & support beams**")
                st.table(pd.DataFrame([
                    ["Beam spacing",      f"{wt_np['beam_spacing_mm']:.0f} mm"],
                    ["t_min (Roark)",     f"{wt_np['t_min_mm']:.2f} mm"],
                    ["t_design",         f"{wt_np['t_design_mm']} mm"],
                    ["t used",           f"{wt_np['t_used_mm']} mm  "
                                        f"({wt_np['thickness_source']})"],
                    ["Beam M_max",        f"{wt_np['M_max_kNm']:.1f} kN·m"],
                    ["Required Z",        f"{wt_np['beam_Z_req_cm3']:.0f} cm³"],
                    ["Selected section",  wt_np["beam_section"]],
                    ["No. of beams",      str(wt_np["n_beams"])],
                    ["Plate weight",      f"{wt_np['weight_plate_kg']:,.1f} kg"],
                    ["Beams weight",      f"{wt_np['weight_beams_kg']:,.1f} kg"],
                    ["Total plate assy.", f"{wt_np['weight_total_kg']:,.1f} kg"],
                ], columns=["Parameter", "Value"]))

    # ─────────────────────────────────────────────────────────────────────
    # TAB 5 · MEDIA
    # ─────────────────────────────────────────────────────────────────────
    with tab_media:
        st.subheader("Media design")

        with st.expander("1 · Geometric volumes", expanded=True):
            df_geo = pd.DataFrame(geo_rows, columns=[
                "Item", "Depth (m)", "Avg area (m²)",
                "V_cyl (m³)", "V_ends (m³)", "Total vol (m³)"])
            st.dataframe(df_geo.style.format({
                "Depth (m)":      "{:.3f}",
                "Avg area (m²)":  "{:.4f}",
                "V_cyl (m³)":     "{:.4f}",
                "V_ends (m³)":    "{:.4f}",
                "Total vol (m³)": "{:.4f}",
            }), use_container_width=True, hide_index=True)

        with st.expander("2 · Media properties", expanded=True):
            df_med = pd.DataFrame(base)[
                ["Type","Depth","Vol","Area","rho_p_eff","epsilon0","d10","cu"]
            ].rename(columns={
                "Type":"Media","Depth":"Depth (m)","Vol":"Vol (m³)",
                "Area":"Avg area (m²)","rho_p_eff":"ρ (kg/m³)",
                "epsilon0":"ε₀","d10":"d10 (mm)","cu":"CU"})
            st.dataframe(df_med, use_container_width=True, hide_index=True)

        with st.expander("3 · Pressure drop — clean/moderate/dirty (all scenarios)", expanded=True):
            st.caption(
                f"Clean ΔP: Ergun equation on virgin bed.  "
                f"Moderate = 50% loaded · Dirty = 100% loaded — cake model (Ruth): "
                f"ΔP_cake = α × μ × LV × M.  "
                f"α ({bw_dp['alpha_source']}) = "
                f"{bw_dp['alpha_used_m_kg']/1e9:.1f} × 10⁹ m/kg  |  "
                f"M_max = {solid_loading:.2f} kg/m²  |  "
                f"Feed: ρ={rho_feed:.1f} kg/m³, μ={mu_feed*1000:.4f} cP"
            )

            # Compute ΔP for all redundancy scenarios
            load_data_dp = filter_loading(total_flow, streams, n_filters, redundancy)
            dp_summary = []
            for x, n_act, q in load_data_dp:
                sc_label = "N" if x == 0 else f"N-{x}"
                sc_dp = pressure_drop(
                    layers=layers,
                    q_filter_m3h=q,
                    avg_area_m2=avg_area,
                    solid_loading_kg_m2=solid_loading,
                    captured_density_kg_m3=captured_solids_density,
                    water_temp_c=feed_temp,
                    rho_water=rho_feed,
                    alpha_m_kg=alpha_specific,
                    dp_trigger_bar=dp_trigger_bar,
                )
                dp_summary.append({
                    "Scenario":        sc_label,
                    "LV (m/h)":        sc_dp["u_m_h"],
                    "ΔP clean (bar)":  sc_dp["dp_clean_bar"],
                    "ΔP clean (mWC)":  sc_dp["dp_clean_mwc"],
                    "ΔP moderate (bar)": sc_dp["dp_moderate_bar"],
                    "ΔP dirty (bar)":  sc_dp["dp_dirty_bar"],
                    "ΔP dirty (mWC)":  sc_dp["dp_dirty_mwc"],
                })

            st.markdown("**Summary — all scenarios**")
            st.dataframe(pd.DataFrame(dp_summary),
                         use_container_width=True, hide_index=True)

            st.markdown("**Per-layer breakdown — N scenario**")
            st.dataframe(pd.DataFrame(bw_dp["layers"]),
                         use_container_width=True, hide_index=True)

            p1, p2, p3 = st.columns(3)
            p1.metric("ΔP clean (N)",
                      f"{bw_dp['dp_clean_bar']:.5f} bar",
                      delta=f"{bw_dp['dp_clean_mwc']:.3f} mWC", delta_color="off")
            p2.metric("ΔP moderate (N)",
                      f"{bw_dp['dp_moderate_bar']:.5f} bar",
                      delta=f"{bw_dp['dp_moderate_mwc']:.3f} mWC", delta_color="off")
            p3.metric("ΔP dirty → nozzle plate ΔP",
                      f"{bw_dp['dp_dirty_bar']:.5f} bar",
                      delta=f"{bw_dp['dp_dirty_mwc']:.3f} mWC", delta_color="off")

        with st.expander("4 · Media inventory", expanded=True):
            total_vessels = streams * n_filters
            inv_rows = []; total_mass = 0
            for b in base:
                mf = b["Vol"] * b["rho_p_eff"]
                mt = mf * total_vessels
                total_mass += mt
                inv_rows.append({
                    "Media":             b["Type"],
                    "d10/CU":            f"{b['d10']}/{b['cu']}",
                    "Vol/filter (m³)":   round(b["Vol"], 4),
                    "Mass/filter (kg)":  round(mf),
                    "Total mass (kg)":   round(mt),
                })
            st.dataframe(pd.DataFrame(inv_rows),
                         use_container_width=True, hide_index=True)
            i1, i2, i3 = st.columns(3)
            i1.metric("Total filters",  total_vessels)
            i2.metric("Total media",    f"{total_mass/1000:.2f} t")
            i3.metric("Per filter",
                      f"{total_mass/total_vessels/1000:.2f} t"
                      if total_vessels else "—")

        with st.expander("5 · Clogging analysis — N scenario", expanded=True):
            st.caption(
                f"Captured solids density: **{captured_solids_density:.0f} kg/m³**  |  "
                f"Total solid loading: **{solid_loading:.2f} kg/m²**"
            )
            clog_cols = ["Media", "Support", "Capture (%)",
                         "Solid load (kg/m²)", "Solid vol (m³/m²)",
                         "ΔεF", "Clogging (%)", "ε clean",
                         "Cake ΔP mod (bar)", "Cake ΔP dirty (bar)"]
            clog_df = pd.DataFrame(bw_dp["layers"])[clog_cols]
            st.dataframe(clog_df, use_container_width=True, hide_index=True)
            st.caption(
                "Support layers (e.g., Gravel) retain no solids. "
                "Cake ΔP = α × μ × LV × M, distributed by capture fraction. "
                "ΔεF shown for reference only — cake model, not voidage reduction, "
                "drives moderate/dirty ΔP."
            )

    # ─────────────────────────────────────────────────────────────────────
    # TAB 6 · BACKWASH
    # ─────────────────────────────────────────────────────────────────────
    with tab_bw:
        st.subheader("Backwash design")

        # Collector check — most important, shown first
        with st.expander("1 · Collector height check — media loss guard",
                         expanded=True):
            status_color = ("🔴" if bw_col["media_loss_risk"]
                            else "🟡" if "WARNING" in bw_col["status"]
                            else "🟢")
            st.markdown(f"### {status_color} {bw_col['status']}")

            cc1, cc2, cc3, cc4 = st.columns(4)
            cc1.metric("Settled bed top",  f"{bw_col['settled_top_m']:.3f} m")
            cc2.metric("Expanded bed top", f"{bw_col['expanded_top_m']:.3f} m")
            cc3.metric("Collector height", f"{bw_col['collector_h_m']:.3f} m")
            cc4.metric("Freeboard",
                       f"{bw_col['freeboard_m']:.3f} m",
                       delta=f"{bw_col['freeboard_pct']:.1f}% of bed",
                       delta_color="normal"
                       if bw_col["freeboard_m"] >= bw_col["min_freeboard_m"]
                       else "inverse")

            st.info(
                f"**Max safe BW velocity: {bw_col['max_safe_bw_m_h']:.1f} m/h** "
                f"(maintains ≥ {freeboard_mm:.0f} mm freeboard below collector).  "
                f"Proposed BW: **{bw_col['proposed_bw_m_h']:.1f} m/h**."
            )

            # Expansion — two scenarios
            # A: water-only BW (pump rate) — governs collector check
            # B: air+water combined (air scour rate as equivalent) — governs cleaning
            exp_rows = []
            for L in bw_col["per_layer"]:
                if L.get("elutriation_risk"):
                    status = "ELUTRIATION RISK"
                elif L["fluidised"]:
                    status = "Fluidised  " + str(L["expansion_pct"]) + "%"
                else:
                    status = "Not fluidised  (u_mf=" + str(L["u_mf_m_h"]) + " m/h)"
                exp_rows.append({
                    "Media":          L["media_type"],
                    "d10 (mm)":       L["d10_mm"],
                    "d50 (mm)":       L.get("d50_mm", "—"),
                    "Ar":             L.get("Ar", "—"),
                    "Re_mf":          L.get("Re_mf", "—"),
                    "u_mf (m/h)":     L["u_mf_m_h"],
                    "n_rz":           L.get("n_rz", "—"),
                    "u_t (m/h)":      L["u_t_m_h"],
                    "ε₀":             L["epsilon0"],
                    "ε_f":            L["eps_f"],
                    "Settled (m)":    L["depth_settled_m"],
                    "Expanded (m)":   L["depth_expanded_m"],
                    "Expansion (%)":  L["expansion_pct"],
                    "Status":         status,
                })
            st.dataframe(pd.DataFrame(exp_rows),
                         use_container_width=True, hide_index=True)

            # Air+water combined scenario
            from engine.backwash import bed_expansion as _bed_exp
            exp_combined = _bed_exp(
                layers=layers,
                bw_velocity_m_h=air_scour_rate,   # use air scour rate as combined equiv.
                water_temp_c=bw_temp,
                rho_water=rho_bw,
            )
            st.markdown(f"**Air + water combined phase** "
                        f"(equivalent velocity = air scour rate = {air_scour_rate:.0f} m/h):")
            comb_rows = []
            for L in exp_combined["layers"]:
                comb_rows.append({
                    "Media":          L["media_type"],
                    "u_mf (m/h)":     L["u_mf_m_h"],
                    "Fluidised":      "Yes ✅" if L["fluidised"] else "No",
                    "ε_f":            L["eps_f"],
                    "Settled (m)":    L["depth_settled_m"],
                    "Expanded (m)":   L["depth_expanded_m"],
                    "Expansion (%)":  L["expansion_pct"],
                    "Note":           L["warning"] if L["warning"] else "OK",
                })
            st.dataframe(pd.DataFrame(comb_rows),
                         use_container_width=True, hide_index=True)

            ec1, ec2, ec3 = st.columns(3)
            ec1.metric("Settled bed",   f"{exp_combined['total_settled_m']:.3f} m")
            ec2.metric("Expanded bed",  f"{exp_combined['total_expanded_m']:.3f} m")
            ec3.metric("Net expansion", f"{exp_combined['total_expansion_pct']:.1f} %")

            st.caption(
                "**Water-only BW** (pump sizing): at 30 m/h, fine sand (u_mf=38 m/h) "
                "and anthracite (u_mf=42 m/h) are NOT hydraulically fluidised — "
                "this is physically correct and typical for MMF design. "
                "**Air scour** (55 m/h) provides the primary cleaning mechanism "
                "through mechanical agitation. The collector check uses the "
                "water-only pump rate as the worst-case hydraulic load on the bed. "
                "The combined phase table shows what expansion occurs when air+water "
                "act simultaneously."
            )

            if bw_col["media_loss_risk"]:
                st.error(
                    f"Expanded bed top ({bw_col['expanded_top_m']:.3f} m) "
                    f"≥ collector ({bw_col['collector_h_m']:.3f} m). "
                    f"Reduce BW velocity to ≤ {bw_col['max_safe_bw_m_h']:.1f} m/h "
                    "or raise the collector."
                )

        with st.expander("2 · BW pump & air blower capacity", expanded=True):
            bh1, bh2, bh3, bh4 = st.columns(4)
            bh1.metric("BW flow",        f"{bw_hyd['q_bw_m3h']:,.0f} m³/h",
                       help=bw_hyd["bw_governs"])
            bh2.metric("BW LV actual",   f"{bw_hyd['bw_lv_actual_m_h']:.1f} m/h")
            bh3.metric("Air scour flow", f"{bw_hyd['q_air_m3h']:,.0f} m³/h")
            bh4.metric("Blower est.",    f"{bw_hyd['p_blower_est_kw']:.1f} kW")
            st.table(pd.DataFrame([
                ["Governing BW flow",
                 f"{bw_hyd['q_bw_m3h']:,.1f} m³/h ({bw_hyd['bw_governs']})"],
                ["BW design capacity (×1.10)",
                 f"{bw_hyd['q_bw_design_m3h']:,.1f} m³/h"],
                ["Air design capacity (×1.10)",
                 f"{bw_hyd['q_air_design_m3h']:,.1f} m³/h"],
                ["Blower power (est., η=0.65)",
                 f"{bw_hyd['p_blower_est_kw']:.1f} kW"],
                ["BW water: ρ",
                 f"{rho_bw:.2f} kg/m³  |  μ={mu_bw*1000:.4f} cP"],
            ], columns=["Parameter", "Value"]))

        with st.expander("3 · BW sequence & waste volumes", expanded=True):
            st.dataframe(pd.DataFrame(bw_seq["steps"]),
                         use_container_width=True, hide_index=True)
            st.divider()
            w1, w2, w3, w4 = st.columns(4)
            w1.metric("BW duration (avg)",  f"{bw_seq['dur_total_avg_min']} min")
            w2.metric("Total vol / filter", f"{bw_seq['total_vol_avg_m3']:.0f} m³")
            w3.metric("Waste / filter",     f"{bw_seq['waste_vol_avg_m3']:.0f} m³")
            w4.metric("Plant waste / day",  f"{bw_seq['waste_vol_daily_m3']:.0f} m³/d")

            st.markdown("**Waste volume & TSS mass balance**")
            st.table(pd.DataFrame([
                ["Low TSS",
                 f"{tss_low:.0f} mg/L",
                 f"{bw_seq['total_vol_low_m3']:.0f} m³",
                 f"{m_sol_low:.0f} kg",
                 f"{w_tss_low:.0f} mg/L",
                 f"{m_daily_low:,.0f} kg/d"],
                ["Avg TSS",
                 f"{tss_avg:.0f} mg/L",
                 f"{bw_seq['total_vol_avg_m3']:.0f} m³",
                 f"{m_sol_avg:.0f} kg",
                 f"{w_tss_avg:.0f} mg/L",
                 f"{m_daily_avg:,.0f} kg/d"],
                ["High TSS",
                 f"{tss_high:.0f} mg/L",
                 f"{bw_seq['total_vol_high_m3']:.0f} m³",
                 f"{m_sol_high:.0f} kg",
                 f"{w_tss_high:.0f} mg/L",
                 f"{m_daily_high:,.0f} kg/d"],
            ], columns=["Scenario", "Feed TSS",
                        "BW vol / filter", "Solids captured / filter",
                        "Waste TSS conc.", "Plant solids / day"]))
            st.caption(
                f"Run time between BW cycles: {run_time_h:.1f} h  "
                f"({bw_cycles_day} cycle/d per filter).  "
                "Solids captured = TSS × Q_filter × run_time.  "
                "Waste TSS = solids mass / waste volume (excl. rinse)."
            )

        with st.expander("4 · Filtration cycle matrix — TSS × temperature", expanded=True):
            if filt_cycles and cycle_matrix:
                first_cyc   = next(iter(filt_cycles.values()))
                _alpha_src  = first_cyc["alpha_source"]
                _alpha_used = first_cyc["alpha_used_m_kg"]
                _alpha_cal  = first_cyc["alpha_calibrated_m_kg"]

                st.info(
                    f"**Ruth cake model** · BW setpoint {dp_trigger_bar:.2f} bar · "
                    f"M_max {solid_loading:.2f} kg/m² · "
                    f"α ({_alpha_src}) = {_alpha_used/1e9:.1f} × 10⁹ m/kg "
                    f"(auto-cal at design temp = {_alpha_cal/1e9:.1f} × 10⁹ m/kg) · "
                    f"Temperature range {temp_low:.0f} – {feed_temp:.0f} – {temp_high:.0f} °C"
                )

                # ── Matrix tables: one per redundancy scenario ────────────
                for sc_lbl, sc_temps in cycle_matrix.items():
                    _lv = filt_cycles[sc_lbl]["lv_m_h"]
                    st.markdown(
                        f"**Scenario {sc_lbl} · LV = {_lv:.1f} m/h**  "
                        f"— Cycle duration (h) to reach {dp_trigger_bar:.2f} bar ΔP"
                    )
                    # Build matrix: rows = TSS label, cols = temp label
                    mat_rows = []
                    for tss_lbl, tss_v in zip(_tss_labels, _tss_vals):
                        row = {"Feed TSS": tss_lbl}
                        for t_lbl in _temp_labels:
                            cyc_t = sc_temps[t_lbl]
                            # find the matching TSS row in tss_results
                            tr = next(
                                (r for r in cyc_t["tss_results"]
                                 if r["TSS (mg/L)"] == tss_v), None)
                            row[t_lbl] = f"{tr['Cycle duration (h)']:.1f} h" if tr else "—"
                        mat_rows.append(row)
                    mat_df = pd.DataFrame(mat_rows).set_index("Feed TSS")
                    st.dataframe(mat_df, use_container_width=True)

                    # Sub-caption: ΔP clean at each temperature for this scenario
                    dp_clean_str = "  ·  ".join(
                        f"{t_lbl}: ΔP_clean = {sc_temps[t_lbl]['dp_clean_bar']:.4f} bar"
                        for t_lbl in _temp_labels
                    )
                    st.caption(
                        f"M* (load at trigger): "
                        + "  ·  ".join(
                            f"{t_lbl}: {sc_temps[t_lbl]['loading_at_trigger_kg_m2']:.2f} kg/m²"
                            for t_lbl in _temp_labels
                        )
                        + f"  |  {dp_clean_str}"
                    )

                # ── ΔP vs solid load curve (N, design temp) ───────────────
                with st.expander("ΔP vs M curve — N scenario, design temperature", expanded=False):
                    st.dataframe(pd.DataFrame(first_cyc["dp_curve"]),
                                 use_container_width=True, hide_index=True)

                st.caption(
                    "ΔP_total = ΔP_clean (Ergun) + α × μ(T) × LV × M.  "
                    "α fixed at design-temperature calibration; temperature effect enters "
                    "through μ(T) — colder water → higher viscosity → shorter cycle.  "
                    "α = 0 → auto-calibrated so dirty ΔP = trigger at M_max and design temp."
                )

                with st.expander("Reference: typical α by TSS type", expanded=False):
                    st.dataframe(pd.DataFrame([
                        {"TSS type": "Coarse mineral / silt",        "α (× 10⁹ m/kg)": "0.1 – 10"},
                        {"TSS type": "Seawater mixed TSS (typical)", "α (× 10⁹ m/kg)": "10 – 50"},
                        {"TSS type": "Organic-rich / algae-laden",   "α (× 10⁹ m/kg)": "100 – 500"},
                        {"TSS type": "Clay / fine colloids",          "α (× 10⁹ m/kg)": "1 000 – 10 000"},
                    ]), use_container_width=True, hide_index=True)
            else:
                st.info("No filtration cycle data available.")

        with st.expander("5 · BW scheduling & system feasibility", expanded=True):
            _bw_steps = [
                ("① Gravity drain",        bw_s_drain),
                ("② Air scour only",       bw_s_air),
                ("③ Air + low-rate water", bw_s_airw),
                ("④ High-rate water",      bw_s_hw),
                ("⑤ Settling",             bw_s_settle),
                ("⑥ Fill & rinse",         bw_s_fill),
            ]
            # BW step summary
            cum = 0
            step_rows = []
            for nm, dur in _bw_steps:
                cum += dur
                step_rows.append({"Step": nm, "Duration (min)": dur,
                                   "Cumulative (min)": cum})
            step_rows.append({"Step": "TOTAL", "Duration (min)": bw_total_min,
                               "Cumulative (min)": bw_total_min})
            cA, cB = st.columns([1, 2])
            with cA:
                st.markdown("**BW step breakdown**")
                st.dataframe(pd.DataFrame(step_rows),
                             use_container_width=True, hide_index=True)

            with cB:
                st.markdown(
                    f"**BW duration: {bw_total_min} min ({_bw_dur_h*60:.0f} min)**  \n"
                    f"Filter cycle + BW = cycle time + {bw_total_min} min.  \n"
                    f"Availability = cycle time / (cycle + BW time) × 100 %."
                )

            if feasibility_matrix:
                for sc_lbl, sc_temps in feasibility_matrix.items():
                    _lv  = filt_cycles[sc_lbl]["lv_m_h"]
                    _nact_f = next(
                        n for x, n, q in _load_data_cyc
                        if ("N" if x == 0 else f"N-{x}") == sc_lbl)
                    st.markdown(
                        f"---\n**Scenario {sc_lbl} · {_nact_f} active filters · "
                        f"LV = {_lv:.1f} m/h**"
                    )

                    # ── Availability % matrix ─────────────────────────────
                    st.markdown("*Availability (%) = filtration time / total period*")
                    avail_rows = []
                    for tss_lbl in _tss_labels:
                        row = {"Feed TSS": tss_lbl}
                        for t_lbl in _temp_labels:
                            kpi = sc_temps[t_lbl][tss_lbl]
                            row[t_lbl] = f"{kpi['avail_pct']:.1f} %"
                        avail_rows.append(row)
                    st.dataframe(
                        pd.DataFrame(avail_rows).set_index("Feed TSS"),
                        use_container_width=True)

                    # ── BW per day matrix ─────────────────────────────────
                    st.markdown("*BW cycles per filter per day*")
                    bwday_rows = []
                    for tss_lbl in _tss_labels:
                        row = {"Feed TSS": tss_lbl}
                        for t_lbl in _temp_labels:
                            kpi = sc_temps[t_lbl][tss_lbl]
                            row[t_lbl] = f"{kpi['bw_per_day']:.1f}"
                        bwday_rows.append(row)
                    st.dataframe(
                        pd.DataFrame(bwday_rows).set_index("Feed TSS"),
                        use_container_width=True)

                    # ── Simultaneity matrix ───────────────────────────────
                    st.markdown(
                        "*Peak simultaneous BW demand "
                        "(expected filters in BW at the same time)*"
                    )
                    sim_rows = []
                    for tss_lbl in _tss_labels:
                        row = {"Feed TSS": tss_lbl}
                        for t_lbl in _temp_labels:
                            kpi = sc_temps[t_lbl][tss_lbl]
                            row[t_lbl] = (
                                f"{kpi['sim_demand']:.2f} "
                                f"→ {kpi['bw_trains']} BW train(s)"
                            )
                        sim_rows.append(row)
                    st.dataframe(
                        pd.DataFrame(sim_rows).set_index("Feed TSS"),
                        use_container_width=True)

                    # ── Feasibility scorecard ─────────────────────────────
                    st.markdown("*Feasibility score*")
                    score_rows = []
                    for tss_lbl in _tss_labels:
                        row = {"Feed TSS": tss_lbl}
                        for t_lbl in _temp_labels:
                            kpi = sc_temps[t_lbl][tss_lbl]
                            row[t_lbl] = kpi["score"]
                        score_rows.append(row)
                    st.dataframe(
                        pd.DataFrame(score_rows).set_index("Feed TSS"),
                        use_container_width=True)

                # ── Design guidance ───────────────────────────────────────
                st.markdown("---")
                st.markdown("**Design guidance**")

                # Find worst-case cell (design scenario N, design temp, high TSS)
                _n_kpi = feasibility_matrix.get("N", {}).get(
                    f"Design ({feed_temp:.0f}°C)", {}).get(
                    f"High ({tss_high:.0f} mg/L)", {})
                if _n_kpi:
                    _flag = _n_kpi["flag"]
                    _trains = _n_kpi["bw_trains"]
                    _avail  = _n_kpi["avail_pct"]
                    _bwday  = _n_kpi["bw_per_day"]
                    _tcyc   = _n_kpi["t_cycle_h"]

                    guidance = []
                    if _flag == "OK":
                        guidance.append(
                            f"🟢 Design is feasible at high TSS / design temp: "
                            f"availability {_avail:.1f} %, "
                            f"{_bwday:.1f} BW cycles/filter/day, "
                            f"1 BW train sufficient."
                        )
                    else:
                        if _trains > 1:
                            guidance.append(
                                f"🔴 **{_trains} simultaneous BW trains required** "
                                f"at high TSS ({tss_high:.0f} mg/L) / design temp — "
                                f"consider: (a) add a dedicated BW pump/blower per stream, "
                                f"(b) staggered BW scheduling with time-lock logic, or "
                                f"(c) increase filter area to extend cycle > 6 h."
                            )
                        if _tcyc < 4:
                            guidance.append(
                                f"⚠️ Cycle time {_tcyc:.1f} h at worst case — "
                                f"BW occupies {bw_total_min} min every "
                                f"{_tcyc*60:.0f} min: consider increasing "
                                f"filter area or adding redundancy to extend cycle."
                            )
                        if _avail < 80:
                            guidance.append(
                                f"🔴 Availability {_avail:.1f} % — "
                                f"the system spends > 20 % of time in BW; "
                                f"net production capacity is significantly reduced."
                            )

                    for g in guidance:
                        st.markdown(g)

                st.caption(
                    "Scoring: 🟢 Good = avail ≥ 90 %, BW trains ≤ 1, cycle ≥ 6 h  |  "
                    "🟡 Caution = avail 80–90 %, trains ≤ 2, cycle ≥ 3 h  |  "
                    "🔴 Critical = avail < 80 %, trains > 2, or cycle < 3 h.  "
                    "Simultaneity = n_active × BW_dur / (cycle + BW_dur).  "
                    "BW trains needed = ⌈simultaneity⌉."
                )

    # ─────────────────────────────────────────────────────────────────────
    # TAB 7 · WEIGHT
    # ─────────────────────────────────────────────────────────────────────
    with tab_weight:
        st.subheader("Empty weight — consolidated")

        with st.expander("1 · Vessel body (shell + 2 heads)", expanded=True):
            wa, wb = st.columns(2)
            with wa:
                st.markdown("**Cylindrical shell**")
                st.table(pd.DataFrame([
                    ["Mean diameter",    f"{wt_body['d_mean_shell_m']:.4f} m"],
                    ["Wall thickness",   f"{mech['t_shell_design_mm']} mm"],
                    ["Surface area",     f"{wt_body['area_shell_m2']:.3f} m²"],
                    ["Metal volume",     f"{wt_body['vol_shell_m3']:.4f} m³"],
                    ["Shell weight",     f"{wt_body['weight_shell_kg']:,.1f} kg"],
                ], columns=["Item", "Value"]))
            with wb:
                st.markdown(f"**Dish ends × 2  ({end_geometry})**")
                st.table(pd.DataFrame([
                    ["Mean diameter",       f"{wt_body['d_mean_head_m']:.4f} m"],
                    ["Wall thickness",      f"{mech['t_head_design_mm']} mm"],
                    ["Surface area (one)", f"{wt_body['area_one_head_m2']:.3f} m²"],
                    ["Both heads weight",  f"{wt_body['weight_two_heads_kg']:,.1f} kg"],
                ], columns=["Item", "Value"]))

        with st.expander("2 · Nozzles (stubs + flanges)", expanded=True):
            df_nozzle = pd.DataFrame(nozzle_sched)
            edited = st.data_editor(
                df_nozzle, use_container_width=True,
                hide_index=True, num_rows="dynamic",
                column_config={
                    "Service":        st.column_config.TextColumn(width=160),
                    "DN (mm)":        st.column_config.SelectboxColumn(
                                          options=DN_SERIES, width=85),
                    "Schedule":       st.column_config.SelectboxColumn(
                                          options=SCHEDULES, width=90),
                    "Rating":         st.column_config.SelectboxColumn(
                                          options=FLANGE_RATINGS, width=80),
                    "Qty":            st.column_config.NumberColumn(width=55),
                    "Wt/nozzle (kg)": st.column_config.NumberColumn(format="%.1f"),
                    "Total wt (kg)":  st.column_config.NumberColumn(format="%.1f"),
                })
            nozzle_wt_edited = (edited["Total wt (kg)"].sum()
                                if "Total wt (kg)" in edited.columns else w_noz)

        with st.expander("3 · Nozzle plate assembly", expanded=True):
            n1, n2, n3 = st.columns(3)
            n1.metric("Plate",        f"{wt_np['weight_plate_kg']:,.0f} kg")
            n2.metric("Support beams",f"{wt_np['weight_beams_kg']:,.0f} kg")
            n3.metric("Total assy.",  f"{wt_np['weight_total_kg']:,.0f} kg")

        with st.expander("4 · Supports", expanded=True):
            q1, q2, q3 = st.columns(3)
            q1.metric("Type",          wt_sup["support_type"])
            q2.metric("Qty",           wt_sup["n_supports"])
            q3.metric("Total weight",  f"{wt_sup['weight_all_supports_kg']:,.0f} kg")

        with st.expander("5 · Vessel internals", expanded=True):
            ii1, ii2, ii3 = st.columns(3)
            ii1.metric("Strainer nozzles",
                       f"{wt_int['weight_strainers_kg']:,.0f} kg",
                       delta=f"{wt_int['n_strainer_nozzles']} × "
                             f"{wt_int['strainer_material']} "
                             f"@ {wt_int['weight_per_strainer_kg']:.3f} kg",
                       delta_color="off")
            ii2.metric("Air scour header",
                       f"{wt_int['weight_air_header_kg']:,.0f} kg",
                       delta=f"DN{wt_int['air_header_dn_mm']} × "
                             f"{wt_int['air_header_length_m']:.1f} m @ "
                             f"{wt_int['air_header_kg_per_m']} kg/m",
                       delta_color="off")
            ii3.metric("Manholes",
                       f"{wt_int['weight_manholes_kg']:,.0f} kg",
                       delta=f"{wt_int['n_manholes']} × {wt_int['manhole_dn']}",
                       delta_color="off")
            st.caption(
                f"Total internals: **{wt_int['weight_internals_kg']:,.0f} kg = "
                f"{wt_int['weight_internals_t']:.3f} t**"
            )

        with st.expander("6 · Consolidated summary", expanded=True):
            w_total_final = (wt_body["weight_body_kg"] + nozzle_wt_edited
                             + wt_np["weight_total_kg"]
                             + wt_sup["weight_all_supports_kg"])
            w_total_final = (wt_body["weight_body_kg"] + nozzle_wt_edited
                             + wt_np["weight_total_kg"]
                             + wt_sup["weight_all_supports_kg"]
                             + wt_int["weight_internals_kg"])
            st.table(pd.DataFrame([
                ["Shell (cylindrical)",
                 f"{wt_body['weight_shell_kg']:>12,.1f} kg"],
                ["2 × Dish ends",
                 f"{wt_body['weight_two_heads_kg']:>12,.1f} kg"],
                ["Nozzles (stubs + flanges)",
                 f"{nozzle_wt_edited:>12,.1f} kg"],
                ["Nozzle plate + IPE beams",
                 f"{wt_np['weight_total_kg']:>12,.1f} kg"],
                [f"Supports ({wt_sup['support_type']})",
                 f"{wt_sup['weight_all_supports_kg']:>12,.1f} kg"],
                ["Strainer nozzles",
                 f"{wt_int['weight_strainers_kg']:>12,.1f} kg"],
                ["Air scour header",
                 f"{wt_int['weight_air_header_kg']:>12,.1f} kg"],
                ["Manholes",
                 f"{wt_int['weight_manholes_kg']:>12,.1f} kg"],
                ["─" * 30, "─" * 16],
                ["TOTAL EMPTY WEIGHT",
                 f"{w_total_final:>12,.1f} kg"],
                ["",
                 f"= {w_total_final/1000:.3f} t"],
            ], columns=["Component", "Weight"]))

            e1, e2, e3, e4, e5, e6 = st.columns(6)
            e1.metric("Shell+heads", f"{wt_body['weight_body_kg']:,.0f} kg")
            e2.metric("Nozzles",     f"{nozzle_wt_edited:,.0f} kg")
            e3.metric("Plate+beams", f"{wt_np['weight_total_kg']:,.0f} kg")
            e4.metric("Supports",    f"{wt_sup['weight_all_supports_kg']:,.0f} kg")
            e5.metric("Internals",   f"{wt_int['weight_internals_kg']:,.0f} kg")
            e6.metric("TOTAL",       f"{w_total_final/1000:.3f} t",
                      delta=f"{w_total_final:,.0f} kg", delta_color="off")
            st.caption(
                "⚠️  Underdrains, platform/walkway, piping manifolds, "
                "and instrument connections not included."
            )

    # ─────────────────────────────────────────────────────────────────────
    # TAB 8 · CARTRIDGE
    # ─────────────────────────────────────────────────────────────────────
    with tab_cart:
        st.subheader("Cartridge (polishing) filter sizing")

        # ── 1. Key metrics ────────────────────────────────────────────────
        with st.expander("1 · Sizing — selected configuration", expanded=True):
            ca1, ca2, ca3, ca4 = st.columns(4)
            ca1.metric("Elements required",  str(cart_result["n_elements"]))
            ca2.metric("Housings required",
                       str(cart_result["n_housings"]),
                       delta=f"{cart_result['n_elem_per_housing']} elem./housing",
                       delta_color="off")
            ca3.metric("Flow / element",
                       f"{cart_result['actual_flow_m3h_element']:.3f} m³/h",
                       delta=f"{cart_result['q_lpm_element']:.1f} lpm",
                       delta_color="off")
            ca4.metric("Dirt hold / element",
                       f"{cart_result['dhc_g_element']:.0f} g",
                       delta=f"{cart_result['element_ties']} TIE",
                       delta_color="off")

            _cip_badge = "🔩 SS 316L — CIP" if cart_result["is_CIP_system"] else "🔵 Polymer — standard"
            st.caption(
                f"{_cip_badge}  |  "
                f"Element: **{cart_size}** ({cart_result['element_ties']} TIE)  |  "
                f"Rating: **{cart_rating} µm absolute**  |  "
                f"Area: {cart_result['element_area_m2']} m²/element  |  "
                f"Feed viscosity: {_cart_mu_cP:.2f} cP  |  "
                f"Safety factor: {cart_result['safety_factor']}×"
            )
            st.table(pd.DataFrame([
                ["Design flow",                f"{cart_result['design_flow_m3h']:,.1f} m³/h"],
                ["Element size",               cart_result["element_size"]],
                ["Element area",               f"{cart_result['element_area_m2']} m²"],
                ["Rating",                     f"{cart_result['rating_um']} µm absolute"],
                ["Base capacity (1 cP)",       f"{cart_result['cap_m3h_element_base']:.3f} m³/h/element"],
                ["Capacity (derated @ μ)",     f"{cart_result['cap_m3h_element_visc']:.3f} m³/h/element"],
                ["Capacity (rated w/ 1.5 SF)", f"{cart_result['cap_m3h_element_rated']:.3f} m³/h/element"],
                ["Elements required",          str(cart_result["n_elements"])],
                ["Elements per housing",       str(cart_result["n_elem_per_housing"])],
                ["Housings required",          str(cart_result["n_housings"])],
                ["Actual flow / element",      f"{cart_result['actual_flow_m3h_element']:.3f} m³/h"],
                ["Actual flux density",        f"{cart_result['actual_flow_m3h_m2']:.3f} m³/h/m²"],
                ["Flow / element",             f"{cart_result['q_lpm_element']:.1f} lpm"],
            ], columns=["Parameter", "Value"]))

        # ── 2. ΔP & performance ───────────────────────────────────────────
        with st.expander("2 · ΔP & performance", expanded=True):
            cb1, cb2, cb3, cb4 = st.columns(4)
            cb1.metric("ΔP clean (BOL)",  f"{cart_result['dp_clean_bar']:.4f} bar")
            cb2.metric("ΔP EOL",          f"{cart_result['dp_eol_bar']:.4f} bar")
            cb3.metric("Replace at",      f"{cart_result['dp_replacement_bar']:.2f} bar")
            cb4.metric("DHC / element",   f"{cart_result['dhc_g_element']:.0f} g")

            _dp_pct = (cart_result['dp_clean_bar'] / DP_REPLACEMENT_BAR * 100
                       if DP_REPLACEMENT_BAR > 0 else 0)
            _dp_ok  = cart_result['dp_clean_bar'] < DP_REPLACEMENT_BAR * 0.5
            st.caption(
                f"ΔP model: vendor quadratic (lpm/element basis, 40\" reference + TIE scaling).  "
                f"Clean ΔP = {cart_result['dp_clean_bar']*1000:.1f} mbar at "
                f"{cart_result['q_lpm_element']:.1f} lpm/element.  "
                f"EOL ΔP ≈ 2× clean.  "
                f"{'✅' if _dp_ok else '⚠️'} BOL ΔP is {_dp_pct:.0f} % of replacement trigger."
            )

        # ── 3. Length optimisation table ──────────────────────────────────
        with st.expander("3 · Element length optimisation", expanded=True):
            st.caption(
                f"Comparing all standard lengths at **{cart_rating} µm** rating, "
                f"μ = **{_cart_mu_cP:.2f} cP**, SF = {cart_result['safety_factor']}×.  "
                "Market round = smallest standard housing size ≥ n_elements "
                "(fits in 1 housing where possible).  "
                "🏆 = recommended (fewest housings)."
            )
            _opt_rows = []
            for r in cart_optim:
                flag = "🏆" if r["is_recommended"] else ""
                sel  = " ◀" if r["size"] == cart_size else ""
                _opt_rows.append({
                    "":              flag,
                    "Length":        r["size"] + sel,
                    "TIE":           r["ties"],
                    "Cap. (m³/h/el)": f"{r['cap_m3h_elem']:.3f}",
                    "Elements":      r["n_elements"],
                    "Market round":  r["market_round"],
                    "Housings":      r["n_housings"],
                    "Fill %":        f"{r['fill_pct']:.0f} %",
                    "lpm/element":   f"{r['q_lpm_element']:.1f}",
                    "ΔP clean (bar)": f"{r['dp_clean_bar']:.4f}",
                    "ΔP EOL (bar)":  f"{r['dp_eol_bar']:.4f}",
                    "DHC/el (g)":    f"{r['dhc_g']:.0f}",
                })
            st.dataframe(
                pd.DataFrame(_opt_rows),
                use_container_width=True,
                hide_index=True,
            )

        # ── 4. Economics ──────────────────────────────────────────────────
        with st.expander("4 · Economics", expanded=True):
            cc1, cc2, cc3 = st.columns(3)
            cc1.metric("Replacement interval", f"{cart_result['replacement_freq_days']} days")
            cc2.metric("Changes / year",        f"{cart_result['replacements_per_year']:.1f}")
            cc3.metric("Annual element cost",   f"USD {cart_result['annual_cost_usd']:,.0f}")
            st.table(pd.DataFrame([
                ["Cost per element",      f"USD {cart_result['cost_per_element_usd']:,.0f}"],
                ["Replacement interval",  f"{cart_result['replacement_freq_days']} days"],
                ["Changes / year",        f"{cart_result['replacements_per_year']:.1f}"],
                ["Total elements",        str(cart_result["n_elements"])],
                ["Annual cost",           f"USD {cart_result['annual_cost_usd']:,.0f}"],
            ], columns=["Item", "Value"]))
            st.caption(
                "Cost estimates are mid-market indicative (2024). "
                "Replacement frequency is indicative — adjust for actual TSS loading."
            )

    # ─────────────────────────────────────────────────────────────────────
    # TAB 9 · ENERGY
    # ─────────────────────────────────────────────────────────────────────
    with tab_energy:
        st.subheader("Energy & hydraulic profile")

        # ── 1. Hydraulic head budget ──────────────────────────────────────
        with st.expander("1 · Filtration pump — head budget", expanded=True):
            st.caption(
                "Flow path: Pump → inlet piping → distributor → media → "
                "strainer nozzle plate → outlet piping → downstream pressure.  "
                f"Media: clean (Ergun) / dirty (cake at M_max = {solid_loading:.2f} kg/m²).  "
                f"Downstream residual = {p_residual:.2f} barg."
            )
            hA, hB = st.columns(2)
            for col, state, bud in [
                (hA, "Clean bed", hyd_prof["clean"]),
                (hB, f"Dirty bed (M_max = {solid_loading:.2f} kg/m²)", hyd_prof["dirty"]),
            ]:
                with col:
                    st.markdown(f"**{state}**")
                    rows = []
                    for component, bar_val in bud["items_bar"].items():
                        mwc_val = bud["items_mwc"][component]
                        rows.append([component,
                                     f"{bar_val:.4f} bar",
                                     f"{mwc_val:.2f} mWC"])
                    rows.append(["**TOTAL pump duty**",
                                 f"**{bud['total_bar']:.4f} bar**",
                                 f"**{bud['total_mwc']:.2f} mWC**"])
                    st.dataframe(pd.DataFrame(rows, columns=["Component", "bar", "mWC"]),
                                 use_container_width=True, hide_index=True)

        # ── 2. Power summary ─────────────────────────────────────────────
        with st.expander("2 · Power — per consumer", expanded=True):
            e1, e2, e3, e4 = st.columns(4)
            e1.metric("Filtration pump\n(dirty, per filter)",
                      f"{energy['p_filt_dirty_kw']:.1f} kW")
            e2.metric("Filtration pump\n(clean, per filter)",
                      f"{energy['p_filt_clean_kw']:.1f} kW")
            e3.metric("BW pump\n(per event)",
                      f"{energy['p_bw_kw']:.1f} kW")
            e4.metric("Air blower\n(electrical, per event)",
                      f"{energy['p_blower_elec_kw']:.1f} kW")

            st.markdown("**Power basis**")
            st.dataframe(pd.DataFrame([
                ["Filtration pump", f"{q_per_filter:.1f} m³/h × {_n_total_filters} filters",
                 f"η_pump={pump_eta:.2f} · η_motor={motor_eta:.2f}",
                 f"H_clean={hyd_prof['clean']['total_mwc']:.1f} mWC",
                 f"H_dirty={hyd_prof['dirty']['total_mwc']:.1f} mWC",
                 f"{energy['p_filt_avg_kw']:.1f} kW avg"],
                ["BW pump",         f"{bw_hyd['q_bw_design_m3h']:.0f} m³/h",
                 f"η_pump={bw_pump_eta:.2f} · η_motor={motor_eta:.2f}",
                 f"H={bw_head_mwc:.1f} mWC", "—",
                 f"{energy['p_bw_kw']:.1f} kW"],
                ["Air blower",      f"{bw_hyd['q_air_design_m3h']:.0f} m³/h air",
                 f"η_motor={motor_eta:.2f}",
                 "ΔP=0.5 bar", "—",
                 f"{energy['p_blower_elec_kw']:.1f} kW elec."],
            ], columns=["Consumer", "Flow", "Efficiency",
                        "Head / ΔP (clean)", "Head / ΔP (dirty)", "Power"]),
            use_container_width=True, hide_index=True)

        # ── 3. Annual energy & cost ───────────────────────────────────────
        with st.expander("3 · Annual energy & operating cost", expanded=True):
            st.caption(
                f"Basis: {op_hours_yr:,.0f} operating hours/year · "
                f"electricity = USD {elec_tariff:.3f}/kWh · "
                f"BW: {energy['bw_per_day_design']:.1f} cycles/filter/day × "
                f"{bw_total_min} min · {_n_total_filters} filters total."
            )
            fa, fb, fc, fd = st.columns(4)
            fa.metric("Filtration pump", f"{energy['e_filt_kwh_yr']/1e3:,.0f} MWh/yr")
            fb.metric("BW pump",         f"{energy['e_bw_pump_kwh_yr']/1e3:,.1f} MWh/yr")
            fc.metric("Air blower",      f"{energy['e_blower_kwh_yr']/1e3:,.1f} MWh/yr")
            fd.metric("TOTAL",           f"{energy['e_total_kwh_yr']/1e3:,.0f} MWh/yr")

            g1, g2, g3 = st.columns(3)
            g1.metric("Specific energy",  f"{energy['kwh_per_m3']:.4f} kWh/m³")
            g2.metric("Annual OPEX (energy)",
                      f"USD {energy['cost_usd_yr']:,.0f}")
            g3.metric("Water treated / yr",
                      f"{energy['total_flow_m3_yr']/1e6:.2f} Mm³")

            st.dataframe(pd.DataFrame([
                ["Filtration pump",   f"{energy['e_filt_kwh_yr']:,.0f}",
                 f"{energy['e_filt_kwh_yr']*elec_tariff:,.0f}"],
                ["BW pump",           f"{energy['e_bw_pump_kwh_yr']:,.0f}",
                 f"{energy['e_bw_pump_kwh_yr']*elec_tariff:,.0f}"],
                ["Air blower",        f"{energy['e_blower_kwh_yr']:,.0f}",
                 f"{energy['e_blower_kwh_yr']*elec_tariff:,.0f}"],
                ["TOTAL",             f"{energy['e_total_kwh_yr']:,.0f}",
                 f"{energy['cost_usd_yr']:,.0f}"],
            ], columns=["Consumer", "Energy (kWh/yr)", "Cost (USD/yr)"]),
            use_container_width=True, hide_index=True)

    # ─────────────────────────────────────────────────────────────────────
    # TAB 10 · REPORT
    # ─────────────────────────────────────────────────────────────────────
    with tab_report:
        st.subheader("Calculation summary")

        w_total_rep = (wt_body["weight_body_kg"] + w_noz
                       + wt_np["weight_total_kg"]
                       + wt_sup["weight_all_supports_kg"]
                       + wt_int["weight_internals_kg"])

        # ── Word export ────────────────────────────────────────────────────
        def _build_docx() -> bytes:
            doc = _DocxDocument()

            # ── Title ──
            t = doc.add_heading("AQUASIGHT™  Horizontal Multi-Media Filter", 0)
            t.alignment = _WD_ALIGN.CENTER
            t2 = doc.add_heading("Calculation Report", 1)
            t2.alignment = _WD_ALIGN.CENTER
            doc.add_paragraph("")

            def _tbl(rows_data, cols=("Parameter", "Value")):
                tbl = doc.add_table(rows=len(rows_data), cols=len(cols))
                tbl.style = "Table Grid"
                for i, row_vals in enumerate(rows_data):
                    for j, v in enumerate(row_vals):
                        tbl.rows[i].cells[j].text = str(v)
                return tbl

            # ── 1. Project ──
            doc.add_heading("1. Project Information", 2)
            _tbl([
                ("Project",      project_name),
                ("Document",     f"{doc_number}  ·  Rev {revision}"),
                ("Client",       client or "—"),
                ("Prepared by",  engineer),
            ])
            doc.add_paragraph("")

            # ── 2. Process ──
            doc.add_heading("2. Process Basis", 2)
            _tbl([
                ("Total plant flow",          f"{total_flow:,.0f} m³/h"),
                ("Streams × filters",    f"{streams} × {n_filters}"),
                ("Redundancy",                f"N to N-{redundancy}"),
                ("Flow / filter (N)",         f"{q_per_filter:.1f} m³/h"),
                ("Filtration rate (N)",       f"{q_per_filter/avg_area:.2f} m/h"),
            ])
            doc.add_paragraph("")

            # ── 3. Water ──
            doc.add_heading("3. Water Properties", 2)
            _tbl([
                ("",            "Feed",                             "Backwash"),
                ("Salinity",    f"{feed_sal:.2f} ppt",             f"{bw_sal:.2f} ppt"),
                ("Temperature", f"{feed_temp:.1f} °C",        f"{bw_temp:.1f} °C"),
                ("Density",     f"{rho_feed:.3f} kg/m³",      f"{rho_bw:.3f} kg/m³"),
                ("Viscosity",   f"{mu_feed*1000:.4f} cP",          f"{mu_bw*1000:.4f} cP"),
            ], cols=("Property", "Feed", "Backwash"))
            doc.add_paragraph("")

            # ── 4. Vessel ──
            doc.add_heading("4. Vessel & Mechanical", 2)
            _tbl([
                ("Nominal ID",           f"{nominal_id:.3f} m"),
                ("Real hydraulic ID",    f"{real_id:.4f} m"),
                ("Total length T/T",     f"{total_length:.3f} m"),
                ("End geometry",         end_geometry),
                ("Material",             material_name),
                ("Shell t_design",       f"{mech['t_shell_design_mm']} mm"),
                ("Head t_design",        f"{mech['t_head_design_mm']} mm"),
                ("Outside diameter",     f"{mech['od_m']:.4f} m"),
                ("Design pressure",      f"{design_pressure:.2f} bar"),
                ("Corrosion allowance",  f"{corrosion:.1f} mm"),
            ])
            doc.add_paragraph("")

            # ── 5. Media ──
            doc.add_heading("5. Media Design", 2)
            media_rows = [("Media", "Depth (m)", "d10 (mm)", "CU", "Vol (m³)", "Area (m²)")]
            for b in base:
                media_rows.append((
                    b["Type"],
                    f"{b['Depth']:.3f}",
                    f"{b['d10']:.2f}",
                    f"{b['cu']:.2f}",
                    f"{b['Vol']:.4f}",
                    f"{b['Area']:.4f}",
                ))
            _tbl(media_rows, cols=("Media", "Depth (m)", "d10 (mm)", "CU",
                                   "Vol (m³)", "Area (m²)"))
            doc.add_paragraph("")

            # ── 6. Backwash ──
            doc.add_heading("6. Backwash — Collector Check", 2)
            _tbl([
                ("Proposed BW velocity",  f"{bw_velocity:.1f} m/h"),
                ("Max safe BW velocity",  f"{bw_col['max_safe_bw_m_h']:.1f} m/h"),
                ("Min. freeboard",        f"{freeboard_mm:.0f} mm"),
                ("Actual freeboard",
                 f"{bw_col['freeboard_m']:.3f} m  ({bw_col['freeboard_pct']:.1f}%)"),
                ("Status",                bw_col["status"]),
            ])
            doc.add_paragraph("")

            # ── 7. Weight ──
            doc.add_heading("7. Empty Weight Summary", 2)
            _tbl([
                ("Shell (cylindrical)",      f"{wt_body['weight_shell_kg']:,.1f} kg"),
                ("2 × Dish ends",       f"{wt_body['weight_two_heads_kg']:,.1f} kg"),
                ("Nozzles",                  f"{w_noz:,.1f} kg"),
                ("Nozzle plate + IPE beams", f"{wt_np['weight_total_kg']:,.1f} kg"),
                (f"Supports ({wt_sup['support_type']})",
                                             f"{wt_sup['weight_all_supports_kg']:,.1f} kg"),
                ("Strainer nozzles",         f"{wt_int['weight_strainers_kg']:,.1f} kg"),
                ("Air scour header",         f"{wt_int['weight_air_header_kg']:,.1f} kg"),
                ("Manholes",                 f"{wt_int['weight_manholes_kg']:,.1f} kg"),
                ("TOTAL EMPTY WEIGHT",
                 f"{w_total_rep:,.1f} kg  =  {w_total_rep/1000:.3f} t"),
            ])
            doc.add_paragraph("")

            # ── 8. Cartridge ──
            doc.add_heading("8. Cartridge Filter", 2)
            _tbl([
                ("Design flow",          f"{cart_result['design_flow_m3h']:,.1f} m³/h"),
                ("Element material",     cart_result["element_material"]),
                ("Element size",         cart_result["element_size"]),
                ("Rating",               f"{cart_result['rating_um']} µm absolute"),
                ("Safety factor",        f"{cart_result['safety_factor']}×"),
                ("Feed viscosity",       f"{cart_result['mu_cP']:.2f} cP"),
                ("Elements required",    str(cart_result["n_elements"])),
                ("Housings required",    str(cart_result["n_housings"])),
                ("Flow / element",       f"{cart_result['actual_flow_m3h_element']:.3f} m³/h ({cart_result['q_lpm_element']:.1f} lpm)"),
                ("ΔP clean (BOL)",       f"{cart_result['dp_clean_bar']:.4f} bar"),
                ("ΔP EOL",               f"{cart_result['dp_eol_bar']:.4f} bar"),
                ("DHC / element",        f"{cart_result['dhc_g_element']:.0f} g"),
                ("Annual element cost",  f"USD {cart_result['annual_cost_usd']:,.0f}"),
            ])
            doc.add_paragraph("")

            # ── 9. Filtration cycle & BW feasibility ──
            doc.add_heading("9. Filtration Cycle & BW Feasibility", 2)
            _tbl([
                ("BW setpoint",           f"{dp_trigger_bar:.2f} bar"),
                ("Max solid loading",     f"{solid_loading:.2f} kg/m²"),
                ("α (specific cake res.)",
                 f"{filt_cycles['N']['alpha_used_m_kg']/1e9:.1f} × 10⁹ m/kg "
                 f"({filt_cycles['N']['alpha_source']})"),
                ("BW duration (total)",   f"{bw_total_min} min"),
                ("BW steps",
                 f"Drain {bw_s_drain}' · Air {bw_s_air}' · Air+W {bw_s_airw}' · "
                 f"HW {bw_s_hw}' · Settle {bw_s_settle}' · Fill {bw_s_fill}'"),
            ])
            doc.add_paragraph("")
            # Design-temp cycle matrix (N scenario)
            doc.add_paragraph("Cycle duration (h) — N scenario, design temperature:")
            _cyc_n_design = cycle_matrix.get("N", {}).get(
                f"Design ({feed_temp:.0f}°C)", {})
            if _cyc_n_design:
                _tss_rows_rep = [("TSS (mg/L)", "Cycle (h)", "Availability (%)",
                                   "BW/day", "BW trains needed")]
                for _tl, _tv in zip(_tss_labels, _tss_vals):
                    _tr2 = next((r for r in _cyc_n_design["tss_results"]
                                 if r["TSS (mg/L)"] == _tv), None)
                    _fk  = feasibility_matrix.get("N", {}).get(
                        f"Design ({feed_temp:.0f}°C)", {}).get(_tl, {})
                    _tss_rows_rep.append((
                        f"{_tv:.0f}",
                        f"{_tr2['Cycle duration (h)']:.1f}" if _tr2 else "—",
                        f"{_fk.get('avail_pct', 0):.1f}",
                        f"{_fk.get('bw_per_day', 0):.1f}",
                        str(_fk.get("bw_trains", "—")),
                    ))
                _tbl(_tss_rows_rep,
                     cols=("TSS (mg/L)", "Cycle (h)", "Availability (%)",
                            "BW/day", "BW trains"))
            doc.add_paragraph("")

            # ── 10. Energy ──
            doc.add_heading("10. Energy & Operating Cost", 2)
            _tbl([
                ("Filtration pump head (clean)",
                 f"{hyd_prof['clean']['total_mwc']:.2f} mWC  "
                 f"({hyd_prof['clean']['total_bar']:.4f} bar)"),
                ("Filtration pump head (dirty)",
                 f"{hyd_prof['dirty']['total_mwc']:.2f} mWC  "
                 f"({hyd_prof['dirty']['total_bar']:.4f} bar)"),
                ("Filtration pump power (dirty, per filter)",
                 f"{energy['p_filt_dirty_kw']:.1f} kW"),
                ("BW pump power",          f"{energy['p_bw_kw']:.1f} kW"),
                ("Air blower power (elec.)",f"{energy['p_blower_elec_kw']:.1f} kW"),
                ("Annual filtration energy",
                 f"{energy['e_filt_kwh_yr']/1e3:,.0f} MWh/yr"),
                ("Annual BW energy",
                 f"{energy['e_bw_pump_kwh_yr']/1e3:,.1f} MWh/yr  "
                 f"(pump + blower = "
                 f"{(energy['e_bw_pump_kwh_yr']+energy['e_blower_kwh_yr'])/1e3:,.1f} MWh/yr)"),
                ("TOTAL annual energy",    f"{energy['e_total_kwh_yr']/1e3:,.0f} MWh/yr"),
                ("Specific energy",        f"{energy['kwh_per_m3']:.4f} kWh/m³"),
                ("Annual energy cost",     f"USD {energy['cost_usd_yr']:,.0f}/yr"),
                ("Electricity tariff",     f"USD {elec_tariff:.3f}/kWh"),
                ("Op. hours / year",       f"{op_hours_yr:,} h"),
            ])
            doc.add_paragraph("")

            # ── Sign-off ──
            doc.add_page_break()
            doc.add_heading("Sign-off", 2)
            doc.add_paragraph(f"Prepared by:  {engineer}")
            doc.add_paragraph("Role:  Process Expert — AQUASIGHT™")
            doc.add_paragraph(f"Document:  {doc_number}  ·  Rev {revision}")
            doc.add_paragraph(f"Project:  {project_name}")

            buf = io.BytesIO()
            doc.save(buf)
            buf.seek(0)
            return buf.getvalue()

        # ── Download button ────────────────────────────────────────────────
        rep_col, _ = st.columns([2, 3])
        with rep_col:
            if _DOCX_OK:
                st.download_button(
                    label="⬇️  Download Word report (.docx)",
                    data=_build_docx(),
                    file_name=f"{doc_number}_Rev{revision}.docx",
                    mime=("application/vnd.openxmlformats-officedocument"
                          ".wordprocessingml.document"),
                )
            else:
                st.warning("Install python-docx to enable Word export: "
                           "`pip install python-docx`")

        st.divider()

        # ── Inline markdown summary ────────────────────────────────────────
        st.markdown(f"""
**Project:** {project_name}
**Document:** {doc_number} · Rev {revision}
**Prepared by:** {engineer}

---

### Process
| Parameter | Value |
|---|---|
| Total plant flow | {total_flow:,.0f} m³/h |
| Streams × filters / stream | {streams} × {n_filters} |
| Redundancy | N to N-{redundancy} |
| Flow / filter (N) | {q_per_filter:.1f} m³/h |
| Filtration rate (N) | {q_per_filter/avg_area:.2f} m/h |

### Water
| | Feed | Backwash |
|---|---|---|
| Salinity | {feed_sal:.2f} ppt | {bw_sal:.2f} ppt |
| Temperature | {feed_temp:.1f} °C | {bw_temp:.1f} °C |
| Density | {rho_feed:.3f} kg/m³ | {rho_bw:.3f} kg/m³ |
| Viscosity | {mu_feed*1000:.4f} cP | {mu_bw*1000:.4f} cP |

### Vessel
| Parameter | Value |
|---|---|
| Nominal ID / Real hyd. ID | {nominal_id:.3f} m / {real_id:.4f} m |
| Total length T/T | {total_length:.3f} m |
| End geometry | {end_geometry} |
| Material | {material_name} |
| Shell t_design | {mech['t_shell_design_mm']} mm |
| Head t_design | {mech['t_head_design_mm']} mm |
| OD | {mech['od_m']:.4f} m |

### Backwash — collector check
| Parameter | Value |
|---|---|
| Proposed BW velocity | {bw_velocity:.1f} m/h |
| Max safe BW velocity | {bw_col['max_safe_bw_m_h']:.1f} m/h |
| Min. freeboard | {freeboard_mm:.0f} mm |
| Freeboard | {bw_col['freeboard_m']:.3f} m ({bw_col['freeboard_pct']:.1f}%) |
| Status | {bw_col['status']} |

### Empty weight
| Component | Weight |
|---|---|
| Shell + 2 heads | {wt_body['weight_body_kg']:,.0f} kg |
| Nozzles | {w_noz:,.0f} kg |
| Nozzle plate assembly | {wt_np['weight_total_kg']:,.0f} kg |
| Supports | {wt_sup['weight_all_supports_kg']:,.0f} kg |
| Internals | {wt_int['weight_internals_kg']:,.0f} kg |
| **Total** | **{w_total_rep:,.0f} kg = {w_total_rep/1000:.3f} t** |

### Cartridge filter
| Parameter | Value |
|---|---|
| Design flow | {cart_result['design_flow_m3h']:,.1f} m³/h |
| Material | {cart_result['element_material']} |
| Element | {cart_result['element_size']} ({cart_result['element_ties']} TIE) · {cart_result['rating_um']} µm |
| Safety factor | {cart_result['safety_factor']}× |
| Feed viscosity | {cart_result['mu_cP']:.2f} cP |
| Elements / Housings | {cart_result['n_elements']} elem. / {cart_result['n_housings']} housings ({cart_result['n_elem_per_housing']} per housing) |
| Flow per element | {cart_result['actual_flow_m3h_element']:.3f} m³/h ({cart_result['q_lpm_element']:.1f} lpm) |
| ΔP clean / EOL | {cart_result['dp_clean_bar']:.4f} / {cart_result['dp_eol_bar']:.4f} bar |
| DHC per element | {cart_result['dhc_g_element']:.0f} g |
| Annual element cost | USD {cart_result['annual_cost_usd']:,.0f} |

### Energy & hydraulic profile
| Component | Clean bed | Dirty bed (M_max) |
|---|---|---|
{"".join(f"| {k} | {hyd_prof['clean']['items_bar'][k]:.4f} bar / {hyd_prof['clean']['items_mwc'][k]:.2f} mWC | {hyd_prof['dirty']['items_bar'][k]:.4f} bar / {hyd_prof['dirty']['items_mwc'][k]:.2f} mWC |" + chr(10) for k in hyd_prof['clean']['items_bar'])}| **Total pump duty** | **{hyd_prof['clean']['total_bar']:.4f} bar / {hyd_prof['clean']['total_mwc']:.2f} mWC** | **{hyd_prof['dirty']['total_bar']:.4f} bar / {hyd_prof['dirty']['total_mwc']:.2f} mWC** |

| KPI | Value |
|---|---|
| Filtration pump power (dirty, per filter) | {energy['p_filt_dirty_kw']:.1f} kW |
| BW pump power | {energy['p_bw_kw']:.1f} kW |
| Air blower power (electrical) | {energy['p_blower_elec_kw']:.1f} kW |
| Annual total energy | {energy['e_total_kwh_yr']/1e3:,.0f} MWh/yr |
| Specific energy | {energy['kwh_per_m3']:.4f} kWh/m³ |
| Annual energy OPEX | USD {energy['cost_usd_yr']:,.0f}/yr |
        """)

        col_sign, _ = st.columns([1, 2])
        with col_sign:
            st.info(f"**{engineer}**  \nProcess Expert  \n\n"
                    f"AQUASIGHT™  \n{doc_number} · Rev {revision}")