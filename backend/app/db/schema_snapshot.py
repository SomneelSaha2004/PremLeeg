from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set
import os
import psycopg


ALLOWED_RELATIONS = [
    ("public", "pl_matches"),
    ("public", "pl_team_match"),
    ("public", "pl_season_table"),
    ("public", "pl_player_standard_stats"),
    ("public", "pl_player_standard_stats_latest"),
    ("public", "v_player_career_totals"),
    ("public", "v_player_totals_by_squad"),
    ("public", "v_team_matches"),
    ("public", "v_team_season_summary"),
    # Precomputed streak views (MUST use these for streak questions)
    ("public", "v_team_win_streaks"),
    ("public", "v_team_unbeaten_streaks"),
    ("public", "v_team_unbeaten_streaks_season"),
    ("public", "v_team_clean_sheet_streaks"),
    ("public", "v_team_clean_sheet_streaks_season"),
    ("public", "v_team_scoring_streaks"),
    ("public", "v_team_scoring_streaks_season"),
]


@dataclass
class SchemaSnapshot:
    schema_text: str
    allowed_columns: Dict[str, Set[str]]


def build_schema_snapshot() -> SchemaSnapshot:
    """
    Returns a compact schema string the model can use to write SQL and
    a mapping of allowed columns per relation for validation.
    """
    dsn = os.environ["DATABASE_URL_READONLY"]
    lines: List[str] = []
    lines.append("DATABASE SCHEMA (Postgres):")
    allowed_columns: Dict[str, Set[str]] = {}

    # Disable server-side prepared statements (pgbouncer-safe)
    with psycopg.connect(dsn, autocommit=True, prepare_threshold=None) as conn:
        try:
            conn.prepare_threshold = None
        except Exception:
            pass
        with conn.cursor() as cur:
            for schema, table in ALLOWED_RELATIONS:
                # columns for tables/views
                cur.execute(
                    """
                    select column_name, data_type
                    from information_schema.columns
                    where table_schema=%s and table_name=%s
                    order by ordinal_position;
                    """,
                    (schema, table),
                )
                cols = cur.fetchall()
                if not cols:
                    lines.append(f"- {schema}.{table}: (not found)")
                    allowed_columns[table] = set()
                    continue

                col_str = ", ".join([f"{c} ({t})" for c, t in cols])
                lines.append(f"- {schema}.{table}: {col_str}")
                allowed_columns[table] = {c for c, _ in cols}

    # Add a tiny glossary / rules (this improves NL→SQL a lot)
    lines.append("")
    lines.append("GLOSSARY / RULES:")
    lines.append("1) public.pl_matches (BASE TABLE)")
    lines.append("   - One row per match. Key: match_id, season_start, match_date.")
    lines.append("   - Scores: ft_home_goals, ft_away_goals, ft_result (H/D/A).")
    lines.append("   - Stats: home_shots, away_shots, home_corners, away_corners, home_fouls, away_fouls.")
    lines.append("   - Cards: home_yellow, away_yellow, home_red, away_red.")
    lines.append("   - Use for: Fixtures, results, H2H, team match stats trends.")

    lines.append("2) public.pl_player_standard_stats (BASE TABLE)")
    lines.append("   - One row per player-season-squad. Key: season_start, player, squad.")
    lines.append("   - Stats: performance_gls (goals), performance_ast (assists), performance_crdy/crdr (cards).")
    lines.append("   - Expected: expected_xg, expected_npxg, expected_xag.")
    lines.append("   - Per 90: per90_gls, per90_ast, per90_xg (use with playing_time_min >= 900).")
    lines.append("   - Use for: Top scorers, player comparisons, season stats.")

    lines.append("3) public.pl_player_standard_stats_latest (VIEW)")
    lines.append("   - Same as pl_player_standard_stats but ONLY for the latest season.")
    lines.append("   - Use for: Current season leaderboards.")

    lines.append("4) public.pl_team_match (VIEW)")
    lines.append("   - Two rows per match (one per team). Key: match_id, team.")
    lines.append("   - Columns: result (W/D/L), points, goals_for, goals_against.")
    lines.append("   - Use for: Team form, points accumulation.")

    lines.append("5) public.pl_season_table (VIEW)")
    lines.append("   - Season standings. Key: season_start, team.")
    lines.append("   - Columns: played, wins, draws, losses, gf, ga, gd, points, rank.")
    lines.append("   - Use for: League tables, title winners (rank=1).")

    lines.append("6) public.v_team_matches (VIEW)")
    lines.append("   - Like pl_team_match but includes cards and match stats.")
    lines.append("   - Columns: yellows, reds, result, goals_for, goals_against.")
    lines.append("   - Use for: Team discipline, match-by-match analysis, STREAK CALCULATIONS.")

    lines.append("7) public.v_team_season_summary (VIEW)")
    lines.append("   - Aggregated season totals per team.")
    lines.append("   - Columns: played, wins, draws, losses, goals_for, goals_against, goal_diff, points, yellows, reds.")
    lines.append("   - Use for: Team season records (most goals, fewest conceded, most cards).")
    lines.append("   - CRITICAL: For season RECORDS, add complete-season filter: WHERE played = (SELECT MAX(played) ...)")

    lines.append("8) public.v_player_career_totals (VIEW)")
    lines.append("   - All-time player totals across entire dataset.")
    lines.append("   - Columns: player, goals, assists, minutes.")
    lines.append("   - Use for: All-time leaders, career totals, 'who scored most ever'.")

    lines.append("9) public.v_player_totals_by_squad (VIEW)")
    lines.append("   - Player totals grouped by squad (club).")
    lines.append("   - Columns: squad, player, goals, assists, minutes, pos, nation.")
    lines.append("   - Use for: Club legends, 'top scorer for [club]', player-club records.")

    lines.append("")
    lines.append("=== STREAK VIEWS (PRECOMPUTED - MUST USE FOR STREAK QUESTIONS) ===")
    
    lines.append("10) public.v_team_win_streaks (VIEW)")
    lines.append("   - Precomputed consecutive wins (all-time).")
    lines.append("   - Columns: team, streak_start, streak_end, win_streak.")
    lines.append("   - Use for: 'longest winning streak', 'most consecutive wins'.")

    lines.append("11) public.v_team_unbeaten_streaks (VIEW)")
    lines.append("   - Precomputed consecutive matches without loss (all-time).")
    lines.append("   - Columns: team, streak_start, streak_end, games, wins, draws.")
    lines.append("   - Use for: 'longest unbeaten run', 'invincibles streak'.")

    lines.append("12) public.v_team_unbeaten_streaks_season (VIEW)")
    lines.append("   - Unbeaten streaks scoped to a single season.")
    lines.append("   - Columns: team, season_start, streak_start, streak_end, games, wins, draws.")
    lines.append("   - Use for: 'longest unbeaten run in a season', 'best unbeaten run in 2019/20'.")

    lines.append("13) public.v_team_clean_sheet_streaks (VIEW)")
    lines.append("   - Precomputed consecutive clean sheets (all-time).")
    lines.append("   - Columns: team, streak_start, streak_end, games.")
    lines.append("   - Use for: 'most consecutive clean sheets', 'longest without conceding'.")

    lines.append("14) public.v_team_clean_sheet_streaks_season (VIEW)")
    lines.append("   - Clean sheet streaks scoped to a single season.")
    lines.append("   - Columns: team, season_start, streak_start, streak_end, games.")

    lines.append("15) public.v_team_scoring_streaks (VIEW)")
    lines.append("   - Precomputed consecutive games with a goal scored (all-time).")
    lines.append("   - Columns: team, streak_start, streak_end, games.")
    lines.append("   - Use for: 'longest scoring streak', 'consecutive games scored'.")

    lines.append("16) public.v_team_scoring_streaks_season (VIEW)")
    lines.append("   - Scoring streaks scoped to a single season.")
    lines.append("   - Columns: team, season_start, streak_start, streak_end, games.")

    lines.append("")
    lines.append("CRITICAL RULES:")
    lines.append("- PREFER VIEWS over base tables (precomputed, faster).")
    lines.append("- For 'all-time' player stats → v_player_career_totals")
    lines.append("- For 'club record' player stats → v_player_totals_by_squad")
    lines.append("- For team season aggregates (goals, points, cards) → v_team_season_summary or pl_season_table")
    lines.append("- For STREAK questions → MUST use streak views (v_team_*_streaks), do NOT compute from match data!")
    lines.append("- NEVER use player views for team/club season records!")
    lines.append("- For record queries (most, fewest, biggest), return ALL ties using WHERE metric = (SELECT MAX/MIN ...)")
    lines.append("- For season records, filter to complete seasons only")
    lines.append("- Only use base tables when views lack needed columns (e.g., shots, corners, fouls)")
    lines.append("- There is NO attendance column - do not reference it.")

    return SchemaSnapshot(schema_text="\n".join(lines), allowed_columns=allowed_columns)
