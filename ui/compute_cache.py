"""Streamlit cache for ``compute_all`` — avoids re-running the full model on every widget rerun."""

from __future__ import annotations

import copy

import streamlit as st


@st.cache_data(show_spinner=False, max_entries=48)
def compute_all_cached(inputs: dict) -> dict:
    """Return ``compute_all(inputs)``; identical inputs hit the LRU cache.

    Inputs are deep-copied so the engine cannot mutate the caller's dict.
    """
    from engine.compute import compute_all

    return compute_all(copy.deepcopy(inputs))
