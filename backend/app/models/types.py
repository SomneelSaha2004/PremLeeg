from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., description="Natural language question")
    limit: Optional[int] = Field(default=100, description="Max rows to return")


class QueryResponse(BaseModel):
    sql: str
    rows: List[Dict[str, Any]]
    explanation: str = ""
