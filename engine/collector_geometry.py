"""Vessel cross-section geometry for underdrain lateral limits and screening."""
from __future__ import annotations

import math
from typing import Any

# Manufacturing / drilling limits
_MIN_PERFORATION_PITCH_MM = 50.0
_PERFORATION_PITCH_ORIFICE_FACTOR = 2.5
_DEFAULT_AUTO_PITCH_MM = 200.0
_MIN_LATERAL_SPACING_M = 0.25
_MAX_LATERAL_VELOCITY_M_S = 3.0
_TARGET_PERFORATION_V_M_S = 2.5
_DEFAULT_MAX_OPEN_AREA_FRACTION = 0.10
_MIN_LIGAMENT_ORIFICE_FACTOR = 1.0
_FREEBOARD_EXPANSION_WARN_FRAC = 0.25
COLLECTOR_CROWN_CLEARANCE_M = 0.10  # 100 mm below internal crown (vessel ID)


def max_collector_centerline_height_m(
    vessel_id_m: float,
    header_id_m: float,
    *,
    crown_clearance_m: float = COLLECTOR_CROWN_CLEARANCE_M,
) -> float:
    """
    Upper limit for BW outlet collector centreline height from vessel bottom (m).

    h_col,max = vessel_ID − crown_clearance − header_ID/2
    (100 mm crown clearance + half header OD below shell).
    """
    vid = max(0.1, float(vessel_id_m))
    hid = max(0.0, float(header_id_m))
    return max(0.0, vid - float(crown_clearance_m) - hid / 2.0)


# Recommended maximum open area (perforations / wall) by lateral material — industry typicals.
LATERAL_MATERIAL_OPTIONS: tuple[str, ...] = (
    "PVC",
    "CPVC / PP",
    "Stainless steel",
    "Wedge wire",
    "Custom",
)
LATERAL_MATERIAL_OPEN_AREA: dict[str, dict[str, Any]] = {
    "PVC": {
        "open_area_max_fraction": 0.12,
        "open_area_range_pct": "8–12%",
        "pipe_note": "Sch 80 PVC common for underdrain; verify temperature & chlorine compatibility.",
    },
    "CPVC / PP": {
        "open_area_max_fraction": 0.15,
        "open_area_range_pct": "10–15%",
        "pipe_note": "CPVC or PP laterals — confirm chemical and temperature limits.",
    },
    "Stainless steel": {
        "open_area_max_fraction": 0.25,
        "open_area_range_pct": "15–25%",
        "pipe_note": "SS316L / 304 — Sch 40 typical; match vessel nozzle class.",
    },
    "Wedge wire": {
        "open_area_max_fraction": 0.35,
        "open_area_range_pct": "higher (slot / wire profile)",
        "pipe_note": "Wedge-wire or wrapped screen — use OEM equivalent open area, not round-hole formula only.",
    },
    "Custom": {
        "open_area_max_fraction": 0.10,
        "open_area_range_pct": "user-defined",
        "pipe_note": "Set max open-area fraction below.",
    },
}


def lateral_material_open_area_limit(
    lateral_material: str,
    user_fraction: float | None = None,
) -> dict[str, Any]:
    """Resolve screening cap from material table or custom user fraction."""
    key = str(lateral_material or "Stainless steel").strip()
    if key not in LATERAL_MATERIAL_OPEN_AREA:
        key = "Stainless steel"
    spec = LATERAL_MATERIAL_OPEN_AREA[key]
    mat_cap = float(spec["open_area_max_fraction"])
    user = float(user_fraction) if user_fraction is not None else 0.0
    if key == "Custom" and user > 0:
        cap = max(0.03, min(0.40, user))
        source = "custom user limit"
    elif user > 0:
        cap = min(mat_cap, max(0.03, min(0.40, user)))
        source = f"{key} table (capped by user {user * 100:.0f}%)"
    else:
        cap = mat_cap
        source = f"{key} recommended maximum ({spec['open_area_range_pct']})"
    return {
        "lateral_material": key,
        "open_area_max_fraction": cap,
        "open_area_limit_pct": round(cap * 100.0, 1),
        "open_area_range_pct": spec["open_area_range_pct"],
        "material_pipe_note": spec["pipe_note"],
        "limit_source": source,
    }


def chord_half_width_m(vessel_radius_m: float, height_from_bottom_m: float) -> float:
    """Horizontal half-chord from centreline to shell at elevation h (m above bottom)."""
    r = float(vessel_radius_m)
    h = max(0.0, float(height_from_bottom_m))
    if r <= 1e-9:
        return 0.0
    if h >= 2.0 * r:
        return 0.0
    return math.sqrt(max(0.0, 2.0 * r * h - h * h))


def lateral_geometry_from_vessel(
    *,
    vessel_id_m: float,
    nozzle_plate_h_m: float,
    collector_h_m: float,
    cyl_len_m: float,
    wall_clearance_m: float = 0.05,
) -> dict[str, Any]:
    """
    Cross-section (elevation) limits for laterals from header at nozzle-plate axis to shell.

    Circle centre at (0, R) with bottom at y=0. Header on centreline at h_np; lateral tip
    on shell at collector_h (BW collector elevation cap). θ is from horizontal.
    """
    r = max(0.1, float(vessel_id_m) / 2.0)
    h_np = max(0.0, float(nozzle_plate_h_m))
    h_col = max(h_np, float(collector_h_m))
    if h_col >= 2.0 * r - wall_clearance_m:
        h_col = max(h_np, 2.0 * r - wall_clearance_m - 0.01)

    l_horiz = chord_half_width_m(r, h_col) - wall_clearance_m
    l_horiz = max(0.1, l_horiz)
    rise = max(0.0, h_col - h_np)
    l_inclined = math.sqrt(l_horiz * l_horiz + rise * rise)
    theta_rad = math.atan2(rise, l_horiz) if l_horiz > 1e-9 else 0.0
    theta_deg = math.degrees(theta_rad)

    # Along-header spacing: coverage rule ≤ ~1× ID between tees; also fit in cyl length
    spacing_max_coverage = max(_MIN_LATERAL_SPACING_M, float(vessel_id_m))
    spacing_max_fit = cyl_len_m / 2.0 if cyl_len_m > 0 else spacing_max_coverage

    return {
        "vessel_radius_m": round(r, 4),
        "underdrain_axis_h_m": round(h_np, 3),
        "collector_h_m": round(h_col, 3),
        "lateral_rise_m": round(rise, 3),
        "lateral_horiz_reach_m": round(l_horiz, 3),
        "lateral_length_max_m": round(l_inclined, 3),
        "theta_deg": round(theta_deg, 2),
        "theta_rad": round(theta_rad, 4),
        "lateral_spacing_max_m": round(min(spacing_max_coverage, spacing_max_fit), 3),
        "wall_clearance_m": wall_clearance_m,
    }


def lateral_wall_area_m(lateral_dn_m: float, lateral_length_m: float) -> float:
    """Cylindrical envelope area used for open-area fraction (conservative, full circumference)."""
    d = max(0.01, float(lateral_dn_m))
    length = max(0.05, float(lateral_length_m))
    return math.pi * d * length


def perforation_open_area_m2(n_holes: int, orifice_d_mm: float) -> float:
    d = max(0.001, float(orifice_d_mm) / 1000.0)
    return max(0, int(n_holes)) * math.pi * (d / 2.0) ** 2


def lateral_structural_screening(
    *,
    lateral_construction: str = "Drilled perforated pipe",
    lateral_dn_mm: float,
    lateral_length_m: float,
    orifice_d_mm: float,
    n_perforations: int,
    max_open_area_fraction: float = _DEFAULT_MAX_OPEN_AREA_FRACTION,
    lateral_material: str = "Stainless steel",
    slot_width_mm: float = 0.0,
    wedge_open_area_fraction: float = 0.0,
    bw_head_mwc: float = 15.0,
) -> dict[str, Any]:
    """Route mechanical screening: drilled ligament rules vs wedge-wire OEM/collapse."""
    from engine.collector_lateral_types import (
        coated_cs_screening,
        is_drilled_construction,
        is_wedge_wire_construction,
        wedge_wire_screening,
    )

    if is_wedge_wire_construction(lateral_construction):
        struct = wedge_wire_screening(
            lateral_dn_mm=lateral_dn_mm,
            lateral_length_m=lateral_length_m,
            open_area_fraction=float(wedge_open_area_fraction),
            slot_width_mm=float(slot_width_mm),
            bw_head_mwc=float(bw_head_mwc),
            lateral_material=lateral_material,
            user_open_area_fraction=float(max_open_area_fraction),
        )
        return struct

    struct = structural_perforation_limits(
        lateral_dn_mm=lateral_dn_mm,
        lateral_length_m=lateral_length_m,
        orifice_d_mm=orifice_d_mm,
        n_perforations=n_perforations,
        max_open_area_fraction=max_open_area_fraction,
        lateral_material=lateral_material,
    )
    struct["screening_model"] = "drilled_perforated"
    struct["lateral_construction"] = lateral_construction
    struct["ligament_check_applies"] = True
    struct["perforation_pitch_check_applies"] = True

    if lateral_construction == "Coated carbon steel (drilled)":
        struct["findings"] = list(struct.get("findings") or []) + coated_cs_screening(
            lateral_material=lateral_material,
            open_area_fraction_pct=float(struct.get("open_area_fraction_pct", 0)),
        )
    return struct


def structural_perforation_limits(
    *,
    lateral_dn_mm: float,
    lateral_length_m: float,
    orifice_d_mm: float,
    n_perforations: int,
    max_open_area_fraction: float = _DEFAULT_MAX_OPEN_AREA_FRACTION,
    lateral_material: str = "Stainless steel",
) -> dict[str, Any]:
    """
    Screen perforation count / pitch so open area does not over-weaken the lateral.

    open_area_fraction = n × π(d/2)² / (π × DN × L)  ≤ material max open area.
    """
    mat_lim = lateral_material_open_area_limit(lateral_material, max_open_area_fraction)
    cap = float(mat_lim["open_area_max_fraction"])
    d_lat_m = max(0.01, float(lateral_dn_mm) / 1000.0)
    l_m = max(0.05, float(lateral_length_m))
    d_orf = max(1.0, float(orifice_d_mm))
    a_wall = lateral_wall_area_m(d_lat_m, l_m)
    n = max(0, int(n_perforations))
    a_open = perforation_open_area_m2(n, d_orf)
    frac = a_open / a_wall if a_wall > 1e-9 else 0.0
    a_hole = math.pi * (d_orf / 1000.0 / 2.0) ** 2
    n_max_struct = max(1, int(a_wall * cap / a_hole)) if a_hole > 1e-12 else n
    pitch = (l_m * 1000.0) / max(n - 1, 1) if n > 1 else l_m * 1000.0
    ligament = pitch - d_orf
    min_lig = _MIN_LIGAMENT_ORIFICE_FACTOR * d_orf
    ok_frac = frac <= cap + 1e-6
    ok_lig = ligament >= min_lig if n > 1 else True
    findings: list[dict[str, str]] = []
    if not ok_frac:
        findings.append({
            "severity": "warning",
            "topic": "Lateral open area",
            "detail": (
                f"Perforation open area **{frac * 100:.1f}%** of lateral wall exceeds "
                f"**{cap * 100:.0f}%** limit — reduce count, smaller Ø, or larger DN/length."
            ),
        })
    if not ok_lig and n > 1:
        findings.append({
            "severity": "warning",
            "topic": "Perforation pitch",
            "detail": (
                f"Wall ligament **{ligament:.0f} mm** < **{min_lig:.0f} mm** "
                f"(pitch {pitch:.0f} mm, Ø {d_orf:.1f} mm) — increase pitch or reduce hole size."
            ),
        })
    return {
        **mat_lim,
        "open_area_fraction": round(frac, 4),
        "open_area_fraction_limit": cap,
        "open_area_fraction_pct": round(frac * 100.0, 2),
        "n_perforations": n,
        "n_perforations_max_structural": n_max_struct,
        "ligament_mm": round(ligament, 1),
        "ligament_min_mm": round(min_lig, 1),
        "structural_ok": ok_frac and ok_lig,
        "findings": findings,
    }


def advise_lateral_pipe_rating(
    *,
    lateral_dn_mm: float,
    design_pressure_bar: float = 7.0,
    bw_head_mwc: float = 15.0,
    default_rating: str = "150#",
    vessel_pressure_bar: float = 2.0,
    lateral_material: str = "Stainless steel",
) -> dict[str, Any]:
    """Advisory schedule / class for underdrain laterals and header (not ASME calc)."""
    p = max(float(design_pressure_bar), float(vessel_pressure_bar))
    head_bar = float(bw_head_mwc) * 0.0981
    p_oper = head_bar + 0.5

    mat_key = str(lateral_material or "Stainless steel").strip()
    mat_spec = LATERAL_MATERIAL_OPEN_AREA.get(mat_key, LATERAL_MATERIAL_OPEN_AREA["Stainless steel"])

    if mat_key == "PVC":
        sched = "Sch 80 (PVC)"
        note = "PVC laterals — verify temperature, chlorine, and support spacing."
    elif mat_key == "CPVC / PP":
        sched = "Sch 80 / SDR per OEM"
        note = "CPVC or PP — confirm chemical compatibility and support."
    elif mat_key == "Wedge wire":
        sched = "OEM wedge-wire / wrapper profile"
        note = "Not plain drilled pipe — follow screen supplier open-area & collapse limits."
    elif p >= 16.0 or p_oper > 12.0:
        sched = "Sch 80"
        note = "Elevated design or BW head — prefer Sch 80 or heavier on underdrain."
    elif p >= 10.0 or p_oper > 8.0:
        sched = "Sch 40"
        note = "Moderate pressure — Sch 40 minimum; confirm with mechanical spec."
    else:
        sched = "Sch 40"
        note = "Typical MMF underdrain — match vessel nozzle rating."

    rating = str(default_rating or "PN 10").strip()
    if "150" in rating or "PN 25" in rating or "PN 40" in rating:
        rating_advice = f"Flanges / stubs: **{rating}** (align with vessel nozzle schedule)."
    else:
        rating_advice = f"Flanges / stubs: **{rating}** — verify gasket rating vs BW pressure."

    mat = mat_spec["pipe_note"]

    return {
        "schedule_suggest": sched,
        "rating_suggest": rating,
        "material_suggest": mat,
        "lateral_material": mat_key,
        "operating_pressure_est_bar": round(p_oper, 2),
        "summary": f"{sched}, {rating}, {mat.split(';')[0]}",
        "notes": [note, rating_advice],
    }


def screen_bed_expansion_vs_collector(
    *,
    bw_col: dict | None,
    collector_h_m: float,
    nozzle_plate_h_m: float,
) -> dict[str, Any]:
    """Relate max bed expansion (from media model) to collector height and underdrain elevation."""
    col = bw_col or {}
    h_col = float(collector_h_m)
    h_np = float(nozzle_plate_h_m)
    expanded_top = float(col.get("expanded_top_m", h_np))
    freeboard_m = float(col.get("freeboard_m", h_col - expanded_top))
    min_fb = float(col.get("min_freeboard_m", 0.1))
    exp_pct = float(col.get("total_expansion_pct", 0.0))
    max_safe = float(col.get("max_safe_bw_m_h", 0.0))
    proposed = float(col.get("proposed_bw_m_h", 0.0))

    findings: list[dict[str, str]] = []
    if col.get("media_loss_risk"):
        findings.append({
            "severity": "critical",
            "topic": "Bed expansion vs collector",
            "detail": col.get("status", "Expanded bed reaches collector — media loss risk."),
        })
    elif freeboard_m < min_fb * 1.25:
        findings.append({
            "severity": "warning",
            "topic": "Bed expansion vs collector",
            "detail": (
                f"Expanded bed top **{expanded_top:.2f} m** leaves only **{freeboard_m * 1000:.0f} mm** "
                f"freeboard below collector **{h_col:.2f} m** (target ≥ {min_fb * 1000:.0f} mm)."
            ),
        })
    if proposed > 0 and max_safe > 0 and proposed > max_safe * 0.9:
        findings.append({
            "severity": "advisory",
            "topic": "BW rate vs expansion",
            "detail": (
                f"Proposed BW **{proposed:.1f} m/h** near max safe **{max_safe:.1f} m/h** "
                f"for **{exp_pct:.0f}%** total bed expansion — verify combined air+water step."
            ),
        })
    if h_np > 0 and (expanded_top - h_np) / max(h_col - h_np, 0.01) > (1.0 - _FREEBOARD_EXPANSION_WARN_FRAC):
        findings.append({
            "severity": "advisory",
            "topic": "Underdrain vs expanded zone",
            "detail": (
                "Laterals sit at nozzle-plate elevation; expanded bed occupies most of the "
                "collector freeboard — confirm perforations are not in high fluidised shear zone."
            ),
        })

    return {
        "expanded_top_m": round(expanded_top, 3),
        "collector_h_m": round(h_col, 3),
        "freeboard_m": round(freeboard_m, 3),
        "total_expansion_pct": round(exp_pct, 1),
        "max_safe_bw_m_h": round(max_safe, 1),
        "findings": findings,
    }


def enrich_collector_design_advisory(
    collector_hyd: dict[str, Any],
    *,
    bw_col: dict | None = None,
    design_pressure_bar: float = 7.0,
    bw_head_mwc: float = 15.0,
    default_rating: str = "150#",
    vessel_pressure_bar: float = 2.0,
    max_open_area_fraction: float = _DEFAULT_MAX_OPEN_AREA_FRACTION,
    lateral_material: str = "Stainless steel",
    lateral_construction: str = "Drilled perforated pipe",
    feed_salinity_ppt: float = 35.0,
    wedge_slot_width_mm: float = 0.0,
    wedge_open_area_fraction: float = 0.0,
) -> dict[str, Any]:
    """Merge structural, expansion, and pipe-rating advisories into collector_hyd output."""
    out = dict(collector_hyd)
    design = dict(out.get("design") or {})
    geo = out.get("geometry") or {}

    l_lat = float(out.get("lateral_length_m") or design.get("lateral_length_used_m") or 0.0)
    d_lat = float(out.get("lateral_dn_mm") or 50.0)
    d_orf = float(out.get("lateral_orifice_d_mm") or 50.0)
    n_perf = int(out.get("n_orifices_per_lateral") or design.get("n_perforations_per_lateral") or 0)

    from engine.collector_lateral_types import (
        is_wedge_wire_construction,
        water_service_material_guidance,
    )

    struct = lateral_structural_screening(
        lateral_construction=lateral_construction,
        lateral_dn_mm=d_lat,
        lateral_length_m=l_lat,
        orifice_d_mm=d_orf,
        n_perforations=n_perf,
        max_open_area_fraction=max_open_area_fraction,
        lateral_material=lateral_material,
        slot_width_mm=wedge_slot_width_mm,
        wedge_open_area_fraction=wedge_open_area_fraction,
        bw_head_mwc=bw_head_mwc,
    )
    water_mat = water_service_material_guidance(
        salinity_ppt=feed_salinity_ppt,
        lateral_construction=lateral_construction,
        lateral_material=lateral_material,
    )
    if not struct["structural_ok"] and struct["n_perforations_max_structural"] < n_perf:
        design["n_perforations_structural_max"] = struct["n_perforations_max_structural"]
        design.setdefault("notes", []).append(
            f"Structural max **{struct['n_perforations_max_structural']}** perforations/lateral "
            f"for ≤{struct['open_area_limit_pct']:.0f}% open area (current {n_perf})."
        )

    rating = advise_lateral_pipe_rating(
        lateral_dn_mm=d_lat,
        design_pressure_bar=design_pressure_bar,
        bw_head_mwc=bw_head_mwc,
        default_rating=default_rating,
        vessel_pressure_bar=vessel_pressure_bar,
        lateral_material=lateral_material,
    )
    expansion = screen_bed_expansion_vs_collector(
        bw_col=bw_col,
        collector_h_m=float(geo.get("collector_h_m") or out.get("collector_h_m") or 0.0),
        nozzle_plate_h_m=float(geo.get("underdrain_axis_h_m") or 0.0),
    )

    advisories: list[dict[str, str]] = []
    recommendations: list[str] = list(water_mat.get("recommendations") or [])
    for block in (struct["findings"], expansion["findings"], water_mat.get("findings") or []):
        advisories.extend(block)
    for note in rating.get("notes") or []:
        recommendations.append(note)

    _wedge = is_wedge_wire_construction(lateral_construction)
    checklist = [
        "Bed expansion / freeboard vs collector height (Backwash §1)",
        f"Water service: **{water_mat.get('water_service', '—')}** ({feed_salinity_ppt:.1f} ppt) — alloy / coating review",
    ]
    if _wedge:
        checklist.extend([
            f"Wedge wire open area (typical {struct.get('open_area_range_pct', '20–60%')}) — "
            f"screening {struct['open_area_fraction_pct']:.1f}% (collapse / OEM, not ligament %)",
            "Collapse strength, rod spacing, slot width, weld integrity, ΔP & air-scour abrasion",
            struct.get("hydraulic_note", "Wedge wire hydraulics — lower entrance loss vs drilled holes"),
        ])
    else:
        checklist.extend([
            f"Drilled open area ≤ {struct['open_area_limit_pct']:.0f}% "
            f"({struct.get('lateral_material', '')}) — current {struct['open_area_fraction_pct']:.1f}%",
            f"Perforation pitch & ligament (min ~{struct['ligament_min_mm']:.0f} mm web)",
        ])
        if lateral_construction == "Coated carbon steel (drilled)":
            checklist.append("Coating holidays, weld edges, BW/air scour abrasion, repair strategy")
    checklist.extend([
        f"N laterals & header spacing ≤ {float(geo.get('lateral_spacing_max_m', 0)):.2f} m",
        f"Lateral length ≤ {float(geo.get('lateral_length_max_m', 0)):.2f} m (θ={float(geo.get('theta_deg', 0)):.1f}°)",
        f"Pipe / screen: {rating['schedule_suggest']} · rating {rating['rating_suggest']}",
        "Hydraulic maldistribution / slot or perforation velocities",
        "Support / tee loads on header (mechanical — not modelled)",
    ])

    out["design"] = {
        **design,
        "structural": struct,
        "pipe_rating": rating,
        "expansion_screen": expansion,
        "water_material": water_mat,
    }
    out["advisories"] = advisories
    out["recommendations"] = recommendations
    out["design_checklist"] = checklist
    out["open_area_fraction_pct"] = struct["open_area_fraction_pct"]
    out["open_area_limit_pct"] = struct["open_area_limit_pct"]
    out["n_perforations_max_structural"] = struct["n_perforations_max_structural"]
    out["lateral_schedule_suggest"] = rating["schedule_suggest"]
    out["lateral_rating_suggest"] = rating["rating_suggest"]
    out["lateral_material"] = struct.get("lateral_material", lateral_material)
    out["lateral_material_open_area_range_pct"] = struct.get("open_area_range_pct", "")
    out["lateral_construction"] = lateral_construction
    out["screening_model"] = struct.get("screening_model", "drilled_perforated")
    out["water_service"] = water_mat.get("water_service", "")
    out["water_material_recommendations"] = water_mat.get("recommendations", [])
    warnings = list(out.get("warnings") or [])
    for f in advisories:
        if f.get("severity") == "warning":
            warnings.append(f"{f.get('topic', '')}: {f.get('detail', '')}")
    out["warnings"] = warnings
    return out


def perforation_pitch_limits_mm(orifice_d_mm: float) -> dict[str, float]:
    d = max(1.0, float(orifice_d_mm))
    pitch_min = max(_MIN_PERFORATION_PITCH_MM, _PERFORATION_PITCH_ORIFICE_FACTOR * d)
    pitch_max = max(pitch_min, 400.0)
    return {"pitch_min_mm": pitch_min, "pitch_max_mm": pitch_max}


def suggest_underdrain_design(
    *,
    q_bw_m3h: float,
    vessel_id_m: float,
    nozzle_plate_h_m: float,
    collector_h_m: float,
    cyl_len_m: float,
    n_laterals: int,
    lateral_dn_mm: float,
    lateral_orifice_d_mm: float,
    lateral_length_m: float = 0.0,
    lateral_spacing_m: float = 0.0,
    n_orifices_per_lateral: int = 0,
    lateral_material: str = "Stainless steel",
    lateral_construction: str = "Drilled perforated pipe",
    max_open_area_fraction: float = 0.0,
    wedge_slot_width_mm: float = 0.0,
    wedge_open_area_fraction: float = 0.0,
    bw_head_mwc: float = 15.0,
) -> dict[str, Any]:
    """Apply geometry limits and light screening for DN, N, perforation pitch."""
    from engine.collector_lateral_types import hydraulic_factors_for_lateral, is_wedge_wire_construction

    _hf = hydraulic_factors_for_lateral(lateral_construction)
    _target_v = float(_hf["target_slot_orifice_v_m_s"])
    geo = lateral_geometry_from_vessel(
        vessel_id_m=vessel_id_m,
        nozzle_plate_h_m=nozzle_plate_h_m,
        collector_h_m=collector_h_m,
        cyl_len_m=cyl_len_m,
    )
    l_max = float(geo["lateral_length_max_m"])
    l_use = min(l_max, float(lateral_length_m)) if lateral_length_m > 0 else l_max

    n_lat = max(1, int(n_laterals))
    sp_max = float(geo["lateral_spacing_max_m"])
    if lateral_spacing_m > 0:
        spacing = min(lateral_spacing_m, sp_max)
    elif n_lat > 1:
        spacing = min(sp_max, max(_MIN_LATERAL_SPACING_M, cyl_len_m / (n_lat + 1)))
    else:
        spacing = cyl_len_m * 0.5

    d_orf = max(1.0, float(lateral_orifice_d_mm))
    pitches = perforation_pitch_limits_mm(d_orf)
    pitch_min = pitches["pitch_min_mm"]
    pitch_max = pitches["pitch_max_mm"]

    if n_orifices_per_lateral > 0:
        n_perf = int(n_orifices_per_lateral)
        pitch_used = (l_use * 1000.0) / max(n_perf - 1, 1) if n_perf > 1 else l_use * 1000.0
    else:
        pitch_used = min(pitch_max, max(pitch_min, _DEFAULT_AUTO_PITCH_MM))
        n_perf = max(1, int(l_use * 1000.0 / pitch_used) + 1)

    notes: list[str] = []
    _oa_user = float(max_open_area_fraction) if max_open_area_fraction > 0 else None
    _wedge = is_wedge_wire_construction(lateral_construction)
    struct_pre = lateral_structural_screening(
        lateral_construction=lateral_construction,
        lateral_dn_mm=float(lateral_dn_mm),
        lateral_length_m=l_use,
        orifice_d_mm=d_orf,
        n_perforations=n_perf,
        max_open_area_fraction=_oa_user or (
            wedge_open_area_fraction if _wedge else lateral_material_open_area_limit(lateral_material)["open_area_max_fraction"]
        ),
        lateral_material=str(lateral_material),
        slot_width_mm=wedge_slot_width_mm,
        wedge_open_area_fraction=wedge_open_area_fraction,
        bw_head_mwc=bw_head_mwc,
    )
    if (
        not _wedge
        and struct_pre.get("n_perforations_max_structural", 0) > 0
        and n_perf > struct_pre["n_perforations_max_structural"]
    ):
        n_perf = struct_pre["n_perforations_max_structural"]
        pitch_used = (l_use * 1000.0) / max(n_perf - 1, 1) if n_perf > 1 else l_use * 1000.0
        notes.append(
            f"Perforation count reduced to **{n_perf}/lateral** for ≤"
            f"{struct_pre['open_area_limit_pct']:.0f}% drilled open area."
        )

    q_lat_m3s = (q_bw_m3h / 3600.0) / n_lat if q_bw_m3h > 0 else 0.0
    d_lat_m = max(0.01, lateral_dn_mm / 1000.0)
    a_lat = math.pi * (d_lat_m / 2.0) ** 2
    v_lat = q_lat_m3s / a_lat if a_lat > 0 else 0.0

    d_lat_suggest_m = d_lat_m
    if v_lat > _MAX_LATERAL_VELOCITY_M_S and q_lat_m3s > 0:
        d_lat_suggest_m = 2.0 * math.sqrt(q_lat_m3s / (_MAX_LATERAL_VELOCITY_M_S * math.pi))

    a_orf = math.pi * (d_orf / 1000.0 / 2.0) ** 2
    v_orf = q_lat_m3s / (n_perf * a_orf) if n_perf > 0 and a_orf > 0 else 0.0
    d_orf_suggest_mm = d_orf
    if v_orf > _target_v * 1.2 and q_lat_m3s > 0:
        d_orf_suggest_mm = 2.0 * math.sqrt(q_lat_m3s / (n_perf * _target_v * math.pi)) * 1000.0

    n_suggest = n_lat
    if cyl_len_m > 0 and spacing > 0:
        n_suggest = max(2, min(24, int(cyl_len_m / spacing)))

    if lateral_length_m > l_max + 0.01:
        notes.append(f"Lateral length capped at geometric max {l_max:.2f} m (θ={geo['theta_deg']:.1f}°).")
    if pitch_used < pitch_min - 0.5:
        notes.append(f"Perforation pitch {pitch_used:.0f} mm < drilling min {pitch_min:.0f} mm — reduce count or shorten lateral.")
    if pitch_used > pitch_max + 0.5:
        notes.append(f"Perforation pitch {pitch_used:.0f} mm is coarse — consider more perforations for distribution.")
    if v_lat > _MAX_LATERAL_VELOCITY_M_S:
        notes.append(
            f"Lateral pipe velocity {v_lat:.2f} m/s > {_MAX_LATERAL_VELOCITY_M_S:.1f} m/s — "
            f"suggest DN ≥ {d_lat_suggest_m * 1000:.0f} mm."
        )

    return {
        **geo,
        "lateral_length_used_m": round(l_use, 3),
        "lateral_spacing_used_m": round(spacing, 3),
        "n_laterals_used": n_lat,
        "n_laterals_suggested": n_suggest,
        "n_perforations_per_lateral": n_perf,
        "perforation_pitch_used_mm": round(pitch_used, 1),
        **pitches,
        "lateral_velocity_m_s": round(v_lat, 3),
        "perforation_velocity_m_s": round(v_orf, 3),
        "lateral_dn_suggest_mm": round(d_lat_suggest_m * 1000.0, 0),
        "perforation_d_suggest_mm": round(d_orf_suggest_mm, 1),
        "structural": struct_pre,
        "notes": notes,
    }
