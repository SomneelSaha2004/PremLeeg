from __future__ import annotations

# Golden questions for UI examples / guidelines.
# NOTE: these are NOT used in runtime prompting; they are for demo UX only.

GOLDEN = [
    # === MATCH RECORDS ===
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
    
    # === CLUB SEASON METRICS (test v_team_season_summary routing) ===
    {
        "question": "Which team collected the most points in a single Premier League season?",
        "expected": "100 points by Manchester City (2017/18). Must use v_team_season_summary or pl_season_table, NOT player views.",
        "tests": "COMPLETE-SEASON filter + correct view selection (team not player)",
    },
    {
        "question": "Which club scored the most goals in a single Premier League season?",
        "expected": "106 goals by Manchester City (2017/18). Must use v_team_season_summary.goals_for.",
        "tests": "CLUB_METRIC_SEASON routing to v_team_season_summary",
    },
    {
        "question": "Which team conceded the fewest goals in a Premier League season?",
        "expected": "15 goals by Chelsea (2004/05). Use v_team_season_summary.goals_against with ASC order.",
        "tests": "CLUB_METRIC_SEASON with ASC direction (fewest)",
    },
    {
        "question": "Which team had the most wins in a single Premier League season?",
        "expected": "32 wins by Man City (2017/18, 2018/19) and Liverpool (2019/20). TIE-SAFE.",
        "tests": "CLUB_METRIC_SEASON with TIE-SAFE pattern",
    },
    {
        "question": "Which club received the most yellow cards in a season?",
        "expected": "105 yellow cards by Chelsea (2023/24). Use v_team_season_summary.yellows.",
        "tests": "CLUB_METRIC_SEASON for discipline stats",
    },
    
    # === CLUB ALL-TIME METRICS (test SUM + GROUP BY routing) ===
    {
        "question": "Which club has scored the most goals in Premier League history?",
        "expected": "Must use SUM(goals_for) FROM v_team_season_summary GROUP BY team.",
        "tests": "CLUB_METRIC_ALL_TIME routing with aggregation",
    },
    {
        "question": "Which club has the most wins ever in the Premier League?",
        "expected": "Must use SUM(wins) FROM v_team_season_summary GROUP BY team.",
        "tests": "CLUB_METRIC_ALL_TIME routing",
    },
    {
        "question": "Which club has the most total points in Premier League history?",
        "expected": "Must use SUM(points) FROM v_team_season_summary GROUP BY team.",
        "tests": "CLUB_METRIC_ALL_TIME routing",
    },
    
    # === TITLES (test pl_season_table with rank=1) ===
    {
        "question": "Who has the most Premier League titles?",
        "expected": "Man United with 13 titles. Use pl_season_table WHERE rank=1 GROUP BY team.",
        "tests": "CLUB_TITLES routing to pl_season_table",
    },
    {
        "question": "Which clubs have won the Premier League?",
        "expected": "List of all clubs with at least one title. Use pl_season_table WHERE rank=1.",
        "tests": "CLUB_TITLES routing",
    },
    
    # === PLAYER FOR CLUB (test v_player_totals_by_squad routing) ===
    {
        "question": "Who is Liverpool's all-time top scorer?",
        "expected": "Use v_player_totals_by_squad WHERE squad='Liverpool' ORDER BY goals DESC.",
        "tests": "PLAYER_FOR_CLUB routing",
    },
    {
        "question": "Which player scored the most goals for Chelsea?",
        "expected": "Use v_player_totals_by_squad WHERE squad='Chelsea' ORDER BY goals DESC.",
        "tests": "PLAYER_FOR_CLUB routing",
    },
]
