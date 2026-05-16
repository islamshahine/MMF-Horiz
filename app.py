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
    NOZZLE_DENSITY_DEFAULT,
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
from engine.default_media_presets import DEFAULT_MEDIA_PRESETS

from ui.compute_cache import compute_all_cached
from ui.feed_pump_context_inputs import reconcile_si_inputs_with_pump_widgets
from ui.sidebar import render_sidebar
from ui.tab_filtration  import render_tab_filtration
from ui.tab_backwash    import render_tab_backwash
from ui.tab_mechanical  import render_tab_mechanical
from ui.tab_media       import render_tab_media
from ui.tab_pump_costing import render_tab_pump_costing
from ui.tab_economics   import render_tab_economics
from ui.tab_assessment  import render_tab_assessment
from ui.tab_report      import render_tab_report
from ui.tab_compare     import render_tab_compare
from ui.scroll_markers import try_consume_pending_scroll
from ui.project_toolbar import consume_deferred_project_actions, render_project_toolbar

# ══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="AQUASIGHT™ MMF", layout="wide",
                   initial_sidebar_state="collapsed")

from ui.layout_enhancements import (
    apply_pending_tab_jumps,
    column_marker,
    init_layout_session_state,
    inject_layout_css,
    render_compute_validation_banners,
    render_quick_jump_bar,
    render_readiness_strip,
    render_section_guide_row,
)

init_layout_session_state()
apply_pending_tab_jumps()
inject_layout_css()

# Media preset catalogue — keys from ``engine.default_media_presets.DEFAULT_MEDIA_PRESETS``
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

consume_deferred_project_actions()

from engine.units import display_value, si_value
from ui.nozzle_header_sync import sync_linked_collector_header_session

_us_early = st.session_state.get("unit_system", "metric")
sync_linked_collector_header_session(
    q_filter_m3h=float(st.session_state.get("mmf_last_q_per_filter") or 0),
    bw_velocity_m_h=si_value(
        float(st.session_state.get("bw_velocity", display_value(30.0, "velocity_m_h", _us_early))),
        "velocity_m_h",
        _us_early,
    ),
    area_filter_m2=float(st.session_state.get("mmf_last_avg_area") or 25),
)

_ctx_collapsed = bool(st.session_state.get("mmf_ctx_collapsed"))

inputs: dict = {}

if _ctx_collapsed:
    inputs = dict(st.session_state.get("mmf_last_inputs") or {})
    if not inputs:
        st.session_state["mmf_ctx_collapsed"] = False
        st.warning("Opening the input panel — there were no saved parameters in this browser session yet.")
        st.rerun()
    else:
        inputs = reconcile_si_inputs_with_pump_widgets(inputs)
else:
    ctx, main = st.columns([1, 4])

    with ctx:
        column_marker("sidebar")
        inputs = render_sidebar(
            MATERIALS, RADIOGRAPHY_OPTIONS, JOINT_EFFICIENCY, PROTECTION_TYPES,
            RUBBER_TYPES, EPOXY_TYPES, CERAMIC_TYPES,
            DEFAULT_LABOR_RUBBER_M2, DEFAULT_LABOR_EPOXY_M2, DEFAULT_LABOR_CERAMIC_M2,
            STEEL_DENSITY_KG_M3, FLANGE_RATINGS, STRAINER_WEIGHT_KG, MANHOLE_WEIGHT_KG,
            SUPPORT_TYPES, NOZZLE_DENSITY_DEFAULT,
            ELEMENT_SIZE_LABELS, RATING_UM_OPTIONS, HOUSING_CAPACITY_OPTIONS,
            DEFAULT_ELEMENTS_PER_HOUSING, SAFETY_FACTOR_CIP, SAFETY_FACTOR_STD,
        )
        st.session_state["mmf_last_inputs"] = inputs

_inputs_for_compute = dict(inputs)
if st.session_state.get("mmf_nozzle_sched_user"):
    _inputs_for_compute["nozzle_sched_override"] = st.session_state["mmf_nozzle_sched_user"]

from ui.nozzle_header_sync import patch_inputs_collector_header_si

_inputs_for_compute = patch_inputs_collector_header_si(
    _inputs_for_compute,
    q_filter_m3h=float(st.session_state.get("mmf_last_q_per_filter") or 0),
    bw_velocity_m_h=float(_inputs_for_compute.get("bw_velocity", 30) or 30),
    area_filter_m2=float(st.session_state.get("mmf_last_avg_area") or 25),
)

from ui.compute_cache import _COMPUTE_CACHE_VERSION

computed = compute_all_cached(_inputs_for_compute, _COMPUTE_CACHE_VERSION)
from engine.design_basis import build_design_basis
from engine.explainability import build_explainability_index
from engine.lifecycle_degradation import build_lifecycle_degradation

computed["design_basis"] = build_design_basis(_inputs_for_compute, computed)
computed["explainability"] = build_explainability_index(_inputs_for_compute, computed)
computed["lifecycle_degradation"] = build_lifecycle_degradation(_inputs_for_compute, computed)
st.session_state["mmf_last_computed"] = computed

_INTRO_CAPTION = (
    "**Columns:** Left = inputs, right = results. Each side scrolls independently where your browser supports "
    "CSS **:has()** (modern Chromium / Firefox / Safari). **Quick jump** switches a tab only (not a field inside a tab). "
    "**Hide input column** widens results; **Show input column** brings the editor back — values stay on your last "
    "**Apply** until you change them again."
)


def _render_main_results_stack(
    *, inputs: dict, computed: dict, inputs_collapsed: bool
) -> None:
    """Project strip → quick jump → intro caption → section guide → validation → tabs (results column)."""
    column_marker("main")
    render_project_toolbar(inputs, computed)
    render_quick_jump_bar(inputs_collapsed=inputs_collapsed)
    st.caption(_INTRO_CAPTION)
    render_section_guide_row()
    render_compute_validation_banners(computed)
    (tab_filtration, tab_backwash, tab_mechanical,
     tab_media, tab_pumps, tab_economics, tab_assessment, tab_report, tab_compare) = st.tabs(
        [
            "💧 Filtration", "🔄 Backwash", "⚙️ Mechanical",
            "🧱 Media", "⚡ Pumps & power", "💰 Economics", "🎯 Assessment", "📄 Report",
            "⚖️ Compare",
        ],
        key="mmf_main_tabs",
    )

    with tab_filtration:
        render_tab_filtration(inputs, computed)

    with tab_backwash:
        render_tab_backwash(inputs, computed)

    with tab_mechanical:
        render_tab_mechanical(inputs, computed)

    with tab_media:
        render_tab_media(inputs, computed)

    with tab_pumps:
        render_tab_pump_costing(inputs, computed)

    with tab_economics:
        render_tab_economics(inputs, computed)

    with tab_assessment:
        render_tab_assessment(inputs, computed)

    with tab_report:
        render_tab_report(inputs, computed)

    with tab_compare:
        render_tab_compare(inputs, computed)


if _ctx_collapsed:
    _render_main_results_stack(
        inputs=inputs, computed=computed, inputs_collapsed=True,
    )
    render_readiness_strip(inputs, computed)
else:
    with main:
        _render_main_results_stack(
            inputs=inputs, computed=computed, inputs_collapsed=False,
        )
    with ctx:
        render_readiness_strip(inputs, computed)

_guide_tip = st.session_state.pop("mmf_guide_banner", None)

if _guide_tip:
    st.info(_guide_tip)

try_consume_pending_scroll(inputs_collapsed=_ctx_collapsed)