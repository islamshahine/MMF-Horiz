"""HTTP routes — POST /compute delegates to ``engine.compute.compute_all``."""

from __future__ import annotations

import copy
import json
import logging
from typing import Annotated, Any, Dict, Literal

from fastapi import APIRouter, Body, HTTPException, Query

from engine.compute import compute_all
from engine.units import convert_inputs

_LOG = logging.getLogger("aquasight.api")

# Same exclusions as SQLite snapshot serialisation (non-JSON / tab callables).
_COMPUTED_EXCLUDE = frozenset({"lv_severity_fn", "ebct_severity_fn"})


def json_safe_computed(computed: Dict[str, Any]) -> Dict[str, Any]:
    """Drop callables and round-trip through JSON for numpy/datetime etc."""
    slim = {
        k: v
        for k, v in computed.items()
        if k not in _COMPUTED_EXCLUDE and not callable(v)
    }
    return json.loads(json.dumps(slim, default=str))


router = APIRouter(tags=["compute"])


@router.post(
    "/compute",
    summary="Run full MMF engineering compute",
    description=(
        "Body: JSON object of **inputs** passed to ``engine.compute.compute_all`` after optional "
        "unit conversion.\n\n"
        "* ``unit_system=metric`` (default): numeric fields are **SI** (same contract as the "
        "Streamlit app after the sidebar builds the inputs dict).\n"
        "* ``unit_system=imperial``: numeric fields use **US customary display** units where "
        "``engine.units.INPUT_QUANTITY_MAP`` applies (e.g. ``total_flow`` in gpm, lengths in ft / "
        "in, pressures in psi). The server runs ``engine.units.convert_inputs`` before compute."
    ),
    responses={422: {"description": "Malformed body or invalid query parameters"}},
)
def post_compute(
    inputs: Annotated[
        Dict[str, Any],
        Body(
            ...,
            openapi_examples={
                "minimal_note": {
                    "summary": "Use a full project export or integration test inputs",
                    "value": {"project_name": "API", "doc_number": "1", "total_flow": 21000.0},
                }
            },
        ),
    ],
    unit_system: Annotated[
        Literal["metric", "imperial"],
        Query(
            description=(
                "Physical units of numeric fields in the JSON body. "
                "`metric` (default): SI. `imperial`: converted to SI via `convert_inputs` before compute."
            ),
        ),
    ] = "metric",
) -> Dict[str, Any]:
    if not isinstance(inputs, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    work = copy.deepcopy(inputs)
    si_inputs = convert_inputs(work, unit_system)
    try:
        out = compute_all(si_inputs)
    except Exception as e:
        _LOG.exception("compute_all failed: %s", e)
        raise HTTPException(status_code=500, detail=f"compute_all failed: {type(e).__name__}: {e}") from e
    try:
        return json_safe_computed(out)
    except (TypeError, ValueError) as e:
        _LOG.exception("serialisation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Response serialisation failed: {e}") from e
