"""Shared Monte Carlo lite sidebar / Filtration controls (C1)."""
from __future__ import annotations

import streamlit as st


def render_monte_carlo_lite_controls() -> None:
    """Checkbox + sample count + seed (session_state keys used by app.py)."""
    st.session_state.setdefault("mc_lite_enabled", False)
    st.session_state.setdefault("mc_lite_n_samples", 200)
    st.session_state.setdefault("mc_lite_seed", 42)

    st.caption(
        "Uniform random samples on α, TSS, capture, and maldistribution (same spans as the "
        "deterministic envelope). Press **Apply** in the input column after enabling."
    )

    st.checkbox(
        "Enable Monte Carlo cycle sampling",
        key="mc_lite_enabled",
    )
    if st.session_state.mc_lite_enabled:
        c1, c2 = st.columns(2)
        with c1:
            st.slider(
                "Samples",
                min_value=50,
                max_value=500,
                step=50,
                key="mc_lite_n_samples",
            )
        with c2:
            st.number_input(
                "Random seed",
                min_value=0,
                max_value=999_999,
                step=1,
                key="mc_lite_seed",
            )
