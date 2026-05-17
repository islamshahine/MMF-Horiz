"""BW distribution panels — legacy entry points (delegate to collector_design_panel)."""
from __future__ import annotations

from ui.collector_design_panel import render_collector_design_panel as _render_collector_full


def render_bw_feed_collector_panel(computed: dict, inputs: dict) -> None:
    """Section 6 — vessel BW nozzles, internal header/plenum (legacy wrapper)."""
    _render_collector_full(computed, inputs)


def render_underdrain_panel(computed: dict, inputs: dict) -> None:
    """Section 7 — underdrain (included in ``render_collector_design_panel``)."""
    return


def render_collector_design_panel(computed: dict, inputs: dict) -> None:
    """Legacy wrapper — both sections."""
    _render_collector_full(computed, inputs)
