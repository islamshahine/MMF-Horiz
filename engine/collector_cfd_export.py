"""
CFD boundary-condition export for external manifold validation (OpenFOAM / ANSYS / etc.).

Derived from the in-app 1D / 1B+ screening model — not a CFD solve.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

SCHEMA_VERSION = "aquasight.collector_cfd.v1"


def build_collector_cfd_bundle(
    inputs: dict,
    computed: dict,
    *,
    export_timestamp_utc: str | None = None,
) -> dict[str, Any]:
    """Structured BC package for third-party CFD from ``collector_hyd`` + inputs."""
    ch = computed.get("collector_hyd") or {}
    ts = export_timestamp_utc or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rho = float(computed.get("rho_bw") or 1000.0)
    mu = float(computed.get("mu_bw") or 0.001)
    feed_mode = str(ch.get("header_feed_mode") or inputs.get("collector_header_feed_mode") or "one_end")

    boundaries: list[dict[str, Any]] = [
        {
            "id": "header_inlet_primary",
            "type": "velocity_inlet",
            "location": "header_x0",
            "v_m_s": round(float(ch.get("header_velocity_max_m_s") or 0) * 0.85, 3),
            "notes": "Screening value — scale to match plant BW pump curve in CFD.",
        },
    ]
    if feed_mode == "dual_end":
        boundaries.append({
            "id": "header_inlet_secondary",
            "type": "velocity_inlet",
            "location": "header_x_L",
            "v_m_s": round(float(ch.get("header_velocity_max_m_s") or 0) * 0.85, 3),
            "notes": "Dual-end feed mode — mirror primary or split mass per 1B+ split.",
        })

    orifice_rows = list(ch.get("orifice_network") or [])
    for row in orifice_rows[:500]:
        q_m3s = float(row.get("flow_m3h", 0)) / 3600.0
        boundaries.append({
            "id": f"L{row.get('lateral_index')}_H{row.get('hole_index')}",
            "type": "mass_flow_outlet",
            "m_dot_kg_s": round(q_m3s * rho, 5),
            "station_m": row.get("station_m"),
            "y_along_lateral_m": row.get("y_along_lateral_m"),
            "velocity_m_s": row.get("velocity_m_s"),
        })

    profile = list(ch.get("profile") or [])
    return {
        "schema_version": SCHEMA_VERSION,
        "export_timestamp_utc": ts,
        "disclaimer": (
            "Boundary conditions exported from AQUASIGHT 1D/1B+ screening — "
            "not a CFD solution. Validate mesh, turbulence, and multiphase effects externally."
        ),
        "project": {
            "name": str(inputs.get("project_name", "")),
            "document": str(inputs.get("doc_number", "")),
        },
        "fluid": {
            "rho_kg_m3": rho,
            "mu_pa_s": mu,
            "temperature_c": float(inputs.get("feed_temp", 25) or 25),
            "phase": "liquid_water_bw",
        },
        "geometry_si": {
            "vessel_length_m": float(computed.get("cyl_len") or inputs.get("total_length", 0)),
            "vessel_id_m": float(computed.get("nominal_id") or inputs.get("nominal_id", 0)),
            "collector_header_id_m": float(ch.get("collector_header_id_m") or 0),
            "lateral_dn_mm": float(ch.get("lateral_dn_mm") or 0),
            "lateral_length_m": float(ch.get("lateral_length_m") or 0),
            "lateral_orifice_d_mm": float(ch.get("lateral_orifice_d_mm") or 0),
            "n_laterals": int(ch.get("n_laterals") or 0),
            "n_orifices_per_lateral": int(ch.get("n_orifices_per_lateral") or 0),
            "header_feed_mode": feed_mode,
        },
        "hydraulics_screening": {
            "q_bw_m3h": float(ch.get("q_bw_m3h") or 0),
            "maldistribution_factor": float(ch.get("maldistribution_factor_calc") or 1.0),
            "flow_imbalance_pct": float(ch.get("flow_imbalance_pct") or 0),
            "header_velocity_max_m_s": float(ch.get("header_velocity_max_m_s") or 0),
            "orifice_velocity_max_m_s": float(ch.get("orifice_velocity_max_m_s") or 0),
            "distribution_residual_rel": ch.get("distribution_residual_rel"),
            "feed_mode_comparison": ch.get("feed_mode_comparison"),
        },
        "boundaries": boundaries,
        "lateral_profile": profile,
        "orifice_network": orifice_rows,
        "openfoam_hints": [
            "Use a porous zone or explicit pipe mesh for header + laterals; orifice outlets as patch faces.",
            "Inlet: fixedValue U or flowRateInletVelocity; match total Q_BW from bundle hydraulics_screening.",
            "Turbulence: k-omega SST or k-epsilon at screening Reynolds — refine near perforations.",
            "Symmetry: half-vessel if lateral layout is symmetric about centreline.",
        ],
        "ansys_fluent_hints": [
            "Mass-flow outlets per orifice row or merged porous jump to plenum.",
            "Coupled VOF only if modelling air scour in same model — BW water-only export is liquid.",
        ],
    }


def bundle_to_json(bundle: dict[str, Any], *, indent: int = 2) -> str:
    return json.dumps(bundle, indent=indent, ensure_ascii=False)


def orifice_network_to_csv(rows: list[dict[str, Any]]) -> str:
    """CSV table of per-hole BCs for spreadsheet / Fluent import."""
    if not rows:
        return "lateral_index,hole_index,station_m,y_along_lateral_m,flow_m3h,velocity_m_s,orifice_d_mm\n"
    cols = [
        "lateral_index", "hole_index", "station_m", "y_along_lateral_m",
        "flow_m3h", "velocity_m_s", "orifice_d_mm",
    ]
    lines = [",".join(cols)]
    for r in rows:
        lines.append(",".join(str(r.get(c, "")) for c in cols))
    return "\n".join(lines) + "\n"


def normalize_cfd_export_format(fmt: str | None) -> str:
    """Map UI/session labels to ``json`` | ``csv_orifices`` (handles legacy display strings)."""
    f = (fmt or "").strip()
    if f in ("json", "csv_orifices"):
        return f
    low = f.lower()
    if "csv" in low and "orifice" in low:
        return "csv_orifices"
    if "json" in low:
        return "json"
    return "json"


def build_cfd_export_bytes(
    bundle: dict[str, Any],
    fmt: str,
) -> tuple[bytes, str, str]:
    """Return (bytes, filename, mime) for json | csv_orifices."""
    fmt = normalize_cfd_export_format(fmt)
    slug = "collector_cfd"
    if fmt == "json":
        return (
            bundle_to_json(bundle).encode("utf-8"),
            f"AQUASIGHT_{slug}.json",
            "application/json",
        )
    if fmt == "csv_orifices":
        return (
            orifice_network_to_csv(list(bundle.get("orifice_network") or [])).encode("utf-8"),
            f"AQUASIGHT_{slug}_orifices.csv",
            "text/csv",
        )
    raise ValueError(f"Unknown CFD export format after normalize: {fmt!r}")
