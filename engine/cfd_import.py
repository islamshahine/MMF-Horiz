"""Import external CFD orifice results and compare to 1D screening model (Tier C2 lite)."""
from __future__ import annotations

import csv
import io
import re
from typing import Any

_VELOCITY_S_ALIASES = frozenset({
    "velocity_m_s", "v_m_s", "velocity_ms", "velocity", "v",
})
_VELOCITY_H_ALIASES = frozenset({
    "velocity_m_h", "v_m_h", "velocity_mh",
})
_FLOW_ALIASES = frozenset({"flow_m3h", "q_m3h", "flow", "q"})
_LAT_ALIASES = frozenset({"lateral_index", "lateral", "l", "lat"})
_HOLE_ALIASES = frozenset({"hole_index", "hole", "h", "orifice"})


def _norm_header(name: str) -> str:
    return re.sub(r"[^\w]+", "_", (name or "").strip().lower()).strip("_")


def _pick_col(norm_map: dict[str, str], aliases: frozenset[str]) -> str | None:
    for a in aliases:
        if a in norm_map:
            return norm_map[a]
    return None


def parse_cfd_results_csv(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse consultant CFD export CSV. Returns (rows, warnings)."""
    warnings: list[str] = []
    if not (text or "").strip():
        return [], ["empty file"]

    reader = csv.DictReader(io.StringIO(text.strip()))
    if not reader.fieldnames:
        return [], ["no header row"]

    norm_map = {_norm_header(h): h for h in reader.fieldnames if h}
    lat_col = _pick_col(norm_map, _LAT_ALIASES)
    hole_col = _pick_col(norm_map, _HOLE_ALIASES)
    if not lat_col or not hole_col:
        return [], ["CSV must include lateral_index and hole_index columns"]

    v_s_col = _pick_col(norm_map, _VELOCITY_S_ALIASES)
    v_h_col = _pick_col(norm_map, _VELOCITY_H_ALIASES)
    flow_col = _pick_col(norm_map, _FLOW_ALIASES)
    if not v_s_col and not v_h_col and not flow_col:
        return [], ["CSV must include velocity_m_s, velocity_m_h, or flow_m3h"]

    rows: list[dict[str, Any]] = []
    for i, raw in enumerate(reader):
        try:
            lat = int(float(raw.get(lat_col, "") or 0))
            hole = int(float(raw.get(hole_col, "") or 0))
        except (TypeError, ValueError):
            warnings.append(f"row {i + 2}: invalid lateral/hole index")
            continue
        rec: dict[str, Any] = {"lateral_index": lat, "hole_index": hole}
        if v_s_col and raw.get(v_s_col) not in (None, ""):
            rec["velocity_m_s"] = float(raw[v_s_col])
        if v_h_col and raw.get(v_h_col) not in (None, ""):
            rec["velocity_m_h"] = float(raw[v_h_col])
        if flow_col and raw.get(flow_col) not in (None, ""):
            rec["flow_m3h"] = float(raw[flow_col])
        if "velocity_m_s" not in rec and "velocity_m_h" in rec:
            rec["velocity_m_s"] = float(rec["velocity_m_h"]) / 3600.0
        rows.append(rec)

    if not rows:
        return [], warnings or ["no data rows parsed"]
    return rows, warnings


def _model_key(row: dict) -> tuple[int, int]:
    return (int(row.get("lateral_index", 0)), int(row.get("hole_index", 0)))


def compare_cfd_to_orifice_network(
    cfd_rows: list[dict[str, Any]],
    model_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Match CFD rows to ``collector_hyd`` orifice_network by lateral/hole index."""
    if not model_rows:
        return {"enabled": False, "reason": "no_model_orifice_network"}
    if not cfd_rows:
        return {"enabled": False, "reason": "no_cfd_rows"}

    model_by_key = {_model_key(r): r for r in model_rows}
    cfd_by_key = {_model_key(r): r for r in cfd_rows}

    compare_rows: list[dict[str, Any]] = []
    deltas_v: list[float] = []
    deltas_q: list[float] = []

    for key, mrow in model_by_key.items():
        crow = cfd_by_key.get(key)
        if crow is None:
            continue
        v_m = float(mrow.get("velocity_m_s") or 0.0)
        v_c = float(crow.get("velocity_m_s") or 0.0)
        q_m = float(mrow.get("flow_m3h") or 0.0)
        q_c = float(crow.get("flow_m3h") or 0.0)
        dv_pct = None
        dq_pct = None
        if v_m > 1e-9 and v_c > 0:
            dv_pct = (v_c - v_m) / v_m * 100.0
            deltas_v.append(abs(dv_pct))
        if q_m > 1e-9 and q_c > 0:
            dq_pct = (q_c - q_m) / q_m * 100.0
            deltas_q.append(abs(dq_pct))
        compare_rows.append({
            "lateral_index": key[0],
            "hole_index": key[1],
            "model_velocity_m_s": round(v_m, 5),
            "cfd_velocity_m_s": round(v_c, 5),
            "delta_velocity_pct": round(dv_pct, 2) if dv_pct is not None else None,
            "model_flow_m3h": round(q_m, 4),
            "cfd_flow_m3h": round(q_c, 4),
            "delta_flow_pct": round(dq_pct, 2) if dq_pct is not None else None,
        })

    n_model = len(model_by_key)
    n_cfd = len(cfd_by_key)
    n_matched = len(compare_rows)

    return {
        "enabled": n_matched > 0,
        "n_model_holes": n_model,
        "n_cfd_holes": n_cfd,
        "n_matched": n_matched,
        "n_unmatched_cfd": max(0, n_cfd - n_matched),
        "mean_abs_delta_velocity_pct": round(sum(deltas_v) / len(deltas_v), 2) if deltas_v else None,
        "max_abs_delta_velocity_pct": round(max(deltas_v), 2) if deltas_v else None,
        "mean_abs_delta_flow_pct": round(sum(deltas_q) / len(deltas_q), 2) if deltas_q else None,
        "max_abs_delta_flow_pct": round(max(deltas_q), 2) if deltas_q else None,
        "rows": compare_rows,
        "summary": (
            f"Matched {n_matched} of {n_model} model holes to CFD export "
            f"({n_cfd} CFD rows)."
        ),
        "method": "index_join_lateral_hole",
        "disclaimer": (
            "External CFD results — not validated by AQUASIGHT. "
            "1D screening remains advisory."
        ),
    }


def build_cfd_import_comparison(
    csv_text: str,
    computed: dict[str, Any],
) -> dict[str, Any]:
    """Parse CSV and compare to in-app orifice network."""
    cfd_rows, warnings = parse_cfd_results_csv(csv_text)
    ch = computed.get("collector_hyd") or {}
    model_rows = list(ch.get("orifice_network") or [])
    out = compare_cfd_to_orifice_network(cfd_rows, model_rows)
    out["parse_warnings"] = warnings
    if warnings and not out.get("enabled"):
        out["reason"] = warnings[0]
    return out
