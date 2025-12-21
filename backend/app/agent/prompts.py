from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from ..context.football_data_notes import FOOTBALL_DATA_NOTES_NON_BETTING


# =============================================================================
# SHARED CONSTANTS FOR MULTI-QUERY GENERATION
# =============================================================================

STREAK_VS_TOTAL_SECTION = """
# CRITICAL: STREAK vs TOTAL DISTINCTION

STREAK = CONSECUTIVE games meeting a condition (use streak views)
TOTAL/COUNT = Sum or count across a period (use aggregation on match/season views)

## STREAK VIEWS are ONLY for:
- "longest winning streak" / "consecutive wins" / "wins in a row" → v_team_win_streaks
- "longest unbeaten run" / "games without losing" → v_team_unbeaten_streaks
- "consecutive clean sheets" / "clean sheet streak" → v_team_clean_sheet_streaks
- "consecutive games scoring" / "scoring streak" → v_team_scoring_streaks

## DO NOT use streak views for:
- "how many clean sheets" / "total clean sheets" / "most clean sheets" → COUNT on v_team_matches WHERE goals_against = 0
- "how many wins" / "total wins" → SUM on v_team_season_summary or pl_season_table
- "games without a red card" → custom window query on pl_matches (no precomputed view)
- "without winning" / "winless" → NOT the same as unbeaten! Use custom query
- "at the start of season without X" → window function with ordering by match_date

## Examples of WRONG vs RIGHT:

Q: "How many clean sheets did Burnley keep in 2024-25?"
WRONG: SELECT * FROM v_team_clean_sheet_streaks WHERE team = 'Burnley' (this gives STREAK length, not count!)
RIGHT: SELECT team, COUNT(*) AS clean_sheets FROM public.v_team_matches WHERE team = 'Burnley' AND season_start = 2024 AND goals_against = 0 GROUP BY team

Q: "Longest run without a red card"
WRONG: SELECT * FROM v_team_clean_sheet_streaks (wrong view entirely!)
RIGHT: Complex window function query on pl_matches tracking red cards - acknowledge if unsure

Q: "Which club went longest at start of season without winning?"
WRONG: SELECT * FROM v_team_unbeaten_streaks (unbeaten means not losing, NOT winless!)
RIGHT: Window function on v_team_matches checking for result != 'W' from season start, ordered by match_date

Q: "How many clubs have gone a whole season without losing an away match?"
WRONG: SELECT * FROM v_team_unbeaten_streaks (this is overall streaks, not away-specific)
RIGHT: Aggregate on v_team_matches WHERE is_home = false GROUP BY team, season_start HAVING SUM(CASE WHEN result = 'L' THEN 1 ELSE 0 END) = 0
"""

VALID_TEAM_NAMES = """
## VALID TEAM NAMES (use EXACTLY as shown, case-sensitive)
Arsenal, Aston Villa, Barnsley, Birmingham, Blackburn, Blackpool, Bolton, Bournemouth,
Bradford, Brentford, Brighton, Burnley, Cardiff, Charlton, Chelsea, Coventry, Crystal Palace,
Derby, Everton, Fulham, Huddersfield, Hull, Ipswich, Leeds, Leicester, Liverpool, Luton,
Man City, Man United, Middlesbrough, Newcastle, Norwich, Nott'm Forest, Oldham, Portsmouth,
QPR, Reading, Sheffield United, Sheffield Weds, Southampton, Stoke, Sunderland, Swansea,
Swindon, Tottenham, Watford, West Brom, West Ham, Wigan, Wimbledon, Wolves

Common name mappings (use the DB name on the right):
- "Manchester City" → 'Man City'
- "Manchester United" / "Man Utd" → 'Man United'  
- "Nottingham Forest" → 'Nott''m Forest'
- "Sheffield Wednesday" → 'Sheffield Weds'
- "West Bromwich Albion" → 'West Brom'
- "Tottenham Hotspur" / "Spurs" → 'Tottenham'
- "Queens Park Rangers" → 'QPR'
"""


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

## STREAK VIEWS (PRECOMPUTED - MUST USE FOR STREAK QUESTIONS)
- public.v_team_win_streaks: team, streak_start, streak_end, win_streak (consecutive wins, all-time)
- public.v_team_unbeaten_streaks: team, streak_start, streak_end, games, wins, draws (unbeaten runs, all-time)
- public.v_team_unbeaten_streaks_season: team, season_start, streak_start, streak_end, games, wins, draws (unbeaten runs per season)
- public.v_team_clean_sheet_streaks: team, streak_start, streak_end, games (consecutive clean sheets, all-time)
- public.v_team_clean_sheet_streaks_season: team, season_start, streak_start, streak_end, games (clean sheets per season)
- public.v_team_scoring_streaks: team, streak_start, streak_end, games (consecutive games with a goal, all-time)
- public.v_team_scoring_streaks_season: team, season_start, streak_start, streak_end, games (scoring streaks per season)

NOTE: There is NO attendance column anywhere. Do not reference attendance.

## VALID TEAM NAMES (use EXACTLY as shown, case-sensitive)
Arsenal, Aston Villa, Barnsley, Birmingham, Blackburn, Blackpool, Bolton, Bournemouth,
Bradford, Brentford, Brighton, Burnley, Cardiff, Charlton, Chelsea, Coventry, Crystal Palace,
Derby, Everton, Fulham, Huddersfield, Hull, Ipswich, Leeds, Leicester, Liverpool, Luton,
Man City, Man United, Middlesbrough, Newcastle, Norwich, Nott'm Forest, Oldham, Portsmouth,
QPR, Reading, Sheffield United, Sheffield Weds, Southampton, Stoke, Sunderland, Swansea,
Swindon, Tottenham, Watford, West Brom, West Ham, Wigan, Wimbledon, Wolves

Common name mappings (use the DB name on the right):
- "Manchester City" → 'Man City'
- "Manchester United" / "Man Utd" → 'Man United'
- "Nottingham Forest" → 'Nott''m Forest'
- "Sheffield Wednesday" → 'Sheffield Weds'
- "West Bromwich Albion" → 'West Brom'
- "Tottenham Hotspur" / "Spurs" → 'Tottenham'
- "Queens Park Rangers" → 'QPR'

# VIEW SELECTION RUBRIC (MUST FOLLOW)

## CLUB-LEVEL METRICS ROUTING (CRITICAL - PREVENTS KNOWN BUGS)
Use this decision tree for club/team aggregate questions:

1. TITLES/CHAMPIONSHIPS: "titles", "trophies", "seasons won", "won the league", "champions"
   → Use public.pl_season_table with WHERE rank = 1
   → Pattern: SELECT team, COUNT(*) AS titles FROM public.pl_season_table WHERE rank = 1 GROUP BY team ORDER BY titles DESC

2. CLUB SEASON METRICS: "in a season", "single season", "most goals scored by a team", "most points"
   → Use public.v_team_season_summary (PRIMARY DEFAULT FOR CLUB METRICS)
   → Columns: goals_for, goals_against, goal_diff, points, wins, draws, losses, yellows, reds
   → Pattern: SELECT team, season_start, <metric> FROM public.v_team_season_summary ORDER BY <metric> DESC/ASC NULLS LAST LIMIT N

3. CLUB ALL-TIME AGGREGATES: "all-time", "ever", "in history", "total goals scored by a club"
   → Use public.v_team_season_summary with SUM + GROUP BY
   → Pattern: SELECT team, SUM(<metric>) AS total FROM public.v_team_season_summary GROUP BY team ORDER BY total DESC/ASC NULLS LAST

4. PLAYER STATS FOR A CLUB: "most goals for Liverpool", "top scorer for Chelsea"
   → Use public.v_player_totals_by_squad
   → Pattern: SELECT player, goals FROM public.v_player_totals_by_squad WHERE squad = 'ClubName' ORDER BY goals DESC

⚠️ CRITICAL BUG PREVENTION:
- NEVER use v_player_totals_by_squad for CLUB season totals (e.g., "which club scored most goals in a season")
- NEVER use pl_player_standard_stats for CLUB metrics
- The phrase "which club/team" almost always means use v_team_season_summary or pl_season_table

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

## STREAK POLICY (CRITICAL - USE PRECOMPUTED VIEWS)
For streak-related questions, you MUST use the precomputed streak views.
Do NOT attempt to compute streaks from pl_matches, pl_team_match, or v_team_matches.

Streak Intent → Preferred View:
- "winning streak" / "consecutive wins" / "wins in a row" → public.v_team_win_streaks
- "unbeaten" / "invincible" / "without losing" → public.v_team_unbeaten_streaks
- "clean sheets" / "not conceding" / "shutouts" → public.v_team_clean_sheet_streaks
- "scoring streak" / "games scored in" → public.v_team_scoring_streaks

Season-scoped questions (add "_season" suffix):
- "in a season" / "single season" / "2019/20" → use *_season variant (e.g., v_team_unbeaten_streaks_season)

All-time questions:
- "ever" / "all-time" / "in history" → use base streak view (e.g., v_team_unbeaten_streaks)

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

## PATTERN C: STREAK QUERIES (USE PRECOMPUTED VIEWS)
For streaks, ALWAYS use the precomputed streak views. Never compute streaks manually.

Longest winning streak ever:
```sql
SELECT team, win_streak, streak_start, streak_end
FROM public.v_team_win_streaks
WHERE win_streak = (SELECT MAX(win_streak) FROM public.v_team_win_streaks)
ORDER BY streak_start
LIMIT 20
```

Longest unbeaten run ever:
```sql
SELECT team, games, wins, draws, streak_start, streak_end
FROM public.v_team_unbeaten_streaks
WHERE games = (SELECT MAX(games) FROM public.v_team_unbeaten_streaks)
ORDER BY streak_start
LIMIT 20
```

Longest clean sheet streak ever:
```sql
SELECT team, games, streak_start, streak_end
FROM public.v_team_clean_sheet_streaks
WHERE games = (SELECT MAX(games) FROM public.v_team_clean_sheet_streaks)
ORDER BY streak_start
LIMIT 20
```

Longest scoring streak in a season:
```sql
SELECT team, season_start, games, streak_start, streak_end
FROM public.v_team_scoring_streaks_season
WHERE games = (SELECT MAX(games) FROM public.v_team_scoring_streaks_season)
ORDER BY streak_start
LIMIT 20
```

Longest winning streak for a specific team:
```sql
SELECT team, win_streak, streak_start, streak_end
FROM public.v_team_win_streaks
WHERE team ILIKE '%Arsenal%'
ORDER BY win_streak DESC
LIMIT 10
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
- For STREAKS: uses precomputed streak views (v_team_*_streaks), NOT manual computation
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


# =============================================================================
# MULTI-QUERY GENERATION (3 diverse queries in one LLM call)
# =============================================================================

def multi_sql_generation_prompt(
    question: str,
    schema_snapshot: str,
    intent_hint: Optional[str] = None,
    previous_errors: Optional[List[str]] = None,
) -> str:
    """
    Generate 3 diverse SQL queries in a single LLM call.
    Each query uses a different primary table/view approach.
    """
    
    error_section = ""
    if previous_errors:
        error_list = "\n".join(f"- Query {i+1}: {e}" for i, e in enumerate(previous_errors) if e)
        error_section = f"""
# PREVIOUS ERRORS (all queries failed - try completely different approaches)
{error_list}

IMPORTANT: The previous approaches all failed. Try different tables, different logic, different aggregation methods.
"""
    
    return f"""
# ROLE
You are an expert Postgres SQL generator for Premier League analytics.

# TASK
Generate EXACTLY 3 different SQL queries to answer the user's question.
Each query MUST use a different primary table/view to ensure diverse approaches.

# OUTPUT FORMAT (strict JSON array)
Return ONLY a JSON array with exactly 3 objects. No markdown fences, no explanation.
[
  {{"approach": "Brief description of approach 1", "primary_table": "table_name", "sql": "SELECT ..."}},
  {{"approach": "Brief description of approach 2", "primary_table": "table_name", "sql": "SELECT ..."}},
  {{"approach": "Brief description of approach 3", "primary_table": "table_name", "sql": "SELECT ..."}}
]

# DIVERSITY REQUIREMENTS (MUST follow)
- Query 1: Use a PRECOMPUTED VIEW if applicable (v_team_season_summary, v_player_career_totals, pl_season_table, etc.)
- Query 2: Use a BASE TABLE with aggregation/window functions (pl_matches, v_team_matches, pl_player_standard_stats)
- Query 3: Use an ALTERNATIVE approach (different view, CTE, different aggregation logic)

If the question clearly can only be answered one way, still provide 3 queries but vary the columns selected or ordering.

# HARD CONSTRAINTS (apply to ALL 3 queries)
1. Read-only SELECT queries only
2. NO EXPLICIT JOINS - use subqueries, CTEs, window functions instead  
3. Always include LIMIT (default 20)
4. Use NULLS LAST in ORDER BY for nullable columns
5. Schema-qualify all tables: public.<table_or_view>
6. Use exact team names from the valid list below

{STREAK_VS_TOTAL_SECTION}

{VALID_TEAM_NAMES}

# DATABASE SCHEMA
{schema_snapshot}

{error_section}

# User question
{question}

# Output (JSON array only, no markdown, no explanation)
""".strip()


def multi_answer_synthesis_prompt(
    question: str,
    query_results: List[Dict[str, Any]],
    max_rows_per_query: int = 10,
) -> str:
    """
    Synthesize answer from multiple query results.
    Cross-references results and picks the best approach.
    """
    
    results_json = []
    for i, qr in enumerate(query_results):
        results_json.append({
            "query_num": i + 1,
            "approach": qr.get("approach", "unknown"),
            "primary_table": qr.get("primary_table", "unknown"),
            "sql": qr.get("sql", ""),
            "success": qr.get("success", False),
            "error": qr.get("error"),
            "columns": qr.get("columns", []),
            "rows": qr.get("rows", [])[:max_rows_per_query],
            "row_count": qr.get("row_count", 0),
        })
    
    return f"""
# Role
You are a careful data analyst for the Premier League.

# Task
Answer the user's question using results from 3 different SQL query approaches.
Cross-reference the results to find the most reliable answer.

# Rules (MUST follow)
1. Compare results across queries - if they agree, high confidence; if they disagree, investigate why
2. Prefer queries that:
   - Returned data (success=true, row_count > 0)
   - Used the correct table for the question type (see approach/primary_table)
3. IGNORE results from queries that used the WRONG approach:
   - Streak view (v_team_*_streaks) for a "total count" question = WRONG
   - Unbeaten view for a "winless" question = WRONG (unbeaten ≠ winless)
   - Player view for a team question = WRONG
4. If NO query adequately answers the question, say "I couldn't find reliable data for this question" and explain why
5. If data was found, give a direct answer first, then note which approach worked best
6. Be concise but conversational

# Query Results (3 approaches)
{json.dumps(results_json, default=str, indent=2)}

# User Question  
{question}

# Output
Write the final answer in plain English. Start with the direct answer if data was found.
""".strip()
