from __future__ import annotations

# IMPORTANT: Non-betting only. Curated from football-data.co.uk notes.txt (as provided by you).
FOOTBALL_DATA_NOTES_NON_BETTING = """
FOOTBALL-DATA COLUMN REFERENCE (NON-BETTING ONLY)

Core match info:
- Div = League Division (E0 = English Premier League)
- Date = Match date (DD/MM/YY)
- Time = Kickoff time
- HomeTeam = Home team name
- AwayTeam = Away team name

Full-time results:
- FTHG (HG) = Full-time home goals
- FTAG (AG) = Full-time away goals
- FTR (Res) = Full-time result (H=Home win, D=Draw, A=Away win)

Half-time results:
- HTHG = Half-time home goals
- HTAG = Half-time away goals
- HTR = Half-time result (H=Home win, D=Draw, A=Away win)

Match statistics (where available):
- Attendance = Crowd attendance
- Referee = Match referee
- HS = Home shots
- AS = Away shots
- HST = Home shots on target
- AST = Away shots on target
- HHW = Home hit woodwork
- AHW = Away hit woodwork
- HC = Home corners
- AC = Away corners
- HF = Home fouls committed
- AF = Away fouls committed
- HO = Home offsides
- AO = Away offsides
- HY = Home yellow cards
- AY = Away yellow cards
- HR = Home red cards
- AR = Away red cards

Important note:
- English/Scottish yellow cards do NOT include the initial yellow that later becomes a second yellow leading to a red.
""".strip()
