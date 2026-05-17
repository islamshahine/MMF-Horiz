"""Sidebar input helpers — hidden widgets keep session / SI defaults."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

import streamlit as st

from ui.ui_mode import current_ui_mode, fallback_value, mode_allows

T = TypeVar("T")


def read_hidden_input(
    key: str,
    widget_fn: Callable[[], T],
    *,
    mode: str | None = None,
    session_key: str | None = None,
) -> T:
    """
    Show ``widget_fn`` when ``mode_allows(key)``; otherwise return
    ``st.session_state[session_key or key]`` or ``REFERENCE_FALLBACK`` default.
    """
    m = mode if mode is not None else current_ui_mode()
    sk = session_key or key
    if mode_allows(key, m):
        return widget_fn()
    existing = st.session_state.get(sk)
    if existing is not None:
        return existing
    default = fallback_value(key)
    if default is not None:
        return default
    return widget_fn()


def assign_if_hidden(out: dict[str, Any], key: str, *, mode: str | None = None) -> None:
    """Set ``out[key]`` from session/fallback when the widget is not shown."""
    if key in out:
        return
    m = mode if mode is not None else current_ui_mode()
    if mode_allows(key, m):
        return
    sk = key
    val = st.session_state.get(sk, fallback_value(key))
    if val is not None:
        out[key] = val
