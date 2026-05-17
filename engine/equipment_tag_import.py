"""Equipment tag registry import (Tier C3 lite) — structured CSV, not P&ID OCR."""
from __future__ import annotations

import csv
import io
import re
from typing import Any

_TAG_ALIASES = frozenset({"tag", "equipment_tag", "tag_id", "name"})
_TYPE_ALIASES = frozenset({"equipment_type", "type", "class", "category"})
_SERVICE_ALIASES = frozenset({"service", "system", "area"})
_PARAM_ALIASES = frozenset({"parameter", "param", "attribute", "property"})
_VALUE_ALIASES = frozenset({"design_value", "value", "design", "rated_value"})
_UNIT_ALIASES = frozenset({"unit", "uom", "units"})
_NOTES_ALIASES = frozenset({"notes", "comment", "remarks"})

_TOLERANCE_PCT = 10.0


def _norm_header(name: str) -> str:
    return re.sub(r"[^\w]+", "_", (name or "").strip().lower()).strip("_")


def _pick_col(norm_map: dict[str, str], aliases: frozenset[str]) -> str | None:
    for a in aliases:
        if a in norm_map:
            return norm_map[a]
    return None


def parse_equipment_tag_csv(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse P&ID export or manual tag list CSV. Returns (rows, warnings)."""
    warnings: list[str] = []
    if not (text or "").strip():
        return [], ["empty file"]

    reader = csv.DictReader(io.StringIO(text.strip()))
    if not reader.fieldnames:
        return [], ["no header row"]

    norm_map = {_norm_header(h): h for h in reader.fieldnames if h}
    tag_col = _pick_col(norm_map, _TAG_ALIASES)
    if not tag_col:
        return [], ["CSV must include a tag column (tag, equipment_tag, or name)"]

    type_col = _pick_col(norm_map, _TYPE_ALIASES)
    svc_col = _pick_col(norm_map, _SERVICE_ALIASES)
    param_col = _pick_col(norm_map, _PARAM_ALIASES)
    val_col = _pick_col(norm_map, _VALUE_ALIASES)
    unit_col = _pick_col(norm_map, _UNIT_ALIASES)
    notes_col = _pick_col(norm_map, _NOTES_ALIASES)

    rows: list[dict[str, Any]] = []
    for i, raw in enumerate(reader):
        tag = (raw.get(tag_col) or "").strip()
        if not tag:
            warnings.append(f"row {i + 2}: missing tag — skipped")
            continue
        rec: dict[str, Any] = {"tag": tag}
        if type_col and raw.get(type_col):
            rec["equipment_type"] = str(raw[type_col]).strip()
        if svc_col and raw.get(svc_col):
            rec["service"] = str(raw[svc_col]).strip()
        if param_col and raw.get(param_col):
            rec["parameter"] = str(raw[param_col]).strip().lower()
        if val_col and raw.get(val_col) not in (None, ""):
            try:
                rec["design_value"] = float(raw[val_col])
            except (TypeError, ValueError):
                warnings.append(f"row {i + 2}: invalid design_value")
        if unit_col and raw.get(unit_col):
            rec["unit"] = str(raw[unit_col]).strip()
        if notes_col and raw.get(notes_col):
            rec["notes"] = str(raw[notes_col]).strip()
        rows.append(rec)

    if not rows:
        return [], warnings or ["no data rows parsed"]
    return rows, warnings


def _model_reference_values(inputs: dict, computed: dict) -> dict[str, tuple[float, str]]:
    """Map normalized keys to (model_value_si, unit_label)."""
    refs: dict[str, tuple[float, str]] = {}
    streams = max(1, int(inputs.get("streams", 1) or 1))
    n_f = max(1, int(inputs.get("n_filters", 1) or 1))
    refs["n_filters_total"] = (float(streams * n_f), "count")

    bw = computed.get("bw_hyd") or {}
    if bw.get("q_bw_design_m3h") is not None:
        refs["q_bw_m3h"] = (float(bw["q_bw_design_m3h"]), "m3/h")

    hyd = computed.get("hyd_prof") or {}
    if hyd.get("q_total_m3h") is not None:
        refs["q_feed_m3h"] = (float(hyd["q_total_m3h"]), "m3/h")

    pp = computed.get("pump_perf") or {}
    feed = pp.get("feed") or {}
    if feed.get("q_design_m3h") is not None:
        refs["q_feed_m3h"] = (float(feed["q_design_m3h"]), "m3/h")
    bw_p = pp.get("backwash") or pp.get("bw") or {}
    if bw_p.get("q_design_m3h") is not None:
        refs["q_bw_m3h"] = (float(bw_p["q_design_m3h"]), "m3/h")

    if bw.get("q_air_m3h") is not None:
        refs["q_air_m3h"] = (float(bw["q_air_m3h"]), "m3/h")

    return refs


def _infer_parameter_key(row: dict[str, Any]) -> str | None:
    if row.get("parameter"):
        return str(row["parameter"]).lower().replace(" ", "_")
    et = str(row.get("equipment_type") or "").lower()
    if "filter" in et or "mmf" in et:
        if row.get("design_value") is not None and float(row["design_value"]) < 100:
            return "n_filters_total"
    if "feed" in et and "pump" in et:
        return "q_feed_m3h"
    if "backwash" in et or "bw" in et:
        if "pump" in et:
            return "q_bw_m3h"
        if "blower" in et or "air" in et:
            return "q_air_m3h"
    return None


def _match_row(row: dict[str, Any], refs: dict[str, tuple[float, str]]) -> dict[str, Any]:
    key = _infer_parameter_key(row)
    out: dict[str, Any] = {
        "tag": row.get("tag"),
        "equipment_type": row.get("equipment_type"),
        "service": row.get("service"),
        "parameter_key": key,
        "design_value": row.get("design_value"),
        "unit": row.get("unit"),
        "notes": row.get("notes"),
        "status": "unmatched",
    }
    if not key or key not in refs:
        return out

    model_val, model_unit = refs[key]
    out["model_value"] = model_val
    out["model_unit"] = model_unit
    dv = row.get("design_value")
    if dv is None:
        out["status"] = "model_only"
        return out

    tol = _TOLERANCE_PCT / 100.0
    denom = max(abs(model_val), 1e-9)
    delta_pct = abs(float(dv) - model_val) / denom * 100.0
    out["delta_pct"] = round(delta_pct, 2)
    if delta_pct <= _TOLERANCE_PCT:
        out["status"] = "match"
    else:
        out["status"] = "mismatch"
    return out


def build_equipment_tag_registry(
    csv_text: str,
    inputs: dict,
    computed: dict,
) -> dict[str, Any]:
    """Compare tag CSV to current model references."""
    rows, warnings = parse_equipment_tag_csv(csv_text)
    if not rows and warnings:
        return {
            "enabled": False,
            "reason": warnings[0],
            "parse_warnings": warnings,
        }

    refs = _model_reference_values(inputs, computed)
    matched = [_match_row(r, refs) for r in rows]
    n_match = sum(1 for m in matched if m.get("status") == "match")
    n_mis = sum(1 for m in matched if m.get("status") == "mismatch")
    n_un = sum(1 for m in matched if m.get("status") == "unmatched")

    return {
        "enabled": True,
        "disclaimer": (
            "Structured tag CSV only — not P&ID OCR. "
            "Cross-check is advisory; verify on issued drawings."
        ),
        "n_tags": len(rows),
        "n_match": n_match,
        "n_mismatch": n_mis,
        "n_unmatched": n_un,
        "tags": matched,
        "model_references": {k: {"value": v[0], "unit": v[1]} for k, v in refs.items()},
        "parse_warnings": warnings,
        "summary": (
            f"{len(rows)} tag(s): {n_match} within {_TOLERANCE_PCT:.0f}% tolerance, "
            f"{n_mis} mismatch, {n_un} unmatched."
        ),
    }
