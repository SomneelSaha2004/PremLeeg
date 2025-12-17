from __future__ import annotations

from typing import Any, Dict

# Minimal stub; later introspect Postgres information_schema for real context

def get_schema_context() -> Dict[str, Any]:
    """Return a lightweight schema context for the LLM prompt.

    In Phase 1, keep a static glossary. Later, query information_schema
    for live columns and types.
    """
    return {
        "tables": [
            {
                "name": "pl_matches",
                "description": "One row per EPL match",
                "columns": [
                    "match_id",
                    "season_code",
                    "season_start",
                    "div",
                    "match_date",
                    "kickoff_time",
                    "home_team",
                    "away_team",
                    "referee",
                    "ft_home_goals",
                    "ft_away_goals",
                    "ft_result",
                    "ht_home_goals",
                    "ht_away_goals",
                    "ht_result",
                    "home_shots",
                    "away_shots",
                    "home_shots_on_target",
                    "away_shots_on_target",
                    "home_fouls",
                    "away_fouls",
                    "home_corners",
                    "away_corners",
                    "home_yellow",
                    "away_yellow",
                    "home_red",
                    "away_red",
                ],
            }
        ],
        "views": [
            {"name": "pl_team_match", "description": "One row per team per match with points/W/D/L"},
            {"name": "pl_season_table", "description": "Season standings with rank"},
        ],
        "glossary": {
            "points": "3 for win, 1 for draw, 0 for loss",
            "rank": "position in season table",
        },
    }
