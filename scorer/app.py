"""FastAPI scorer service (contracts.md §4.3).

  POST /score           §4.1 request -> §4.2 verdict (synchronous, <= 60s)
  POST /admin/load_ref  reload the reference graph from CSV (humans only)
  GET  /health          liveness + reference stats

`get_reference()` is the backend factory. Today it returns `InMemoryReference`
(CSV, no database). A `SCORER_REFERENCE_BACKEND=neo4j` env hook is left in place
so a future `Neo4jReference` can be dropped in without touching the scorer.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .models import ScoreRequest, ScoreResponse
from .reference import InMemoryReference, ReferenceGraph
from .scoring import score_job

_reference: ReferenceGraph | None = None


def _build_reference() -> ReferenceGraph:
    backend = os.environ.get("SCORER_REFERENCE_BACKEND", "memory").lower()
    if backend == "neo4j":
        # Env hook only — the GDS-backed backend is a documented TODO (A4).
        from .reference_neo4j import Neo4jReference

        return Neo4jReference.from_env()
    return InMemoryReference.from_csv()


def get_reference() -> ReferenceGraph:
    """Return the process-wide reference graph, building it on first use."""
    global _reference
    if _reference is None:
        _reference = _build_reference()
    return _reference


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_reference()  # preload so the first /score is warm
    yield


app = FastAPI(title="GraphJudge Scorer", version="0.1", lifespan=lifespan)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "reference": get_reference().stats()}


@app.post("/score", response_model=ScoreResponse)
def score(request: ScoreRequest) -> ScoreResponse:
    return score_job(request, get_reference())


@app.post("/admin/load_ref")
def load_ref() -> dict:
    """Rebuild the reference graph from CSV (or the configured backend)."""
    global _reference
    _reference = _build_reference()
    return {"reloaded": True, "reference": _reference.stats()}
