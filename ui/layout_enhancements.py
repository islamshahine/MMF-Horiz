"""Layout shell: column scroll, sticky tab bars, quick-jump navigation.

Streamlit limits:
- True in-page scroll-to-widget search is not supported without custom JS components.
- We switch tabs via ``st.tabs(..., key=...)`` session values and a selectbox "Quick jump".

CSS uses ``:has()`` (modern browsers) to tie rules to hidden marker spans in the input and main columns.
"""
from __future__ import annotations

import streamlit as st

# Must match ``app.py`` / ``sidebar.py`` tab label strings exactly (including emoji).
MAIN_TAB_LABELS: tuple[str, ...] = (
    "💧 Filtration",
    "🔄 Backwash",
    "⚙️ Mechanical",
    "🧱 Media",
    "⚡ Pumps & power",
    "💰 Economics",
    "🎯 Assessment",
    "📄 Report",
    "⚖️ Compare",
)

SIDEBAR_TAB_LABELS: tuple[str, ...] = (
    "⚙️ Process",
    "🏗️ Vessel",
    "🧱 Media",
    "🔄 BW",
    "💰 Econ",
)

_JUMP_PLACEHOLDER = "— Quick jump —"
_SECTION_GUIDE_PLACEHOLDER = "— Section guide (tab + where to look) —"

# (list label, "sidebar"|"main", exact tab title, tip, scroll anchor id or "")
SECTION_GUIDE_ROWS: tuple[tuple[str, str, str, str, str], ...] = (
    ("Guide · Project & plant duty", "sidebar", "⚙️ Process",
     "**Inputs → Process:** project row, streams, feed/BW water, performance caption.",
     "mmf-anchor-sb-process"),
    ("Guide · Cartridge & CF", "sidebar", "⚙️ Process",
     "**Process** tab → expand **Cartridge & solids calibration**.",
     "mmf-anchor-sb-process-cartridge"),
    ("Guide · Vessel / ASME / lining", "sidebar", "🏗️ Vessel",
     "**Vessel** tab: geometry, ASME, radiography, lining / coating.",
     "mmf-anchor-sb-vessel"),
    ("Guide · Nozzle plate & layers", "sidebar", "🧱 Media",
     "**Media** tab: nozzle plate, then **Media layers** block.",
     "mmf-anchor-sb-media-nozzle"),
    ("Guide · Media layer stack", "sidebar", "🧱 Media",
     "**Media** tab → **Media layers** (depths, capture %, LV/EBCT per layer).",
     "mmf-anchor-sb-media-layers"),
    ("Guide · M_max, α & fouling", "sidebar", "🧱 Media",
     "**Media** tab → **Filtration performance** and **Calibration / fouling** expanders.",
     "mmf-anchor-sb-media-mmax"),
    ("Guide · BW hydraulics & steps", "sidebar", "🔄 BW",
     "**BW** tab: collector, velocities, air scour, step durations, equipment.",
     "mmf-anchor-sb-bw"),
    ("Guide · Economics inputs", "sidebar", "💰 Econ",
     "**Econ** tab: tariff, hours, media intervals, financial lifecycle.",
     "mmf-anchor-sb-econ"),
    ("Guide · Filtration results", "main", "💧 Filtration",
     "**Filtration** tab: flow table, LV/EBCT, ΔP expanders, cycles, cartridge.",
     "mmf-anchor-main-filtration"),
    ("Guide · Backwash results", "main", "🔄 Backwash",
     "**Backwash** tab: expansion, sequence, timeline, feasibility.",
     "mmf-anchor-main-backwash"),
    ("Guide · Mechanical outputs", "main", "⚙️ Mechanical",
     "**Mechanical** tab: geometry metrics, ASME, nozzle schedule, weights, drawing.",
     "mmf-anchor-main-mechanical"),
    ("Guide · Media ΔP tables", "main", "🧱 Media",
     "**Media** tab §3: per-layer clean / moderate / dirty ΔP.",
     "mmf-anchor-main-media"),
    ("Guide · Pumps & power", "main", "⚡ Pumps & power",
     "**Pumps & power** tab: hydraulics, staging, energy, screening CAPEX.",
     "mmf-anchor-main-pumps"),
    ("Guide · Economics outputs", "main", "💰 Economics",
     "**Economics** tab: OPEX, CAPEX, financial model.",
     "mmf-anchor-main-economics"),
    ("Guide · Assessment", "main", "🎯 Assessment",
     "**Assessment** tab.",
     "mmf-anchor-main-assessment"),
    ("Guide · Report", "main", "📄 Report",
     "**Report** tab: PDF / Word; project JSON is saved from the **Project file** strip at the top of this column.",
     "mmf-anchor-main-report"),
    ("Guide · Compare", "main", "⚖️ Compare",
     "**Compare** tab.",
     "mmf-anchor-main-compare"),
)


def init_layout_session_state() -> None:
    if "mmf_ctx_collapsed" not in st.session_state:
        st.session_state["mmf_ctx_collapsed"] = False
    if "mmf_main_tabs" not in st.session_state:
        st.session_state["mmf_main_tabs"] = MAIN_TAB_LABELS[0]
    if "mmf_sidebar_tabs" not in st.session_state:
        st.session_state["mmf_sidebar_tabs"] = SIDEBAR_TAB_LABELS[0]
    if "mmf_quick_jump_select" not in st.session_state:
        st.session_state["mmf_quick_jump_select"] = _JUMP_PLACEHOLDER
    if "mmf_section_guide" not in st.session_state:
        st.session_state["mmf_section_guide"] = _SECTION_GUIDE_PLACEHOLDER


def apply_pending_tab_jumps() -> None:
    """Apply one-shot jump flags (set by Quick jump on_change) before widgets mount."""
    jm = st.session_state.pop("mmf_pending_main_tab", None)
    if isinstance(jm, str) and jm in MAIN_TAB_LABELS:
        st.session_state["mmf_main_tabs"] = jm
    js = st.session_state.pop("mmf_pending_sidebar_tab", None)
    if isinstance(js, str) and js in SIDEBAR_TAB_LABELS:
        st.session_state["mmf_sidebar_tabs"] = js


def _on_quick_jump_change() -> None:
    pick = st.session_state.get("mmf_quick_jump_select")
    if not isinstance(pick, str) or pick == _JUMP_PLACEHOLDER:
        return
    if pick.startswith("Sidebar · "):
        label = pick.removeprefix("Sidebar · ")
        if label in SIDEBAR_TAB_LABELS:
            st.session_state["mmf_pending_sidebar_tab"] = label
    elif pick.startswith("Main · "):
        label = pick.removeprefix("Main · ")
        if label in MAIN_TAB_LABELS:
            st.session_state["mmf_pending_main_tab"] = label
    st.session_state["mmf_quick_jump_select"] = _JUMP_PLACEHOLDER


def render_quick_jump_bar(*, inputs_collapsed: bool) -> None:
    """Top-of-app row: quick tab jump + show/hide input column (clear labels)."""
    opts = [_JUMP_PLACEHOLDER] + [
        f"Sidebar · {x}" for x in SIDEBAR_TAB_LABELS
    ] + [f"Main · {x}" for x in MAIN_TAB_LABELS]
    c1, c2, c3 = st.columns([4, 1.2, 1.8])
    with c1:
        st.selectbox(
            "Quick jump",
            options=opts,
            key="mmf_quick_jump_select",
            label_visibility="collapsed",
            on_change=_on_quick_jump_change,
        )
    with c2:
        st.caption("Jump → tab")
    with c3:
        if inputs_collapsed:
            if st.button("Show input column", type="primary", use_container_width=True, key="mmf_expand_ctx"):
                st.session_state["mmf_ctx_collapsed"] = False
                st.rerun()
        else:
            if st.button("Hide input column", type="secondary", use_container_width=True, key="mmf_collapse_ctx"):
                st.session_state["mmf_ctx_collapsed"] = True
                st.rerun()
    if inputs_collapsed:
        st.caption(
            "Input column hidden — results use your last **Apply**. **Show input column** (above) to edit."
        )


def render_compute_validation_banners(computed: dict) -> None:
    """Engine validation / reference fallback — render inside the results column (not above the whole app)."""
    _iv = computed.get("input_validation") or {}
    if computed.get("compute_used_reference_fallback"):
        st.error(
            "**Reference baseline run** — inputs failed validation. All tabs show **built-in SI reference** "
            "results, not your sidebar values, until the errors below are fixed."
        )
    for _msg in _iv.get("errors", ()):
        st.error(_msg)
    for _msg in _iv.get("warnings", ()):
        st.warning(_msg)
    if _iv.get("errors"):
        _vus = _iv.get("unit_system") or st.session_state.get("unit_system", "metric")
        if _vus == "imperial":
            st.caption(
                "Thresholds above use **imperial** units to match the sidebar toggle. "
                "The engine still calculates in SI internally."
            )
        else:
            st.caption(
                "Validation uses **metric (SI)** units, matching the sidebar toggle."
            )


def _on_section_guide_change() -> None:
    pick = st.session_state.get("mmf_section_guide")
    if not isinstance(pick, str) or pick == _SECTION_GUIDE_PLACEHOLDER:
        return
    for label, zone, tab, tip, anchor in SECTION_GUIDE_ROWS:
        if pick != label:
            continue
        if zone == "sidebar" and tab in SIDEBAR_TAB_LABELS:
            st.session_state["mmf_pending_sidebar_tab"] = tab
        elif zone == "main" and tab in MAIN_TAB_LABELS:
            st.session_state["mmf_pending_main_tab"] = tab
        st.session_state["mmf_guide_banner"] = tip
        if anchor:
            st.session_state["mmf_scroll_to_id"] = anchor
        break
    st.session_state["mmf_section_guide"] = _SECTION_GUIDE_PLACEHOLDER


def render_section_guide_row() -> None:
    """Curated index: jump to the right tab and show where to look (no in-tab auto-scroll)."""
    opts = [_SECTION_GUIDE_PLACEHOLDER] + [r[0] for r in SECTION_GUIDE_ROWS]
    g1, g2 = st.columns([4, 2])
    with g1:
        st.selectbox(
            "Section guide",
            options=opts,
            key="mmf_section_guide",
            label_visibility="collapsed",
            on_change=_on_section_guide_change,
        )
    with g2:
        st.caption("Tab + hint + scroll")


def inject_layout_css() -> None:
    """Inject independent column scroll + sticky tab headers (requires :has() support)."""
    st.markdown(
        """
        <style>
        @supports selector(:has(*)) {
            section.main div[data-testid="column"]:has(.mmf-sidebar-mark),
            section.main div[data-testid="column"]:has(.mmf-main-mark) {
                max-height: calc(100vh - 9.5rem);
                overflow-y: auto;
                overflow-x: hidden;
                align-self: flex-start;
            }
            section.main div[data-testid="column"]:has(.mmf-main-mark) [data-testid="stTabs"] > div:first-child,
            section.main div[data-testid="column"]:has(.mmf-sidebar-mark) [data-testid="stTabs"] > div:first-child {
                position: sticky;
                top: 0;
                z-index: 50;
                background: var(--secondary-background-color, #f0f2f6);
                padding-bottom: 0.2rem;
                border-bottom: 1px solid rgba(49, 51, 63, 0.1);
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_readiness_strip(inputs: dict, computed: dict) -> None:
    """Compact readiness / risk line (used in both split and collapsed layouts)."""
    from ui.helpers import fmt

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
        st.warning(
            f"⚠️ Media carryover risk — max safe BW rate: "
            f"{fmt(_bw_col['max_safe_bw_m_h'], 'velocity_m_h', 1)}"
        )
    st.caption("AQUASIGHT™ | Proprietary")


def column_marker(side: str) -> None:
    """Hidden marker for :has() CSS (sidebar | main)."""
    cls = "mmf-sidebar-mark" if side == "sidebar" else "mmf-main-mark"
    st.markdown(
        f'<span class="{cls}" style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )
