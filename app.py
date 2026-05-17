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
_duty_only = bool(st.session_state.pop("_bw_duty_only_rerun", False))
st.session_state.pop("_bw_duty_fast_ui", None)  # legacy flag — no longer hides tabs

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
            lightweight_duty_refresh=_duty_only,
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
from ui.bw_timeline_cache import (
    inputs_for_compute_cache,
    merge_bw_duty_applied,
    refresh_bw_timeline_in_computed,
    _repair_bw_timeline_slot,
)

_last = st.session_state.get("mmf_last_computed")
_duty_fast = _duty_only and isinstance(_last, dict) and bool(_last)

if _duty_fast:
    computed = dict(_last)
    _repair_bw_timeline_slot(computed)
    _merged = merge_bw_duty_applied(_inputs_for_compute)
    _stag = str(_merged.get("bw_timeline_stagger", "feasibility_trains"))
    with st.spinner(
        f"Updating duty chart ({_stag.replace('_', ' ')})…"
    ):
        refresh_bw_timeline_in_computed(_merged, computed)
elif _duty_only:
    st.warning(
        "No saved plant model in this session — running a **full** calculation once. "
        "After that, **Update duty chart** only refreshes the timeline (fast)."
    )
    computed = compute_all_cached(
        inputs_for_compute_cache(_inputs_for_compute),
        _COMPUTE_CACHE_VERSION,
    )
else:
    computed = compute_all_cached(
        inputs_for_compute_cache(_inputs_for_compute),
        _COMPUTE_CACHE_VERSION,
    )
if not st.session_state.get("_bw_duty_applied"):
    st.session_state["_bw_duty_applied"] = {
        "bw_schedule_horizon_days": 7,
        "bw_timeline_stagger": "feasibility_trains",
        "bw_peak_tariff_start_h": 14.0,
        "bw_peak_tariff_end_h": 22.0,
        "bw_tariff_peak_multiplier": 1.5,
        "bw_maintenance_blackout_enabled": False,
        "bw_maintenance_blackout_t0_h": 0.0,
        "bw_maintenance_blackout_t1_h": 0.0,
    }

if not _duty_only:
    from engine.design_basis import build_design_basis
    from engine.explainability import build_explainability_index
    from engine.lifecycle_degradation import build_lifecycle_degradation
    from engine.design_targets import build_design_targets_summary, targets_from_inputs
    from engine.operating_envelope import build_operating_envelope

    computed["operating_envelope"] = build_operating_envelope(_inputs_for_compute, computed)
    from engine.spatial_distribution import (
        build_spatial_distribution,
        enrich_hole_network_with_spatial,
    )

    computed["spatial_distribution"] = build_spatial_distribution(
        _inputs_for_compute, computed, flow_basis="backwash",
    )
    computed["spatial_distribution_filtration"] = build_spatial_distribution(
        _inputs_for_compute, computed, flow_basis="filtration",
    )
    _sp = computed.get("spatial_distribution") or {}
    if _sp.get("enabled"):
        _np_plate = computed.get("collector_nozzle_plate")
        if isinstance(_np_plate, dict) and _np_plate.get("hole_network"):
            _np_plate["hole_network"] = enrich_hole_network_with_spatial(
                list(_np_plate["hole_network"]), _sp,
            )
    computed["design_targets"] = build_design_targets_summary(
        _inputs_for_compute,
        computed,
        targets=targets_from_inputs(_inputs_for_compute),
    )
    from engine.blower_maps import build_blower_map_analysis

    _bm_in = dict(_inputs_for_compute)
    _bm_in["pp_n_blowers"] = int(st.session_state.get("pp_n_blowers", _bm_in.get("pp_n_blowers", 1)) or 1)
    _bm_in["pp_blower_mode"] = str(
        st.session_state.get("pp_blower_mode", _bm_in.get("pp_blower_mode", "single_duty"))
    )
    _bm_in.setdefault("blower_map_auto_curve", bool(st.session_state.get("blower_map_auto_curve", True)))
    _bm_in.setdefault(
        "blower_curve_id",
        str(st.session_state.get("blower_map_curve_sel", _bm_in.get("blower_curve_id", "oem_vendor_motor"))),
    )
    computed["blower_map"] = build_blower_map_analysis(_bm_in, computed)
    computed["design_basis"] = build_design_basis(_inputs_for_compute, computed)
    computed["explainability"] = build_explainability_index(_inputs_for_compute, computed)
    computed["lifecycle_degradation"] = build_lifecycle_degradation(_inputs_for_compute, computed)
    if st.session_state.get("mc_lite_enabled"):
        from engine.monte_carlo_lite import build_monte_carlo_cycle_lite

        computed["monte_carlo_cycle"] = build_monte_carlo_cycle_lite(
            _inputs_for_compute,
            computed,
            n_samples=int(st.session_state.get("mc_lite_n_samples", 200) or 200),
            seed=int(st.session_state.get("mc_lite_seed", 42) or 42),
        )
    else:
        computed["monte_carlo_cycle"] = {"enabled": False}
    _cfd_csv = st.session_state.get("mmf_cfd_import_text")
    if _cfd_csv:
        from engine.cfd_import import build_cfd_import_comparison

        computed["cfd_import_comparison"] = build_cfd_import_comparison(_cfd_csv, computed)
    else:
        computed["cfd_import_comparison"] = {"enabled": False}
    _ops_telemetry = st.session_state.get("mmf_ops_telemetry_text")
    if _ops_telemetry:
        from engine.digital_twin_lite import build_digital_twin_lite

        computed["digital_twin_lite"] = build_digital_twin_lite(
            _ops_telemetry, _inputs_for_compute, computed,
        )
    else:
        computed["digital_twin_lite"] = {"enabled": False}
    _tag_csv = st.session_state.get("mmf_equipment_tag_text")
    if _tag_csv:
        from engine.equipment_tag_import import build_equipment_tag_registry

        computed["equipment_tag_registry"] = build_equipment_tag_registry(
            _tag_csv, _inputs_for_compute, computed,
        )
    else:
        computed["equipment_tag_registry"] = {"enabled": False}

st.session_state["mmf_last_computed"] = computed

_INTRO_CAPTION = (
    "**Columns:** Left = inputs, right = results. Each side scrolls independently where your browser supports "
    "CSS **:has()** (modern Chromium / Firefox / Safari). **Quick jump** switches a tab only (not a field inside a tab). "
    "**Hide input column** widens results; **Show input column** brings the editor back — values stay on your last "
    "**Apply** until you change them again."
)


def _render_main_results_stack(
    *, inputs: dict, computed: dict, inputs_collapsed: bool, duty_fast: bool = False
) -> None:
    """Project strip → quick jump → intro caption → section guide → validation → tabs (results column)."""
    column_marker("main")
    render_project_toolbar(inputs, computed)
    render_quick_jump_bar(inputs_collapsed=inputs_collapsed)
    st.caption(_INTRO_CAPTION)
    if duty_fast:
        st.caption(
            "⚡ **Duty chart updated** — timeline refreshed from sidebar settings. "
            "All tabs show your last full model; change plant inputs then rerun from sidebar as usual."
        )
    render_section_guide_row()
    render_compute_validation_banners(computed)
    (tab_filtration, tab_backwash, tab_mechanical, tab_media, tab_pumps,
     tab_economics, tab_assessment, tab_report, tab_compare) = st.tabs(
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
        inputs=inputs, computed=computed, inputs_collapsed=True, duty_fast=_duty_fast,
    )
    render_readiness_strip(inputs, computed)
else:
    with main:
        _render_main_results_stack(
            inputs=inputs, computed=computed, inputs_collapsed=False, duty_fast=_duty_fast,
        )
    with ctx:
        render_readiness_strip(inputs, computed)

_guide_tip = st.session_state.pop("mmf_guide_banner", None)

if _guide_tip:
    st.info(_guide_tip)

try_consume_pending_scroll(inputs_collapsed=_ctx_collapsed)