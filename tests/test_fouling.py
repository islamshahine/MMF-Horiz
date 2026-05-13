"""Tests for engine/fouling.py — monotone empirical trends."""
import pytest

from engine.fouling import (
    estimate_bw_frequency,
    estimate_fouling_severity,
    estimate_run_time,
    estimate_solids_loading,
)


def test_higher_sdi_shorter_run_time():
    base = dict(mfi_index=2.0, tss_mg_l=10.0, lv_m_h=10.0)
    t_low = estimate_run_time(sdi15=1.0, **base)["run_time_h"]
    t_high = estimate_run_time(sdi15=8.0, **base)["run_time_h"]
    assert t_high < t_low


def test_higher_tss_higher_solids_loading():
    base = dict(lv_m_h=10.0, sdi15=3.0, mfi_index=2.0)
    m_low = estimate_solids_loading(tss_mg_l=5.0, **base)["solid_loading_kg_m2"]
    m_high = estimate_solids_loading(tss_mg_l=30.0, **base)["solid_loading_kg_m2"]
    assert m_high > m_low


def test_low_sdi_lower_bw_frequency():
    """Lower SDI ⇒ longer run ⇒ fewer BW cycles per day (same other inputs)."""
    base = dict(mfi_index=2.0, tss_mg_l=10.0, lv_m_h=10.0)
    rt_clean = estimate_run_time(sdi15=1.0, **base)["run_time_h"]
    rt_dirty = estimate_run_time(sdi15=7.0, **base)["run_time_h"]
    f_clean = estimate_bw_frequency(run_time_h=rt_clean)["bw_cycles_per_day"]
    f_dirty = estimate_bw_frequency(run_time_h=rt_dirty)["bw_cycles_per_day"]
    assert rt_clean > rt_dirty
    assert f_clean < f_dirty


def test_high_sdi_emits_warning():
    out = estimate_solids_loading(tss_mg_l=10.0, lv_m_h=10.0, sdi15=6.5, mfi_index=2.0)
    assert any("SDI15" in w for w in out["warnings"])


def test_severity_increases_with_indices():
    a = estimate_fouling_severity(sdi15=1.0, mfi_index=1.0, tss_mg_l=5.0, lv_m_h=8.0)
    b = estimate_fouling_severity(sdi15=4.0, mfi_index=4.0, tss_mg_l=20.0, lv_m_h=12.0)
    assert b["score"] > a["score"]


def test_bw_frequency_monotone_in_run_time():
    f1 = estimate_bw_frequency(run_time_h=20.0)["bw_cycles_per_day"]
    f2 = estimate_bw_frequency(run_time_h=10.0)["bw_cycles_per_day"]
    assert f2 > f1
