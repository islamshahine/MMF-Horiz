"""HTTP routes — POST /compute delegates to ``engine.compute.compute_all``."""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Body, HTTPException

from engine.compute import compute_all

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
    description="Body must be a JSON object: the same **SI** ``inputs`` dict as ``compute_all`` "
    "(after sidebar ``convert_inputs`` in the Streamlit app). Returns a JSON-serialisable **computed** dict.",
    responses={422: {"description": "Malformed body (not a JSON object)"}},
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
) -> Dict[str, Any]:
    if not isinstance(inputs, dict):
        raise HTTPException(status_code=422, detail="Request body must be a JSON object.")
    try:
        out = compute_all(inputs)
    except Exception as e:
        _LOG.exception("compute_all failed: %s", e)
        raise HTTPException(status_code=500, detail=f"compute_all failed: {type(e).__name__}: {e}") from e
    try:
        return json_safe_computed(out)
    except (TypeError, ValueError) as e:
        _LOG.exception("serialisation failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Response serialisation failed: {e}") from e
