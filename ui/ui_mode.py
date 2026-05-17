"""
ui/ui_mode.py
─────────────
UI mode configuration for AQUASIGHT™ MMF.

Three audience modes control which sidebar widgets and result panels are
shown. Mode is a DISPLAY FILTER only — it never changes ``compute_all()``
or removes keys from the ``inputs`` dict.

Hidden widgets use ``st.session_state`` or ``REFERENCE_FALLBACK_INPUTS``.
"""
from __future__ import annotations

from typing import Any, Final

from engine.validators import REFERENCE_FALLBACK_INPUTS
from ui.layout_enhancements import MAIN_TAB_LABELS, SIDEBAR_TAB_LABELS

UI_MODES: Final[tuple[str, ...]] = ("client", "engineer", "expert")

MODE_LABELS: Final[dict[str, str]] = {
    "client": "👔 Client",
    "engineer": "⚙️ Engineer",
    "expert": "🔬 Expert",
}

MODE_DESCRIPTIONS: Final[dict[str, str]] = {
    "client": (
        "Key project inputs and summary metrics. Calibration and advanced "
        "tuning are hidden. Ideal for client review meetings."
    ),
    "engineer": (
        "Full design workflow — all physical inputs; calibration in "
        "collapsed expanders when needed."
    ),
    "expert": (
        "All inputs including §6.3 calibration knobs plus Tier-C validation "
        "tools on results tabs."
    ),
}

SESSION_KEY: Final[str] = "ui_mode"
DEFAULT_MODE: Final[str] = "engineer"

# §6.3 — engineering judgement / tuning (not primary geometry)
CALIBRATION_KEYS: Final[frozenset[str]] = frozenset({
    "solid_loading_scale",
    "alpha_specific",
    "alpha_calibration_factor",
    "maldistribution_factor",
    "use_calculated_maldistribution",
    "tss_capture_efficiency",
    "expansion_calibration_scale",
})

# Must never be hidden in any mode
CRITICAL_INPUT_KEYS: Final[frozenset[str]] = frozenset({
    "total_flow",
    "streams",
    "n_filters",
    "hydraulic_assist",
    "redundancy",
    "nominal_id",
    "total_length",
    "layers",
})

# Sidebar widget keys hidden in Client (values still in session / fallback)
_CLIENT_HIDDEN: frozenset[str] = frozenset({
    "end_geometry",
    "lining_mm",
    "design_pressure",
    "design_temp",
    "corrosion",
    "shell_radio",
    "head_radio",
    "ov_shell",
    "ov_head",
    "steel_density",
    "protection_type",
    "np_bore_dia",
    "np_density",
    "np_beam_sp",
    "np_override_t",
    "np_slot_dp",
    "nozzle_catalogue_id",
    "n_nozzle_rows",
    "freeboard_mm",
    "bw_s_drain",
    "bw_s_air",
    "bw_s_airw",
    "bw_s_hw",
    "bw_s_settle",
    "bw_s_fill",
    "bw_cycles_day",
    "air_scour_rate",
    "solid_loading_scale",
    "alpha_calibration_factor",
    "maldistribution_factor",
    "use_calculated_maldistribution",
    "tss_capture_efficiency",
    "expansion_calibration_scale",
    "velocity_threshold",
    "ebct_threshold",
    "steel_cost_usd_kg",
    "erection_usd_vessel",
    "engineering_pct",
    "contingency_pct",
    "media_replace_years",
    "discount_rate",
    "tax_rate",
    "depreciation_method",
    "inflation_rate",
    "escalation_energy_pct",
    "salvage_value_pct",
    "steel_carbon_kg",
    "pump_eta",
    "bw_pump_eta",
    "motor_eta",
})

# Engineer: calibration knobs hidden from per-key gating (shown in expander blocks)
_ENGINEER_HIDDEN: frozenset[str] = frozenset({
    "solid_loading_scale",
    "alpha_calibration_factor",
    "maldistribution_factor",
    "tss_capture_efficiency",
    "expansion_calibration_scale",
})

_EXPERT_HIDDEN: frozenset[str] = frozenset()

HIDDEN_KEYS: Final[dict[str, frozenset[str]]] = {
    "client": _CLIENT_HIDDEN,
    "engineer": _ENGINEER_HIDDEN,
    "expert": _EXPERT_HIDDEN,
}

VISIBLE_SIDEBAR_TABS: Final[dict[str, tuple[str, ...]]] = {
    "client": ("⚙️ Process", "🏗️ Vessel", "🧱 Media"),
    "engineer": SIDEBAR_TAB_LABELS,
    "expert": SIDEBAR_TAB_LABELS,
}

_COMPARE_TAB: Final[str] = "⚖️ Compare"

VISIBLE_MAIN_TABS: Final[dict[str, tuple[str, ...]]] = {
    "client": tuple(t for t in MAIN_TAB_LABELS if t != _COMPARE_TAB),
    "engineer": MAIN_TAB_LABELS,
    "expert": MAIN_TAB_LABELS,
}


def normalize_mode(mode: str | None) -> str:
    m = str(mode or DEFAULT_MODE).strip().lower()
    return m if m in UI_MODES else DEFAULT_MODE


def mode_allows(key: str, mode: str | None = None) -> bool:
    """True if a sidebar widget for this ``inputs`` key should be shown."""
    m = normalize_mode(mode)
    return key not in HIDDEN_KEYS.get(m, _ENGINEER_HIDDEN)


def is_calibration_key(key: str) -> bool:
    return key in CALIBRATION_KEYS


def fallback_value(key: str) -> Any:
    """SI default for a hidden widget (session wins at read time in UI)."""
    if key in REFERENCE_FALLBACK_INPUTS:
        return REFERENCE_FALLBACK_INPUTS[key]
    return None


def get_mode_config(mode: str | None = None) -> dict[str, Any]:
    m = normalize_mode(mode)
    return {
        "mode": m,
        "label": MODE_LABELS.get(m, m),
        "description": MODE_DESCRIPTIONS.get(m, ""),
        "hidden_keys": HIDDEN_KEYS.get(m, _ENGINEER_HIDDEN),
        "visible_sidebar_tabs": VISIBLE_SIDEBAR_TABS.get(m, SIDEBAR_TAB_LABELS),
        "visible_main_tabs": VISIBLE_MAIN_TABS.get(m, MAIN_TAB_LABELS),
        "show_calibration_expander": m in ("engineer", "expert"),
        "show_calibration_knobs": m == "expert",
        "show_tier_c_results": m == "expert",
        "show_engineer_tools": m in ("engineer", "expert"),
        "show_compare_tab": m in ("engineer", "expert"),
        "read_only_hint": m == "client",
    }


def visible_main_tab_labels(
    all_labels: tuple[str, ...] | None = None,
    mode: str | None = None,
) -> tuple[str, ...]:
    m = normalize_mode(mode) if mode is not None else current_ui_mode()
    allowed = frozenset(VISIBLE_MAIN_TABS.get(m, MAIN_TAB_LABELS))
    src = all_labels if all_labels is not None else MAIN_TAB_LABELS
    return tuple(lbl for lbl in src if lbl in allowed)


def merge_hidden_input_defaults(out: dict[str, Any], mode: str | None = None) -> dict[str, Any]:
    """
    Ensure keys without widgets in this mode still reach ``convert_inputs``.
    Does not overwrite keys already set in ``out``.
    """
    import copy

    import streamlit as st

    m = normalize_mode(mode)
    merged = dict(out)
    if m == "expert":
        return merged

    for key in (
        "solid_loading_scale",
        "alpha_calibration_factor",
        "maldistribution_factor",
        "tss_capture_efficiency",
        "expansion_calibration_scale",
        "use_calculated_maldistribution",
    ):
        if key not in merged:
            merged[key] = st.session_state.get(key, fallback_value(key))

    if "captured_solids_density" not in merged:
        merged["captured_solids_density"] = float(
            st.session_state.get(
                "captured_solids_density",
                fallback_value("captured_solids_density") or 1020.0,
            )
            or 1020.0
        )
    if "alpha_specific" not in merged:
        _a9 = float(st.session_state.get("alpha_res", 0.0) or 0.0)
        merged["alpha_specific"] = _a9 * 1e9 if _a9 else float(
            fallback_value("alpha_specific") or 1e12
        )

    if m == "client":
        for key, default in REFERENCE_FALLBACK_INPUTS.items():
            if key in merged or key == "mat_info":
                continue
            merged[key] = copy.deepcopy(
                st.session_state.get(key, default)
            )
    return merged


# ── Streamlit session (UI layer only) ────────────────────────


def init_ui_mode_state() -> None:
    import streamlit as st

    if SESSION_KEY not in st.session_state:
        _legacy = st.session_state.get("mmf_ui_profile")
        if _legacy:
            st.session_state[SESSION_KEY] = (
                "client" if str(_legacy).lower().startswith("client") else "engineer"
            )
        else:
            st.session_state[SESSION_KEY] = DEFAULT_MODE
    st.session_state.pop("mmf_ui_profile", None)


def current_ui_mode() -> str:
    import streamlit as st

    init_ui_mode_state()
    return normalize_mode(st.session_state.get(SESSION_KEY))


def render_ui_mode_selector() -> str:
    """Top-of-sidebar mode radio. Returns normalized mode name."""
    import streamlit as st

    init_ui_mode_state()
    mode = current_ui_mode()
    labels = [MODE_LABELS[m] for m in UI_MODES]
    idx = UI_MODES.index(mode) if mode in UI_MODES else 1
    picked = st.radio(
        "View mode",
        labels,
        index=idx,
        horizontal=True,
        key="_ui_mode_radio_display",
        help=(
            "**Client** — key inputs for review meetings.\n\n"
            "**Engineer** — full design workflow.\n\n"
            "**Expert** — calibration knobs + validation tooling."
        ),
    )
    resolved = UI_MODES[labels.index(picked)]
    st.session_state[SESSION_KEY] = resolved
    cfg = get_mode_config(resolved)
    st.caption(cfg["description"])
    if cfg["read_only_hint"]:
        st.info(
            "📋 **Client view** — limited inputs shown. "
            "Switch to **Engineer** or **Expert** to edit all parameters."
        )
    return resolved


def show_engineer_tools(mode: str | None = None) -> bool:
    """Engineer + Expert: Compare, collector studies, project library."""
    return normalize_mode(mode or current_ui_mode()) in ("engineer", "expert")


def show_tier_c_tools(mode: str | None = None) -> bool:
    """Expert only: Monte Carlo, digital twin, design optim, etc."""
    return normalize_mode(mode or current_ui_mode()) == "expert"
