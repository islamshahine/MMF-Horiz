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

import streamlit as st

from engine.mechanical import (
    MATERIALS, RADIOGRAPHY_OPTIONS, JOINT_EFFICIENCY,
    STEEL_DENSITY_KG_M3, SUPPORT_TYPES,
    NOZZLE_DENSITY_MIN, NOZZLE_DENSITY_MAX, NOZZLE_DENSITY_DEFAULT,
    STRAINER_WEIGHT_KG, MANHOLE_WEIGHT_KG,
)
from engine.coating import (
    PROTECTION_TYPES, RUBBER_TYPES, EPOXY_TYPES, CERAMIC_TYPES,
    DEFAULT_LABOR_RUBBER_M2, DEFAULT_LABOR_EPOXY_M2, DEFAULT_LABOR_CERAMIC_M2,
)
from engine.cartridge import (
    ELEMENT_SIZE_LABELS, RATING_UM_OPTIONS,
    HOUSING_CAPACITY_OPTIONS, DEFAULT_ELEMENTS_PER_HOUSING,
    SAFETY_FACTOR_STD, SAFETY_FACTOR_CIP,
)
from engine.nozzles import FLANGE_RATINGS

from engine.compute import compute_all
from ui.sidebar import render_sidebar
from ui.helpers import fmt
from ui.tab_filtration  import render_tab_filtration
from ui.tab_backwash    import render_tab_backwash
from ui.tab_mechanical  import render_tab_mechanical
from ui.tab_media       import render_tab_media
from ui.tab_economics   import render_tab_economics
from ui.tab_assessment  import render_tab_assessment
from ui.tab_report      import render_tab_report

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="AQUASIGHT™ MMF", layout="wide",
                   initial_sidebar_state="collapsed")

# ══════════════════════════════════════════════════════════════════════════════
# MEDIA PRESETS  (default 3-layer: Gravel / Sand / Anthracite)
# ══════════════════════════════════════════════════════════════════════════════
def _eps0_from_psi(psi: float) -> float:
    """Empirical estimate: ε₀ ≈ 0.4 + 0.1·(1−ψ)/ψ  (Kozeny-based, random packing)."""
    return round(0.4 + 0.1 * (1.0 - psi) / max(psi, 0.01), 3)

def _rho_eff_porous(rho_dry: float, eps_p: float, rho_water: float = 1025.0) -> float:
    """Water-saturated particle density for porous media.
    ρ_eff = ρ_dry + ρ_water × ε_p
    where ρ_dry is apparent dry-particle density and ε_p is internal particle porosity.
    """
    return rho_dry + rho_water * eps_p

# Fields: d10 (mm), cu (CU=d60/d10), epsilon0, rho_p_eff (kg/m³), d60 (mm),
#         psi (sphericity), is_porous, default_depth (m)
DEFAULT_MEDIA_PRESETS = {
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

# Always sync: add any new catalogue entries, remove renamed ones
if "media_presets" not in st.session_state or set(
        st.session_state.media_presets.keys()) != set(DEFAULT_MEDIA_PRESETS.keys()):
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
# LAYOUT: context tabs (left) | output tabs (right)
# ══════════════════════════════════════════════════════════════════════════════
ctx, main = st.columns([1, 4])

with ctx:
    inputs = render_sidebar(
        MATERIALS, RADIOGRAPHY_OPTIONS, JOINT_EFFICIENCY, PROTECTION_TYPES,
        RUBBER_TYPES, EPOXY_TYPES, CERAMIC_TYPES,
        DEFAULT_LABOR_RUBBER_M2, DEFAULT_LABOR_EPOXY_M2, DEFAULT_LABOR_CERAMIC_M2,
        STEEL_DENSITY_KG_M3, FLANGE_RATINGS, STRAINER_WEIGHT_KG, MANHOLE_WEIGHT_KG,
        SUPPORT_TYPES, NOZZLE_DENSITY_DEFAULT, NOZZLE_DENSITY_MIN, NOZZLE_DENSITY_MAX,
        ELEMENT_SIZE_LABELS, RATING_UM_OPTIONS, HOUSING_CAPACITY_OPTIONS,
        DEFAULT_ELEMENTS_PER_HOUSING, SAFETY_FACTOR_CIP, SAFETY_FACTOR_STD,
    )

computed = compute_all(inputs)

# ── Status badges (context column, below sidebar tabs) ────────────────────────
with ctx:
    st.divider()
    _bw_col = computed["bw_col"]
    _status_items = {
        "Project":    bool(inputs["project_name"]),
        "Process":    inputs["total_flow"] > 0 and inputs["n_filters"] > 0,
        "Water":      inputs["feed_sal"] >= 0 and inputs["feed_temp"] > 0,
        "Geometry":   inputs["nominal_id"] > 0 and inputs["total_length"] > 0,
        "Mechanical": inputs["design_pressure"] > 0,
        "Media":      (len(inputs["layers"]) > 0
                       and all(L["Depth"] > 0 for L in inputs["layers"])),
        "Backwash":   not _bw_col["media_loss_risk"],
        "Weight":     computed["w_total"] > 0,
    }
    _cols_status = st.columns(2)
    for i, (label, done) in enumerate(_status_items.items()):
        icon = ("🟢" if done else
                "🔴" if label == "Backwash" and _bw_col["media_loss_risk"]
                else "⚪")
        _cols_status[i % 2].markdown(f"{icon} {label}")
    if _bw_col["media_loss_risk"]:
        st.warning(f"⚠️ Media carryover risk — max safe BW rate: "
                   f"{fmt(_bw_col['max_safe_bw_m_h'], 'velocity_m_h', 1)}")
    st.caption("AQUASIGHT™ | Proprietary")

with main:
    (tab_filtration, tab_backwash, tab_mechanical,
     tab_media, tab_economics, tab_assessment, tab_report) = st.tabs([
        "💧 Filtration", "🔄 Backwash", "⚙️ Mechanical",
        "🧱 Media", "💰 Economics", "🎯 Assessment", "📄 Report",
    ])

    with tab_filtration:
        render_tab_filtration(inputs, computed)

    with tab_backwash:
        render_tab_backwash(inputs, computed)

    with tab_mechanical:
        render_tab_mechanical(inputs, computed)

    with tab_media:
        render_tab_media(inputs, computed)

    with tab_economics:
        render_tab_economics(inputs, computed)

    with tab_assessment:
        render_tab_assessment(inputs, computed)

    with tab_report:
        render_tab_report(inputs, computed)
