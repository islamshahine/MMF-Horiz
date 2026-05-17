"""Backward-compatible aliases — prefer ``ui.ui_mode`` for new code."""
from __future__ import annotations

from ui.ui_mode import (
    current_ui_mode,
    merge_hidden_input_defaults,
    render_ui_mode_selector,
    show_engineer_tools,
    show_tier_c_tools,
    visible_main_tab_labels,
    init_ui_mode_state,
)

PROFILE_ENGINEER = "Engineer"
PROFILE_CLIENT = "Client"


def init_ui_profile_state() -> None:
    init_ui_mode_state()


def ui_profile() -> str:
    m = current_ui_mode()
    return PROFILE_CLIENT if m == "client" else PROFILE_ENGINEER


def is_engineer_mode() -> bool:
    """Not client — Engineer or Expert (sidebar tools, Compare tab)."""
    return show_engineer_tools()


def is_client_mode() -> bool:
    return current_ui_mode() == "client"


def is_expert_mode() -> bool:
    return show_tier_c_tools()


def render_ui_profile_selector() -> None:
    render_ui_mode_selector()


def merge_client_sidebar_defaults(out: dict) -> dict:
    return merge_hidden_input_defaults(out, current_ui_mode())
