from __future__ import annotations

import json
from typing import Any, Dict, List

from ..context.football_data_notes import FOOTBALL_DATA_NOTES_NON_BETTING


def sql_generation_prompt(question: str, schema_snapshot: str) -> str:
    return f"""
You are a senior data analyst writing Postgres SQL.

GOAL:
Convert the user's question into ONE Postgres SQL query to answer it.

HARD RULES:
- Output ONLY SQL. No markdown, no explanation, no backticks.
- Read-only only: SELECT or WITH ... SELECT.
- Single statement only.
- Use only these relations:
  - public.pl_matches
  - public.pl_team_match
  - public.pl_season_table
- Always include LIMIT <= 200.
- Prefer views for analytics:
  - public.pl_season_table for standings / champions / ranks / points.
  - public.pl_team_match for wins/draws/losses, points, per-team match rows.
  - public.pl_matches for raw match stats (shots, cards, corners, fouls, goals).

COLUMN MEANINGS (from football-data notes; NON-BETTING ONLY):
{FOOTBALL_DATA_NOTES_NON_BETTING}

DATABASE SCHEMA:
{schema_snapshot}

USER QUESTION:
{question}
""".strip()


def answer_synthesis_prompt(
    question: str,
    sql: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    max_rows: int = 20,
) -> str:
    """Summarize query results into a grounded natural-language answer."""
    safe_rows = rows[:max_rows]
    payload = {
        "question": question,
        "sql": sql,
        "columns": columns,
        "rows": safe_rows,
    }

    return f"""
You are a data analyst answering the user's question based ONLY on the SQL query results provided.

RULES:
- Use only the provided rows/columns. If the result is empty, say you found no data.
- Do NOT invent numbers, teams, seasons, or facts not present in the rows.
- Be concise but clear (2-6 sentences).
- If the query returns a ranking/table, mention the top entries.

Helpful column meanings (NON-BETTING ONLY):
{FOOTBALL_DATA_NOTES_NON_BETTING}

QUERY RESULTS (JSON):
{json.dumps(payload, default=str)}

Write the answer now:
""".strip()
