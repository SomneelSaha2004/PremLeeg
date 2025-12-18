from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Set

import sqlglot
from sqlglot import exp


BANNED_REGEX = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|copy|call|do)\b",
    re.IGNORECASE,
)

ALLOWED_TABLES: Set[str] = {
    "pl_matches",
    "pl_team_match",
    "pl_season_table",
    "pl_player_standard_stats",
}

DEFAULT_LIMIT = 50

# Guardrails to avoid costly/low-quality queries
PER90_PREFIX = "per90_"
MINUTES_FLOOR = 900


@dataclass
class ValidatedSQL:
    sql: str


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
    parsed = sqlglot.parse_one(sql, read="postgres")
    join = parsed.find(exp.Join)
    if join is not None:
        raise SQLValidationError("Joins are not allowed for this endpoint.")


def _ensure_no_set_ops(sql: str) -> None:
    parsed = sqlglot.parse_one(sql, read="postgres")
    if parsed.find(exp.Union) or parsed.find(exp.Except) or parsed.find(exp.Intersect):
        raise SQLValidationError("Set operations (UNION/INTERSECT/EXCEPT) are not allowed.")


def _ensure_no_window_functions(sql: str) -> None:
    parsed = sqlglot.parse_one(sql, read="postgres")
    if parsed.find(exp.Window):
        raise SQLValidationError("Window functions are not allowed.")


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
    if "pl_player_standard_stats" not in tables:
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


def validate_and_patch_sql(sql: str, limit: int = DEFAULT_LIMIT) -> ValidatedSQL:
    sql = (sql or "").strip().rstrip(";")
    if not sql:
        raise SQLValidationError("Empty SQL.")
    _ensure_single_statement(sql)
    _ensure_select_only(sql)
    _ensure_allowed_tables(sql)
    _ensure_no_joins(sql)
    _ensure_no_set_ops(sql)
    _ensure_no_window_functions(sql)
    sql = _ensure_limit(sql, limit=limit)
    sql = _ensure_minutes_floor_if_per90(sql)
    return ValidatedSQL(sql=sql)
