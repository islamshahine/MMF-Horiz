"""Digital twin lite — recalibrate screening factors from plant telemetry CSV (Tier C4)."""
from __future__ import annotations

import csv
import io
import re
import statistics
from typing import Any

_CYCLE_ALIASES = frozenset({
    "cycle_hours_h", "cycle_h", "run_time_h", "filtration_cycle_h", "cycle_duration_h",
})
_DP_ALIASES = frozenset({
    "dp_dirty_bar", "dp_bar", "delta_p_bar", "pressure_drop_bar", "dp_total_bar",
})
_LV_ALIASES = frozenset({"lv_m_h", "filtration_velocity_m_h", "velocity_m_h", "lv"})
_TSS_ALIASES = frozenset({"tss_mg_l", "tss", "feed_tss_mg_l"})


def _norm_header(name: str) -> str:
    return re.sub(r"[^\w]+", "_", (name or "").strip().lower()).strip("_")


def _pick_col(norm_map: dict[str, str], aliases: frozenset[str]) -> str | None:
    for a in aliases:
        if a in norm_map:
            return norm_map[a]
    return None


def parse_ops_telemetry_csv(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """Parse plant SCADA / log export (one row per filtration cycle or sample)."""
    warnings: list[str] = []
    if not (text or "").strip():
        return [], ["empty file"]

    reader = csv.DictReader(io.StringIO(text.strip()))
    if not reader.fieldnames:
        return [], ["no header row"]

    norm_map = {_norm_header(h): h for h in reader.fieldnames if h}
    cyc_col = _pick_col(norm_map, _CYCLE_ALIASES)
    dp_col = _pick_col(norm_map, _DP_ALIASES)
    lv_col = _pick_col(norm_map, _LV_ALIASES)
    tss_col = _pick_col(norm_map, _TSS_ALIASES)
    if not cyc_col and not dp_col:
        return [], ["CSV needs cycle_hours_h and/or dp_dirty_bar column"]

    rows: list[dict[str, Any]] = []
    for i, raw in enumerate(reader):
        rec: dict[str, Any] = {}
        try:
            if cyc_col and raw.get(cyc_col) not in (None, ""):
                rec["cycle_hours_h"] = float(raw[cyc_col])
            if dp_col and raw.get(dp_col) not in (None, ""):
                rec["dp_dirty_bar"] = float(raw[dp_col])
            if lv_col and raw.get(lv_col) not in (None, ""):
                rec["lv_m_h"] = float(raw[lv_col])
            if tss_col and raw.get(tss_col) not in (None, ""):
                rec["tss_mg_l"] = float(raw[tss_col])
        except (TypeError, ValueError):
            warnings.append(f"row {i + 2}: invalid number")
            continue
        if rec:
            rows.append(rec)

    if not rows:
        return [], warnings or ["no data rows"]
    return rows, warnings


def _median(vals: list[float]) -> float | None:
    finite = [v for v in vals if v == v and v > 0]
    if not finite:
        return None
    return float(statistics.median(finite))


def _mean(vals: list[float]) -> float | None:
    finite = [v for v in vals if v == v and v > 0]
    if not finite:
        return None
    return float(statistics.mean(finite))


def build_digital_twin_lite(
    csv_text: str,
    inputs: dict[str, Any],
    computed: dict[str, Any],
) -> dict[str, Any]:
    """
    Suggest ``alpha_calibration_factor`` (and optionally ``tss_avg``) from plant data.

    Cycle-time scaling: longer observed cycles → lower effective cake resistance factor.
    """
    rows, warnings = parse_ops_telemetry_csv(csv_text)
    if not rows:
        return {"enabled": False, "parse_warnings": warnings, "reason": warnings[0] if warnings else "no data"}

    cycles = [r["cycle_hours_h"] for r in rows if "cycle_hours_h" in r]
    dps = [r["dp_dirty_bar"] for r in rows if "dp_dirty_bar" in r]
    lvs = [r["lv_m_h"] for r in rows if "lv_m_h" in r]
    tsss = [r["tss_mg_l"] for r in rows if "tss_mg_l" in r]

    obs_cycle = _median(cycles)
    obs_dp = _mean(dps)
    obs_lv = _mean(lvs)
    obs_tss = _median(tsss)

    cu_n = (computed.get("cycle_uncertainty") or {}).get("N") or {}
    model_cycle = float(cu_n.get("cycle_expected_h") or 0.0)
    if model_cycle <= 0:
        fc = (computed.get("filt_cycles") or {}).get("N") or {}
        for tr in fc.get("tss_results") or []:
            if abs(float(tr.get("TSS (mg/L)", 0)) - float(inputs.get("tss_avg", 0))) < 1e-3:
                model_cycle = float(tr.get("Cycle duration (h)", 0) or 0)
                break

    model_dp = float((computed.get("bw_dp") or {}).get("dp_dirty_bar") or 0.0)
    acf = max(0.05, min(3.0, float(computed.get("alpha_calibration_factor", 1.0) or 1.0)))
    design_tss = max(0.1, float(inputs.get("tss_avg") or 10.0))

    suggested: dict[str, float] = {}
    rationale: list[str] = []
    method = []

    if obs_cycle and model_cycle > 0.1:
        scale = model_cycle / obs_cycle
        new_acf = max(0.3, min(3.0, acf * scale))
        suggested["alpha_calibration_factor"] = round(new_acf, 3)
        method.append("cycle_time_ratio")
        rationale.append(
            f"Median plant cycle **{obs_cycle:.1f} h** vs model expected **{model_cycle:.1f} h** "
            f"→ α calibration **{acf:.2f}** → **{new_acf:.2f}**."
        )
    elif obs_dp and model_dp > 0.01:
        scale = obs_dp / model_dp
        new_acf = max(0.3, min(3.0, acf * scale))
        suggested["alpha_calibration_factor"] = round(new_acf, 3)
        method.append("dp_dirty_ratio")
        rationale.append(
            f"Mean plant ΔP dirty **{obs_dp:.3f} bar** vs model **{model_dp:.3f} bar** "
            f"→ α calibration **{acf:.2f}** → **{new_acf:.2f}**."
        )

    if obs_tss and abs(obs_tss - design_tss) / design_tss > 0.12:
        suggested["tss_avg"] = round(obs_tss, 2)
        rationale.append(
            f"Median plant TSS **{obs_tss:.1f} mg/L** differs from design **{design_tss:.1f}** — "
            "optional TSS patch."
        )

    n = len(rows)
    confidence = "high" if n >= 20 else ("medium" if n >= 8 else "low")

    return {
        "enabled": bool(suggested),
        "method": method,
        "n_samples": n,
        "confidence": confidence,
        "observed": {
            "cycle_hours_median": round(obs_cycle, 2) if obs_cycle else None,
            "dp_dirty_bar_mean": round(obs_dp, 4) if obs_dp else None,
            "lv_m_h_mean": round(obs_lv, 2) if obs_lv else None,
            "tss_mg_l_median": round(obs_tss, 2) if obs_tss else None,
        },
        "model": {
            "cycle_expected_h": round(model_cycle, 2) if model_cycle else None,
            "dp_dirty_bar": round(model_dp, 4) if model_dp else None,
            "alpha_calibration_factor": acf,
            "tss_avg_mg_l": design_tss,
        },
        "suggested_patches": suggested,
        "rationale": rationale,
        "parse_warnings": warnings,
        "summary": (
            f"Recalibration from {n} plant row(s) ({confidence} confidence)."
            if suggested
            else "Insufficient overlap between plant CSV and model metrics."
        ),
        "disclaimer": (
            "Advisory regression only — not online digital twin control. "
            "Validate with lab / pilot before design sign-off."
        ),
    }
