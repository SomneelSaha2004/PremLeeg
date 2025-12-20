"""Golden query runner for manual verification.

Sends each question to the /query API and prints SQL, summary, and row samples.
Expected answers are documented for quick eyeballing; no automated asserts here.
Set API_URL env var to point at the running FastAPI service (default http://localhost:8000/query).

IMPORTANT: These golden prompts are for EVALUATION ONLY and must NOT be embedded
in the runtime SQL generation prompts to avoid data leakage.
"""

import json
import os
from typing import List, Dict

import requests

API_URL = os.getenv("API_URL", "http://localhost:8000/query")

# Golden questions with expected human answers (ASCII only)
# These test various failure modes: ties, complete seasons, streaks, team vs player disambiguation
GOLDEN: List[Dict[str, str]] = [
    # === MATCH RECORDS (test ties) ===
    {
        "question": "What's the biggest home win ever recorded in the Premier League?",
        "expected": "Multiple 9-0 wins: Man United 9-0 Ipswich Town (4 Mar 1995); Man United 9-0 Southampton (2 Feb 2021); Liverpool 9-0 AFC Bournemouth (27 Aug 2022). Should return ALL ties.",
        "tests": "TIE-SAFE pattern for home wins",
    },
    {
        "question": "What's the biggest away win in Premier League history?",
        "expected": "Southampton 0-9 Leicester City (25 Oct 2019). 9-goal margin.",
        "tests": "TIE-SAFE pattern for away wins",
    },
    {
        "question": "What is the highest-scoring match in Premier League history?",
        "expected": "Portsmouth 7-4 Reading (29 Sep 2007). 11 goals total.",
        "tests": "TIE-SAFE pattern for total goals",
    },
    {
        "question": "What's the highest-scoring draw ever in the Premier League?",
        "expected": "West Brom 5-5 Man United (19 May 2013). 10 goals total.",
        "tests": "TIE-SAFE pattern with draw filter",
    },
    
    # === TEAM SEASON RECORDS (test complete-season filter + ties) ===
    {
        "question": "Which team collected the most points in a single Premier League season?",
        "expected": "100 points by Manchester City (2017/18). Must use v_team_season_summary or pl_season_table, NOT player views.",
        "tests": "COMPLETE-SEASON filter + correct view selection (team not player)",
    },
    {
        "question": "Which team scored the most goals in a single Premier League season?",
        "expected": "106 goals by Manchester City (2017/18). Must use v_team_season_summary.goals_for or pl_season_table.gf.",
        "tests": "COMPLETE-SEASON filter + team view (NOT v_player_totals_by_squad)",
    },
    {
        "question": "Which team conceded the fewest goals in a Premier League season?",
        "expected": "15 goals conceded by Chelsea (2004/05). Must filter out incomplete 2025 season.",
        "tests": "COMPLETE-SEASON filter critical (avoid partial 2025 data)",
    },
    {
        "question": "Which team conceded the most goals in a Premier League season?",
        "expected": "104 goals conceded by Sheffield United (2023/24).",
        "tests": "COMPLETE-SEASON filter + TIE-SAFE",
    },
    {
        "question": "Which team had the fewest points in a Premier League season?",
        "expected": "11 points by Derby County (2007/08). Must filter out incomplete 2025 season.",
        "tests": "COMPLETE-SEASON filter critical (avoid partial 2025 data)",
    },
    {
        "question": "Which team won the most games in a single Premier League season?",
        "expected": "32 wins by Manchester City (2017/18 and 2018/19) and Liverpool (2019/20). Should return ALL ties.",
        "tests": "COMPLETE-SEASON + TIE-SAFE for multiple tied records",
    },
    
    # === TEAM DISCIPLINE (test correct view) ===
    {
        "question": "Which team received the most yellow cards in a single Premier League season?",
        "expected": "105 yellow cards by Chelsea (2023/24). Must use v_team_season_summary.yellows.",
        "tests": "Correct view selection (v_team_season_summary has yellows)",
    },
    {
        "question": "Which team got the most red cards in a single Premier League season?",
        "expected": "9 red cards by Sunderland (2009/10) and QPR (2011/12). Should return ALL ties.",
        "tests": "TIE-SAFE + v_team_season_summary.reds",
    },
    
    # === STREAK QUESTIONS (test precomputed streak views) ===
    {
        "question": "What is the longest winning streak by a team in the Premier League?",
        "expected": "18 consecutive wins by Manchester City (Aug-Dec 2017) and Liverpool (Oct 2019-Feb 2020).",
        "tests": "Must use v_team_win_streaks (precomputed), NOT manual window functions",
    },
    {
        "question": "Which team went the longest unbeaten in Premier League history?",
        "expected": "49 games unbeaten by Arsenal (May 2003-Oct 2004).",
        "tests": "Must use v_team_unbeaten_streaks (precomputed), NOT manual window functions",
    },
    {
        "question": "What is the longest unbeaten run in a single Premier League season?",
        "expected": "38 matches by Arsenal (2003/04 Invincibles season).",
        "tests": "Must use v_team_unbeaten_streaks_season for season-specific streaks",
    },
    {
        "question": "What is the longest clean sheet streak in Premier League history?",
        "expected": "Petr Cech/Chelsea kept 10 consecutive clean sheets (2004/05). Should use v_team_clean_sheet_streaks.",
        "tests": "Must use v_team_clean_sheet_streaks (precomputed)",
    },
    {
        "question": "Which team had the longest scoring streak in a single Premier League season?",
        "expected": "Should show consecutive matches where a team scored at least one goal.",
        "tests": "Must use v_team_scoring_streaks_season for season-specific scoring streaks",
    },
    {
        "question": "What is Arsenal's longest winning streak in the Premier League?",
        "expected": "14 consecutive wins by Arsenal.",
        "tests": "Must use v_team_win_streaks with team filter, NOT manual computation",
    },
    
    # === PLAYER SINGLE-SEASON RECORDS (test correct view + ties) ===
    {
        "question": "Who scored the most goals in a single Premier League season?",
        "expected": "36 goals by Erling Haaland (2022/23). Use pl_player_standard_stats.",
        "tests": "Player single-season record (NOT career totals)",
    },
    {
        "question": "Who provided the most assists in a single Premier League season?",
        "expected": "20 assists by Thierry Henry (2002/03) and Kevin De Bruyne (2019/20). Should return ALL ties.",
        "tests": "TIE-SAFE for player assists record",
    },
    {
        "question": "Which player had the most combined goals and assists in a single Premier League season?",
        "expected": "47 goal involvements by Andy Cole (1993/94), Alan Shearer (1994/95), and Mohamed Salah (2024/25). Should return ALL ties.",
        "tests": "TIE-SAFE for combined stat (performance_g_plus_a)",
    },
    
    # === PLAYER CAREER/CLUB RECORDS (test view selection) ===
    {
        "question": "Who is the Premier League's all-time leading goal scorer?",
        "expected": "260 goals by Alan Shearer (1992/93-2005/06). Use v_player_career_totals.",
        "tests": "ALL-TIME = v_player_career_totals (not single season)",
    },
    {
        "question": "Who is the Premier League's all-time assist leader?",
        "expected": "162 assists by Ryan Giggs (1992/93-2013/14). Use v_player_career_totals.",
        "tests": "ALL-TIME = v_player_career_totals",
    },
    {
        "question": "Which player scored the most Premier League goals for a single club?",
        "expected": "213 goals by Harry Kane for Tottenham Hotspur (2013/14-2022/23). Use v_player_totals_by_squad.",
        "tests": "CLUB-SPECIFIC = v_player_totals_by_squad (not career totals)",
    },
]


def run_all():
    print(f"Using API_URL={API_URL}")
    passed = 0
    failed = 0
    
    for idx, item in enumerate(GOLDEN, start=1):
        q = item["question"]
        expected = item["expected"]
        tests = item.get("tests", "")
        print("\n" + "=" * 80)
        print(f"[{idx}] Question: {q}")
        print(f"Expected: {expected}")
        print(f"Tests: {tests}")

        try:
            resp = requests.post(
                API_URL,
                headers={"Content-Type": "application/json"},
                data=json.dumps({"question": q, "include_rows": True, "summarize": True}),
                timeout=30,
            )
        except Exception as exc:  # network or other errors
            print(f"Error: {exc}")
            failed += 1
            continue

        if resp.status_code != 200:
            print(f"HTTP {resp.status_code}: {resp.text}")
            failed += 1
            continue

        payload = resp.json()
        print("SQL:")
        print(payload.get("sql"))

        summary = payload.get("summary", "")
        if summary:
            print("Summary:")
            print(summary)

        rows = payload.get("rows") or []
        row_count = len(rows)
        print(f"Row count: {row_count}")
        
        if rows:
            print("Rows (sample):")
            print(json.dumps(rows[:5], indent=2, default=str))
        
        # Check for retry tokens (indicates failure)
        retry_token = payload.get("retry_token")
        if retry_token:
            print(f"RETRY TOKEN: {retry_token}")
            print(f"RETRY REASON: {payload.get('retry_reason')}")
            failed += 1
        else:
            passed += 1
    
    print("\n" + "=" * 80)
    print(f"SUMMARY: {passed} passed, {failed} failed out of {len(GOLDEN)}")


if __name__ == "__main__":
    run_all()
