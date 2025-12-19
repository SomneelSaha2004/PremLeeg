from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..context.football_data_notes import FOOTBALL_DATA_NOTES_NON_BETTING


def sql_generation_prompt(question: str, schema_snapshot: str, intent_hint: Optional[str] = None) -> str:
        """
        Prompt-pack style: clear sections + constraints + examples, with a light intent hint
        so the model picks the right table (player vs match/team).
        """
        intent_line = intent_hint or "unknown"
        return f"""
# Role
You are a senior data analyst. You write correct Postgres SQL for analytics.

# Task
Convert the user question into ONE Postgres SQL query.

# Intent hint (use to pick the right table)
- Detected intent: {intent_line}. If player-focused, prefer public.pl_player_standard_stats. If match/team-focused, prefer public.pl_team_match or public.pl_season_table. Only join tables if absolutely required.

# Hard constraints (must follow)
- Output ONLY the SQL (no markdown, no explanation, no backticks).
- Read-only only: SELECT or WITH ... SELECT.
- Single statement only.
- Allowed relations (one relation only; no joins):
    - public.pl_player_standard_stats (player-season stats from FBref)
    - public.pl_player_standard_stats_latest (latest season slice of player stats)
    - public.v_player_career_totals (career totals per player)
    - public.v_player_totals_by_squad (player totals grouped by squad)
    - public.pl_matches (raw match facts)
    - public.pl_team_match (per-team per-match rows)
    - public.v_team_matches (per-team per-match with cards)
    - public.v_team_season_summary (per-team per-season aggregates)
    - public.pl_season_table (season standings)
- No JOIN/UNION/EXCEPT/INTERSECT; use a single relation. Use the prebuilt views above instead of joining.
- Always include LIMIT. Default to LIMIT 50 unless the user explicitly asks for more (never omit LIMIT; keep <= 200 unless user insists).
- Use season_start for seasons. "since YEAR" -> season_start >= YEAR. If a season is named like 2018/2019, use season_start = 2018. If a vague range is given, default to season_start >= 2000. If the user omits seasons, prefer the latest season or a small recent range.
- Avoid window functions and expensive wildcards (prefer exact filters). Avoid ILIKE '%term%'; prefer exact or prefix matches.
- Avoid unnecessary joins; answer from one table when possible.

# Player table guidance (public.pl_player_standard_stats / _latest)
- One row per player-season; unique on (season_start, player, squad).
- performance_* fields are season totals (e.g., performance_gls = goals, performance_ast = assists).
- per90_* fields are per-90 rates; include a minutes floor (e.g., playing_time_min >= 900) when comparing per-90 stats.
- Common filters: season_start, squad (team), pos, playing_time_min.
- Safe aggregates: SUM(performance_gls) for goals, SUM(performance_ast) for assists.
- If the user does not specify a season and wants current stats, prefer public.pl_player_standard_stats_latest.
- For all-time totals, prefer public.v_player_career_totals (by player) or public.v_player_totals_by_squad (by player+squad).

# Match/team guidance
- Standings/champions/rank/points -> public.pl_season_table
- Wins/draws/losses/points per team -> public.pl_team_match or public.v_team_season_summary
- Per-match team stats with cards/goals/result -> public.v_team_matches
- Raw match stats (shots, corners, cards, fouls) -> public.pl_matches

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
LIMIT 50

Example 3:
Question: Who has the most goals in 2018/2019?
SQL:
SELECT player, squad, performance_gls AS goals
FROM public.pl_player_standard_stats
WHERE season_start = 2018
ORDER BY goals DESC
LIMIT 10

Example 4:
Question: Best per-90 goal scorers since 2010 (min 900 minutes)
SQL:
SELECT player, squad, season_start, per90_gls, playing_time_min
FROM public.pl_player_standard_stats
WHERE season_start >= 2010 AND playing_time_min >= 900
ORDER BY per90_gls DESC
LIMIT 20

Example 5:
Question: Latest season top assists (no season provided)
SQL:
SELECT player, squad, performance_ast AS assists
FROM public.pl_player_standard_stats
WHERE season_start = (SELECT MAX(season_start) FROM public.pl_player_standard_stats)
ORDER BY assists DESC
LIMIT 10

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
- Always mention the season scope and the metric used (e.g., goals, assists, xG, per-90).
- If relevant, include a short top-N rundown (player/team, season, metric value) using the returned ordering.
- Be concise: 2–6 sentences.

# Helpful column meanings (non-betting only)
{FOOTBALL_DATA_NOTES_NON_BETTING}

# Data (JSON)
{json.dumps(payload, default=str)}

# Output
Write the final answer in plain English.
""".strip()
