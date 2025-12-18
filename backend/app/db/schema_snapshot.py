from __future__ import annotations

from typing import List
import os
import psycopg


ALLOWED_RELATIONS = [
    ("public", "pl_matches"),
    ("public", "pl_team_match"),
    ("public", "pl_season_table"),
    ("public", "pl_player_standard_stats"),
]


def build_schema_snapshot() -> str:
    """
    Returns a compact schema string the model can use to write SQL.
    Keeps it small and focused for cost and accuracy.
    """
    dsn = os.environ["DATABASE_URL_READONLY"]
    lines: List[str] = []
    lines.append("DATABASE SCHEMA (Postgres):")
    with psycopg.connect(dsn, autocommit=True) as conn:
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
                    continue

                col_str = ", ".join([f"{c} ({t})" for c, t in cols])
                lines.append(f"- {schema}.{table}: {col_str}")

    # Add a tiny glossary / rules (this improves NL→SQL a lot)
    lines.append("")
    lines.append("GLOSSARY / RULES:")
    lines.append("- Prefer views for analytics:")
    lines.append("  - public.pl_season_table: season standings (points, rank)")
    lines.append("  - public.pl_team_match: per-team per-match rows (result, points)")
    lines.append("  - public.pl_matches: raw match facts + basic stats")
    lines.append("  - public.pl_player_standard_stats: player-season stats scraped from FBref")
    lines.append("- Player table notes (public.pl_player_standard_stats):")
    lines.append("  - One row per player-season; unique (season_start, player, squad).")
    lines.append("  - Identity: season, season_start, player, nation, pos, squad, age_years, age_days.")
    lines.append("  - Playing time: playing_time_min, playing_time_starts, playing_time_mp, playing_time_90s.")
    lines.append("  - Totals: performance_gls (goals), performance_ast (assists), performance_g_plus_a, performance_pk, performance_pkatt, performance_crdy/crdr.")
    lines.append("  - Expected: expected_xg, expected_npxg, expected_xag, expected_npxg_plus_xag.")
    lines.append("  - Progression: progression_prgc, progression_prgp, progression_prgr.")
    lines.append("  - Per-90 metrics: per90_gls, per90_ast, per90_xg, per90_xag, per90_npxg, per90_g_plus_a, etc.; use with a minutes floor (e.g., playing_time_min >= 900).")
    lines.append("  - Use season_start for season filters (e.g., season_start = 2018 or season_start >= 2010).")
    lines.append("- 'title' or 'champion' means rank = 1 in pl_season_table for that season_start.")
    lines.append("- 'since YEAR' means season_start >= YEAR.")
    lines.append("- If a range is vague, default to season_start >= 2000.")
    lines.append("- Return at most 50 rows by default (use LIMIT) unless the user explicitly asks for full results.")
    return "\n".join(lines)
