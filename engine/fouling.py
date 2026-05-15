"""Fouling indicators → solids loading, run time, severity, and BW interval (empirical).

This module provides **order-of-magnitude engineering guidance** only. It is not a
substitute for pilot data, membrane autopsy programmes, or site-specific SDI/MFI
protocol QA. All correlations are **monotone blends** of feed indices so trends
are physically plausible; absolute numbers should be calibrated against plant
history before using in design sign-off.

**Assumptions (explicit)**

1. **SDI₁₅** — ASTM D4189 style 15-minute index. Treat values above ~5 as outside
   the intended correlation band; a warning is emitted.
2. **MFI proxy** — ``mfi_index`` is a **dimensionless 0–10+ severity scalar** derived
   from MFI₀.₄₅ (or equivalent) off-line tests, **already normalised** by the
   analyst to this scale (1 ≈ low fouling potential, 5+ ≈ high). Raw s/L² values
   are **not** converted here.
3. **TSS** — Total suspended solids in **mg/L** (isokinetic or representative grab).
4. **Filtration velocity** ``lv_m_h`` — superficial approach velocity through the
   clean media bed (m/h), same basis as the MMF tabs.
5. **Flux** — Optional ``flux_m3_m2_h`` (m³/m²/h) for documentation; the current
   correlations **do not** use flux separately from ``lv_m_h`` (void fraction /
   porosity effects are folded into the empirical coefficients).

**Units**

- ``solid_loading_kg_m2`` in outputs matches ``inputs["solid_loading"]`` (kg/m²
  cake inventory scale used in ``engine.backwash``).
- Run time and intervals in **hours**.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

_REF_TSS = 10.0  # mg/L — mid-range open-intake seawater after screening
_REF_LV = 10.0  # m/h — nominal MMF LV reference for scaling
_SDI_SOFT_CAP = 5.0  # above this: extrapolation warning
_MFI_SOFT_CAP = 8.0
# When ASTM SDI₁₅ blocks (∞), UI offers a bracketing cap for advisory correlation only.
SDI_BLOCKED_CAP_OPTIONS: tuple[float, ...] = (6.0, 8.0, 10.0)
SDI_BLOCKED_CAP_DEFAULT = 8.0


def effective_sdi15_for_correlation(
    sdi15: float,
    *,
    test_blocked: bool = False,
    blocked_cap: float = SDI_BLOCKED_CAP_DEFAULT,
) -> tuple[float, list[str]]:
    """
    Return SDI₁₅ value used in correlations and any extra user-facing warnings.

    When the 15-min test never completes (plugging factor → ∞), pass ``test_blocked=True``
  and a **cap** (typically 6–10). Design basis for M_max should still rely on TSS / pilot data.
    """
    extra: List[str] = []
    if test_blocked:
        cap = float(blocked_cap)
        if cap not in SDI_BLOCKED_CAP_OPTIONS:
            cap = max(6.0, min(cap, 15.0))
        extra.append(
            f"SDI₁₅ reported as blocked (∞) — correlation uses cap **{cap:g}** for advisory only. "
            "Set **M_max** from Process TSS bands, pilot cake loading, or site history; "
            "do not use this cap as sole design sign-off."
        )
        return cap, extra
    return max(float(sdi15), 0.0), extra


def _warn_extrapolation(
    *,
    sdi15: float,
    mfi_index: float,
    tss_mg_l: float,
    warnings: List[str],
) -> None:
    if sdi15 > _SDI_SOFT_CAP:
        warnings.append(
            f"SDI15={sdi15:g} exceeds {_SDI_SOFT_CAP:g} — correlation extrapolated beyond "
            "typical SWRO pretreatment envelope; treat run time as conservative."
        )
    if mfi_index > _MFI_SOFT_CAP:
        warnings.append(
            f"MFI index={mfi_index:g} exceeds {_MFI_SOFT_CAP:g} — high colloidal fouling "
            "risk; validate with pilot or normalised MFI protocol."
        )
    if tss_mg_l > 50.0:
        warnings.append(
            f"TSS={tss_mg_l:g} mg/L is high for open seawater MMF feed — check sampling "
            "and storm / dredging events."
        )


def estimate_solids_loading(
    *,
    tss_mg_l: float,
    lv_m_h: float,
    sdi15: float,
    mfi_index: float,
    flux_m3_m2_h: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Estimate representative **max solids inventory** scale (kg/m²) from feed quality.

    Correlation (power-law mass-flux intuition, coefficients tuned for 0.5–3 kg/m²):

    ``loading ≈ k × (TSS/T_ref)^0.6 × (LV/LV_ref)^0.4 × f(SDI) × f(MFI)``

    where ``f(SDI) = 1 + 0.12·max(0, SDI−2)``, ``f(MFI) = 1 + 0.15·max(0, MFI−1)``.
    ``flux_m3_m2_h`` is accepted for API compatibility but **not used** in v1.
    """
    warnings: List[str] = []
    tss = max(float(tss_mg_l), 0.05)
    lv = max(float(lv_m_h), 0.1)
    sdi = max(float(sdi15), 0.0)
    mfi = max(float(mfi_index), 0.0)

    k_base = 0.28
    core = k_base * (tss / _REF_TSS) ** 0.6 * (lv / _REF_LV) ** 0.4
    f_sdi = 1.0 + 0.12 * max(0.0, sdi - 2.0)
    f_mfi = 1.0 + 0.15 * max(0.0, mfi - 1.0)
    loading = core * f_sdi * f_mfi
    loading = max(0.05, min(loading, 25.0))  # hard clamp to sane display band

    _warn_extrapolation(sdi15=sdi, mfi_index=mfi, tss_mg_l=tss, warnings=warnings)

    return {
        "solid_loading_kg_m2": loading,
        "warnings": warnings,
        "f_sdi": f_sdi,
        "f_mfi": f_mfi,
        "flux_m3_m2_h_ignored": flux_m3_m2_h,
    }


def estimate_fouling_severity(
    *,
    sdi15: float,
    mfi_index: float,
    tss_mg_l: float,
    lv_m_h: float,
) -> Dict[str, Any]:
    """
    Map feed indices to a **0–100 score** and a coarse label.

    Score = weighted sum of normalised SDI, MFI, TSS, LV contributions (40/25/20/15 %).
    Labels: low < 25, moderate < 45, high < 70, else severe.
    """
    warnings: List[str] = []
    sdi = max(float(sdi15), 0.0)
    mfi = max(float(mfi_index), 0.0)
    tss = max(float(tss_mg_l), 0.0)
    lv = max(float(lv_m_h), 0.0)

    s_sdi = min(sdi / 6.0, 1.5)  # >9 SDI maps beyond 1.5 → capped in score
    s_mfi = min(mfi / 6.0, 1.5)
    s_tss = min(tss / 40.0, 1.5)
    s_lv = min(lv / 15.0, 1.5)

    score = 100.0 * math.sqrt(
        (0.40 * s_sdi) ** 2 + (0.25 * s_mfi) ** 2 + (0.20 * s_tss) ** 2 + (0.15 * s_lv) ** 2
    ) / math.sqrt(0.40**2 + 0.25**2 + 0.20**2 + 0.15**2)
    score = max(0.0, min(score, 100.0))

    if score < 25.0:
        label = "low"
    elif score < 45.0:
        label = "moderate"
    elif score < 70.0:
        label = "high"
    else:
        label = "severe"

    _warn_extrapolation(sdi15=sdi, mfi_index=mfi, tss_mg_l=tss, warnings=warnings)

    return {
        "score": score,
        "severity": label,
        "warnings": warnings,
        "components": {"sdi_norm": s_sdi, "mfi_norm": s_mfi, "tss_norm": s_tss, "lv_norm": s_lv},
    }


def estimate_run_time(
    *,
    sdi15: float,
    mfi_index: float,
    tss_mg_l: float,
    lv_m_h: float,
    base_run_hours: float = 48.0,
    min_run_hours: float = 4.0,
    max_run_hours: float = 168.0,
) -> Dict[str, Any]:
    """
    Estimate **filter run time between backwashes** (hours).

    Uses ``estimate_fouling_severity`` score ``S``: ``t ≈ base × (55 / (15+S))`` so
    higher fouling shortens run time. Clamped to ``[min_run_hours, max_run_hours]``.
    """
    sev = estimate_fouling_severity(
        sdi15=sdi15, mfi_index=mfi_index, tss_mg_l=tss_mg_l, lv_m_h=lv_m_h
    )
    s = float(sev["score"])
    raw = base_run_hours * (55.0 / (15.0 + s))
    t_run = max(min_run_hours, min(max_run_hours, raw))
    warnings = list(sev["warnings"])
    if raw < min_run_hours + 1e-6:
        warnings.append("Run time hit minimum clamp — consider additional pretreatment or BW capacity.")
    if raw > max_run_hours - 1e-6:
        warnings.append("Run time hit maximum clamp — very clean feed or low LV.")

    return {
        "run_time_h": t_run,
        "warnings": warnings,
        "severity": sev["severity"],
        "score": sev["score"],
    }


def estimate_bw_frequency(
    *,
    run_time_h: float,
    bw_cycle_duration_h: float = 1.5,
) -> Dict[str, Any]:
    """
    From estimated **run time** and assumed **blocked BW window** (hours per event),
    return recommended interval and implied daily BW cycles.

    ``bw_cycle_duration_h`` is the engineering placeholder for total offline time
    (drain + air + rinse + refill) per train event.
    """
    rt = max(float(run_time_h), 0.5)
    bw = max(float(bw_cycle_duration_h), 0.1)
    interval = rt
    cycles_per_day = 24.0 / (rt + bw)
    return {
        "recommended_interval_h": interval,
        "bw_cycles_per_day": cycles_per_day,
        "assumed_bw_block_h": bw,
    }


def water_stability_class(
    *,
    severity: str,
    seasonal_variability: str,
    algae_risk: str,
) -> Dict[str, Any]:
    """Qualitative feed stability for fouling workflow (advisory only)."""
    sev = str(severity).lower()
    rank = {"low": 0, "moderate": 1, "high": 2, "severe": 3}.get(sev, 1)
    if seasonal_variability in ("high", "very_high"):
        rank += 1
    if algae_risk in ("moderate", "high"):
        rank += 1
    if rank <= 0:
        label, tone = "stable", "ok"
    elif rank == 1:
        label, tone = "moderate", "caution"
    elif rank == 2:
        label, tone = "aggressive", "warning"
    else:
        label, tone = "unstable", "critical"
    return {"label": label, "tone": tone, "rank": rank}


def fouling_confidence_level(
    *,
    sdi15: float,
    mfi_index: float,
    tss_mg_l: float,
    has_upstream_uf_daf: bool,
    seasonal_variability: str,
) -> Dict[str, Any]:
    """How much to trust fouling guidance from input completeness (not statistics)."""
    score = 0
    if float(sdi15) > 0:
        score += 25
    if float(mfi_index) > 0:
        score += 25
    if float(tss_mg_l) > 0:
        score += 25
    if has_upstream_uf_daf:
        score += 15
    if seasonal_variability not in ("unknown", ""):
        score += 10
    if score >= 75:
        level = "high"
        note = "Key indices provided — still validate M_max and BW frequency on site."
    elif score >= 50:
        level = "moderate"
        note = "Partial characterisation — treat suggested M_max as bracketing only."
    else:
        level = "low"
        note = "Sparse inputs — use fouling panel for orientation, not design sign-off."
    return {"level": level, "score": score, "note": note}


def fouling_advisory_recommendations(
    *,
    severity: str,
    score: float,
    stability_label: str,
    run_time_h: float,
) -> List[str]:
    """Non-binding design hints — user must Apply changes explicitly."""
    rec: List[str] = []
    sev = str(severity).lower()
    if sev in ("high", "severe"):
        rec.append("Consider additional filter in service (N+1 margin) or lower approach LV.")
        rec.append("Review BW step durations and peak concurrent BW demand in the feasibility matrix.")
    if stability_label in ("aggressive", "unstable"):
        rec.append("Plan for seasonal TSS/SDI peaks — align M_max and BW cycles with conservative case.")
    if float(run_time_h) < 12.0:
        rec.append("Short indicative run time — verify BW train count and cartridge loading.")
    if float(score) >= 70:
        rec.append("Elevated fouling score — confirm pretreatment (DAF/UF) and chlorination strategy with client.")
    if not rec:
        rec.append("Current fouling indices are in a typical SWRO pretreatment band — maintain monitoring.")
    rec.append("Optional: compare cycle uncertainty band on **Filtration** tab after Apply.")
    return rec


__all__ = [
    "estimate_solids_loading",
    "estimate_run_time",
    "estimate_fouling_severity",
    "estimate_bw_frequency",
    "effective_sdi15_for_correlation",
    "SDI_BLOCKED_CAP_OPTIONS",
    "SDI_BLOCKED_CAP_DEFAULT",
    "water_stability_class",
    "fouling_confidence_level",
    "fouling_advisory_recommendations",
]
