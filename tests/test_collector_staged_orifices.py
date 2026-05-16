"""Staged orifice advisory schedule from orifice_network."""

from engine.collector_staged_orifices import recommend_staged_orifice_schedule


def _minimal_hyd_network(*, d_mm: float = 8.0, construction: str = "Drilled perforated pipe"):
    """Two laterals, three holes each, skewed flows (synthetic)."""
    rows = []
    q_skew = [1.2, 1.0, 0.8]
    a0 = 3.14159 * (d_mm / 1000.0 / 2.0) ** 2
    for li in (1, 2):
        for j, qf in enumerate(q_skew):
            qh = qf * 10.0  # m3/h scale
            q_s = qh / 3600.0
            v = q_s / a0 if a0 > 0 else 0.0
            rows.append({
                "lateral_index": li,
                "hole_index": j + 1,
                "station_m": float(li),
                "y_along_lateral_m": 0.1 * j,
                "flow_m3h": qh,
                "velocity_m_s": round(v, 4),
                "orifice_d_mm": d_mm,
                "construction": construction,
            })
    return {
        "lateral_orifice_d_mm": d_mm,
        "lateral_construction": construction,
        "orifice_network": rows,
    }


def test_staged_inactive_wedge():
    hyd = _minimal_hyd_network(construction="Wedge wire screen")
    out = recommend_staged_orifice_schedule(hyd, n_groups=2)
    assert out["active"] is False
    assert "Wedge" in (out.get("note") or "")


def test_staged_inactive_bad_n_groups():
    hyd = _minimal_hyd_network()
    assert recommend_staged_orifice_schedule(hyd, n_groups=1)["active"] is False
    assert recommend_staged_orifice_schedule(hyd, n_groups=5)["active"] is False


def test_staged_active_groups_and_baseline_d():
    hyd = _minimal_hyd_network(d_mm=6.0)
    out = recommend_staged_orifice_schedule(hyd, n_groups=2)
    assert out["active"] is True
    assert out["baseline_orifice_d_mm"] == 6.0
    assert len(out["groups"]) >= 2
    assert out["groups"][0]["d_mm_recommended"] > 0
    assert "per_hole" in out
    assert len(out["per_hole"]) == 6


def test_staged_uniform_flow_uniform_snap():
    d_mm = 10.0
    rows = []
    for li in (1,):
        for j in range(4):
            qh = 5.0
            a0 = 3.14159 * (d_mm / 1000.0 / 2.0) ** 2
            v = (qh / 3600.0) / a0
            rows.append({
                "lateral_index": 1,
                "hole_index": j + 1,
                "flow_m3h": qh,
                "velocity_m_s": round(v, 4),
                "orifice_d_mm": d_mm,
                "construction": "Drilled perforated pipe",
            })
    hyd = {
        "lateral_orifice_d_mm": d_mm,
        "lateral_construction": "Drilled perforated pipe",
        "orifice_network": rows,
    }
    out = recommend_staged_orifice_schedule(hyd, n_groups=2)
    assert out["active"] is True
    rec_ds = {g["d_mm_recommended"] for g in out["groups"]}
    assert len(rec_ds) == 1
