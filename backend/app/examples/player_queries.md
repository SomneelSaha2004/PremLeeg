# Player query CLI examples

Run from repository root (ensuring `DATABASE_URL_READONLY` is set):

1) Top scorers in 2018/2019
```
python -m backend.app.cli --question "Who has the most goals in 2018/2019?" --max-rows 10
```

2) Top 10 assists in 2022/2023
```
python -m backend.app.cli --question "Top 10 assists in 2022/2023?" --max-rows 10
```

3) Best per-90 goal scorers since 2010 with minutes floor
```
python -m backend.app.cli --question "Best per-90 goal scorers since 2010 (min 900 minutes)?" --max-rows 15
```

4) Team-specific player filter (Arsenal xG leaders in 2024/2025)
```
python -m backend.app.cli --question "Which Arsenal player has the highest xG in 2024/2025?" --max-rows 10
```

5) Player comparison by per-90 goals in a season
```
python -m backend.app.cli --question "Compare Salah vs Kane goals per 90 in 2017/2018" --max-rows 5
```

Toggles: add `--no-summary` to skip LLM summarization or `--no-rows` to omit row output if you only need the SQL.
