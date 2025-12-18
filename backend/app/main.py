from __future__ import annotations

from fastapi import FastAPI

from .agent.pipeline import AgentPipeline
from .models.types import QueryRequest, QueryResponse

app = FastAPI(title="PL Data Copilot API")
pipeline = AgentPipeline()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    out = pipeline.run(req.question, summarize=req.summarize, include_rows=req.include_rows)
    return QueryResponse(sql=out.sql, columns=out.columns, rows=out.rows, summary=out.summary)
