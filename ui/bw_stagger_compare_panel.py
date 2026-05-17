"""Compare multiple BW stagger models — build once, switch instantly."""
from __future__ import annotations

import streamlit as st

from engine.bw_stagger_compare import COMPARE_STAGGER_DEFAULTS
from ui.bw_timeline_cache import (
    build_stagger_comparison_cached,
    merge_bw_duty_applied,
    minimal_computed_stub,
)
_STAGGER_LABELS = {
    "feasibility_trains": "Feasibility BW trains",
    "optimized_trains": "Optimized trains (peak)",
    "tariff_aware_v3": "Tariff-aware v3",
    "milp_lite": "MILP lite",
    "uniform": "Uniform (legacy)",
}


def render_bw_stagger_compare_panel(inputs: dict, computed: dict) -> dict | None:
    """
  Render compare UI inside duty timeline expander.
  Returns the timeline dict to display (from cache view or None to use default).
    """
    with st.expander("Compare stagger models (build cache)", expanded=False):
        st.caption(
            "Pre-build **2–5** stagger schedules with the **same** horizon and tariff settings. "
            "After the one-time build, switch models **instantly** without re-running the optimizers."
        )
        _all_opts = list(_STAGGER_LABELS.keys())
        _default = [m for m in COMPARE_STAGGER_DEFAULTS if m in _all_opts]
        _pick = st.multiselect(
            "Models to compare",
            options=_all_opts,
            default=_default,
            format_func=lambda x: _STAGGER_LABELS.get(x, x),
            key="bw_stagger_compare_pick",
        )
        _c1, _c2 = st.columns(2)
        _build = _c1.button("Build comparison cache", type="primary", key="bw_stagger_compare_build")
        _clear = _c2.button("Clear cache", key="bw_stagger_compare_clear")

        if _clear:
            st.session_state.pop("bw_stagger_compare_cache", None)
            st.session_state.pop("bw_stagger_compare_view", None)
            st.rerun()

        _merged = merge_bw_duty_applied(inputs)
        if _build and _pick:
            from engine.bw_stagger_compare import compare_fingerprint

            _fp = compare_fingerprint(_merged, computed, tuple(_pick))
            with st.spinner(f"Building {len(_pick)} stagger model(s)…"):
                _cache = build_stagger_comparison_cached(
                    _fp,
                    _merged,
                    minimal_computed_stub(computed),
                    tuple(_pick),
                )
            st.session_state["bw_stagger_compare_cache"] = _cache
            st.session_state["bw_stagger_compare_view"] = _pick[0]
            if _cache.get("errors"):
                for _m, _err in _cache["errors"].items():
                    st.warning(f"{_STAGGER_LABELS.get(_m, _m)}: {_err}")
            st.success(
                f"Cached {len(_cache.get('timelines') or {})} model(s) · "
                f"fingerprint `{_cache.get('fingerprint', '—')}`"
            )

        _cache = st.session_state.get("bw_stagger_compare_cache") or {}
        _timelines = _cache.get("timelines") or {}
        if not _timelines:
            return None

        _rows = _cache.get("summary") or []
        if _rows:
            import pandas as pd

            _df = pd.DataFrame(_rows)
            _df["label"] = _df["stagger_model"].map(
                lambda s: _STAGGER_LABELS.get(str(s), str(s))
            )
            st.dataframe(
                _df[
                    [
                        "label",
                        "peak_concurrent_bw",
                        "meets_bw_trains_cap",
                        "hours_at_n",
                        "hours_at_n_minus_1",
                        "peak_tariff_filter_h",
                        "method",
                    ]
                ].rename(columns={
                    "label": "Model",
                    "peak_concurrent_bw": "Peak concurrent",
                    "meets_bw_trains_cap": "Meets train cap",
                    "hours_at_n": "h @ N",
                    "hours_at_n_minus_1": "h @ N−1",
                    "peak_tariff_filter_h": "Peak-tariff filter·h",
                    "method": "Solver",
                }),
                use_container_width=True,
                hide_index=True,
            )

        _keys = list(_timelines.keys())
        _view = st.radio(
            "View cached model (instant)",
            options=_keys,
            format_func=lambda x: _STAGGER_LABELS.get(x, x),
            horizontal=True,
            key="bw_stagger_compare_view",
            index=_keys.index(st.session_state.get("bw_stagger_compare_view", _keys[0]))
            if st.session_state.get("bw_stagger_compare_view") in _keys
            else 0,
        )
        st.session_state["bw_stagger_compare_view"] = _view
        return _timelines.get(_view)

    return None
