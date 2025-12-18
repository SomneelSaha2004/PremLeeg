from __future__ import annotations

from typing import Any, Dict, List
from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    summarize: bool = True
    include_rows: bool = True


class QueryResponse(BaseModel):
    sql: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    summary: str
