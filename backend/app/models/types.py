from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class QueryAttemptTrace(BaseModel):
    attempt: int
    raw_sql: Optional[str] = None
    validated_sql: Optional[str] = None
    warning: Optional[str] = None
    error: Optional[str] = None
    row_count: Optional[int] = None
    outcome: str
    retry_reason: Optional[str] = None


class QueryRequest(BaseModel):
    question: str
    summarize: bool = True
    include_rows: bool = True


class QueryResponse(BaseModel):
    sql: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    summary: str
    retry_token: Optional[str] = None
    retry_reason: Optional[str] = None

    # Debug/trace fields for the demo UI (lets the frontend show retries, warnings, etc.)
    attempt_count: Optional[int] = None
    trace: Optional[List[QueryAttemptTrace]] = None
