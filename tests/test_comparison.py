"""Tests for engine/comparison.py — diff_value, compare_designs, metrics."""
import pytest

from engine.comparison import COMPARISON_METRICS, compare_designs, diff_value


class TestDiffValue:
    def test_significant_difference(self):
        d = diff_value(100.0, 115.0, threshold_pct=5.0)
        assert d["is_significant"] is True
        assert d["pct_diff"] == pytest.approx(15.0)
        assert d["direction"] == "higher"

    def test_insignificant_difference(self):
        d = diff_value(100.0, 103.0, threshold_pct=5.0)
        assert d["is_significant"] is False
        assert d["direction"] == "same"
        assert d["favours"] == "equal"

    def test_higher_is_better_favours_b(self):
        d = diff_value(30.0, 45.0, threshold_pct=5.0, higher_is_better=True)
        assert d["favours"] == "B"

    def test_higher_is_worse_favours_a(self):
        d = diff_value(100.0, 120.0, threshold_pct=5.0, higher_is_better=False)
        assert d["favours"] == "A"

    def test_none_values_no_crash(self):
        d = diff_value(None, 100.0)
        assert d["abs_diff"] is None
        assert d["pct_diff"] is None

    def test_zero_base_no_crash(self):
        d = diff_value(0.0, 100.0)
        assert d["pct_diff"] == 0.0

    def test_exact_match(self):
        d = diff_value(100.0, 100.0, threshold_pct=1.0)
        assert d["direction"] == "same"
        assert d["favours"] == "equal"
        assert d["abs_diff"] == pytest.approx(0.0)


class TestCompareDesigns:
    def test_empty_dicts_no_crash(self):
        r = compare_designs({}, {}, "A", "B")
        assert "metrics" in r
        assert "summary" in r
        assert isinstance(r["metrics"], list)

    def test_labels_preserved(self):
        r = compare_designs({}, {}, "Conservative", "Optimistic")
        assert r["label_a"] == "Conservative"
        assert r["label_b"] == "Optimistic"

    def test_metric_count(self):
        r = compare_designs({}, {})
        assert len(r["metrics"]) == len(COMPARISON_METRICS)

    def test_identical_designs_no_winner(self):
        computed = {
            "q_per_filter": 1312.5,
            "filt_cycles": {"N": {"lv_m_h": 10.0}},
            "real_id": 5.492,
            "cyl_len": 21.55,
            "w_total": 85000,
            "bw_dp": {"dp_clean_bar": 0.025, "dp_dirty_bar": 0.51},
            "bw_hyd": {"q_bw_m3h": 3600},
            "bw_col": {"max_safe_bw_m_h": 55.0, "freeboard_m": 1.3},
            "bw_exp": {"total_expansion_pct": 4.7},
            "econ_capex": {"total_capex_usd": 2000000},
            "econ_opex": {"total_opex_usd_yr": 150000},
        }
        r = compare_designs(computed, computed)
        assert r["overall_winner"] == "equal"
        assert r["n_significant"] == 0

    def test_different_capex_detected(self):
        a = {"econ_capex": {"total_capex_usd": 1000000}}
        b = {"econ_capex": {"total_capex_usd": 1200000}}
        r = compare_designs(a, b)
        capex_row = next(m for m in r["metrics"] if "CAPEX" in m["label"])
        assert capex_row["is_significant"] is True
        assert capex_row["favours"] == "A"

    def test_summary_is_string(self):
        r = compare_designs({}, {})
        assert isinstance(r["summary"], str)
        assert len(r["summary"]) > 0


class TestComparisonMetrics:
    def test_all_metrics_have_required_fields(self):
        assert len(COMPARISON_METRICS) >= 10
        for entry in COMPARISON_METRICS:
            assert len(entry) == 7, f"Metric entry wrong length: {entry}"
            label, key, sub, qty, dec, hib, thresh = entry
            assert isinstance(label, str)
            assert isinstance(key, str)
            assert isinstance(sub, (str, type(None), tuple))
            assert isinstance(dec, int)
            assert isinstance(hib, bool)
            assert isinstance(thresh, float)
            assert thresh > 0
