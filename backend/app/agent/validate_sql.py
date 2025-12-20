from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

import sqlglot
from sqlglot import exp


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
