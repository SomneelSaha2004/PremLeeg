from __future__ import annotations

import json
from typing import Any, Dict, List

from app.context.football_data_notes import FOOTBALL_DATA_NOTES_NON_BETTING


def sql_generation_prompt(question: str, schema_snapshot: str) -> str:
    """
    Prompt-pack style: clear sections + constraints + tiny examples.
    Based on OpenAI guidance to structure prompts and keep instructions clear. :contentReference[oaicite:3]{index=3}
    """
    return f"""
# Role
You are a senior data analyst. You write correct Postgres SQL for analytics.

# Task
Convert the user question into ONE Postgres SQL query.

# Hard constraints (must follow)
- Output ONLY the SQL (no markdown, no explanation, no backticks).
- Read-only only: SELECT or WITH ... SELECT.
- Single statement only.
- Use ONLY these relations:
  - public.pl_matches
  - public.pl_team_match
  - public.pl_season_table
- Always include LIMIT <= 200.
- Prefer the views:
  - standings/champions/rank/points -> public.pl_season_table
  - wins/draws/losses/points per team -> public.pl_team_match
  - raw match stats (shots, corners, cards, fouls) -> public.pl_matches

# Column reference (non-betting only)
{FOOTBALL_DATA_NOTES_NON_BETTING}

# Database schema
{schema_snapshot}

# Examples (pattern only — adapt to question)
Example 1:
Question: Top 5 teams by total wins since 2000
SQL:
SELECT team, COUNT(*) AS wins
FROM public.pl_team_match
WHERE season_start >= 2000 AND result = 'W'
GROUP BY team
ORDER BY wins DESC
LIMIT 5

Example 2:
Question: Champions by season since 2010
SQL:
SELECT season_start, team
FROM public.pl_season_table
WHERE season_start >= 2010 AND rank = 1
ORDER BY season_start
LIMIT 200

# Self-check before final output
Confirm your SQL:
- uses allowed relations only
- includes LIMIT
- is valid Postgres
- answers the question precisely

# User question
{question}
""".strip()


def answer_synthesis_prompt(
    question: str,
    sql: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    returned_row_count: int,
    max_rows_sent: int = 20,
) -> str:
    """
    Prompt-pack style answer synthesis: grounded + concise + avoids global claims on truncated results.
    """
    payload = {
        "question": question,
        "sql": sql,
        "columns": columns,
        "rows": rows[:max_rows_sent],
        "returned_row_count": returned_row_count,
        "note": (
            f"Only the first {max_rows_sent} rows are shown if the result is larger. "
            "Do not claim global facts unless the SQL guarantees it (e.g., ORDER BY ... LIMIT)."
        ),
    }

    return f"""
# Role
You are a careful data analyst.

# Task
Answer the user's question using ONLY the SQL results provided.

# Rules (must follow)
- Use only the provided rows/columns. If no rows, say no data returned.
- Do NOT invent numbers, teams, or seasons not present.
- If results may be truncated, avoid global claims unless the SQL guarantees top results.
- Be concise: 2–6 sentences.

# Helpful column meanings (non-betting only)
{FOOTBALL_DATA_NOTES_NON_BETTING}

# Data (JSON)
{json.dumps(payload, default=str)}

# Output
Write the final answer in plain English.
""".strip()
