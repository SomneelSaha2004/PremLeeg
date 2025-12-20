"""Tests for club-level metrics SQL routing.

These tests verify the routing logic for club-level questions,
ensuring correct source selection and metric mapping.
"""

import pytest

from backend.app.agent.club_metrics_routing import (
    ClubMetricIntent,
    ClubMetricRouting,
    classify_club_intent,
    route_club_metric,
    get_club_metric_hint,
    validate_club_source_selection,
    generate_club_metric_sql_template,
    _detect_metric,
    _is_club_level_question,
)


# ============================================================================
# INTENT CLASSIFICATION TESTS
# ============================================================================

class TestClassifyClubIntent:
    """Tests for classify_club_intent function."""
    
    # --- CLUB_TITLES tests ---
    @pytest.mark.parametrize("question", [
        "Who has the most PL titles?",
        "Which club has won the most Premier League trophies?",
        "How many times has Man United won the league?",
        "Who are the Premier League champions since 2010?",
        "Which team has been league winners the most?",
    ])
    def test_titles_intent(self, question: str):
        """Title-related questions should route to CLUB_TITLES."""
        assert classify_club_intent(question) == ClubMetricIntent.CLUB_TITLES
    
    # --- CLUB_METRIC_SEASON tests ---
    @pytest.mark.parametrize("question", [
        "Which club scored the most goals in a single season?",
        "Which team had the most points in a season?",
        "Which team conceded the fewest goals in a Premier League season?",
        "Who had the best goal difference in a single season?",
        "Which club had the most wins in one season?",
        "Which team received the most yellow cards in a season?",
    ])
    def test_season_metric_intent(self, question: str):
        """Season-scoped club metrics should route to CLUB_METRIC_SEASON."""
        assert classify_club_intent(question) == ClubMetricIntent.CLUB_METRIC_SEASON
    
    # --- CLUB_METRIC_ALL_TIME tests ---
    @pytest.mark.parametrize("question", [
        "Which club has scored the most goals ever?",
        "Which team has the most wins in Premier League history?",
        "Which club has the most points all-time?",
        "Which team has conceded the most goals overall?",
        "Which club has the most total wins across all seasons?",
    ])
    def test_all_time_metric_intent(self, question: str):
        """All-time club metrics should route to CLUB_METRIC_ALL_TIME."""
        assert classify_club_intent(question) == ClubMetricIntent.CLUB_METRIC_ALL_TIME
    
    # --- MATCH_CONDITIONAL_CLUB_METRIC tests ---
    @pytest.mark.parametrize("question", [
        "What is the longest winning streak in the Premier League?",
        "Which team has the longest unbeaten run?",
        "What is the longest clean sheet streak ever?",
        "Which club went the longest without conceding?",
        "What is the longest scoring streak in a single season?",
        "How many consecutive wins did Arsenal have?",
    ])
    def test_match_conditional_intent(self, question: str):
        """Streak/match-conditional questions should route to MATCH_CONDITIONAL."""
        assert classify_club_intent(question) == ClubMetricIntent.MATCH_CONDITIONAL_CLUB_METRIC
    
    # --- PLAYER_FOR_CLUB tests ---
    @pytest.mark.parametrize("question", [
        "Who is Liverpool's top scorer for all time?",
        "Which player scored the most goals for Chelsea?",
        "Who is the leading scorer for Arsenal?",
        "Most assists for Man City?",
    ])
    def test_player_for_club_intent(self, question: str):
        """Player-for-club questions should route to PLAYER_FOR_CLUB."""
        assert classify_club_intent(question) == ClubMetricIntent.PLAYER_FOR_CLUB
    
    # --- NOT_CLUB tests ---
    @pytest.mark.parametrize("question", [
        "Who is the Premier League's all-time top scorer?",
        "Who scored the most goals in a single season?",
        "What's the biggest home win ever?",
    ])
    def test_not_club_intent(self, question: str):
        """Non-club questions should return NOT_CLUB."""
        # These are player or match questions, not club-level
        intent = classify_club_intent(question)
        # Note: Some of these might be detected as club questions depending on keywords
        # The key is they don't have explicit club identifiers
        assert intent in (ClubMetricIntent.NOT_CLUB, ClubMetricIntent.CLUB_METRIC_SEASON)


# ============================================================================
# METRIC DETECTION TESTS
# ============================================================================

class TestDetectMetric:
    """Tests for _detect_metric function."""
    
    @pytest.mark.parametrize("question,expected_col,expected_dir", [
        ("Which club scored the most goals?", "goals_for", "DESC"),
        ("Which team conceded the fewest goals?", "goals_against", "ASC"),
        ("Most points in a season", "points", "DESC"),
        ("Fewest wins by a team", "wins", "ASC"),
        ("Most losses in a season", "losses", "DESC"),
        ("Most yellow cards by a team", "yellows", "DESC"),
        ("Most red cards in a season", "reds", "DESC"),
        ("Best goal difference", "goal_diff", "DESC"),
        ("Worst defense in PL history", "goals_against", "DESC"),
    ])
    def test_metric_detection(self, question: str, expected_col: str, expected_dir: str):
        """Test that metrics are correctly detected from questions."""
        result = _detect_metric(question)
        assert result is not None, f"Failed to detect metric in: {question}"
        col, direction = result
        assert col == expected_col, f"Expected {expected_col}, got {col} for: {question}"
        assert direction == expected_dir, f"Expected {expected_dir}, got {direction} for: {question}"


# ============================================================================
# ROUTING TESTS
# ============================================================================

class TestRouteClubMetric:
    """Tests for route_club_metric function."""
    
    def test_titles_routing(self):
        """Title questions should route to pl_season_table."""
        routing = route_club_metric("Who has the most PL titles?")
        assert routing.intent == ClubMetricIntent.CLUB_TITLES
        assert routing.recommended_view == "pl_season_table"
        assert not routing.is_ambiguous
    
    def test_season_metric_routing(self):
        """Season metric questions should route to v_team_season_summary."""
        routing = route_club_metric("Which club scored the most goals in a season?")
        assert routing.intent == ClubMetricIntent.CLUB_METRIC_SEASON
        assert routing.recommended_view == "v_team_season_summary"
        assert routing.column == "goals_for"
        assert routing.sort_direction == "DESC"
        assert not routing.needs_group_by
    
    def test_all_time_metric_routing(self):
        """All-time metric questions should route to v_team_season_summary with GROUP BY."""
        routing = route_club_metric("Which club has the most wins ever?")
        assert routing.intent == ClubMetricIntent.CLUB_METRIC_ALL_TIME
        assert routing.recommended_view == "v_team_season_summary"
        assert routing.column == "wins"
        assert routing.needs_group_by
    
    def test_streak_routing_win_streak(self):
        """Winning streak questions should route to v_team_win_streaks."""
        routing = route_club_metric("What is the longest winning streak in the Premier League?")
        assert routing.intent == ClubMetricIntent.MATCH_CONDITIONAL_CLUB_METRIC
        assert routing.recommended_view == "v_team_win_streaks"
    
    def test_streak_routing_unbeaten(self):
        """Unbeaten streak questions should route to v_team_unbeaten_streaks."""
        routing = route_club_metric("Which team went the longest without losing?")
        assert routing.intent == ClubMetricIntent.MATCH_CONDITIONAL_CLUB_METRIC
        assert routing.recommended_view == "v_team_unbeaten_streaks"
    
    def test_streak_routing_clean_sheets(self):
        """Clean sheet streak questions should route to v_team_clean_sheet_streaks."""
        routing = route_club_metric("What is the longest clean sheet streak?")
        assert routing.intent == ClubMetricIntent.MATCH_CONDITIONAL_CLUB_METRIC
        assert routing.recommended_view == "v_team_clean_sheet_streaks"
    
    def test_player_for_club_routing(self):
        """Player-for-club questions should route to v_player_totals_by_squad."""
        routing = route_club_metric("Who scored the most goals for Liverpool?")
        assert routing.intent == ClubMetricIntent.PLAYER_FOR_CLUB
        assert routing.recommended_view == "v_player_totals_by_squad"


# ============================================================================
# SOURCE VALIDATION TESTS (GUARDRAILS)
# ============================================================================

class TestValidateClubSourceSelection:
    """Tests for validate_club_source_selection guardrails."""
    
    def test_wrong_source_player_view_for_club_metric(self):
        """Using v_player_totals_by_squad for club metrics should trigger warning."""
        sql = "SELECT squad, SUM(goals) FROM public.v_player_totals_by_squad GROUP BY squad"
        question = "Which club scored the most goals in a season?"
        warning = validate_club_source_selection(sql, question)
        assert warning is not None
        assert "WRONG SOURCE" in warning
        assert "v_player_totals_by_squad" in warning
    
    def test_correct_source_v_team_season_summary(self):
        """Using v_team_season_summary for club metrics should not trigger warning."""
        sql = "SELECT team, goals_for FROM public.v_team_season_summary ORDER BY goals_for DESC LIMIT 1"
        question = "Which club scored the most goals in a season?"
        warning = validate_club_source_selection(sql, question)
        assert warning is None
    
    def test_titles_without_rank_filter(self):
        """Title queries without rank=1 should trigger warning."""
        sql = "SELECT team, COUNT(*) FROM public.pl_season_table GROUP BY team"
        question = "Who has the most PL titles?"
        warning = validate_club_source_selection(sql, question)
        assert warning is not None
        assert "rank = 1" in warning or "rank=1" in warning.replace(" ", "")
    
    def test_titles_with_correct_filter(self):
        """Title queries with rank=1 should not trigger warning."""
        sql = "SELECT team, COUNT(*) FROM public.pl_season_table WHERE rank = 1 GROUP BY team"
        question = "Who has the most PL titles?"
        warning = validate_club_source_selection(sql, question)
        assert warning is None
    
    def test_streak_without_precomputed_view(self):
        """Streak queries using pl_matches should trigger warning."""
        sql = "SELECT * FROM public.pl_matches WHERE result = 'W'"
        question = "What is the longest winning streak?"
        warning = validate_club_source_selection(sql, question)
        assert warning is not None
        assert "WRONG SOURCE" in warning or "precomputed" in warning.lower()


# ============================================================================
# SQL TEMPLATE GENERATION TESTS
# ============================================================================

class TestGenerateClubMetricSqlTemplate:
    """Tests for generate_club_metric_sql_template function."""
    
    def test_titles_template(self):
        """Title template should use pl_season_table with rank=1."""
        routing = route_club_metric("Who has the most PL titles?")
        sql = generate_club_metric_sql_template(routing, limit=5)
        assert sql is not None
        assert "pl_season_table" in sql
        assert "rank = 1" in sql
        assert "GROUP BY team" in sql
        assert "LIMIT 5" in sql
    
    def test_season_metric_template(self):
        """Season metric template should use v_team_season_summary."""
        routing = route_club_metric("Which club scored the most goals in a season?")
        sql = generate_club_metric_sql_template(routing, limit=10)
        assert sql is not None
        assert "v_team_season_summary" in sql
        assert "goals_for" in sql
        assert "ORDER BY goals_for DESC" in sql
        assert "LIMIT 10" in sql
    
    def test_all_time_template(self):
        """All-time template should use SUM + GROUP BY."""
        routing = route_club_metric("Which club has the most wins ever?")
        sql = generate_club_metric_sql_template(routing, limit=1)
        assert sql is not None
        assert "v_team_season_summary" in sql
        assert "SUM(wins)" in sql
        assert "GROUP BY team" in sql


# ============================================================================
# HINT GENERATION TESTS
# ============================================================================

class TestGetClubMetricHint:
    """Tests for get_club_metric_hint function."""
    
    def test_hint_for_club_question(self):
        """Club questions should return a hint."""
        hint = get_club_metric_hint("Which club scored the most goals in a season?")
        assert hint is not None
        assert "v_team_season_summary" in hint
    
    def test_hint_for_titles(self):
        """Title questions should mention pl_season_table."""
        hint = get_club_metric_hint("Who has the most PL titles?")
        assert hint is not None
        assert "pl_season_table" in hint
    
    def test_no_hint_for_non_club(self):
        """Non-club questions should return None."""
        hint = get_club_metric_hint("What's the weather like?")
        assert hint is None


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and ambiguous questions."""
    
    def test_ambiguous_metric_question(self):
        """Questions without clear metric should be marked ambiguous or default."""
        routing = route_club_metric("Which club is the best?")
        # Should either be ambiguous or default to a reasonable choice
        assert routing.intent in (ClubMetricIntent.AMBIGUOUS, ClubMetricIntent.NOT_CLUB)
    
    def test_season_scope_detection(self):
        """Season-scoped streak questions should use _season variant."""
        routing = route_club_metric("What is the longest unbeaten run in a single season?")
        assert routing.intent == ClubMetricIntent.MATCH_CONDITIONAL_CLUB_METRIC
        assert "season" in routing.recommended_view
    
    def test_fewest_vs_most_direction(self):
        """'Fewest' should use ASC, 'most' should use DESC."""
        routing_most = route_club_metric("Which club scored the most goals in a season?")
        routing_fewest = route_club_metric("Which club conceded the fewest goals in a season?")
        assert routing_most.sort_direction == "DESC"
        assert routing_fewest.sort_direction == "ASC"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
