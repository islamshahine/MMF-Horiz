"""
tests/test_process.py
─────────────────────
Tests for engine/process.py — filter_loading() flow distribution.

Reference calculations
----------------------
filter_loading(...) returns ``(standby_count, active_count, flow_per_filter_m3h)`` per row.

filter_loading(total_flow, streams, n_filters, redundancy, hydraulic_assist=0)
  ``n_filters`` = physical installed per stream (includes spares).
  ``hydraulic_assist`` = physical **standby** count excluded from design **N**::

      active = n_filters - hydraulic_assist - x

N scenario (16 physical, 0 standby, 1 stream, 21 000 m³/h):
  active = 16,  flow = 21000 / 16 = 1312.5 m³/h  ✓

N+1 physical (17 filters, 1 standby, assist=1), N case:
  active = 16,  flow = 21000 / 16 = 1312.5 m³/h  ✓

N-1 scenario (16 physical, 0 standby, 1 offline):
  active = 15,  flow = 21000 / 15 = 1400.0 m³/h  ✓

N-2 scenario (2 standby out of 16):
  active = 14,  flow = 21000 / 14 = 1500.0 m³/h  ✓

2-stream, 8 filters/stream, total=21 000 m³/h:
  N:   active = 8,  flow = 21000 / (2×8) = 1312.5 m³/h  ✓
  N-1: active = 7,  flow = 21000 / (2×7) = 1500.0 m³/h  ✓

Single filter (n=1, 1 standby):
  N:   active = 1, flow = 21000.0 m³/h
  N-1: active = 0, flow = 0          ✓

Tolerances: rel=0.001 for exact arithmetic; exact == for counts.
"""
import pytest
from engine.process import filter_loading


# ═════════════════════════════════════════════════════════════════════════════
# N scenario — all filters in service
# ═════════════════════════════════════════════════════════════════════════════

class TestNScenario:

    def test_n_scenario_flow_per_filter(self):
        """
        16 filters, 1 stream, total=21 000 m³/h.
        N scenario: flow = 21000 / 16 = 1312.5 m³/h.
        """
        result = filter_loading(21000, 1, 16, 1)
        n_row = result[0]
        assert n_row[0] == 0                                 # 0 standby
        assert n_row[1] == 16                                # 16 active
        assert n_row[2] == pytest.approx(1312.5, rel=0.001)

    def test_n_scenario_active_count(self):
        """N scenario has all 16 filters active, 0 standby."""
        result = filter_loading(21000, 1, 16, 1)
        standby, active, _ = result[0]
        assert standby == 0
        assert active == 16

    def test_two_stream_n_scenario_flow(self):
        """
        2 streams × 8 filters, total=21 000 m³/h.
        N flow = 21000 / (2×8) = 1312.5 m³/h.
        """
        result = filter_loading(21000, 2, 8, 1)
        n_row = result[0]
        assert n_row[2] == pytest.approx(1312.5, rel=0.001)

    def test_three_streams_n_scenario_flow(self):
        """
        3 streams × 8 filters, total=24 000 m³/h.
        N flow = 24000 / (3×8) = 1000.0 m³/h.
        """
        result = filter_loading(24000, 3, 8, 1)
        assert result[0][2] == pytest.approx(1000.0, rel=0.001)

    def test_zero_redundancy_returns_single_row(self):
        """
        redundancy=0 → only the N scenario row is returned.
        """
        result = filter_loading(21000, 1, 16, 0)
        assert len(result) == 1
        assert result[0][0] == 0    # 0 standby

    def test_flow_times_active_equals_total(self):
        """flow_per_filter × active_count = total_flow (1 stream)."""
        result = filter_loading(21000, 1, 16, 1)
        _, active, flow = result[0]
        assert active * flow == pytest.approx(21000.0, rel=0.001)


# ═════════════════════════════════════════════════════════════════════════════
# N-1 and N-2 scenarios
# ═════════════════════════════════════════════════════════════════════════════

class TestRedundancyScenarios:

    def test_n_minus_1_flow(self):
        """
        16 filters, 1 standby: flow = 21000 / 15 = 1400.0 m³/h.
        """
        result = filter_loading(21000, 1, 16, 1)
        row = result[1]
        assert row[0] == 1                                   # 1 standby
        assert row[1] == 15                                  # 15 active
        assert row[2] == pytest.approx(1400.0, rel=0.001)

    def test_n_minus_2_flow(self):
        """
        16 filters, 2 standby: flow = 21000 / 14 = 1500.0 m³/h.
        """
        result = filter_loading(21000, 1, 16, 2)
        row = result[2]
        assert row[0] == 2                                   # 2 standby
        assert row[1] == 14                                  # 14 active
        assert row[2] == pytest.approx(1500.0, rel=0.001)

    def test_redundancy_2_returns_three_rows(self):
        """redundancy=2 → three scenario rows: N, N-1, N-2."""
        result = filter_loading(21000, 1, 16, 2)
        assert len(result) == 3

    def test_flow_increases_monotonically_with_standby(self):
        """
        Removing filters from service raises flow on the remaining ones.
        N < N-1 < N-2.
        """
        result = filter_loading(21000, 1, 16, 2)
        flows = [row[2] for row in result]
        assert flows[0] < flows[1] < flows[2]

    def test_active_decreases_with_standby(self):
        """Active count decreases by 1 for each additional standby."""
        result = filter_loading(21000, 1, 16, 2)
        actives = [row[1] for row in result]
        assert actives == [16, 15, 14]

    def test_two_stream_n_minus_1_flow(self):
        """
        2 streams × 8 filters, 1 standby: flow = 21000 / (2×7) = 1500.0 m³/h.
        """
        result = filter_loading(21000, 2, 8, 1)
        row = result[1]
        assert row[2] == pytest.approx(1500.0, rel=0.001)


# ═════════════════════════════════════════════════════════════════════════════
# Edge cases
# ═════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_single_filter_n_scenario(self):
        """
        1 filter, 1 stream: N flow = total_flow = 21 000 m³/h.
        """
        result = filter_loading(21000, 1, 1, 1)
        assert result[0][1] == 1
        assert result[0][2] == pytest.approx(21000.0, rel=0.001)

    def test_single_filter_n_minus_1_active_is_zero(self):
        """
        1 filter with 1 standby: N-1 scenario has 0 active filters.
        """
        result = filter_loading(21000, 1, 1, 1)
        assert result[1][1] == 0

    def test_single_filter_n_minus_1_flow_is_zero(self):
        """
        0 active filters → flow per filter = 0.
        """
        result = filter_loading(21000, 1, 1, 1)
        assert result[1][2] == 0

    def test_standby_count_matches_row_index(self):
        """
        Row index i corresponds to i standby filters.
        result[i][0] == i for all rows.
        """
        result = filter_loading(21000, 1, 16, 2)
        for i, row in enumerate(result):
            assert row[0] == i


class TestHydraulicAssist:
    """Physical standby filters: design N = installed − spares (true N+1 bank)."""

    def test_n_plus_one_matches_nominal_n_flow(self):
        """17 physical, 1 spare → design N=16 → same q as 16/0."""
        r = filter_loading(21000, 1, 17, 1, hydraulic_assist=1)[0]
        assert r[0] == 0 and r[1] == 16
        assert r[2] == pytest.approx(1312.5, rel=1e-6)

    def test_n_plus_one_n_minus_1_row(self):
        """With 1 spare, one extra outage → 15 paths."""
        row = filter_loading(21000, 1, 17, 1, hydraulic_assist=1)[1]
        assert row[0] == 1 and row[1] == 15
        assert row[2] == pytest.approx(21000.0 / 15.0, rel=1e-6)
