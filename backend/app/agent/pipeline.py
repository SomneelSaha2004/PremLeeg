from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .prompts import sql_generation_prompt, answer_synthesis_prompt
from .validate_sql import SQLValidationError, validate_and_patch_sql, detect_streak_intent
from .club_metrics_routing import (
    get_club_metric_hint,
    route_club_metric,
    ClubMetricIntent,
    CLUB_RETRY_TOKEN,
    format_retry_token,
)
from ..db.client import PostgresClient, QueryResult
from ..db.schema_snapshot import build_schema_snapshot
from ..context.team_names import get_team_filter_hint
from ..llm import OpenAILLM


# Keywords that suggest player-focused questions
PLAYER_KEYWORDS = {
    "player",
    "players",
    "scorer",
    "scorers",
    "goals",
    "assists",
    "xg",
    "npxg",
    "xag",
    "per90",
    "per 90",
    "per-90",
    "minutes",
    "per 90s",
    "career",
    "all-time top",
    "leading",
}

# Keywords that suggest match/team-focused questions
MATCH_KEYWORDS = {
    "match",
    "matches",
    "game",
    "games",
    "wins",
    "losses",
    "draws",
    "points",
    "table",
    "standing",
    "standings",
    "rank",
    "home",
    "away",
    "team",
    "club",
    "streak",
    "unbeaten",
    "consecutive",
    "season",
}

# Keywords that indicate record/superlative questions (need tie handling)
RECORD_KEYWORDS = {
    "biggest",
    "largest",
    "highest",
    "most",
    "record",
    "best",
    "worst",
    "fewest",
    "lowest",
    "longest",
    "shortest",
    "ever",
    "all-time",
    "history",
}

# Retry tokens for orchestrator
RETRY_TOKEN = "__RETRY_SQL__"
RETRY_WITH_ERROR_TOKEN = "__RETRY_WITH_ERROR_CONTEXT__"


def classify_intent(question: str) -> str:
    """Lightweight keyword intent classifier to steer table choice."""
    q = question.lower()
    player_score = sum(1 for kw in PLAYER_KEYWORDS if kw in q)
    match_score = sum(1 for kw in MATCH_KEYWORDS if kw in q)
    if player_score == 0 and match_score == 0:
        return "unknown"
    return "player" if player_score >= match_score else "match"


def is_record_question(question: str) -> bool:
    """Check if question is asking for a record/superlative."""
    q = question.lower()
    return any(kw in q for kw in RECORD_KEYWORDS)


def get_streak_hint(question: str) -> Optional[str]:
    """
    Detect streak-related intent and return a hint for the LLM.
    Returns a string explaining which streak view to use, or None.
    """
    recommended_view = detect_streak_intent(question)
    if not recommended_view:
        return None
    
    # Build a specific hint based on the recommended view
    view_descriptions = {
        "v_team_win_streaks": "Use v_team_win_streaks for consecutive wins (all-time streaks).",
        "v_team_unbeaten_streaks": "Use v_team_unbeaten_streaks for unbeaten runs (all-time).",
        "v_team_unbeaten_streaks_season": "Use v_team_unbeaten_streaks_season for unbeaten runs within a single season.",
        "v_team_clean_sheet_streaks": "Use v_team_clean_sheet_streaks for consecutive clean sheets (all-time).",
        "v_team_clean_sheet_streaks_season": "Use v_team_clean_sheet_streaks_season for clean sheet streaks within a single season.",
        "v_team_scoring_streaks": "Use v_team_scoring_streaks for consecutive matches scoring (all-time).",
        "v_team_scoring_streaks_season": "Use v_team_scoring_streaks_season for scoring streaks within a single season.",
    }
    return view_descriptions.get(recommended_view, f"Use {recommended_view} for this streak question.")


@dataclass
class PipelineOutput:
    sql: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    summary: str
    retry_token: Optional[str] = None
    retry_reason: Optional[str] = None
    attempt_count: int = 0
    trace: Optional[List[Dict[str, Any]]] = None


class AgentPipeline:
    def __init__(self):
        self.db = PostgresClient()
        self.llm = OpenAILLM()

    def run(
        self,
        question: str,
        summarize: bool = True,
        include_rows: bool = True,
        raise_on_error: bool = False,
    ) -> PipelineOutput:
        schema = build_schema_snapshot()
        intent = classify_intent(question)
        is_record = is_record_question(question)
        streak_hint = get_streak_hint(question)
        team_hint = get_team_filter_hint(question)
        
        # NEW: Get club-level routing hint
        club_routing = route_club_metric(question)
        club_hint = get_club_metric_hint(question)
        
        # Check for ambiguous club routing that requires clarification
        if club_routing.is_ambiguous and club_routing.intent != ClubMetricIntent.NOT_CLUB:
            # Log the ambiguity but continue with best-effort routing
            pass  # Will include hint in the prompt
        
        max_retries = 2  # Increased from 1 to allow more retry attempts
        last_error = None
        raw_sql = ""
        validated_sql = ""
        warning: Optional[str] = None

        trace: List[Dict[str, Any]] = []
        
        for attempt in range(max_retries + 1):
            attempt_num = attempt + 1
            try:
                # Build hints for the LLM
                hints = []
                if streak_hint:
                    hints.append(streak_hint)
                if team_hint:
                    hints.append(team_hint)
                # NEW: Add club routing hint
                if club_hint:
                    hints.append(club_hint)
                
                # Build error context for retries
                error_context = last_error
                if warning and attempt > 0:
                    error_context = f"{last_error or ''}\nWarning: {warning}"
                
                # On first attempt, include hints as guidance
                if hints and attempt == 0:
                    hint_text = "\n".join(hints)
                    error_context = hint_text if not error_context else f"{hint_text}\n{error_context}"
                
                # Generate SQL with error context if retrying
                prompt = sql_generation_prompt(
                    question,
                    schema.schema_text,
                    intent_hint=intent,
                    previous_error=error_context
                )
                
                raw_sql = self.llm.generate_sql(prompt).text.strip()
                
                # Validate (now includes intent mismatch detection)
                validated = validate_and_patch_sql(
                    raw_sql,
                    limit=50,
                    allowed_columns=schema.allowed_columns,
                    question=question,
                )
                validated_sql = validated.sql
                warning = validated.warning
                
                # If there's an intent mismatch warning and this is the first attempt,
                # trigger a retry with the warning as feedback
                if warning and attempt == 0:
                    last_error = warning
                    trace.append(
                        {
                            "attempt": attempt_num,
                            "raw_sql": raw_sql,
                            "validated_sql": validated_sql,
                            "warning": warning,
                            "error": None,
                            "row_count": None,
                            "outcome": "retry",
                            "retry_reason": warning,
                        }
                    )
                    continue
                
                # Execute
                result: QueryResult = self.db.run_select(validated_sql)
                
                # Check for zero rows - may indicate wrong query approach
                if result.row_count == 0 and attempt < max_retries:
                    last_error = (
                        "Query returned 0 rows. This may indicate wrong table/view choice or "
                        "overly restrictive filters. Try a different approach."
                    )
                    trace.append(
                        {
                            "attempt": attempt_num,
                            "raw_sql": raw_sql,
                            "validated_sql": validated_sql,
                            "warning": warning,
                            "error": None,
                            "row_count": result.row_count,
                            "outcome": "retry",
                            "retry_reason": last_error,
                        }
                    )
                    continue
                
                # Check for single row when expecting ties (record questions)
                if is_record and result.row_count == 1 and attempt < max_retries:
                    # This is just a soft warning - continue anyway but note it
                    pass
                
                # Success - synthesize answer
                summary = ""
                if summarize:
                    synthesis_prompt = answer_synthesis_prompt(
                        question=question,
                        sql=validated_sql,
                        columns=result.columns,
                        rows=result.rows,
                        returned_row_count=result.row_count,
                        max_rows_sent=20,
                    )
                    summary = self.llm.generate_text(synthesis_prompt).text

                trace.append(
                    {
                        "attempt": attempt_num,
                        "raw_sql": raw_sql,
                        "validated_sql": validated_sql,
                        "warning": warning,
                        "error": None,
                        "row_count": result.row_count,
                        "outcome": "success",
                        "retry_reason": None,
                    }
                )
                
                return PipelineOutput(
                    sql=validated_sql,
                    columns=result.columns,
                    rows=result.rows if include_rows else [],
                    summary=summary,
                    attempt_count=attempt_num,
                    trace=trace,
                )
                
            except SQLValidationError as e:
                last_error = f"Validation error: {str(e)}"
                trace.append(
                    {
                        "attempt": attempt_num,
                        "raw_sql": raw_sql,
                        "validated_sql": validated_sql or None,
                        "warning": warning,
                        "error": last_error,
                        "row_count": None,
                        "outcome": "error" if attempt >= max_retries else "retry",
                        "retry_reason": last_error if attempt < max_retries else None,
                    }
                )
                if attempt < max_retries:
                    continue
                if raise_on_error:
                    raise
                return PipelineOutput(
                    sql=raw_sql,
                    columns=[],
                    rows=[],
                    summary=f"Failed after {max_retries + 1} attempts. {last_error}",
                    retry_token=RETRY_TOKEN,
                    retry_reason=last_error,
                    attempt_count=attempt_num,
                    trace=trace,
                )
                
            except Exception as e:
                last_error = f"Execution error: {str(e)}"
                trace.append(
                    {
                        "attempt": attempt_num,
                        "raw_sql": raw_sql,
                        "validated_sql": validated_sql or None,
                        "warning": warning,
                        "error": last_error,
                        "row_count": None,
                        "outcome": "error" if attempt >= max_retries else "retry",
                        "retry_reason": last_error if attempt < max_retries else None,
                    }
                )
                if attempt < max_retries:
                    continue
                if raise_on_error:
                    raise
                return PipelineOutput(
                    sql=validated_sql or raw_sql,
                    columns=[],
                    rows=[],
                    summary=f"Failed after {max_retries + 1} attempts. {last_error}",
                    retry_token=RETRY_TOKEN,
                    retry_reason=last_error,
                    attempt_count=attempt_num,
                    trace=trace,
                )
        
        # Should never reach here, but just in case
        return PipelineOutput(
            sql=raw_sql,
            columns=[],
            rows=[],
            summary="Unknown error in pipeline.",
            retry_token=RETRY_TOKEN,
            retry_reason="Max retries exceeded",
            attempt_count=max_retries + 1,
            trace=trace,
        )
