"""Client vs engineer UI — hide calibration / Tier-C tooling for demos."""
from __future__ import annotations

import streamlit as st

PROFILE_ENGINEER = "Engineer"
PROFILE_CLIENT = "Client"
_PROFILE_KEY = "mmf_ui_profile"

# Keys still sent to compute when widgets are hidden in Client mode.
_CLIENT_SIDEBAR_DEFAULTS: dict[str, object] = {
    "solid_loading_scale": 1.0,
    "alpha_calibration_factor": 1.0,
    "tss_capture_efficiency": 1.0,
    "expansion_calibration_scale": 1.0,
    "maldistribution_factor": 1.0,
    "use_calculated_maldistribution": False,
}

_CLIENT_HIDDEN_MAIN_TABS: frozenset[str] = frozenset({
    "⚖️ Compare",
})


def init_ui_profile_state() -> None:
    st.session_state.setdefault(_PROFILE_KEY, PROFILE_ENGINEER)


def ui_profile() -> str:
    init_ui_profile_state()
    p = str(st.session_state.get(_PROFILE_KEY, PROFILE_ENGINEER))
    return p if p in (PROFILE_ENGINEER, PROFILE_CLIENT) else PROFILE_ENGINEER


def is_engineer_mode() -> bool:
    return ui_profile() == PROFILE_ENGINEER


def is_client_mode() -> bool:
    return not is_engineer_mode()


def render_ui_profile_selector() -> None:
    init_ui_profile_state()
    _idx = 0 if ui_profile() == PROFILE_ENGINEER else 1
    st.radio(
        "UI mode",
        options=(PROFILE_ENGINEER, PROFILE_CLIENT),
        index=_idx,
        horizontal=True,
        key=_PROFILE_KEY,
        help=(
            "**Engineer** — calibration factors, Monte Carlo, collector studies, "
            "design optimisation, digital twin / tag import. "
            "**Client** — core sizing inputs and standard results tabs only."
        ),
    )
    if is_client_mode():
        st.caption(
            "Client mode: hidden inputs use standard defaults (α factor = 1, no Monte Carlo)."
        )


def visible_main_tab_labels(all_labels: tuple[str, ...]) -> tuple[str, ...]:
    if is_engineer_mode():
        return all_labels
    return tuple(lbl for lbl in all_labels if lbl not in _CLIENT_HIDDEN_MAIN_TABS)


def merge_client_sidebar_defaults(out: dict) -> dict:
    """Ensure hidden calibration keys still reach ``convert_inputs`` / compute."""
    if is_engineer_mode():
        return out
    merged = dict(out)
    for key, default in _CLIENT_SIDEBAR_DEFAULTS.items():
        if key not in merged:
            merged[key] = st.session_state.get(key, default)
    if "captured_solids_density" not in merged:
        merged["captured_solids_density"] = float(
            st.session_state.get("captured_solids_density", 1020.0) or 1020.0
        )
    if "alpha_specific" not in merged:
        _a9 = float(st.session_state.get("alpha_res", 0.0) or 0.0)
        merged["alpha_specific"] = _a9 * 1e9
    return merged
