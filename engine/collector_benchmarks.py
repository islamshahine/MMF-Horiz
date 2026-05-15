"""Hand-calc style regression benchmarks for collector 1A/1B (1D model).

These are **sanity and monotonicity** checks against engineering expectations,
not vendor CFD validation. See ``tests/test_collector_benchmarks.py``.
"""
from __future__ import annotations

import math
from typing import Any, Callable

from engine.collector_hydraulics import compute_collector_hydraulics

BenchmarkFn = Callable[[], tuple[bool, str]]


def _base_kw() -> dict[str, Any]:
    return dict(
      q_bw_m3h=150.0,
      filter_area_m2=28.0,
      cyl_len_m=22.0,
      nominal_id_m=5.5,
      np_bore_dia_mm=50.0,
      np_density_per_m2=45.0,
      collector_header_id_m=0.30,
      n_laterals=6,
      lateral_dn_mm=50.0,
      lateral_spacing_m=3.2,
      lateral_length_m=2.4,
      lateral_orifice_d_mm=8.0,
      n_orifices_per_lateral=12,
      nozzle_plate_h_m=1.0,
      collector_h_m=4.0,
      use_geometry_lateral=False,
  )


def check_profile_flow_conservation(out: dict[str, Any], *, rtol: float = 0.02) -> tuple[bool, str]:
    """Σ lateral Q ≈ total BW Q after distribution solve."""
    prof = out.get("profile") or []
    if not prof:
        return True, "No profile (zero flow case)."
    q_total_m3h = float(out.get("q_bw_m3h", 0) or 0)
    q_lat = sum(float(p.get("lateral_flow_m3h", 0) or 0) for p in prof)
    if q_total_m3h <= 0:
        return True, "Zero flow."
    err = abs(q_lat - q_total_m3h) / q_total_m3h
    ok = err <= rtol
    return ok, f"Lateral sum {q_lat:.1f} m³/h vs total {q_total_m3h:.1f} m³/h (rel err {err:.3f})."


def check_profile_header_flow_decreases(out: dict[str, Any]) -> tuple[bool, str]:
    """Header flow at each tee should not increase downstream (one-end feed)."""
    prof = out.get("profile") or []
    if len(prof) < 2:
        return True, "Single lateral — N/A."
    flows = [float(p.get("header_flow_m3h", 0) or 0) for p in prof]
    for i in range(len(flows) - 1):
        if flows[i + 1] > flows[i] + 0.05:
            return False, f"Header flow rises between station {i + 1} and {i + 2}: {flows[i]:.2f} → {flows[i + 1]:.2f} m³/h."
    return True, "Header residual flow non-increasing along manifold."


def check_collector_hyd_sanity(out: dict[str, Any] | None) -> list[dict[str, str]]:
    """Quick checks on a single ``collector_hyd`` dict (for Backwash UI)."""
    if not out:
        return [{"check": "present", "ok": "no", "detail": "No collector_hyd in computed."}]
    rows: list[dict[str, str]] = []
    mal = float(out.get("maldistribution_factor_calc", 1) or 1)
    rows.append({
        "check": "maldistribution ≥ 1",
        "ok": "yes" if mal >= 1.0 else "no",
        "detail": f"mal = {mal:.3f}",
    })
    conv = bool(out.get("distribution_converged"))
    res = out.get("distribution_residual_rel")
    rows.append({
        "check": "distribution converged",
        "ok": "yes" if conv else "no",
        "detail": f"residual = {res}",
    })
    ok_c, msg_c = check_profile_flow_conservation(out)
    rows.append({"check": "flow conservation", "ok": "yes" if ok_c else "no", "detail": msg_c})
    ok_h, msg_h = check_profile_header_flow_decreases(out)
    rows.append({"check": "header flow monotone", "ok": "yes" if ok_h else "no", "detail": msg_h})
    return rows


def _bench_header_id_monotonic() -> tuple[bool, str]:
    kw = _base_kw()
    loose = compute_collector_hydraulics(**{**kw, "collector_header_id_m": 0.40})
    tight = compute_collector_hydraulics(**{**kw, "collector_header_id_m": 0.14})
    m_lo = float(loose["maldistribution_factor_calc"])
    m_ti = float(tight["maldistribution_factor_calc"])
    ok = m_ti >= m_lo and m_ti >= 1.0
    return ok, f"mal: ID 0.40 m → {m_lo:.3f}; ID 0.14 m → {m_ti:.3f} (expect tighter ≥ looser)."


def _bench_more_laterals_lowers_mal() -> tuple[bool, str]:
    kw = _base_kw()
    few = compute_collector_hydraulics(**{**kw, "n_laterals": 4, "lateral_spacing_m": 4.0})
    many = compute_collector_hydraulics(**{**kw, "n_laterals": 10, "lateral_spacing_m": 2.0})
    m4 = float(few["maldistribution_factor_calc"])
    m10 = float(many["maldistribution_factor_calc"])
    ok = m10 <= m4 + 0.05
    return ok, f"mal: 4 laterals → {m4:.3f}; 10 laterals → {m10:.3f} (expect more branches ≤ fewer)."


def _bench_double_flow_raises_header_velocity() -> tuple[bool, str]:
    kw = _base_kw()
    low = compute_collector_hydraulics(**kw)
    high = compute_collector_hydraulics(**{**kw, "q_bw_m3h": 300.0})
    v0 = float(low.get("header_velocity_max_m_s", 0) or 0)
    v1 = float(high.get("header_velocity_max_m_s", 0) or 0)
    ok = v1 > v0 * 1.4
    return ok, f"V_header max: Q×1 → {v0:.2f} m/s; Q×2 → {v1:.2f} m/s."


def _bench_distribution_converges() -> tuple[bool, str]:
    """Use a case known to need header loss (tighter ID) so the solver actually iterates."""
    kw = {**_base_kw(), "collector_header_id_m": 0.16, "n_laterals": 6, "lateral_spacing_m": 3.0}
    out = compute_collector_hydraulics(**kw)
    from engine.collector_hydraulics import distribution_solver_converged

    conv = distribution_solver_converged(out)
    _raw_res = out.get("distribution_residual_rel")
    res = float(_raw_res) if _raw_res is not None else 1.0
    it = int(out.get("distribution_iterations") or 0)
    ok = conv and res <= 0.002 and it >= 1
    return ok, f"converged={conv}, residual={res:.5f}, iterations={it}."


def _bench_profile_conservation() -> tuple[bool, str]:
    out = compute_collector_hydraulics(**_base_kw())
    return check_profile_flow_conservation(out)


def _bench_profile_header_monotone() -> tuple[bool, str]:
    out = compute_collector_hydraulics(**_base_kw())
    return check_profile_header_flow_decreases(out)


def _bench_mal_equals_qmax_over_qmean() -> tuple[bool, str]:
    out = compute_collector_hydraulics(**_base_kw())
    prof = out.get("profile") or []
    if not prof:
        return False, "Empty profile."
    q_lat = [float(p["lateral_flow_m3h"]) / 3600.0 for p in prof]
    q_mean = sum(q_lat) / len(q_lat)
    q_max = max(q_lat)
    mal = float(out["maldistribution_factor_calc"])
    expected = max(1.0, q_max / q_mean if q_mean > 0 else 1.0)
    ok = abs(mal - min(expected, 2.0)) < 0.02
    return ok, f"mal={mal:.4f}, q_max/q_mean={expected:.4f} (cap 2.0)."


def _bench_zero_flow_neutral() -> tuple[bool, str]:
    kw = {**_base_kw(), "q_bw_m3h": 0.0}
    out = compute_collector_hydraulics(**kw)
    ok = (
        float(out["maldistribution_factor_calc"]) == 1.0
        and out.get("profile") == []
        and bool(out.get("distribution_converged"))
    )
    return ok, "Q=0 → mal=1, empty profile, converged flag set."


BENCHMARK_REGISTRY: list[tuple[str, str, BenchmarkFn]] = [
    ("header_id_monotonic", "Smaller header ID increases maldistribution", _bench_header_id_monotonic),
    ("more_laterals", "More laterals reduces maldistribution (same vessel)", _bench_more_laterals_lowers_mal),
    ("double_flow_velocity", "Double BW flow raises header velocity", _bench_double_flow_raises_header_velocity),
    ("distribution_converges", "Distribution solver converges (base case)", _bench_distribution_converges),
    ("flow_conservation", "Σ lateral flow = total BW flow", _bench_profile_conservation),
    ("header_monotone", "Header residual flow decreases along manifold", _bench_profile_header_monotone),
    ("mal_definition", "mal ≈ q_max / q_mean (capped)", _bench_mal_equals_qmax_over_qmean),
    ("zero_flow", "Zero flow → neutral mal", _bench_zero_flow_neutral),
]


def run_collector_benchmark_suite() -> list[dict[str, Any]]:
    """Run all registered benchmarks; for pytest and optional UI."""
    results: list[dict[str, Any]] = []
    for bid, title, fn in BENCHMARK_REGISTRY:
        try:
            passed, detail = fn()
        except Exception as ex:
            passed, detail = False, f"Exception: {ex}"
        results.append({
            "id": bid,
            "title": title,
            "passed": bool(passed),
            "detail": detail,
        })
    return results


def suite_all_passed(results: list[dict[str, Any]] | None = None) -> bool:
    rows = results if results is not None else run_collector_benchmark_suite()
    return bool(rows) and all(r.get("passed") for r in rows)
