"""SQL template patterns for common query types.

These templates demonstrate the correct patterns for:
- Tie-safe record queries (MAX/MIN with subquery)
- Complete-season filtering
- Streak calculations (winning, unbeaten)

IMPORTANT: These are reference templates. The LLM should adapt these patterns
to the specific question, not copy them verbatim.
"""

from __future__ import annotations


# =============================================================================
# PATTERN A: TIE-SAFE RECORD QUERIES
# =============================================================================

# For "biggest", "most", "record" questions - return ALL tied records
TIE_SAFE_MAX_TEMPLATE = """
SELECT {columns}
FROM public.{view}
WHERE {metric} = (
    SELECT MAX({metric})
    FROM public.{view}
    {where_clause}
)
{additional_where}
ORDER BY {order_by} NULLS LAST
LIMIT {limit}
"""

TIE_SAFE_MIN_TEMPLATE = """
SELECT {columns}
FROM public.{view}
WHERE {metric} = (
    SELECT MIN({metric})
    FROM public.{view}
    {where_clause}
)
{additional_where}
ORDER BY {order_by} NULLS LAST
LIMIT {limit}
"""

# Example: Biggest home win
BIGGEST_HOME_WIN = """
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
"""

# Example: Biggest away win
BIGGEST_AWAY_WIN = """
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
"""


# =============================================================================
# PATTERN B: COMPLETE-SEASON FILTER
# =============================================================================

# PL had 42-game seasons (1992-1994) and 38-game seasons (1995+)
# Filter for teams with max games played in their season
COMPLETE_SEASON_FILTER = """
WHERE s.played = (
    SELECT MAX(s2.played)
    FROM public.v_team_season_summary s2
    WHERE s2.season_start = s.season_start
)
"""

# Example: Team with most goals in a complete season
MOST_GOALS_COMPLETE_SEASON = """
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
"""

# Example: Fewest goals conceded in a complete season
FEWEST_CONCEDED_COMPLETE_SEASON = """
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
"""


# =============================================================================
# PATTERN C: WINNING STREAK (consecutive wins)
# =============================================================================

# Uses window function to create streak groups
# Logic: increment group number each time result != 'W'
WINNING_STREAK = """
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
"""


# =============================================================================
# PATTERN D: UNBEATEN STREAK (consecutive non-losses)
# =============================================================================

# Uses window function to create streak groups
# Logic: increment group number each time result = 'L'
UNBEATEN_STREAK = """
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
"""


# =============================================================================
# PATTERN E: LOSING STREAK (consecutive losses)
# =============================================================================

LOSING_STREAK = """
WITH ordered AS (
    SELECT team, match_date, result,
           SUM(CASE WHEN result != 'L' THEN 1 ELSE 0 END) 
               OVER (PARTITION BY team ORDER BY match_date) AS grp
    FROM public.v_team_matches
),
streaks AS (
    SELECT team, grp, COUNT(*) AS streak_len,
           MIN(match_date) AS streak_start, MAX(match_date) AS streak_end
    FROM ordered
    WHERE result = 'L'
    GROUP BY team, grp
)
SELECT team, streak_len, streak_start, streak_end
FROM streaks
WHERE streak_len = (SELECT MAX(streak_len) FROM streaks)
ORDER BY streak_start
LIMIT 20
"""


# =============================================================================
# VIEW SELECTION RUBRIC
# =============================================================================

VIEW_SELECTION_RUBRIC = """
QUESTION TYPE → CORRECT VIEW/TABLE

Match Records (biggest win, highest scoring, most cards in a match):
→ public.pl_matches

Team Season Records (most points, most goals, fewest conceded, most cards in a season):
→ public.v_team_season_summary (has yellows, reds)
→ public.pl_season_table (has gf, ga, gd, points, rank)
NEVER use player views for team/club season records!

Team Discipline (cards per season):
→ public.v_team_season_summary (yellows, reds columns)

Winning Streak:
→ public.v_team_matches with window functions (see WINNING_STREAK pattern)

Unbeaten Streak:
→ public.v_team_matches with window functions (see UNBEATEN_STREAK pattern)

Player Single-Season Records:
→ public.pl_player_standard_stats (with season_start filter)
→ public.pl_player_standard_stats_latest (for current season)

Player Career/All-Time Records:
→ public.v_player_career_totals

Player Records for a Specific Club:
→ public.v_player_totals_by_squad
"""
