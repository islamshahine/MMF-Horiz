"""1D backwash collector / lateral / orifice ladder (deterministic, no CFD)."""
from __future__ import annotations

import math
from typing import Any

from engine.collector_geometry import lateral_geometry_from_vessel, suggest_underdrain_design
from engine.collector_lateral_types import hydraulic_factors_for_lateral, is_wedge_wire_construction

GRAVITY = 9.81
_F_DARCY_DEFAULT = 0.02
_CD_DEFAULT = 0.62
_HEADER_V_WARN_M_S = 3.0
_ORIFICE_V_WARN_M_S = 5.0
_MAL_CAP = 2.0
_DEFAULT_PERFORATION_PITCH_MM = 200.0
_MAX_PERFORATIONS_PER_LATERAL = 120
_MAX_DIST_ITER = 64
DISTRIBUTION_TOL_REL = 0.002
_DIST_TOL_REL = DISTRIBUTION_TOL_REL


def distribution_metadata_available(collector_hyd: dict | None) -> bool:
    """False for legacy cached ``collector_hyd`` blobs (predates distribution solver)."""
    return bool(collector_hyd) and "distribution_residual_rel" in collector_hyd


def distribution_residual_rel(collector_hyd: dict | None) -> float | None:
    """Relative flow residual, or ``None`` when not computed yet."""
    if not distribution_metadata_available(collector_hyd):
        return None
    try:
        return float(collector_hyd["distribution_residual_rel"])  # type: ignore[index]
    except (TypeError, ValueError, KeyError):
        return None


def distribution_solver_converged(collector_hyd: dict | None) -> bool:
    """True when relative flow residual is within tolerance (authoritative)."""
    res = distribution_residual_rel(collector_hyd)
    if res is None:
        return False
    return res <= _DIST_TOL_REL


def refresh_collector_distribution_metadata(inputs: dict, computed: dict) -> None:
    """Fill distribution solver fields on legacy ``collector_hyd`` (in-place)."""
    ch = computed.get("collector_hyd")
    if not isinstance(ch, dict) or distribution_metadata_available(ch):
        if isinstance(ch, dict):
            ch["distribution_converged"] = distribution_solver_converged(ch)
        return

    avg_area = float(computed.get("avg_area") or 1.0)
    bw_vel = float(inputs.get("bw_velocity", 30) or 30)
    q_bw = max(bw_vel * avg_area, float(computed.get("q_per_filter", 0) or 0) * 2.0)

    fresh = compute_collector_hydraulics(
        q_bw_m3h=q_bw,
        filter_area_m2=avg_area,
        cyl_len_m=float(computed.get("cyl_len") or inputs.get("cyl_len", 8) or 8),
        nominal_id_m=float(computed.get("nominal_id") or inputs.get("nominal_id", 5.5) or 5.5),
        np_bore_dia_mm=float(inputs.get("np_bore_dia", 50) or 50),
        np_density_per_m2=float(inputs.get("np_density", 10) or 10),
        collector_header_id_m=float(inputs.get("collector_header_id_m", 0.25) or 0.25),
        n_laterals=int(inputs.get("n_bw_laterals", 4) or 4),
        lateral_dn_mm=float(inputs.get("lateral_dn_mm", 50) or 50),
        lateral_spacing_m=float(inputs.get("lateral_spacing_m", 0) or 0),
        lateral_length_m=float(inputs.get("lateral_length_m", 0) or 0),
        lateral_orifice_d_mm=float(inputs.get("lateral_orifice_d_mm", 0) or 0),
        n_orifices_per_lateral=int(inputs.get("n_orifices_per_lateral", 0) or 0),
        nozzle_plate_h_m=float(inputs.get("nozzle_plate_h", 1) or 1),
        collector_h_m=float(inputs.get("collector_h", 4.2) or 4.2),
        use_geometry_lateral=bool(inputs.get("use_geometry_lateral", True)),
        lateral_material=str(inputs.get("lateral_material", "Stainless steel")),
        lateral_construction=str(inputs.get("lateral_construction", "Drilled perforated pipe")),
        max_open_area_fraction=float(inputs.get("max_lateral_open_area_fraction", 0) or 0),
        wedge_slot_width_mm=float(inputs.get("wedge_slot_width_mm", 0) or 0),
        wedge_open_area_fraction=float(inputs.get("wedge_open_area_fraction", 0) or 0),
        bw_head_mwc=float(inputs.get("bw_head_mwc", 15) or 15),
        discharge_coefficient=float(inputs.get("lateral_discharge_cd", 0.62) or 0.62),
        rho_water=float(computed.get("rho_bw") or 1000),
    )
    for key in (
        "distribution_iterations",
        "distribution_residual_rel",
        "distribution_converged",
        "flow_imbalance_pct",
        "maldistribution_factor_calc",
    ):
        if key in fresh:
            ch[key] = fresh[key]
    ch["distribution_converged"] = distribution_solver_converged(ch)


def _darcy_head_m(*, f: float, length_m: float, diameter_m: float, velocity_m_s: float) -> float:
    if diameter_m <= 0 or length_m <= 0:
        return 0.0
    return f * (length_m / diameter_m) * (velocity_m_s**2) / (2.0 * GRAVITY)


def _orifice_head_m(*, q_m3_s: float, cd: float, diameter_m: float, rho: float) -> float:
    area = math.pi * (diameter_m / 2.0) ** 2
    if area <= 0 or cd <= 0 or q_m3_s <= 0:
        return 0.0
    return (q_m3_s / (cd * area)) ** 2 / (2.0 * GRAVITY * max(rho, 1.0))


def compute_collector_hydraulics(
    *,
    q_bw_m3h: float,
    filter_area_m2: float,
    cyl_len_m: float,
    nominal_id_m: float,
    np_bore_dia_mm: float,
    np_density_per_m2: float,
    collector_header_id_m: float,
    n_laterals: int,
    lateral_dn_mm: float,
    lateral_spacing_m: float = 0.0,
    lateral_length_m: float = 0.0,
    lateral_orifice_d_mm: float = 0.0,
    n_orifices_per_lateral: int = 0,
    nozzle_plate_h_m: float = 0.0,
    collector_h_m: float = 0.0,
    use_geometry_lateral: bool = True,
    lateral_material: str = "Stainless steel",
    lateral_construction: str = "Drilled perforated pipe",
    max_open_area_fraction: float = 0.0,
    wedge_slot_width_mm: float = 0.0,
    wedge_open_area_fraction: float = 0.0,
    bw_head_mwc: float = 15.0,
    discharge_coefficient: float = _CD_DEFAULT,
    rho_water: float = 1000.0,
    friction_factor: float = _F_DARCY_DEFAULT,
    header_feed_mode: str = "one_end",
) -> dict[str, Any]:
    """
  Estimate lateral flow imbalance and a maldistribution factor from a 1D header + lateral model.

  Assumptions (documented in UI):
  - Header fed from one end; laterals are identical orifices with Darcy losses in header and lateral pipe.
  - Orifice head loss uses orifice equation with discharge coefficient Cd.
  """
    n_lat = max(1, int(n_laterals))
    q_total = max(0.0, float(q_bw_m3h)) / 3600.0
    rho = max(800.0, float(rho_water))
    f = max(0.008, min(0.08, float(friction_factor)))
    _hf = hydraulic_factors_for_lateral(lateral_construction)
    cd = max(0.3, min(0.95, float(discharge_coefficient)))
    if abs(cd - _CD_DEFAULT) < 1e-6:
        cd = float(_hf["discharge_cd"])
    _target_v = float(_hf["target_slot_orifice_v_m_s"])
    _hl_f = float(_hf["headloss_factor"])

    d_header = max(0.02, float(collector_header_id_m))
    d_lat = max(0.01, float(lateral_dn_mm) / 1000.0)
    d_orf_mm = float(lateral_orifice_d_mm or np_bore_dia_mm)
    d_orf = max(0.001, d_orf_mm / 1000.0)

    h_np = float(nozzle_plate_h_m) if nozzle_plate_h_m > 0 else max(0.5, float(nominal_id_m) * 0.08)
    h_col = float(collector_h_m) if collector_h_m > 0 else h_np + 0.5

    design = suggest_underdrain_design(
        q_bw_m3h=q_bw_m3h,
        vessel_id_m=nominal_id_m,
        nozzle_plate_h_m=h_np,
        collector_h_m=h_col,
        cyl_len_m=cyl_len_m,
        n_laterals=n_lat,
        lateral_dn_mm=float(lateral_dn_mm),
        lateral_orifice_d_mm=d_orf_mm,
        lateral_length_m=float(lateral_length_m) if not use_geometry_lateral else 0.0,
        lateral_spacing_m=float(lateral_spacing_m),
        n_orifices_per_lateral=int(n_orifices_per_lateral),
        lateral_material=str(lateral_material),
        lateral_construction=str(lateral_construction),
        max_open_area_fraction=float(max_open_area_fraction),
        wedge_slot_width_mm=float(wedge_slot_width_mm),
        wedge_open_area_fraction=float(wedge_open_area_fraction),
        bw_head_mwc=float(bw_head_mwc),
    )
    geo = lateral_geometry_from_vessel(
        vessel_id_m=nominal_id_m,
        nozzle_plate_h_m=h_np,
        collector_h_m=h_col,
        cyl_len_m=cyl_len_m,
    )

    l_lat = float(lateral_length_m)
    if use_geometry_lateral or l_lat <= 0:
        l_lat = float(design["lateral_length_used_m"])
    else:
        l_lat = min(l_lat, float(geo["lateral_length_max_m"]))

    spacing = float(lateral_spacing_m)
    if spacing <= 0:
        spacing = float(design["lateral_spacing_used_m"])

    n_orf_user = int(n_orifices_per_lateral)
    perforation_pitch_mm = float(design.get("perforation_pitch_used_mm") or _DEFAULT_PERFORATION_PITCH_MM)
    if n_orf_user > 0:
        n_orf = min(_MAX_PERFORATIONS_PER_LATERAL, n_orf_user)
        orf_auto_source = "user"
    else:
        n_orf = min(_MAX_PERFORATIONS_PER_LATERAL, int(design["n_perforations_per_lateral"]))
        orf_auto_source = f"auto pitch {perforation_pitch_mm:.0f} mm (geom limits {design['pitch_min_mm']:.0f}–{design['pitch_max_mm']:.0f} mm)"
    n_orf_total = n_orf * n_lat
    # Nozzle plate count kept for reference only (different component).
    n_nozzle_plate_ref = max(0, int(round(max(0.0, np_density_per_m2) * max(0.0, filter_area_m2))))

    if q_total <= 1e-9:
        return {
            "method": "1D Darcy-Weisbach + orifice discharge (one-end header feed)",
            "q_bw_m3h": round(float(q_bw_m3h), 3),
            "n_laterals": n_lat,
            "n_orifices_per_lateral": n_orf,
            "n_orifices_total": n_orf_total,
            "perforation_auto_source": orf_auto_source,
            "nozzle_plate_holes_ref": n_nozzle_plate_ref,
            "lateral_spacing_m": round(spacing, 3),
            "lateral_length_m": round(l_lat, 3),
            "collector_header_id_m": round(d_header, 4),
            "lateral_dn_mm": round(d_lat * 1000.0, 1),
            "lateral_orifice_d_mm": round(d_orf * 1000.0, 2),
            "discharge_coefficient": cd,
            "maldistribution_factor_calc": 1.0,
            "flow_imbalance_pct": 0.0,
            "profile": [],
            "header_velocity_max_m_s": 0.0,
            "orifice_velocity_max_m_s": 0.0,
            "orifice_velocity_min_m_s": 0.0,
            "warnings": ["Zero BW flow — maldistribution defaults to 1.0."],
            "flags": [],
            "distribution_iterations": 0,
            "distribution_converged": True,
            "distribution_residual_rel": 0.0,
            "header_feed_mode": str(header_feed_mode or "one_end"),
            "dual_end_meta": {},
            "feed_mode_comparison": None,
            "orifice_network": [],
            "geometry": geo,
            "design": design,
            "theta_deg": geo["theta_deg"],
            "lateral_length_max_m": geo["lateral_length_max_m"],
            "lateral_spacing_max_m": geo["lateral_spacing_max_m"],
            "perforation_pitch_min_mm": design.get("pitch_min_mm"),
            "perforation_pitch_max_mm": design.get("pitch_max_mm"),
        }

    # Station positions along header (m from inlet)
    positions = [spacing * (i + 1) for i in range(n_lat)]
    if positions and positions[-1] > cyl_len_m * 1.05 and cyl_len_m > 0:
        positions = [cyl_len_m * (i + 1) / (n_lat + 1) for i in range(n_lat)]

    from engine.collector_manifold import (
        _segment_lengths,
        build_orifice_network,
        compare_feed_modes,
        normalize_header_feed_mode,
        solve_lateral_distribution_dual_end,
        solve_lateral_distribution_one_end,
    )

    feed_mode = normalize_header_feed_mode(header_feed_mode)
    seg_lens = _segment_lengths(positions, cyl_len_m)
    _solve_kw = dict(
        q_total_m3_s=q_total,
        positions_m=positions,
        segment_lengths_m=seg_lens,
        d_header_m=d_header,
        d_lat_m=d_lat,
        l_lat_m=l_lat,
        n_orifices=n_orf,
        friction_factor=f,
        headloss_factor=_hl_f,
        rho=rho,
    )
    q_lat_one, it_one, res_one, conv_one = solve_lateral_distribution_one_end(**_solve_kw)
    dual_meta: dict[str, Any] = {}
    feed_cmp: dict[str, Any] | None = None
    if feed_mode == "dual_end":
        q_lat, dist_iterations, dist_residual, dist_converged, dual_meta = (
            solve_lateral_distribution_dual_end(
                q_total_m3_s=q_total,
                positions_m=positions,
                cyl_len_m=cyl_len_m,
                d_header_m=d_header,
                d_lat_m=d_lat,
                l_lat_m=l_lat,
                n_orifices=n_orf,
                friction_factor=f,
                headloss_factor=_hl_f,
                rho=rho,
            )
        )
        feed_cmp = compare_feed_modes(q_lat_one, q_lat)
    else:
        q_lat = q_lat_one
        dist_iterations = it_one
        dist_residual = res_one
        dist_converged = conv_one

    q_mean = q_total / n_lat
    q_max = max(q_lat)
    q_min = min(q_lat)
    mal = max(1.0, min(_MAL_CAP, q_max / q_mean if q_mean > 1e-12 else 1.0))
    imbalance_pct = (q_max - q_min) / q_mean * 100.0 if q_mean > 1e-12 else 0.0

    profile: list[dict[str, Any]] = []
    q_rem = q_total
    cum_dp_pa = 0.0
    v_header_prev = 0.0
    header_v_max = 0.0
    orf_v_max = 0.0
    orf_v_min = 1e9
    flags: list[str] = []
    warnings: list[str] = []

    for i, (x_m, q_i) in enumerate(zip(positions, q_lat)):
        seg_len = spacing if i == 0 else spacing
        v_header = q_rem / (math.pi * (d_header / 2.0) ** 2) if q_rem > 0 else 0.0
        header_v_max = max(header_v_max, v_header)
        v_seg = 0.5 * (v_header + v_header_prev)
        hf_seg = _darcy_head_m(f=f, length_m=seg_len, diameter_m=d_header, velocity_m_s=v_seg) * _hl_f
        cum_dp_pa += hf_seg * rho * GRAVITY

        v_lat = q_i / (math.pi * (d_lat / 2.0) ** 2) if q_i > 0 else 0.0
        hf_lat = _darcy_head_m(f=f, length_m=l_lat, diameter_m=d_lat, velocity_m_s=v_lat) * _hl_f
        q_per_orf = q_i / n_orf if n_orf > 0 else q_i
        v_orf = q_per_orf / (math.pi * (d_orf / 2.0) ** 2) if q_per_orf > 0 else 0.0
        orf_v_max = max(orf_v_max, v_orf)
        orf_v_min = min(orf_v_min, v_orf) if v_orf > 0 else orf_v_min

        profile.append({
            "station_m": round(x_m, 3),
            "lateral_index": i + 1,
            "header_flow_m3h": round(q_rem * 3600.0, 2),
            "header_velocity_m_s": round(v_header, 3),
            "lateral_flow_m3h": round(q_i * 3600.0, 2),
            "lateral_velocity_m_s": round(v_lat, 3),
            "orifice_velocity_m_s": round(v_orf, 3),
            "cumulative_header_loss_kpa": round(cum_dp_pa / 1000.0, 3),
        })
        q_rem = max(0.0, q_rem - q_i)
        v_header_prev = v_header

    if header_v_max > _HEADER_V_WARN_M_S:
        flags.append("header_velocity_high")
        warnings.append(
            f"Header velocity up to {header_v_max:.2f} m/s — consider larger collector ID."
        )
    _orf_warn = _target_v * 1.4 if is_wedge_wire_construction(lateral_construction) else _ORIFICE_V_WARN_M_S
    if orf_v_max > _orf_warn:
        flags.append("orifice_velocity_high")
        _orf_lbl = "slot" if is_wedge_wire_construction(lateral_construction) else "orifice"
        warnings.append(
            f"Lateral {_orf_lbl} velocity up to {orf_v_max:.2f} m/s "
            f"(target ~{_target_v:.1f} m/s) — check erosion / plugging / distribution."
        )
    if mal >= 1.15:
        warnings.append(
            f"Estimated lateral imbalance {imbalance_pct:.1f}% → maldistribution factor {mal:.3f}."
        )

    if orf_v_min > 1e8:
        orf_v_min = 0.0

    orifice_net = build_orifice_network(
        positions_m=positions,
        q_lat_m3_s=q_lat,
        n_orifices=n_orf,
        lateral_length_m=l_lat,
        orifice_d_m=d_orf,
        pitch_mm=perforation_pitch_mm,
        lateral_construction=str(lateral_construction),
    )
    _method = (
        "1D Darcy-Weisbach + orifice discharge (dual-end header feed, 1B+)"
        if feed_mode == "dual_end"
        else "1D Darcy-Weisbach + orifice discharge (one-end header feed)"
    )

    return {
        "method": _method,
        "header_feed_mode": feed_mode,
        "dual_end_meta": dual_meta,
        "feed_mode_comparison": feed_cmp,
        "orifice_network": orifice_net,
        "q_bw_m3h": round(float(q_bw_m3h), 3),
        "n_laterals": n_lat,
        "n_orifices_per_lateral": n_orf,
        "n_orifices_total": n_orf_total,
        "perforation_auto_source": orf_auto_source,
        "nozzle_plate_holes_ref": n_nozzle_plate_ref,
        "perforation_pitch_mm": perforation_pitch_mm,
        "lateral_spacing_m": round(spacing, 3),
        "lateral_length_m": round(l_lat, 3),
        "collector_header_id_m": round(d_header, 4),
        "lateral_dn_mm": round(d_lat * 1000.0, 1),
        "lateral_orifice_d_mm": round(d_orf * 1000.0, 2),
        "discharge_coefficient": cd,
        "lateral_construction": str(lateral_construction),
        "target_opening_velocity_m_s": round(_target_v, 2),
        "hydraulic_headloss_factor": round(_hl_f, 3),
        "maldistribution_factor_calc": round(mal, 4),
        "flow_imbalance_pct": round(imbalance_pct, 2),
        "distribution_iterations": dist_iterations,
        "distribution_converged": dist_converged,
        "distribution_residual_rel": round(dist_residual, 5),
        "profile": profile,
        "header_velocity_max_m_s": round(header_v_max, 3),
        "orifice_velocity_max_m_s": round(orf_v_max, 3),
        "orifice_velocity_min_m_s": round(orf_v_min, 3),
        "warnings": warnings + list(design.get("notes") or []),
        "flags": flags,
        "geometry": geo,
        "design": design,
        "theta_deg": geo["theta_deg"],
        "lateral_length_max_m": geo["lateral_length_max_m"],
        "lateral_horiz_reach_m": geo["lateral_horiz_reach_m"],
        "lateral_spacing_max_m": geo["lateral_spacing_max_m"],
        "perforation_pitch_min_mm": design.get("pitch_min_mm"),
        "perforation_pitch_max_mm": design.get("pitch_max_mm"),
        "perforation_pitch_used_mm": round(perforation_pitch_mm, 1),
    }
