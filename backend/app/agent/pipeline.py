from __future__ import annotations

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .prompts import (
    sql_generation_prompt,
    answer_synthesis_prompt,
    multi_sql_generation_prompt,
    multi_answer_synthesis_prompt,
)
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


# Timeout for individual query execution (seconds)
QUERY_TIMEOUT_SECONDS = 10


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

    # =========================================================================
    # MULTI-QUERY PIPELINE (3 diverse queries with parallel execution)
    # =========================================================================

    def _extract_queries_from_malformed_json(self, raw_text: str) -> List[Dict[str, Any]]:
        """
        Attempt to extract SQL queries from malformed JSON response.
        Uses regex to find SQL statements and metadata.
        """
        queries = []
        
        # Pattern to match JSON objects with sql field
        # Handles escaped quotes within SQL
        sql_pattern = re.compile(
            r'\{\s*"approach"\s*:\s*"([^"]*)"[^}]*"primary_table"\s*:\s*"([^"]*)"[^}]*"sql"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}',
            re.DOTALL
        )
        
        matches = sql_pattern.findall(raw_text)
        for approach, primary_table, sql in matches:
            # Unescape the SQL string
            sql = sql.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
            queries.append({
                "approach": approach or "unknown",
                "primary_table": primary_table or "unknown",
                "sql": sql.strip(),
            })
        
        # If that didn't work, try simpler pattern just for SQL
        if not queries:
            simple_sql_pattern = re.compile(r'"sql"\s*:\s*"((?:[^"\\]|\\.)*)"', re.DOTALL)
            sql_matches = simple_sql_pattern.findall(raw_text)
            for i, sql in enumerate(sql_matches):
                sql = sql.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
                queries.append({
                    "approach": f"Query {i+1}",
                    "primary_table": "unknown",
                    "sql": sql.strip(),
                })
        
        return queries[:3]  # Return at most 3 queries

    def _execute_single_query(
        self,
        query_info: Dict[str, Any],
        allowed_columns: Dict[str, set],
        question: str,
    ) -> Dict[str, Any]:
        """Execute a single query with validation. Returns result dict."""
        sql = query_info.get("sql", "")
        approach = query_info.get("approach", "unknown")
        primary_table = query_info.get("primary_table", "unknown")
        
        if not sql.strip():
            return {
                "approach": approach,
                "primary_table": primary_table,
                "sql": sql,
                "success": False,
                "error": "Empty SQL query",
                "columns": [],
                "rows": [],
                "row_count": 0,
            }
        
        try:
            validated = validate_and_patch_sql(
                sql,
                limit=50,
                allowed_columns=allowed_columns,
                question=question,
            )
            result = self.db.run_select(validated.sql)
            return {
                "approach": approach,
                "primary_table": primary_table,
                "sql": validated.sql,
                "success": True,
                "warning": validated.warning,
                "columns": result.columns,
                "rows": result.rows,
                "row_count": result.row_count,
            }
        except SQLValidationError as e:
            return {
                "approach": approach,
                "primary_table": primary_table,
                "sql": sql,
                "success": False,
                "error": f"Validation error: {str(e)}",
                "columns": [],
                "rows": [],
                "row_count": 0,
            }
        except Exception as e:
            return {
                "approach": approach,
                "primary_table": primary_table,
                "sql": sql,
                "success": False,
                "error": f"Execution error: {str(e)}",
                "columns": [],
                "rows": [],
                "row_count": 0,
            }

    async def run_multi_query(
        self,
        question: str,
        summarize: bool = True,
        include_rows: bool = True,
        raise_on_error: bool = False,
    ) -> PipelineOutput:
        """
        Execute 3 diverse SQL queries in parallel and synthesize results.
        
        - Generates 3 queries in a single LLM call
        - Executes all queries in parallel with timeout
        - Synthesizes answer from all successful results
        - Retries once if ALL queries fail
        """
        schema = build_schema_snapshot()
        trace: List[Dict[str, Any]] = []
        
        # Generate 3 queries in one LLM call
        prompt = multi_sql_generation_prompt(
            question,
            schema.schema_text,
            intent_hint=classify_intent(question),
        )
        raw_response = self.llm.generate_json(prompt).text
        
        # Parse JSON response
        queries: List[Dict[str, Any]] = []
        try:
            parsed = json.loads(raw_response)
            if isinstance(parsed, list):
                queries = parsed[:3]
            else:
                raise ValueError("Expected JSON array")
        except (json.JSONDecodeError, ValueError) as e:
            # Try regex extraction for malformed JSON
            queries = self._extract_queries_from_malformed_json(raw_response)
            if not queries:
                # Fall back to single query mode
                trace.append({
                    "multi_query_parse_error": str(e),
                    "raw_response": raw_response[:500],
                    "fallback": "single_query",
                })
                return self.run(question, summarize, include_rows, raise_on_error)
        
        # Ensure we have at least 1 query
        if not queries:
            return self.run(question, summarize, include_rows, raise_on_error)
        
        # Execute queries in parallel with timeout
        async def execute_with_timeout(query_info: Dict) -> Dict[str, Any]:
            loop = asyncio.get_running_loop()
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        self._execute_single_query,
                        query_info,
                        schema.allowed_columns,
                        question,
                    ),
                    timeout=QUERY_TIMEOUT_SECONDS,
                )
                return result
            except asyncio.TimeoutError:
                return {
                    "approach": query_info.get("approach", "unknown"),
                    "primary_table": query_info.get("primary_table", "unknown"),
                    "sql": query_info.get("sql", ""),
                    "success": False,
                    "error": f"Query timed out after {QUERY_TIMEOUT_SECONDS}s",
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                }
        
        # Run all queries concurrently
        query_results = await asyncio.gather(*[execute_with_timeout(q) for q in queries])
        
        # Check success status
        successful_results = [qr for qr in query_results if qr.get("success") and qr.get("row_count", 0) > 0]
        all_failed = len(successful_results) == 0
        
        # Single retry if ALL queries failed
        if all_failed:
            previous_errors = [qr.get("error", "Unknown error") for qr in query_results]
            trace.append({
                "attempt": 1,
                "queries_attempted": len(queries),
                "all_failed": True,
                "errors": previous_errors,
                "retrying": True,
            })
            
            # Retry with error context
            retry_prompt = multi_sql_generation_prompt(
                question,
                schema.schema_text,
                intent_hint=classify_intent(question),
                previous_errors=previous_errors,
            )
            retry_response = self.llm.generate_json(retry_prompt).text
            
            retry_queries = []
            try:
                parsed = json.loads(retry_response)
                if isinstance(parsed, list):
                    retry_queries = parsed[:3]
            except (json.JSONDecodeError, ValueError):
                retry_queries = self._extract_queries_from_malformed_json(retry_response)
            
            if retry_queries:
                query_results = await asyncio.gather(*[execute_with_timeout(q) for q in retry_queries])
                successful_results = [qr for qr in query_results if qr.get("success") and qr.get("row_count", 0) > 0]
        
        # Record trace
        trace.append({
            "multi_query": True,
            "queries_attempted": len(queries),
            "successful": len(successful_results),
            "results": [
                {
                    "approach": qr.get("approach"),
                    "primary_table": qr.get("primary_table"),
                    "success": qr.get("success"),
                    "error": qr.get("error"),
                    "row_count": qr.get("row_count"),
                }
                for qr in query_results
            ],
        })
        
        # Synthesize answer from all results
        summary = ""
        if summarize:
            synth_prompt = multi_answer_synthesis_prompt(question, query_results)
            summary = self.llm.generate_text(synth_prompt).text
        
        # Pick the best successful query for the response
        best = successful_results[0] if successful_results else query_results[0]
        
        return PipelineOutput(
            sql=best.get("sql", ""),
            columns=best.get("columns", []),
            rows=best.get("rows", []) if include_rows else [],
            summary=summary,
            attempt_count=2 if all_failed else 1,
            trace=trace,
            retry_token=RETRY_TOKEN if not successful_results else None,
            retry_reason="All queries failed" if not successful_results else None,
        )
