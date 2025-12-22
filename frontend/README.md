# PLQuery Frontend (Demo)

React + Chakra UI demo dashboard for the PLQuery backend.

## Run

From the repo root:

1) Start backend (FastAPI):
- `cd backend`
- `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

2) Start frontend (Vite):
- `cd frontend`
- `npm install`
- `npm run dev`

Then open `http://localhost:5173`.

## Backend wiring

- Frontend calls `GET /api/schema`, `GET /api/golden-prompts`, `POST /api/query`.
- `frontend/vite.config.js` proxies `/api` to `http://localhost:8000` during development.
