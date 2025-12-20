from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

import sqlglot
from sqlglot import exp

from .club_metrics_routing import (
    ClubMetricIntent,
    route_club_metric,
    validate_club_source_selection,
    get_club_metric_hint,
)


BANNED_REGEX = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|call|do)\b",
    re.IGNORECASE,
)

# Detect explicit JOIN keywords
JOIN_REGEX = re.compile(
    r"\b(inner\s+join|left\s+join|right\s+join|full\s+join|cross\s+join|natural\s+join|join)\b",
    re.IGNORECASE,
)

ALLOWED_TABLES: Set[str] = {
    "pl_matches",
    "pl_team_match",
    "pl_season_table",
    "pl_player_standard_stats",
    "pl_player_standard_stats_latest",
    "v_player_career_totals",
    "v_player_totals_by_squad",
    "v_team_matches",
    "v_team_season_summary",
    # Streak views (precomputed - prefer these for streak questions)
    "v_team_win_streaks",
    "v_team_unbeaten_streaks",
    "v_team_unbeaten_streaks_season",
    "v_team_clean_sheet_streaks",
    "v_team_clean_sheet_streaks_season",
    "v_team_scoring_streaks",
    "v_team_scoring_streaks_season",
}

# Views that are PLAYER-focused (should NOT be used for team/club season aggregates)
PLAYER_VIEWS: Set[str] = {
    "v_player_career_totals",
    "v_player_totals_by_squad",
    "pl_player_standard_stats",
    "pl_player_standard_stats_latest",
}

# Views that are TEAM-focused (should be used for team/club season aggregates)
TEAM_VIEWS: Set[str] = {
    "pl_season_table",
    "v_team_season_summary",
    "v_team_matches",
    "pl_team_match",
}

# Precomputed streak views (MUST use these for streak questions)
STREAK_VIEWS: Set[str] = {
    "v_team_win_streaks",
    "v_team_unbeaten_streaks",
    "v_team_unbeaten_streaks_season",
    "v_team_clean_sheet_streaks",
    "v_team_clean_sheet_streaks_season",
    "v_team_scoring_streaks",
    "v_team_scoring_streaks_season",
}

# Streak intent keywords and their preferred views
STREAK_INTENT_MAP: Dict[str, str] = {
    # Win streak keywords
    "winning streak": "v_team_win_streaks",
    "win streak": "v_team_win_streaks",
    "consecutive wins": "v_team_win_streaks",
    "wins in a row": "v_team_win_streaks",
    "longest win": "v_team_win_streaks",
    # Unbeaten streak keywords
    "unbeaten": "v_team_unbeaten_streaks",
    "invincible": "v_team_unbeaten_streaks",
    "without losing": "v_team_unbeaten_streaks",
    "undefeated": "v_team_unbeaten_streaks",
    "not lost": "v_team_unbeaten_streaks",
    # Clean sheet streak keywords
    "clean sheet": "v_team_clean_sheet_streaks",
    "clean sheets": "v_team_clean_sheet_streaks",
    "not conceding": "v_team_clean_sheet_streaks",
    "without conceding": "v_team_clean_sheet_streaks",
    "shutout": "v_team_clean_sheet_streaks",
    "shutouts": "v_team_clean_sheet_streaks",
    # Scoring streak keywords
    "scoring streak": "v_team_scoring_streaks",
    "consecutive games scored": "v_team_scoring_streaks",
    "games scored in": "v_team_scoring_streaks",
    "scoring run": "v_team_scoring_streaks",
}

# Keywords that indicate team/club season aggregate questions
TEAM_SEASON_KEYWORDS: List[str] = [
    "team scored",
    "club scored",
    "team conceded",
    "club conceded",
    "team points",
    "club points",
    "team wins",
    "club wins",
    "team goals",
    "club goals",
    "fewest goals conceded",
    "most goals scored",
    "fewest points",
    "most points",
    "most wins",
    "most losses",
    "most draws",
    "team yellow",
    "team red",
    "club yellow",
    "club red",
]

DEFAULT_LIMIT = 50

# Guardrails to avoid costly/low-quality queries
PER90_PREFIX = "per90_"
MINUTES_FLOOR = 900


@dataclass
class ValidatedSQL:
    sql: str
    warning: Optional[str] = None


class SQLValidationError(ValueError):
    pass


def _ensure_single_statement(sql: str) -> None:
    parsed = sqlglot.parse(sql, read="postgres")
    if len(parsed) != 1:
        raise SQLValidationError("Only a single SQL statement is allowed.")


def _ensure_select_only(sql: str) -> None:
    if BANNED_REGEX.search(sql):
        raise SQLValidationError("Only read-only SELECT queries are allowed.")


def _ensure_allowed_tables(sql: str) -> None:
    parsed = sqlglot.parse_one(sql, read="postgres")
    tables = {t.name for t in parsed.find_all(exp.Table)}
    # Allow schema-qualified names too; we only care about the table identifier
    if not tables:
        return
    unknown = {t for t in tables if t not in ALLOWED_TABLES}
    if unknown:
        raise SQLValidationError(f"Query references non-allowed tables/views: {sorted(unknown)}")


def _ensure_no_joins(sql: str) -> None:
    """Block explicit JOIN keywords but allow comma-separated tables in FROM for compatibility."""
    # Check for explicit JOIN syntax
    if JOIN_REGEX.search(sql):
        raise SQLValidationError("Explicit JOINs (INNER JOIN, LEFT JOIN, etc.) are not allowed. Use subqueries or CTEs instead.")
    
    # Also check via AST
    parsed = sqlglot.parse_one(sql, read="postgres")
    join = parsed.find(exp.Join)
    if join is not None:
        raise SQLValidationError("Joins are not allowed for this endpoint. Use subqueries, CTEs, or window functions instead.")


def _ensure_no_set_ops(sql: str) -> None:
    """Allow UNION ALL but block UNION, EXCEPT, INTERSECT."""
    parsed = sqlglot.parse_one(sql, read="postgres")
    # UNION ALL is fine (used by views); block distinct UNION
    for union in parsed.find_all(exp.Union):
        # Union has a 'distinct' property - if not UNION ALL, it's problematic
        if union.args.get("distinct"):
            raise SQLValidationError("UNION (distinct) is not allowed. Use UNION ALL if needed.")
    if parsed.find(exp.Except) or parsed.find(exp.Intersect):
        raise SQLValidationError("Set operations (INTERSECT/EXCEPT) are not allowed.")


def _ensure_limit(sql: str, limit: int = DEFAULT_LIMIT) -> str:
    parsed = sqlglot.parse_one(sql, read="postgres")
    # If it's a SELECT or a WITH...SELECT, enforce LIMIT
    select = parsed.find(exp.Select)
    if select is None:
        # If model returns something weird, just block it
        raise SQLValidationError("Only SELECT queries are allowed.")
    if select.args.get("limit") is None:
        select.set("limit", exp.Limit(this=exp.Literal.number(limit)))
        return parsed.sql(dialect="postgres")
    return sql


def _has_minutes_floor(expr: Optional[exp.Expression]) -> bool:
    if expr is None:
        return False

    for node, _, _ in expr.walk():
        if isinstance(node, (exp.GreaterEq, exp.GreaterThan)):
            left, right = node.args.get("this"), node.args.get("expression")
            if isinstance(left, exp.Column) and left.name == "playing_time_min":
                return True
            if isinstance(right, exp.Column) and right.name == "playing_time_min":
                return True
        if isinstance(node, exp.Between):
            target = node.args.get("this")
            if isinstance(target, exp.Column) and target.name == "playing_time_min":
                return True
    return False


def _uses_per90_columns(parsed: exp.Expression) -> bool:
    for col in parsed.find_all(exp.Column):
        if col.name and col.name.lower().startswith(PER90_PREFIX):
            return True
    return False


def _ensure_minutes_floor_if_per90(sql: str) -> str:
    parsed = sqlglot.parse_one(sql, read="postgres")

    # Only apply when the player table is used
    tables = {t.name for t in parsed.find_all(exp.Table)}
    if not ({"pl_player_standard_stats", "pl_player_standard_stats_latest"} & tables):
        return sql

    if not _uses_per90_columns(parsed):
        return sql

    where = parsed.args.get("where")
    if _has_minutes_floor(where):
        return sql

    floor_expr = exp.GreaterEq(this=exp.column("playing_time_min"), expression=exp.Literal.number(MINUTES_FLOOR))
    if where is None:
        parsed.set("where", floor_expr)
    else:
        parsed.set("where", exp.and_(where, floor_expr))

    return parsed.sql(dialect="postgres")


def _ensure_allowed_columns(sql: str, allowed_columns: Optional[Dict[str, Set[str]]]) -> None:
    if not allowed_columns:
        return

    parsed = sqlglot.parse_one(sql, read="postgres")
    tables = {t.name for t in parsed.find_all(exp.Table)}
    if not tables:
        return
    
    # Collect all aliases defined in SELECT clauses (these are computed, not table columns)
    # This includes: COUNT(*) AS titles, SUM(goals_for) AS total_goals, etc.
    select_aliases: Set[str] = set()
    for alias in parsed.find_all(exp.Alias):
        if alias.alias:
            select_aliases.add(alias.alias.lower())
    
    # For queries with CTEs or subqueries, we may have multiple tables
    # Just validate columns for tables we know about
    for table in tables:
        if table not in allowed_columns:
            continue
        
        allowed = {c.lower() for c in allowed_columns.get(table, set())}
        if not allowed:
            continue

        unknown_cols = set()
        for col in parsed.find_all(exp.Column):
            # Skip wildcards and numeric literals
            if col.name in (None, "*"):
                continue
            # Skip if this is a reference to a computed alias
            if col.name.lower() in select_aliases:
                continue
            # If column has a table qualifier, check if it matches
            if col.table:
                if col.table.lower() not in (table, table.lower(), "s", "s2", "s3", "s4", "ordered", "streaks"):
                    continue  # Alias from CTE, skip
            if col.name.lower() not in allowed:
                # Only flag if this is the main query table
                if len(tables) == 1 or col.table == table:
                    unknown_cols.add(col.name)

        if unknown_cols and len(tables) == 1:
            raise SQLValidationError(
                f"Query references non-allowed columns for {table}: {sorted(unknown_cols)}. Allowed: {sorted(allowed)}"
            )


def detect_streak_intent(question: str) -> Optional[str]:
    """
    Detect if question is about streaks and return the preferred view.
    Returns the recommended streak view name, or None if not a streak question.
    """
    if not question:
        return None
    
    q_lower = question.lower()
    
    # Check for streak keywords and find the best matching view
    for keyword, view in STREAK_INTENT_MAP.items():
        if keyword in q_lower:
            # Check if season-scoped version is needed
            needs_season_scope = any(term in q_lower for term in [
                "in a season", "single season", "one season",
                "season_start", "2019", "2020", "2021", "2022", "2023", "2024", "2025",
                "/20", "/21", "/22", "/23", "/24", "/25",
            ])
            
            if needs_season_scope and f"{view}_season" in STREAK_VIEWS:
                return f"{view}_season"
            return view
    
    return None


def _detect_intent_mismatch(sql: str, question: Optional[str]) -> Optional[str]:
    """
    Detect if the SQL uses wrong views for the question intent.
    Returns a warning message if there's a mismatch.
    """
    if not question:
        return None
    
    q_lower = question.lower()
    parsed = sqlglot.parse_one(sql, read="postgres")
    tables = {t.name for t in parsed.find_all(exp.Table)}
    
    # NEW: Check club-level routing validation first
    club_warning = validate_club_source_selection(sql, question)
    if club_warning:
        return club_warning
    
    # Check for streak intent mismatch
    streak_view = detect_streak_intent(question)
    if streak_view:
        uses_streak_view = any(t in STREAK_VIEWS for t in tables)
        uses_raw_match_tables = any(t in {"pl_matches", "pl_team_match", "v_team_matches"} for t in tables)
        
        if uses_raw_match_tables and not uses_streak_view:
            return (
                f"Streak intent mismatch: Question appears to be about streaks. "
                f"Use the precomputed streak view public.{streak_view} instead of computing from match data. "
                f"Do NOT compute streaks manually from pl_matches or v_team_matches."
            )
    
    # Check if question is about team/club season aggregates but uses player views
    is_team_season_question = any(kw in q_lower for kw in TEAM_SEASON_KEYWORDS)
    uses_player_view = any(t in PLAYER_VIEWS for t in tables)
    uses_team_view = any(t in TEAM_VIEWS for t in tables)
    
    if is_team_season_question and uses_player_view and not uses_team_view:
        return (
            f"Intent mismatch: Question appears to be about team/club season stats "
            f"but query uses player views {tables & PLAYER_VIEWS}. "
            f"Consider using v_team_season_summary or pl_season_table instead."
        )
    
    return None


def validate_and_patch_sql(
    sql: str,
    limit: int = DEFAULT_LIMIT,
    allowed_columns: Optional[Dict[str, Set[str]]] = None,
    question: Optional[str] = None,
) -> ValidatedSQL:
    """
    Validate and patch SQL for safety and correctness.
    
    Args:
        sql: The SQL query to validate
        limit: Maximum rows to return (default 50)
        allowed_columns: Dict mapping table names to allowed column sets
        question: Original user question (for intent matching)
    
    Returns:
        ValidatedSQL with the patched SQL and optional warning
    
    Raises:
        SQLValidationError if validation fails
    """
    sql = (sql or "").strip().rstrip(";")
    if not sql:
        raise SQLValidationError("Empty SQL.")
    
    _ensure_single_statement(sql)
    _ensure_select_only(sql)
    _ensure_allowed_tables(sql)
    _ensure_no_joins(sql)
    _ensure_no_set_ops(sql)
    # Note: Window functions are now ALLOWED for streak queries
    sql = _ensure_limit(sql, limit=limit)
    sql = _ensure_minutes_floor_if_per90(sql)
    _ensure_allowed_columns(sql, allowed_columns)
    
    # Intent mismatch is a warning, not an error
    warning = _detect_intent_mismatch(sql, question)
    
    return ValidatedSQL(sql=sql, warning=warning)
    # Column allowlist check disabled to avoid blocking on harmless aliases; relies on table allowlist and read-only guardrails.
    return ValidatedSQL(sql=sql)
