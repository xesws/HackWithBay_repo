"""FastAPI scorer service (contracts.md §4.3).

  POST /score           §4.1 request -> §4.2 verdict (synchronous, <= 60s)
  POST /admin/load_ref  reload the reference graph (humans only)
  GET  /health          liveness + reference stats

`get_reference()` is the backend factory. `SCORER_REFERENCE_BACKEND` selects it:

  * ``auto`` (default) — use the live `Neo4jReference` (bolt + GDS) when Neo4j is
    reachable; only if it is NOT reachable fall back to the in-memory CSV backend
    (emergency demo tier — NOT an acceptable submitted state).
  * ``neo4j`` — force Neo4j; raise loudly if the pod is unreachable.
  * ``memory`` — force the in-memory CSV backend (tests / emergency).
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .models import ScoreRequest, ScoreResponse
from .reference import InMemoryReference, ReferenceGraph
from .scoring import score_job
from .verify import router as verify_router  # Track B, Shape 2 /verify (territory exemption)

_reference: ReferenceGraph | None = None


def _build_reference() -> ReferenceGraph:
    backend = os.environ.get("SCORER_REFERENCE_BACKEND", "auto").lower()

    if backend == "memory":
        return InMemoryReference.from_csv()

    if backend == "neo4j":
        from .reference_neo4j import Neo4jReference

        return Neo4jReference.from_env()  # raises if the pod is unreachable

    # auto: prefer live Neo4j; degrade to in-memory ONLY if it is unreachable.
    try:
        from .reference_neo4j import Neo4jReference

        return Neo4jReference.from_env()
    except Exception as exc:  # pragma: no cover - emergency demo tier
        print(
            f"[scorer] WARNING: Neo4j backend unavailable ({exc!r}); "
            "falling back to EMERGENCY in-memory CSV backend.",
            file=sys.stderr,
        )
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

from fastapi.middleware.cors import CORSMiddleware  # browser SPA -> /verify is cross-origin
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(verify_router)  # Track B /verify (Shape 2, single public port)


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
