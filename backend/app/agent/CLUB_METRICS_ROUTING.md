# Club-Level Metrics SQL Routing

## Overview

This module implements robust SQL source selection and query generation for club-level metrics in the Premier League stats pipeline. It follows strict constraints:

- **NO JOINS** of any kind
- **Prefer VIEWS** over base tables
- SQL must be PostgreSQL compatible
- Output must be deterministic and correct

## Routing Logic Order

The routing logic is applied in the following order (first match wins):

1. **CLUB_TITLES** - titles, trophies, seasons won, champions
   - Keywords: `titles`, `trophies`, `seasons won`, `won the league`, `champions`
   - Route to: `pl_season_table` with `WHERE rank = 1`

2. **MATCH_CONDITIONAL_CLUB_METRIC** - clean sheets, streaks, consecutive
   - Keywords: `clean sheet`, `consecutive`, `streak`, `unbeaten`, `in a row`
   - Route to: Appropriate streak view (e.g., `v_team_win_streaks`, `v_team_unbeaten_streaks`)

3. **PLAYER_FOR_CLUB** - player stats for a specific club
   - Keywords: `top scorer for`, `most goals for`, `leading scorer for`
   - Route to: `v_player_totals_by_squad`

4. **CLUB_METRIC_SEASON** - single season club metrics
   - Keywords: `in a season`, `single season`, `record season`
   - Route to: `v_team_season_summary`

5. **CLUB_METRIC_ALL_TIME** - all-time club aggregates
   - Keywords: `all-time`, `ever`, `history`, `overall`
   - Route to: `v_team_season_summary` with `SUM(...) GROUP BY team`

6. **AMBIGUOUS** - cannot safely decide
   - Returns retry token for clarification

## Key Views

### v_team_season_summary (PRIMARY DEFAULT FOR CLUB METRICS)
- **Grain**: one row per (team, season_start)
- **Columns**: team, season_start, played, wins, draws, losses, goals_for, goals_against, goal_diff, points, yellows, reds
- **Use for**:
  - "most X in a season" club metrics
  - All-time club aggregates by using `SUM(...) GROUP BY team`

### pl_season_table (TITLES / RANK-BASED)
- **Grain**: one row per (team, season_start, season_code)
- **Columns**: team, season_start, points, wins/draws/losses, rank
- **Use for**:
  - "seasons won", "most titles", "most league wins" (rank=1 counts)

### v_player_totals_by_squad (PLAYER AGGREGATES ONLY)
- **Grain**: player+club totals (not season club totals)
- **Use for**:
  - "most goals for a club by a player"
  - "top scorers for [club]"
- ⚠️ **Do NOT use** for club season totals

### Streak Views (PRECOMPUTED)
- `v_team_win_streaks` - consecutive wins
- `v_team_unbeaten_streaks` - unbeaten runs (all-time)
- `v_team_unbeaten_streaks_season` - unbeaten runs (single season)
- `v_team_clean_sheet_streaks` - consecutive clean sheets
- `v_team_scoring_streaks` - consecutive games with a goal

## Metric Mapping

Common phrases are mapped to columns with sort direction:

| Phrase | Column | Direction |
|--------|--------|-----------|
| "goals scored", "most goals" | `goals_for` | DESC |
| "conceded", "fewest conceded" | `goals_against` | ASC |
| "most conceded" | `goals_against` | DESC |
| "points", "most points" | `points` | DESC |
| "wins", "most wins" | `wins` | DESC |
| "yellow cards" | `yellows` | DESC |
| "red cards" | `reds` | DESC |
| "goal difference" | `goal_diff` | DESC |

### Direction Modifiers
- `most`, `highest`, `best`, `largest` → DESC
- `fewest`, `lowest`, `worst`, `least` → ASC

## SQL Templates

### Most goals scored by a club in a single season
```sql
SELECT team, season_start, goals_for
FROM public.v_team_season_summary
ORDER BY goals_for DESC NULLS LAST
LIMIT 1;
```

### Most goals scored by a club all-time
```sql
SELECT team, SUM(goals_for) AS total_goals
FROM public.v_team_season_summary
GROUP BY team
ORDER BY total_goals DESC NULLS LAST
LIMIT 1;
```

### Most seasons won (titles)
```sql
SELECT team, COUNT(*) AS titles
FROM public.pl_season_table
WHERE rank = 1
GROUP BY team
ORDER BY titles DESC
LIMIT 1;
```

## Guardrails

The system includes guardrails to prevent known bugs:

1. **v_player_totals_by_squad Misuse**: If question is about club season totals but SQL uses `v_player_totals_by_squad`, a warning is triggered and the query retries.

2. **Title Queries**: If question is about titles but SQL doesn't use `pl_season_table` with `rank = 1`, a warning is triggered.

3. **Streak Queries**: If question is about streaks but SQL uses raw match tables instead of precomputed streak views, a warning is triggered.

## Retry Mechanism

If routing is ambiguous or metric mapping fails, the system returns a retry token:

```
<<NEED_SCHEMA_OR_CLARIFICATION_RETRY>>
RETRY_REASON: <one line explanation>
CANDIDATE_SOURCES: [v_team_season_summary, pl_season_table, v_team_matches, v_player_totals_by_squad]
QUESTION: "<original question>"
```

## How to Add New Club Metrics

1. **Add the metric phrase** to `CLUB_METRIC_MAP` in `club_metrics_routing.py`:
   ```python
   CLUB_METRIC_MAP["new phrase"] = ("column_name", "DESC")
   ```

2. **Add keyword patterns** if needed:
   - For scope keywords: add to `SEASON_SCOPE_KEYWORDS` or `ALL_TIME_SCOPE_KEYWORDS`
   - For match-conditional: add to `MATCH_CONDITIONAL_KEYWORDS`

3. **Update tests** in `tests/test_club_metrics_routing.py`:
   - Add parametrized test cases for the new metric
   - Test both season and all-time variants

4. **Update prompts** if the LLM needs explicit guidance (in `prompts.py`)

## File Structure

```
backend/app/agent/
├── club_metrics_routing.py  # Core routing logic
├── validate_sql.py          # Integration with validation
├── pipeline.py              # Pipeline integration
├── prompts.py               # LLM prompt templates
└── ...

backend/tests/
├── test_club_metrics_routing.py  # Unit tests
└── ...
```

## Testing

Run tests with:
```bash
cd backend
python -m pytest tests/test_club_metrics_routing.py -v
```

## Known Limitations

1. **Attendance**: There is no attendance column in the schema. Questions about attendance should be handled gracefully (return "data not available").

2. **Partial Seasons**: For current/incomplete seasons, the complete-season filter should be applied to avoid incorrect rankings.

3. **Team Name Variants**: Team names must match the canonical database names (e.g., "Man City" not "Manchester City").
