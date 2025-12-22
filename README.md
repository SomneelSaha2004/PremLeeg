# PLQuery

> Natural language SQL agent for Premier League analytics

Ask questions about 25 seasons of Premier League data in plain English. Powered by an AI SQL agent that generates, validates, and executes queries automatically.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Node](https://img.shields.io/badge/Node-18+-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- **Natural Language Queries**: Ask questions like "Which team scored the most goals in 2023-24?"
- **Multi-Query Mode**: Generates 3 diverse SQL approaches for better accuracy
- **SQL Validation**: SELECT-only enforcement, table/column allowlists, CTE support
- **Streak Analysis**: 7 precomputed streak views (win, unbeaten, clean sheet, etc.)
- **Real-time Trace**: See the LLM's reasoning and query iterations

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 18, Vite, Chakra UI |
| Backend | FastAPI, Python 3.11+ |
| Database | PostgreSQL (Supabase) |
| AI | OpenAI GPT-4o-mini, LangChain |
| SQL Parsing | sqlglot |

## Project Structure

```
PLQuery/
├── backend/           # FastAPI server + SQL agent
│   ├── app/
│   │   ├── agent/     # SQL generation, validation, prompts
│   │   ├── context/   # Team names, data notes
│   │   ├── db/        # Database client
│   │   ├── llm/       # LangChain/OpenAI client
│   │   └── models/    # Pydantic types
│   └── requirements.txt
├── frontend/          # React + Vite app
│   ├── src/
│   │   ├── components/
│   │   └── api.js
│   └── package.json
├── data/              # Data pipeline scripts
│   ├── epl/           # Match data scraper
│   ├── fbref_player/  # Player stats scraper
│   └── requirements.txt
└── schema_snapshot.json
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL database (or Supabase account)
- OpenAI API key

### 1. Clone & Setup Environment

```bash
git clone https://github.com/SomneelSaha2004/PLQuery.git
cd PLQuery

# Copy environment template
cp .env.example .env
# Edit .env with your DATABASE_URL and OPENAI_API_KEY
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### 4. Open the App

Navigate to [http://localhost:5173](http://localhost:5173)

## Data Pipeline (Optional)

If you need to refresh the data:

```bash
cd data
pip install -r requirements.txt

# Download match data
python epl/download_and_clean_epl.py

# Scrape player stats (requires Chrome + ChromeDriver)
python fbref_player/scrape_fbref_player_standard_raw_all_seasons.py
python fbref_player/finalize_all_for_db.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `OPENAI_MODEL` | No | Model name (default: gpt-4o-mini) |
| `FRONTEND_URL` | No | Frontend URL for CORS |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/query` | POST | Execute natural language query |
| `/api/schema` | GET | Get database schema snapshot |
| `/api/golden-prompts` | GET | Get example queries |
| `/health` | GET | Health check |

## License

MIT

## Author

[Somneel Saha](https://github.com/SomneelSaha2004)
