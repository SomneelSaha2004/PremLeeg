from __future__ import annotations

from typing import List
import os
import psycopg


ALLOWED_RELATIONS = [
    ("public", "pl_matches"),
    ("public", "pl_team_match"),
    ("public", "pl_season_table"),
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
    lines.append("- 'title' or 'champion' means rank = 1 in pl_season_table for that season_start.")
    lines.append("- 'since YEAR' means season_start >= YEAR.")
    lines.append("- Return at most 200 rows (use LIMIT).")
    return "\n".join(lines)
