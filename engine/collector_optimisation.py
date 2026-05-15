"""Grid search over 1D collector hydraulics — fast local optimiser (not full plant compute)."""
from __future__ import annotations

import copy
from typing import Any

from engine.collector_hydraulics import (
    compute_collector_hydraulics,
    distribution_metadata_available,
    distribution_solver_converged,
)
from engine.nozzles import DN_SERIES

_HEADER_V_CAP_M_S = 3.0
_MAX_CANDIDATES = 320


def _score_collector_hyd(collector_hyd: dict) -> float:
    """Lower is better — balance maldistribution, velocities, convergence."""
    if not distribution_metadata_available(collector_hyd):
        return 1.0e6
    mal = float(collector_hyd.get("maldistribution_factor_calc", 1.0) or 1.0)
    imb = float(collector_hyd.get("flow_imbalance_pct", 0.0) or 0.0)
    v_hdr = float(collector_hyd.get("header_velocity_max_m_s", 0.0) or 0.0)
    v_orf = float(collector_hyd.get("orifice_velocity_max_m_s", 0.0) or 0.0)
    v_tgt = float(collector_hyd.get("target_opening_velocity_m_s", 2.5) or 2.5)
    score = mal * 100.0 + imb
    score += max(0.0, v_hdr - _HEADER_V_CAP_M_S) * 50.0
    score += max(0.0, v_orf - v_tgt * 1.35) * 35.0
    if not distribution_solver_converged(collector_hyd):
        score += 400.0
    for flag in collector_hyd.get("flags") or []:
        if flag == "header_velocity_high":
            score += 60.0
        elif flag == "orifice_velocity_high":
            score += 40.0
    oa = float(collector_hyd.get("open_area_fraction_pct", 0.0) or 0.0)
    oa_lim = float(collector_hyd.get("open_area_limit_pct", 60.0) or 60.0)
    if oa > oa_lim + 0.5:
        score += (oa - oa_lim) * 5.0
    return score


def _dn_grid(current_mm: float, suggest_mm: float) -> list[int]:
    base = int(round(max(current_mm, suggest_mm, 15)))
    out: set[int] = set()
    for dn in DN_SERIES:
        if 0.65 * base <= dn <= 1.6 * base + 1:
            out.add(dn)
    if not out:
        out.add(base)
    return sorted(out)[:6]


def _n_lateral_grid(current: int, suggested: int, cyl_len_m: float) -> list[int]:
    c0 = max(2, int(current))
    s0 = max(2, int(suggested or c0))
    lo = max(2, min(c0, s0) - 2)
    hi = min(24, max(c0, s0) + 3)
    if cyl_len_m > 0:
        hi = min(hi, max(4, int(cyl_len_m / 0.35)))
    return list(range(lo, hi + 1))


def optimise_collector_design(context: dict) -> dict[str, Any]:
    """
    Search N laterals × lateral DN × perforation count for minimum imbalance score.

    ``context`` — SI dict with keys matching ``compute_collector_hydraulics`` plus
    ``n_bw_laterals``, ``lateral_dn_mm``, etc. (current sidebar values).
    """
    ctx = copy.deepcopy(context)
    q_bw = float(ctx.get("q_bw_m3h", 0) or 0)
    if q_bw <= 0:
        return {
            "ok": False,
            "message": "BW flow is zero — set BW velocity and run compute first.",
            "patch": {},
            "collector_hyd": {},
            "candidates_evaluated": 0,
        }

    n0 = int(ctx.get("n_bw_laterals", 4) or 4)
    dn0 = float(ctx.get("lateral_dn_mm", 50) or 50)
    cyl_len = float(ctx.get("cyl_len_m", 8) or 8)

    baseline = compute_collector_hydraulics(
        q_bw_m3h=q_bw,
        filter_area_m2=float(ctx.get("filter_area_m2", 25) or 25),
        cyl_len_m=cyl_len,
        nominal_id_m=float(ctx.get("nominal_id_m", 5.5) or 5.5),
        np_bore_dia_mm=float(ctx.get("np_bore_dia_mm", 50) or 50),
        np_density_per_m2=float(ctx.get("np_density_per_m2", 10) or 10),
        collector_header_id_m=float(ctx.get("collector_header_id_m", 0.25) or 0.25),
        n_laterals=n0,
        lateral_dn_mm=dn0,
        lateral_spacing_m=float(ctx.get("lateral_spacing_m", 0) or 0),
        lateral_length_m=float(ctx.get("lateral_length_m", 0) or 0),
        lateral_orifice_d_mm=float(ctx.get("lateral_orifice_d_mm", 0) or 0),
        n_orifices_per_lateral=int(ctx.get("n_orifices_per_lateral", 0) or 0),
        nozzle_plate_h_m=float(ctx.get("nozzle_plate_h_m", 1) or 1),
        collector_h_m=float(ctx.get("collector_h_m", 4.2) or 4.2),
        use_geometry_lateral=bool(ctx.get("use_geometry_lateral", True)),
        lateral_material=str(ctx.get("lateral_material", "Stainless steel")),
        lateral_construction=str(ctx.get("lateral_construction", "Drilled perforated pipe")),
        max_open_area_fraction=float(ctx.get("max_lateral_open_area_fraction", 0) or 0),
        wedge_slot_width_mm=float(ctx.get("wedge_slot_width_mm", 0) or 0),
        wedge_open_area_fraction=float(ctx.get("wedge_open_area_fraction", 0) or 0),
        bw_head_mwc=float(ctx.get("bw_head_mwc", 15) or 15),
        discharge_coefficient=float(ctx.get("lateral_discharge_cd", 0.62) or 0.62),
        rho_water=float(ctx.get("rho_water", 1000) or 1000),
    )
    des = baseline.get("design") or {}
    dn_sug = float(des.get("lateral_dn_suggest_mm", dn0) or dn0)
    n_sug = int(des.get("n_laterals_suggested", n0) or n0)
    n_perf_struct = int(baseline.get("n_perforations_max_structural", 0) or 0)
    n_perf0 = int(ctx.get("n_orifices_per_lateral", 0) or 0)
    perf_opts = [0]
    if n_perf_struct > 0:
        perf_opts.append(n_perf_struct)
    if n_perf0 > 0 and n_perf0 not in perf_opts:
        perf_opts.append(n_perf0)

    best_score = _score_collector_hyd(baseline)
    best_hyd = baseline
    best_patch: dict[str, Any] = {}
    n_eval = 1

    def _hyd_call(
        *,
        n_laterals: int,
        lateral_dn_mm: float,
        n_orifices_per_lateral: int,
    ) -> dict:
        return compute_collector_hydraulics(
            q_bw_m3h=q_bw,
            filter_area_m2=float(ctx.get("filter_area_m2", 25) or 25),
            cyl_len_m=cyl_len,
            nominal_id_m=float(ctx.get("nominal_id_m", 5.5) or 5.5),
            np_bore_dia_mm=float(ctx.get("np_bore_dia_mm", 50) or 50),
            np_density_per_m2=float(ctx.get("np_density_per_m2", 10) or 10),
            collector_header_id_m=float(ctx.get("collector_header_id_m", 0.25) or 0.25),
            nozzle_plate_h_m=float(ctx.get("nozzle_plate_h_m", 1) or 1),
            collector_h_m=float(ctx.get("collector_h_m", 4.2) or 4.2),
            lateral_material=str(ctx.get("lateral_material", "Stainless steel")),
            lateral_construction=str(
                ctx.get("lateral_construction", "Drilled perforated pipe"),
            ),
            max_open_area_fraction=float(ctx.get("max_lateral_open_area_fraction", 0) or 0),
            wedge_slot_width_mm=float(ctx.get("wedge_slot_width_mm", 0) or 0),
            wedge_open_area_fraction=float(ctx.get("wedge_open_area_fraction", 0) or 0),
            bw_head_mwc=float(ctx.get("bw_head_mwc", 15) or 15),
            discharge_coefficient=float(ctx.get("lateral_discharge_cd", 0.62) or 0.62),
            rho_water=float(ctx.get("rho_water", 1000) or 1000),
            n_laterals=n_laterals,
            lateral_dn_mm=lateral_dn_mm,
            lateral_spacing_m=0.0,
            lateral_length_m=0.0,
            lateral_orifice_d_mm=float(ctx.get("lateral_orifice_d_mm", 0) or 0),
            n_orifices_per_lateral=n_orifices_per_lateral,
            use_geometry_lateral=True,
        )

    for n_lat in _n_lateral_grid(n0, n_sug, cyl_len):
        for dn in _dn_grid(dn0, dn_sug):
            for n_perf in perf_opts:
                if n_eval >= _MAX_CANDIDATES:
                    break
                trial = _hyd_call(
                    n_laterals=int(n_lat),
                    lateral_dn_mm=float(dn),
                    n_orifices_per_lateral=int(n_perf),
                )
                n_eval += 1
                sc = _score_collector_hyd(trial)
                if sc < best_score - 1e-9:
                    best_score = sc
                    best_hyd = trial
                    best_patch = {
                        "n_bw_laterals": n_lat,
                        "lateral_dn_mm": float(dn),
                        "n_orifices_per_lateral": int(n_perf),
                        "lateral_spacing_m": 0.0,
                        "lateral_length_m": 0.0,
                        "use_geometry_lateral": True,
                        "use_calculated_maldistribution": True,
                        "maldistribution_factor": min(
                            2.0,
                            float(trial.get("maldistribution_factor_calc", 1.0) or 1.0),
                        ),
                    }
            if n_eval >= _MAX_CANDIDATES:
                break
        if n_eval >= _MAX_CANDIDATES:
            break

    if not best_patch:
        best_patch = {
            "n_bw_laterals": n0,
            "lateral_dn_mm": dn0,
            "use_geometry_lateral": True,
            "use_calculated_maldistribution": True,
            "maldistribution_factor": min(
                2.0, float(baseline.get("maldistribution_factor_calc", 1.0) or 1.0),
            ),
        }

    mal = float(best_hyd.get("maldistribution_factor_calc", 1.0) or 1.0)
    imb = float(best_hyd.get("flow_imbalance_pct", 0.0) or 0.0)
    mat = str(ctx.get("lateral_material", ""))
    con = str(ctx.get("lateral_construction", ""))
    msg = (
        f"Evaluated **{n_eval}** layouts ({con} / {mat}) — best mal **{mal:.3f}**, "
        f"imbalance **{imb:.1f}%**, "
        f"N={best_patch.get('n_bw_laterals', n0)}, "
        f"DN **{best_patch.get('lateral_dn_mm', dn0):.0f}** mm. "
        "Sizes updated — rerun compute to refresh Backwash plots."
    )
    return {
        "ok": True,
        "message": msg,
        "patch": best_patch,
        "collector_hyd": best_hyd,
        "candidates_evaluated": n_eval,
        "score": round(best_score, 3),
    }
