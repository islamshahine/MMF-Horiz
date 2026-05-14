"""Per-layer filtration LV and EBCT threshold helpers (SI).

Layers may include ``lv_threshold_m_h`` (max allowable superficial velocity)
and ``ebct_threshold_min`` (minimum acceptable empty-bed contact time, minutes).
Support layers use ``None`` for both — envelope checks skip them.

Legacy inputs may omit per-layer keys; fall back to top-level
``velocity_threshold`` / ``ebct_threshold`` then to module defaults.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

_DEFAULT_LV_CAP = 12.0
_DEFAULT_EBCT_MIN = 5.0


def layer_lv_cap_m_h(
    layer: Mapping[str, Any],
    *,
    inputs_fallback: Optional[Mapping[str, Any]] = None,
) -> float:
    """Maximum LV (m/h) for severity / envelope checks for this layer."""
    v = layer.get("lv_threshold_m_h")
    if v is not None:
        try:
            fv = float(v)
            if fv > 0.0:
                return fv
        except (TypeError, ValueError):
            pass
    if inputs_fallback:
        try:
            fb = float(inputs_fallback.get("velocity_threshold", _DEFAULT_LV_CAP))
            if fb > 0.0:
                return fb
        except (TypeError, ValueError):
            pass
    return _DEFAULT_LV_CAP


def layer_ebct_floor_min(
    layer: Mapping[str, Any],
    *,
    inputs_fallback: Optional[Mapping[str, Any]] = None,
) -> float:
    """Minimum EBCT (minutes) for severity / envelope checks for this layer."""
    v = layer.get("ebct_threshold_min")
    if v is not None:
        try:
            fv = float(v)
            if fv > 0.0:
                return fv
        except (TypeError, ValueError):
            pass
    if inputs_fallback:
        try:
            fb = float(inputs_fallback.get("ebct_threshold", _DEFAULT_EBCT_MIN))
            if fb > 0.0:
                return fb
        except (TypeError, ValueError):
            pass
    return _DEFAULT_EBCT_MIN


def ensure_layer_threshold_defaults(inputs: dict) -> None:
    """
    Mutate ``inputs["layers"]`` in place: fill missing per-layer thresholds from
    legacy globals, then set globals from non-support layers for API back-compat.
    """
    layers = inputs.get("layers")
    if not isinstance(layers, list) or not layers:
        inputs.setdefault("velocity_threshold", _DEFAULT_LV_CAP)
        inputs.setdefault("ebct_threshold", _DEFAULT_EBCT_MIN)
        return

    v_g = float(inputs.get("velocity_threshold", _DEFAULT_LV_CAP) or _DEFAULT_LV_CAP)
    e_g = float(inputs.get("ebct_threshold", _DEFAULT_EBCT_MIN) or _DEFAULT_EBCT_MIN)

    for L in layers:
        if not isinstance(L, dict):
            continue
        if L.get("is_support"):
            if "lv_threshold_m_h" not in L:
                L["lv_threshold_m_h"] = None
            if "ebct_threshold_min" not in L:
                L["ebct_threshold_min"] = None
            continue
        if L.get("lv_threshold_m_h") is None:
            L["lv_threshold_m_h"] = v_g
        if L.get("ebct_threshold_min") is None:
            L["ebct_threshold_min"] = e_g

    ns = [L for L in layers if isinstance(L, dict) and not L.get("is_support")]
    lvs = []
    ebs = []
    for L in ns:
        try:
            x = L.get("lv_threshold_m_h")
            if x is not None:
                lvs.append(float(x))
        except (TypeError, ValueError):
            pass
        try:
            y = L.get("ebct_threshold_min")
            if y is not None:
                ebs.append(float(y))
        except (TypeError, ValueError):
            pass

    if lvs:
        inputs["velocity_threshold"] = max(lvs)
    else:
        inputs.setdefault("velocity_threshold", v_g)
    if ebs:
        inputs["ebct_threshold"] = min(ebs)
    else:
        inputs.setdefault("ebct_threshold", e_g)
