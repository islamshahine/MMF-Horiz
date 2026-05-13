"""
Public design-comparison API for AQUASIGHT™ MMF.

The numeric metric matrix lives in ``engine.comparison`` (``compare_designs``,
``diff_value``, ``COMPARISON_METRICS``). This module adds playbook-facing names
and small helpers so imports can use ``engine.compare`` without duplicating logic.
"""

from __future__ import annotations

from typing import Any, Optional

from engine.comparison import COMPARISON_METRICS, compare_designs, diff_value

# Playbook alias: same behaviour as ``diff_value``.
compare_numeric = diff_value

# Lower rank = lower operational risk (better).
_SEVERITY_RANK = {
    "STABLE": 0,
    "MARGINAL": 1,
    "ELEVATED": 2,
    "CRITICAL": 3,
}


def compare_severity(
    severity_a: Optional[str],
    severity_b: Optional[str],
) -> dict[str, Any]:
    """
    Compare two ``overall_risk``-style labels from ``computed``.

    Returns
    -------
    dict with keys:
        severity_a, severity_b, rank_a, rank_b,
        better: "A" | "B" | None,
        same: bool
    """
    out: dict[str, Any] = {
        "severity_a": severity_a,
        "severity_b": severity_b,
        "rank_a": None,
        "rank_b": None,
        "better": None,
        "same": False,
    }
    if not severity_a and not severity_b:
        out["same"] = True
        return out
    ra = _SEVERITY_RANK.get(str(severity_a).strip().upper()) if severity_a else None
    rb = _SEVERITY_RANK.get(str(severity_b).strip().upper()) if severity_b else None
    out["rank_a"], out["rank_b"] = ra, rb
    if ra is None or rb is None:
        return out
    if ra == rb:
        out["same"] = True
        return out
    out["better"] = "A" if ra < rb else "B"
    return out


def generate_delta_summary(compare_designs_result: dict) -> str:
    """Return the human-readable summary string from a ``compare_designs`` result."""
    s = compare_designs_result.get("summary")
    return s if isinstance(s, str) else ""


__all__ = [
    "COMPARISON_METRICS",
    "compare_designs",
    "diff_value",
    "compare_numeric",
    "compare_severity",
    "generate_delta_summary",
]
