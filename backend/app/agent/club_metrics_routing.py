"""Club-level metrics SQL routing module.

Implements robust source selection and query generation for club-level metrics.
Follows the NO JOINS constraint and prefers views over base tables.

ROUTING LOGIC ORDER:
1. CLUB_TITLES - titles, trophies, seasons won, champions → pl_season_table
2. MATCH_CONDITIONAL_CLUB_METRIC - clean sheets, streaks, consecutive → v_team_matches or streak views
3. PLAYER_FOR_CLUB - player stats for a specific club → v_player_totals_by_squad
4. CLUB_METRIC_SEASON - single season club metrics → v_team_season_summary
5. CLUB_METRIC_ALL_TIME - all-time club aggregates → v_team_season_summary with GROUP BY
6. AMBIGUOUS - cannot safely decide → return retry token

HARD CONSTRAINTS:
- NO JOINS of any kind
- Prefer VIEWS over BASE TABLES
- SQL must be PostgreSQL compatible
- Output must be deterministic and correct
- Avoid attendance-related logic (no attendance column exists)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class ClubMetricIntent(Enum):
    """Classification of club-level question intents."""
    CLUB_METRIC_SEASON = "club_metric_season"
    CLUB_METRIC_ALL_TIME = "club_metric_all_time"
    CLUB_TITLES = "club_titles"
    PLAYER_FOR_CLUB = "player_for_club"
    MATCH_CONDITIONAL_CLUB_METRIC = "match_conditional_club_metric"
    AMBIGUOUS = "ambiguous"
    NOT_CLUB = "not_club"  # Not a club-level question


# Retry token for ambiguous questions
CLUB_RETRY_TOKEN = "<<NEED_SCHEMA_OR_CLARIFICATION_RETRY>>"


@dataclass
class ClubMetricRouting:
    """Result of club metric routing decision."""
    intent: ClubMetricIntent
    recommended_view: str
    column: Optional[str] = None
    sort_direction: str = "DESC"
    needs_group_by: bool = False
    is_ambiguous: bool = False
    retry_reason: Optional[str] = None
    hint: Optional[str] = None


# ============================================================================
# KEYWORD PATTERNS FOR INTENT CLASSIFICATION
# ============================================================================

# Title/trophy keywords → CLUB_TITLES
TITLE_KEYWORDS: Set[str] = {
    "titles",
    "trophies",
    "trophy",
    "seasons won",
    "won the league",
    "champions",
    "league winners",
    "premier league titles",
    "won premier league",
    "how many times",
    "championship",
    "league champion",
}

# Season-scope keywords → CLUB_METRIC_SEASON
SEASON_SCOPE_KEYWORDS: Set[str] = {
    "in a season",
    "single season",
    "one season",
    "record season",
    "best season",
    "worst season",
    "per season",
    "season record",
    "in a premier league season",
}

# All-time scope keywords → CLUB_METRIC_ALL_TIME
ALL_TIME_SCOPE_KEYWORDS: Set[str] = {
    "all-time",
    "all time",
    "ever",
    "history",
    "in pl history",
    "in premier league history",
    "overall",
    "total",
    "combined",
    "across all seasons",
    "throughout history",
}

# Match-conditional keywords → MATCH_CONDITIONAL_CLUB_METRIC
MATCH_CONDITIONAL_KEYWORDS: Set[str] = {
    "clean sheet",
    "clean sheets",
    "consecutive",
    "streak",
    "streaks",
    "unbeaten",
    "without conceding",
    "not conceding",
    "in a row",
    "winning streak",
    "losing streak",
    "scoring streak",
    "longest run",
    "without losing",
    "shutout",
    "shutouts",
}

# Player-for-club keywords → PLAYER_FOR_CLUB
PLAYER_FOR_CLUB_KEYWORDS: Set[str] = {
    "player scored",
    "player goals",
    "top scorer for",
    "leading scorer for",
    "most goals for",
    "scored for",
    "assists for",
    "player with most",
    "who scored the most for",
    "player at",
}

# Club identifiers (words that indicate club-level question)
CLUB_IDENTIFIERS: Set[str] = {
    "team",
    "teams",
    "club",
    "clubs",
    "which club",
    "which team",
    "what team",
    "what club",
}

# ============================================================================
# METRIC MAPPING: phrases → (column, direction, view_column_override)
# ============================================================================

# Maps common phrases to column names in v_team_season_summary
CLUB_METRIC_MAP: Dict[str, Tuple[str, str]] = {
    # Goals scored
    "goals scored": ("goals_for", "DESC"),
    "most goals": ("goals_for", "DESC"),
    "scored the most": ("goals_for", "DESC"),
    "highest scoring": ("goals_for", "DESC"),
    "scored most goals": ("goals_for", "DESC"),
    "fewest goals scored": ("goals_for", "ASC"),
    "least goals scored": ("goals_for", "ASC"),
    
    # Goals conceded
    "conceded": ("goals_against", "DESC"),
    "goals conceded": ("goals_against", "DESC"),
    "most conceded": ("goals_against", "DESC"),
    "fewest conceded": ("goals_against", "ASC"),
    "fewest goals conceded": ("goals_against", "ASC"),
    "least conceded": ("goals_against", "ASC"),
    "best defense": ("goals_against", "ASC"),
    "worst defense": ("goals_against", "DESC"),
    
    # Goal difference
    "goal difference": ("goal_diff", "DESC"),
    "best gd": ("goal_diff", "DESC"),
    "best goal difference": ("goal_diff", "DESC"),
    "worst goal difference": ("goal_diff", "ASC"),
    "highest goal difference": ("goal_diff", "DESC"),
    "lowest goal difference": ("goal_diff", "ASC"),
    
    # Points
    "points": ("points", "DESC"),
    "most points": ("points", "DESC"),
    "fewest points": ("points", "ASC"),
    "least points": ("points", "ASC"),
    
    # Wins
    "wins": ("wins", "DESC"),
    "most wins": ("wins", "DESC"),
    "fewest wins": ("wins", "ASC"),
    "least wins": ("wins", "ASC"),
    
    # Draws
    "draws": ("draws", "DESC"),
    "most draws": ("draws", "DESC"),
    "fewest draws": ("draws", "ASC"),
    
    # Losses
    "losses": ("losses", "DESC"),
    "most losses": ("losses", "DESC"),
    "fewest losses": ("losses", "ASC"),
    "least losses": ("losses", "ASC"),
    
    # Yellow cards
    "yellow cards": ("yellows", "DESC"),
    "most yellows": ("yellows", "DESC"),
    "most yellow cards": ("yellows", "DESC"),
    "fewest yellow cards": ("yellows", "ASC"),
    
    # Red cards
    "red cards": ("reds", "DESC"),
    "most reds": ("reds", "DESC"),
    "most red cards": ("reds", "DESC"),
    "fewest red cards": ("reds", "ASC"),
}

# Superlative modifiers that override direction
DESC_MODIFIERS: Set[str] = {"most", "highest", "best", "largest", "biggest", "record"}
ASC_MODIFIERS: Set[str] = {"fewest", "lowest", "worst", "smallest", "least"}


# ============================================================================
# ROUTING FUNCTIONS
# ============================================================================

def _contains_any(text: str, keywords: Set[str]) -> bool:
    """Check if text contains any of the keywords."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def _is_club_level_question(question: str) -> bool:
    """Check if question is about club/team level metrics."""
    q = question.lower()
    
    # Check for explicit club identifiers
    if _contains_any(q, CLUB_IDENTIFIERS):
        return True
    
    # Check for club names
    club_name_patterns = [
        r"\b(arsenal|chelsea|liverpool|man city|man united|tottenham)\b",
        r"\b(everton|newcastle|aston villa|west ham|leicester)\b",
        r"\bthe (gunners|blues|reds|citizens|spurs)\b",
    ]
    for pattern in club_name_patterns:
        if re.search(pattern, q, re.IGNORECASE):
            return True
    
    # Check for team-focused metrics without player context
    team_metrics = {"goals scored", "goals conceded", "points", "wins", "losses", "draws"}
    player_context = {"player", "scorer", "who scored", "top scorer"}
    
    has_team_metric = any(m in q for m in team_metrics)
    has_player_context = any(p in q for p in player_context)
    
    return has_team_metric and not has_player_context


def _detect_metric(question: str) -> Optional[Tuple[str, str]]:
    """
    Detect the metric column and sort direction from the question.
    Returns (column, direction) or None if not detected.
    """
    q = question.lower()
    
    # First, check for complete phrases in our map
    for phrase, (column, direction) in CLUB_METRIC_MAP.items():
        if phrase in q:
            return (column, direction)
    
    # If no exact phrase match, try to infer from individual words
    column = None
    direction = "DESC"  # Default
    
    # Check for metric keywords
    if "goal" in q and ("scored" in q or "score" in q or "scoring" in q):
        column = "goals_for"
    elif "concede" in q:
        column = "goals_against"
    elif "point" in q:
        column = "points"
    elif "win" in q:
        column = "wins"
    elif "draw" in q:
        column = "draws"
    elif "loss" in q or "lose" in q or "lost" in q:
        column = "losses"
    elif "yellow" in q:
        column = "yellows"
    elif "red" in q and "card" in q:
        column = "reds"
    elif "goal difference" in q or " gd " in q or "gd" in q:
        column = "goal_diff"
    
    if column is None:
        return None
    
    # Check for direction modifiers
    if _contains_any(q, ASC_MODIFIERS):
        direction = "ASC"
    elif _contains_any(q, DESC_MODIFIERS):
        direction = "DESC"
    
    # Special case: "worst defense" means most conceded
    if "worst" in q and "defense" in q:
        column = "goals_against"
        direction = "DESC"
    
    return (column, direction)


def classify_club_intent(question: str) -> ClubMetricIntent:
    """
    Classify the intent of a club-level question.
    
    Routing logic order:
    A. TITLES - titles, trophies, seasons won, champions
    B. MATCH_CONDITIONAL - clean sheets, streaks, consecutive
    C. PLAYER_FOR_CLUB - player stats for a specific club
    D. CLUB_METRIC_SEASON - single season club metrics
    E. CLUB_METRIC_ALL_TIME - all-time club aggregates
    F. AMBIGUOUS - cannot safely decide
    """
    q = question.lower()
    
    # First check if this is a club-level question at all
    if not _is_club_level_question(question):
        return ClubMetricIntent.NOT_CLUB
    
    # A. TITLES: titles, trophies, seasons won, champions, league winners
    if _contains_any(q, TITLE_KEYWORDS):
        return ClubMetricIntent.CLUB_TITLES
    
    # B. MATCH_CONDITIONAL: clean sheets, streaks, consecutive, etc.
    if _contains_any(q, MATCH_CONDITIONAL_KEYWORDS):
        return ClubMetricIntent.MATCH_CONDITIONAL_CLUB_METRIC
    
    # C. PLAYER_FOR_CLUB: player + club combo
    if _contains_any(q, PLAYER_FOR_CLUB_KEYWORDS):
        return ClubMetricIntent.PLAYER_FOR_CLUB
    
    # D. CLUB_METRIC_SEASON: explicit "in a season" or season-scope keywords
    if _contains_any(q, SEASON_SCOPE_KEYWORDS):
        return ClubMetricIntent.CLUB_METRIC_SEASON
    
    # E. CLUB_METRIC_ALL_TIME: explicit all-time keywords
    if _contains_any(q, ALL_TIME_SCOPE_KEYWORDS):
        return ClubMetricIntent.CLUB_METRIC_ALL_TIME
    
    # Default: if question has club-level metric but no scope qualifier,
    # default to CLUB_METRIC_SEASON (most common interpretation)
    metric = _detect_metric(question)
    if metric is not None:
        return ClubMetricIntent.CLUB_METRIC_SEASON
    
    # F. AMBIGUOUS: cannot determine
    return ClubMetricIntent.AMBIGUOUS


def route_club_metric(question: str) -> ClubMetricRouting:
    """
    Route a club-level question to the appropriate view and column.
    
    Returns a ClubMetricRouting with:
    - intent: the classified intent
    - recommended_view: the view to use
    - column: the column to query (if applicable)
    - sort_direction: ASC or DESC
    - needs_group_by: whether to aggregate across seasons
    - is_ambiguous: whether routing is uncertain
    - retry_reason: explanation if ambiguous
    - hint: SQL generation hint for the LLM
    """
    intent = classify_club_intent(question)
    
    # Handle non-club questions
    if intent == ClubMetricIntent.NOT_CLUB:
        return ClubMetricRouting(
            intent=intent,
            recommended_view="",
            hint="This does not appear to be a club-level question."
        )
    
    # A. CLUB_TITLES
    if intent == ClubMetricIntent.CLUB_TITLES:
        return ClubMetricRouting(
            intent=intent,
            recommended_view="pl_season_table",
            column="rank",
            sort_direction="DESC",
            hint=(
                "Use pl_season_table with rank=1 filter. "
                "Pattern: SELECT team, COUNT(*) AS titles FROM public.pl_season_table "
                "WHERE rank = 1 GROUP BY team ORDER BY titles DESC LIMIT N"
            )
        )
    
    # B. MATCH_CONDITIONAL_CLUB_METRIC
    if intent == ClubMetricIntent.MATCH_CONDITIONAL_CLUB_METRIC:
        # Determine which streak view to use based on keywords
        q = question.lower()
        if "clean sheet" in q or "shutout" in q or "not conceding" in q:
            view = "v_team_clean_sheet_streaks"
            if _contains_any(q, SEASON_SCOPE_KEYWORDS):
                view = "v_team_clean_sheet_streaks_season"
        elif "winning" in q or "win" in q and "streak" in q:
            view = "v_team_win_streaks"
        elif "unbeaten" in q or "without losing" in q:
            view = "v_team_unbeaten_streaks"
            if _contains_any(q, SEASON_SCOPE_KEYWORDS):
                view = "v_team_unbeaten_streaks_season"
        elif "scoring" in q and "streak" in q:
            view = "v_team_scoring_streaks"
            if _contains_any(q, SEASON_SCOPE_KEYWORDS):
                view = "v_team_scoring_streaks_season"
        else:
            view = "v_team_matches"
        
        return ClubMetricRouting(
            intent=intent,
            recommended_view=view,
            hint=(
                f"Use public.{view} for this streak/match-conditional question. "
                "Do NOT compute streaks manually from pl_matches."
            )
        )
    
    # C. PLAYER_FOR_CLUB
    if intent == ClubMetricIntent.PLAYER_FOR_CLUB:
        return ClubMetricRouting(
            intent=intent,
            recommended_view="v_player_totals_by_squad",
            hint=(
                "Use v_player_totals_by_squad for player stats at a specific club. "
                "Pattern: SELECT player, goals, assists FROM public.v_player_totals_by_squad "
                "WHERE squad = 'ClubName' ORDER BY goals DESC LIMIT N"
            )
        )
    
    # D. CLUB_METRIC_SEASON
    if intent == ClubMetricIntent.CLUB_METRIC_SEASON:
        metric = _detect_metric(question)
        if metric is None:
            return ClubMetricRouting(
                intent=intent,
                recommended_view="v_team_season_summary",
                is_ambiguous=True,
                retry_reason="Cannot determine which metric column to use for season query.",
                hint="Use v_team_season_summary but could not detect specific column."
            )
        
        column, direction = metric
        return ClubMetricRouting(
            intent=intent,
            recommended_view="v_team_season_summary",
            column=column,
            sort_direction=direction,
            needs_group_by=False,
            hint=(
                f"Use v_team_season_summary for single-season club metrics. "
                f"Column: {column}, Direction: {direction}. "
                f"Pattern: SELECT team, season_start, {column} FROM public.v_team_season_summary "
                f"ORDER BY {column} {direction} NULLS LAST LIMIT N"
            )
        )
    
    # E. CLUB_METRIC_ALL_TIME
    if intent == ClubMetricIntent.CLUB_METRIC_ALL_TIME:
        metric = _detect_metric(question)
        if metric is None:
            return ClubMetricRouting(
                intent=intent,
                recommended_view="v_team_season_summary",
                needs_group_by=True,
                is_ambiguous=True,
                retry_reason="Cannot determine which metric column to aggregate for all-time query.",
                hint="Use v_team_season_summary with SUM + GROUP BY but could not detect column."
            )
        
        column, direction = metric
        return ClubMetricRouting(
            intent=intent,
            recommended_view="v_team_season_summary",
            column=column,
            sort_direction=direction,
            needs_group_by=True,
            hint=(
                f"Use v_team_season_summary with SUM for all-time aggregates. "
                f"Column: {column}, Direction: {direction}. "
                f"Pattern: SELECT team, SUM({column}) AS total_{column} "
                f"FROM public.v_team_season_summary GROUP BY team "
                f"ORDER BY total_{column} {direction} NULLS LAST LIMIT N"
            )
        )
    
    # F. AMBIGUOUS
    return ClubMetricRouting(
        intent=ClubMetricIntent.AMBIGUOUS,
        recommended_view="v_team_season_summary",
        is_ambiguous=True,
        retry_reason=(
            "Cannot determine if user wants single season or all-time aggregate, "
            "or which metric column to use."
        ),
        hint="Routing is ambiguous. Consider asking for clarification."
    )


def get_club_metric_hint(question: str) -> Optional[str]:
    """
    Get a routing hint for club-level questions.
    Returns a string hint for the LLM, or None if not a club question.
    """
    routing = route_club_metric(question)
    
    if routing.intent == ClubMetricIntent.NOT_CLUB:
        return None
    
    if routing.is_ambiguous:
        return (
            f"CLUB METRIC ROUTING (AMBIGUOUS): "
            f"Recommended view: {routing.recommended_view}. "
            f"Warning: {routing.retry_reason}"
        )
    
    return (
        f"CLUB METRIC ROUTING: Intent={routing.intent.value}, "
        f"View={routing.recommended_view}. "
        f"{routing.hint}"
    )


def format_retry_token(question: str, routing: ClubMetricRouting) -> str:
    """
    Format the retry token with structured information for ambiguous routing.
    """
    return (
        f"{CLUB_RETRY_TOKEN}\n"
        f"RETRY_REASON: {routing.retry_reason}\n"
        f"CANDIDATE_SOURCES: [v_team_season_summary, pl_season_table, v_team_matches, v_player_totals_by_squad]\n"
        f"QUESTION: \"{question}\""
    )


def validate_club_source_selection(sql: str, question: str) -> Optional[str]:
    """
    Validate that the SQL uses the correct source for club-level questions.
    
    Returns a warning message if there's a mismatch, None otherwise.
    
    Key guardrail: Prevent using v_player_totals_by_squad for club season totals.
    """
    routing = route_club_metric(question)
    
    if routing.intent == ClubMetricIntent.NOT_CLUB:
        return None
    
    sql_lower = sql.lower()
    
    # CRITICAL GUARDRAIL: v_player_totals_by_squad should NOT be used for
    # CLUB_METRIC_SEASON or CLUB_METRIC_ALL_TIME questions
    if routing.intent in (ClubMetricIntent.CLUB_METRIC_SEASON, ClubMetricIntent.CLUB_METRIC_ALL_TIME):
        if "v_player_totals_by_squad" in sql_lower:
            return (
                f"WRONG SOURCE: Question is about club-level season metrics "
                f"(intent={routing.intent.value}) but query uses v_player_totals_by_squad. "
                f"Use {routing.recommended_view} instead. "
                f"v_player_totals_by_squad is for player stats, not club aggregates."
            )
    
    # Check that CLUB_TITLES uses pl_season_table with rank=1
    if routing.intent == ClubMetricIntent.CLUB_TITLES:
        if "pl_season_table" not in sql_lower:
            return (
                "WRONG SOURCE: Question is about titles/championships. "
                "Use pl_season_table with rank=1 filter."
            )
        if "rank" not in sql_lower or "= 1" not in sql_lower.replace(" ", ""):
            return (
                "MISSING FILTER: For title questions, must filter WHERE rank = 1 "
                "to count only championship seasons."
            )
    
    # Check that MATCH_CONDITIONAL uses appropriate streak view or v_team_matches
    if routing.intent == ClubMetricIntent.MATCH_CONDITIONAL_CLUB_METRIC:
        if routing.recommended_view.startswith("v_team_"):
            if routing.recommended_view not in sql_lower:
                # Check if they're using a raw match table instead of precomputed view
                if "pl_matches" in sql_lower or "pl_team_match" in sql_lower:
                    return (
                        f"WRONG SOURCE: Use precomputed {routing.recommended_view} "
                        f"for streak questions. Do NOT compute streaks manually from pl_matches."
                    )
    
    return None


# ============================================================================
# SQL TEMPLATE GENERATION
# ============================================================================

def generate_club_metric_sql_template(routing: ClubMetricRouting, limit: int = 1) -> Optional[str]:
    """
    Generate a SQL template based on the routing decision.
    
    Returns a SQL template string, or None if routing is ambiguous/invalid.
    """
    if routing.is_ambiguous or routing.intent == ClubMetricIntent.NOT_CLUB:
        return None
    
    # CLUB_TITLES
    if routing.intent == ClubMetricIntent.CLUB_TITLES:
        return f"""SELECT team, COUNT(*) AS titles
FROM public.pl_season_table
WHERE rank = 1
GROUP BY team
ORDER BY titles DESC
LIMIT {limit}"""
    
    # CLUB_METRIC_SEASON
    if routing.intent == ClubMetricIntent.CLUB_METRIC_SEASON and routing.column:
        return f"""SELECT team, season_start, {routing.column}
FROM public.v_team_season_summary
ORDER BY {routing.column} {routing.sort_direction} NULLS LAST
LIMIT {limit}"""
    
    # CLUB_METRIC_ALL_TIME
    if routing.intent == ClubMetricIntent.CLUB_METRIC_ALL_TIME and routing.column:
        return f"""SELECT team, SUM({routing.column}) AS total_{routing.column}
FROM public.v_team_season_summary
GROUP BY team
ORDER BY total_{routing.column} {routing.sort_direction} NULLS LAST
LIMIT {limit}"""
    
    # PLAYER_FOR_CLUB (basic template, needs club name)
    if routing.intent == ClubMetricIntent.PLAYER_FOR_CLUB:
        return f"""SELECT squad, player, goals, assists, minutes
FROM public.v_player_totals_by_squad
WHERE squad = '{{club_name}}'
ORDER BY goals DESC NULLS LAST
LIMIT {limit}"""
    
    return None
