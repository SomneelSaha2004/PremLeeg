from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .prompts import sql_generation_prompt, answer_synthesis_prompt
from .validate_sql import SQLValidationError, validate_and_patch_sql
from ..db.client import PostgresClient, QueryResult
from ..db.schema_snapshot import build_schema_snapshot
from ..llm import OpenAILLM


@dataclass
class PipelineOutput:
    sql: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    summary: str


class AgentPipeline:
    def __init__(self):
        self.db = PostgresClient()
        self.llm = OpenAILLM()

    def run(self, question: str) -> PipelineOutput:
        schema = build_schema_snapshot()
        prompt = sql_generation_prompt(question, schema)

        raw_sql = self.llm.generate_sql(prompt).text.strip()
        try:
            validated = validate_and_patch_sql(raw_sql, limit=200)
        except SQLValidationError as e:
            return PipelineOutput(
                sql=raw_sql,
                columns=[],
                rows=[],
                summary=f"Blocked unsafe/invalid SQL: {e}",
            )

        result: QueryResult = self.db.run_select(validated.sql)

        # IMPORTANT: don't send huge results to the LLM (cost + hallucination risk)
        synthesis_prompt = answer_synthesis_prompt(
            question=question,
            sql=validated.sql,
            columns=result.columns,
            rows=result.rows,
            returned_row_count=len(result.rows),
            max_rows_sent=20,
        )
        summary = self.llm.generate_text(synthesis_prompt).text

        return PipelineOutput(
            sql=validated.sql,
            columns=result.columns,
            rows=result.rows,
            summary=summary,
        )
