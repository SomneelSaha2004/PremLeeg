from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..context.football_data_notes import FOOTBALL_DATA_NOTES_NON_BETTING


def sql_generation_prompt(question: str, schema_snapshot: str, intent_hint: Optional[str] = None, previous_error: Optional[str] = None) -> str:
        """
        View-first SQL generation with comprehensive examples and retry support.
        """
        intent_line = intent_hint or "unknown"
        
        error_section = ""
        if previous_error:
            error_section = f"""

# PREVIOUS ERROR (Fix this)
The previous query failed with: {previous_error}

COMMON FIXES:
- "column does not exist" → check schema below, use correct column names, try a different view
- "table does not exist" → use public.<name> prefix or check spelling
- "Joins not allowed" → ensure only ONE relation in FROM clause
- NULL ordering issues → add NULLS LAST to ORDER BY
- Aggregation across seasons → use v_player_career_totals or v_player_totals_by_squad, NOT pl_player_standard_stats
- "team/club most goals in a season" → use v_team_season_summary or pl_season_table, NOT player views
- "returned incomplete season" → add complete-season filter (see CRITICAL PATTERNS)
- "returned only 1 row but ties exist" → use MAX/MIN subquery pattern (see CRITICAL PATTERNS)
"""
        
        return f"""
# ROLE
You are an expert Postgres SQL generator for Premier League analytics.

# TASK
Convert the user question into ONE Postgres SQL query.

# HARD CONSTRAINTS (MUST FOLLOW)
1. Output ONLY SQL (no markdown, no explanations, no backticks)
2. Read-only SELECT queries only
3. NO EXPLICIT JOINS - do NOT use JOIN keyword or comma-joins
4. ALLOWED: subqueries, CTEs (WITH), window functions, UNION ALL, aggregates
5. PREFER VIEWS over base tables (views are precomputed and optimized)
6. Always include LIMIT (default 20 for rankings; higher for record queries with ties)
7. Use NULLS LAST when ordering nullable columns
8. Use COALESCE for nullable numeric aggregates
9. Always schema-qualify: public.<table_or_view>

# DATABASE SCHEMA (Postgres)

## BASE TABLES (use only when views lack needed columns)
- public.pl_matches: match_id, season_start, match_date, home_team, away_team, ft_home_goals, ft_away_goals, ft_result, home_shots, away_shots, home_corners, away_corners, home_fouls, away_fouls, home_yellow, away_yellow, home_red, away_red, referee
- public.pl_player_standard_stats: player_season_id, season_start, player, squad, pos, nation, playing_time_min, playing_time_90s, playing_time_mp, playing_time_starts, performance_gls, performance_ast, performance_g_plus_a, performance_crdy, performance_crdr, expected_xg, expected_npxg, expected_xag, per90_gls, per90_ast

## VIEWS (PREFER THESE - precomputed and optimized)
- public.pl_player_standard_stats_latest: Same as pl_player_standard_stats but ONLY latest season
- public.v_player_career_totals: player, goals, assists, minutes (ALL-TIME totals across entire dataset)
- public.v_player_totals_by_squad: squad, player, goals, assists, minutes, pos, nation (totals per club)
- public.pl_season_table: season_start, team, played, wins, draws, losses, gf, ga, gd, points, rank
- public.v_team_season_summary: season_start, team, played, wins, draws, losses, goals_for, goals_against, goal_diff, points, yellows, reds
- public.v_team_matches: season_start, match_date, team, opponent, is_home, goals_for, goals_against, yellows, reds, result (2 rows per match)
- public.pl_team_match: match_id, season_start, team, opponent, is_home, goals_for, goals_against, result, points (2 rows per match)

NOTE: There is NO attendance column anywhere. Do not reference attendance.

# VIEW SELECTION RUBRIC (MUST FOLLOW)

## Match Records (biggest win, highest scoring, most cards in a match):
→ Use public.pl_matches (only table with shots, corners, fouls, match-level cards)
- "Biggest home win" = MAX(ft_home_goals - ft_away_goals) WHERE ft_result = 'H'
- "Biggest away win" = MAX(ft_away_goals - ft_home_goals) WHERE ft_result = 'A'
- "Highest scoring match" = MAX(ft_home_goals + ft_away_goals)

## Team Season Records (most points, most goals, fewest conceded in a season):
→ Use public.v_team_season_summary OR public.pl_season_table
- pl_season_table has: gf, ga, gd, points, rank
- v_team_season_summary has: goals_for, goals_against, yellows, reds, points
- NEVER use v_player_* views for team/club season aggregates!
- ALWAYS apply complete-season filter (see below)

## Team Discipline (cards per season):
→ Use public.v_team_season_summary (has yellows, reds columns)

## Winning/Losing Streaks:
→ Use public.v_team_matches with window functions (see STREAK PATTERN below)

## Unbeaten Streaks:
→ Use public.v_team_matches with window functions (see UNBEATEN STREAK PATTERN below)

## Player Single-Season Records (most goals in one season):
→ Use public.pl_player_standard_stats with season_start filter
- "Current season" / "this season" → use pl_player_standard_stats_latest

## Player Career/All-Time Records:
→ Use public.v_player_career_totals

## Player Records for a Specific Club:
→ Use public.v_player_totals_by_squad

# CRITICAL PATTERNS (MUST USE)

## PATTERN A: TIE-SAFE RECORD QUERIES
For "biggest", "most", "record", "best", "worst" questions, return ALL tied rows:
```sql
SELECT ...
FROM public.<view>
WHERE <metric> = (SELECT MAX(<metric>) FROM public.<view>)
ORDER BY ... NULLS LAST
LIMIT 20
```
For MIN records (fewest, least, worst):
```sql
SELECT ...
FROM public.<view>
WHERE <metric> = (SELECT MIN(<metric>) FROM public.<view>)
ORDER BY ... NULLS LAST
LIMIT 20
```

## PATTERN B: COMPLETE-SEASON FILTER
PL had both 42-game (1992-1994) and 38-game seasons. Filter for complete seasons:
```sql
SELECT s.*
FROM public.v_team_season_summary s
WHERE s.played = (
    SELECT MAX(s2.played)
    FROM public.v_team_season_summary s2
    WHERE s2.season_start = s.season_start
)
ORDER BY ... NULLS LAST
```

## PATTERN C: WINNING STREAK (consecutive wins)
Use window functions to compute streak groups:
```sql
WITH ordered AS (
    SELECT team, match_date, result,
           SUM(CASE WHEN result != 'W' THEN 1 ELSE 0 END) 
               OVER (PARTITION BY team ORDER BY match_date) AS grp
    FROM public.v_team_matches
),
streaks AS (
    SELECT team, grp, COUNT(*) AS streak_len,
           MIN(match_date) AS streak_start, MAX(match_date) AS streak_end
    FROM ordered
    WHERE result = 'W'
    GROUP BY team, grp
)
SELECT team, streak_len, streak_start, streak_end
FROM streaks
WHERE streak_len = (SELECT MAX(streak_len) FROM streaks)
ORDER BY streak_start
LIMIT 20
```

## PATTERN D: UNBEATEN STREAK (consecutive non-losses)
```sql
WITH ordered AS (
    SELECT team, match_date, result,
           SUM(CASE WHEN result = 'L' THEN 1 ELSE 0 END) 
               OVER (PARTITION BY team ORDER BY match_date) AS grp
    FROM public.v_team_matches
),
streaks AS (
    SELECT team, grp, COUNT(*) AS streak_len,
           MIN(match_date) AS streak_start, MAX(match_date) AS streak_end
    FROM ordered
    WHERE result != 'L'
    GROUP BY team, grp
)
SELECT team, streak_len, streak_start, streak_end
FROM streaks
WHERE streak_len = (SELECT MAX(streak_len) FROM streaks)
ORDER BY streak_start
LIMIT 20
```

# Column reference (non-betting only)
{FOOTBALL_DATA_NOTES_NON_BETTING}

# Database schema & Glossary
{schema_snapshot}

# EXAMPLES

## Ex1: Biggest home win ever (TIE-SAFE)
SELECT match_date, home_team, away_team, ft_home_goals, ft_away_goals,
       (ft_home_goals - ft_away_goals) AS margin
FROM public.pl_matches
WHERE ft_result = 'H'
  AND (ft_home_goals - ft_away_goals) = (
      SELECT MAX(ft_home_goals - ft_away_goals)
      FROM public.pl_matches
      WHERE ft_result = 'H'
  )
ORDER BY match_date
LIMIT 20

## Ex2: Biggest away win ever (TIE-SAFE)
SELECT match_date, home_team, away_team, ft_home_goals, ft_away_goals,
       (ft_away_goals - ft_home_goals) AS margin
FROM public.pl_matches
WHERE ft_result = 'A'
  AND (ft_away_goals - ft_home_goals) = (
      SELECT MAX(ft_away_goals - ft_home_goals)
      FROM public.pl_matches
      WHERE ft_result = 'A'
  )
ORDER BY match_date
LIMIT 20

## Ex3: Team with most goals in a single season (COMPLETE-SEASON + TIE-SAFE)
SELECT s.team, s.season_start, s.goals_for
FROM public.v_team_season_summary s
WHERE s.played = (
    SELECT MAX(s2.played)
    FROM public.v_team_season_summary s2
    WHERE s2.season_start = s.season_start
)
AND s.goals_for = (
    SELECT MAX(s3.goals_for)
    FROM public.v_team_season_summary s3
    WHERE s3.played = (
        SELECT MAX(s4.played)
        FROM public.v_team_season_summary s4
        WHERE s4.season_start = s3.season_start
    )
)
ORDER BY s.season_start
LIMIT 20

## Ex4: Fewest goals conceded in a season (COMPLETE-SEASON + TIE-SAFE)
SELECT s.team, s.season_start, s.goals_against
FROM public.v_team_season_summary s
WHERE s.played = (
    SELECT MAX(s2.played)
    FROM public.v_team_season_summary s2
    WHERE s2.season_start = s.season_start
)
AND s.goals_against = (
    SELECT MIN(s3.goals_against)
    FROM public.v_team_season_summary s3
    WHERE s3.played = (
        SELECT MAX(s4.played)
        FROM public.v_team_season_summary s4
        WHERE s4.season_start = s3.season_start
    )
)
ORDER BY s.season_start
LIMIT 20

## Ex5: All-time Premier League top scorers
SELECT player, goals, assists, minutes
FROM public.v_player_career_totals
ORDER BY goals DESC NULLS LAST
LIMIT 20

## Ex6: Liverpool's all-time top scorer
SELECT player, goals, assists, minutes
FROM public.v_player_totals_by_squad
WHERE squad = 'Liverpool'
ORDER BY goals DESC NULLS LAST
LIMIT 1

## Ex7: Most goals by a player in a single season (TIE-SAFE)
SELECT player, squad, season_start, performance_gls AS goals
FROM public.pl_player_standard_stats
WHERE performance_gls = (
    SELECT MAX(performance_gls)
    FROM public.pl_player_standard_stats
)
ORDER BY season_start
LIMIT 20

## Ex8: Most yellow cards by a team in a season (COMPLETE-SEASON + TIE-SAFE)
SELECT s.team, s.season_start, s.yellows
FROM public.v_team_season_summary s
WHERE s.played = (
    SELECT MAX(s2.played)
    FROM public.v_team_season_summary s2
    WHERE s2.season_start = s.season_start
)
AND s.yellows = (
    SELECT MAX(s3.yellows)
    FROM public.v_team_season_summary s3
    WHERE s3.played = (
        SELECT MAX(s4.played)
        FROM public.v_team_season_summary s4
        WHERE s4.season_start = s3.season_start
    )
)
ORDER BY s.season_start
LIMIT 20

## Ex9: Highest scoring match ever (TIE-SAFE)
SELECT match_date, home_team, away_team, ft_home_goals, ft_away_goals,
       (ft_home_goals + ft_away_goals) AS total_goals
FROM public.pl_matches
WHERE (ft_home_goals + ft_away_goals) = (
    SELECT MAX(ft_home_goals + ft_away_goals)
    FROM public.pl_matches
)
ORDER BY match_date
LIMIT 20

## Ex10: Premier League champions since 2010
SELECT season_start, team, points
FROM public.pl_season_table
WHERE season_start >= 2010 AND rank = 1
ORDER BY season_start
LIMIT 20

{error_section}

# Self-check before final output
Confirm your SQL:
- Uses allowed relations only
- Uses correct view for the question type (team vs player, season vs career)
- For team season records: uses v_team_season_summary or pl_season_table (NOT player views)
- For record queries: returns ALL ties with MAX/MIN subquery pattern
- For season records: applies complete-season filter
- For streaks: uses window function pattern
- Includes LIMIT
- Is valid Postgres
- Uses NULLS LAST in ORDER BY when ordering by nullable columns
- Does NOT reference non-existent columns (e.g., attendance)

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
You are a helpful and precise data analyst for the Premier League.

# Task
Answer the user's question using ONLY the SQL results provided.

# Rules (must follow)
- Use only the provided rows/columns. If no rows, say "No data found matching your criteria."
- Do NOT invent numbers, teams, or seasons not present in the data.
- If results are truncated (returned_row_count > max_rows_sent), mention that these are the top results.
- Always mention the season scope (e.g., "In the 2023/24 season...") and the metric used.
- Provide a direct answer first, then supporting details (e.g., "The top scorer was Erling Haaland with 36 goals.").
- If the SQL query seems to have failed to answer the specific nuance of the question (e.g., asked for "all time" but SQL only checked one season), mention this limitation politely.
- Be concise but conversational.

# Helpful column meanings (non-betting only)
{FOOTBALL_DATA_NOTES_NON_BETTING}

# Data (JSON)
{json.dumps(payload, default=str)}

# Output
Write the final answer in plain English.
""".strip()
