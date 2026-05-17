"""Fast duty Gantt — matplotlib (static), not hundreds of Plotly traces."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import streamlit as st

_COLORS = {"operate": "#27ae60", "bw": "#c0392b"}


def timeline_figure_cache_key(bw_timeline: dict) -> str:
    payload: list[Any] = [
        bw_timeline.get("stagger_model"),
        round(float(bw_timeline.get("horizon_h", 24) or 24), 2),
        int(bw_timeline.get("horizon_days") or 1),
    ]
    for f in bw_timeline.get("filters") or []:
        for s in f.get("segments") or []:
            payload.append(
                (
                    int(f.get("filter_index", 0)),
                    str(s.get("state")),
                    round(float(s.get("t0", 0)), 2),
                    round(float(s.get("t1", 0)), 2),
                )
            )
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


@st.cache_data(show_spinner=False, max_entries=24)
def build_bw_timeline_gantt_figure(cache_key: str, bw_timeline: dict) -> Any:
    del cache_key
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    frows = bw_timeline.get("filters") or []
    if not frows:
        return None

    hdays = int(
        bw_timeline.get("horizon_days")
        or max(1, round(float(bw_timeline.get("horizon_h", 24)) / 24))
    )
    hor = float(bw_timeline.get("horizon_h", 24.0))
    n = len(frows)
    fig_h = max(3.6, min(14.0, 0.32 * n + 1.2))
    fig, ax = plt.subplots(figsize=(11.0, fig_h))

    for yi, row in enumerate(frows):
        for s in row.get("segments") or []:
            t0 = float(s.get("t0", 0))
            t1 = float(s.get("t1", 0))
            if t1 - t0 <= 1e-9:
                continue
            stt = str(s.get("state", "operate"))
            ax.barh(
                yi,
                t1 - t0,
                left=t0,
                height=0.72,
                color=_COLORS.get(stt, "#7f8c8d"),
                align="center",
                edgecolor="none",
            )

    ax.set_yticks(range(n))
    ax.set_yticklabels([f"Filter {int(r.get('filter_index', i + 1))}" for i, r in enumerate(frows)])
    ax.set_xlim(0.0, hor)
    ax.set_xlabel("Time (h)")
    ax.set_title(f"Filter duty — {hdays} d horizon")
    ax.legend(
        handles=[
            Patch(facecolor=_COLORS["operate"], label="Operate / online"),
            Patch(facecolor=_COLORS["bw"], label="Backwash"),
        ],
        loc="upper right",
        fontsize=8,
    )
    ax.grid(axis="x", alpha=0.25, linewidth=0.6)
    fig.tight_layout()
    return fig


def render_bw_timeline_gantt(bw_timeline: dict, *, chart_key: str = "bw_timeline_gantt") -> None:
    del chart_key
    if not bw_timeline.get("filters"):
        st.info("No filter rows for timeline (check filter count).")
        return
    ck = timeline_figure_cache_key(bw_timeline)
    fig = build_bw_timeline_gantt_figure(ck, bw_timeline)
    if fig is not None:
        st.pyplot(fig, clear_figure=True, use_container_width=True)
