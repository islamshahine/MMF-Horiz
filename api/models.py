"""Pydantic models for HTTP error payloads (compute body stays a generic JSON object)."""

from typing import List, Optional

from pydantic import BaseModel, Field


class HttpErrorBody(BaseModel):
    """Structured error returned on 4xx/5xx when applicable."""

    detail: str = Field(..., description="Human-readable summary")
    errors: Optional[List[str]] = Field(None, description="Optional validation or engine messages")
