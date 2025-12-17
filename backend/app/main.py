from fastapi import FastAPI, HTTPException
from .models.types import QueryRequest, QueryResponse
from .agent.pipeline import run_pipeline

app = FastAPI(title="Premier League Data Copilot API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest) -> QueryResponse:
    try:
        result = run_pipeline(req.question, limit=req.limit)
        return result
    except Exception as exc:  # noqa: BLE001
        # Keep generic to avoid leaking internals
        raise HTTPException(status_code=500, detail="Query failed") from exc
