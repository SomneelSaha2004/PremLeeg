from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .prompts import sql_generation_prompt, answer_synthesis_prompt
from .validate_sql import SQLValidationError, validate_and_patch_sql
from ..db.client import PostgresClient, QueryResult
from ..db.schema_snapshot import build_schema_snapshot
from ..llm import OpenAILLM


PLAYER_KEYWORDS = {
    "player",
    "players",
    "scorer",
    "goals",
    "assists",
    "xg",
    "npxg",
    "xag",
    "per90",
    "per 90",
    "per-90",
    "minutes",
    "per 90s",
}

MATCH_KEYWORDS = {
    "match",
    "matches",
    "game",
    "games",
    "wins",
    "losses",
    "draws",
    "points",
    "table",
    "standing",
    "standings",
    "rank",
    "home",
    "away",
}


def classify_intent(question: str) -> str:
    """Lightweight keyword intent classifier to steer table choice."""
    q = question.lower()
    player_score = sum(1 for kw in PLAYER_KEYWORDS if kw in q)
    match_score = sum(1 for kw in MATCH_KEYWORDS if kw in q)
    if player_score == 0 and match_score == 0:
        return "unknown"
    return "player" if player_score >= match_score else "match"


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

    def run(
        self,
        question: str,
        summarize: bool = True,
        include_rows: bool = True,
        raise_on_error: bool = False,
    ) -> PipelineOutput:
        schema = build_schema_snapshot()
        intent = classify_intent(question)
        prompt = sql_generation_prompt(question, schema.schema_text, intent_hint=intent)

        raw_sql = self.llm.generate_sql(prompt).text.strip()
        try:
            validated = validate_and_patch_sql(raw_sql, limit=50, allowed_columns=schema.allowed_columns)
        except SQLValidationError as e:
            if raise_on_error:
                raise
            return PipelineOutput(
                sql=raw_sql,
                columns=[],
                rows=[],
                summary=f"Blocked unsafe/invalid SQL: {e}",
            )

        try:
            result: QueryResult = self.db.run_select(validated.sql)
        except Exception as db_exc:
            if raise_on_error:
                raise
            return PipelineOutput(
                sql=validated.sql,
                columns=[],
                rows=[],
                summary=f"Database error: {db_exc}",
            )

        summary = ""
        if summarize:
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
            rows=result.rows if include_rows else [],
            summary=summary,
        )
