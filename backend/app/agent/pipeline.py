from __future__ import annotations

import os
from typing import Any, Dict, List

from ..db.client import execute_select
from ..db.schema_snapshot import get_schema_context
from ..llm.client import SQLLLM
from ..models.types import QueryResponse
from .validate_sql import validate_and_sanitize


def run_pipeline(question: str, limit: int | None = 100) -> QueryResponse:
    """
    Structured pipeline:
      1) schema context
      2) generate SQL (LLM placeholder)
      3) validate SQL (SELECT-only, LIMIT)
      4) execute with read-only
      5) summarize (simple for now)
    """
    schema = get_schema_context()

    # Step 2: LLM generation (placeholder returns a safe stub if no DB configured)
    llm = SQLLLM()
    sql_raw = llm.generate_sql(question=question, schema_context=schema, limit=limit)

    # Step 3: Validate & sanitize
    sql = validate_and_sanitize(sql_raw, default_limit=limit or 100)

    # Step 4: Execute (may return empty if DB not configured)
    rows: List[Dict[str, Any]] = []
    explanation = ""
    try:
        rows = execute_select(sql)
    except Exception as e:  # noqa: BLE001
        # Keep running even if DB is not reachable so the flow is testable
        explanation = (
            "Query not executed: database not reachable or credentials missing. "
            f"Detail: {type(e).__name__}"
        )

    # Step 5: Minimal explanation for now
    if not explanation:
        explanation = "Generated and executed SQL based on your question."

    return QueryResponse(sql=sql, rows=rows, explanation=explanation)
