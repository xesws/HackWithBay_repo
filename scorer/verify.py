#!/usr/bin/env python3
"""verify — GraphJudge product-facing pipeline route (Shape 2, Track B).

`POST /verify` is the single public entry point for the product (contracts §4.4).
It is a self-contained FastAPI **APIRouter** so it can be mounted on Track A's
scorer app WITHOUT editing scorer/app.py (territory ruling). Track A / the
orchestrator adds exactly these two lines to scorer/app.py:

    from scorer.verify import router
    app.include_router(router)

Flow (contracts §4.4 -> §4.2):
    body {user_id, job_id?, text}
      -> job_id = uuid4() if absent            (contracts v1.1, decisions #1)
      -> consume_credit(user_id, job_id)       (Track C §4.5; insufficient ->
                                                {"error":"insufficient_credits","balance":0})
      -> run the graphjudge.pipe                (extract §4.1 -> score §4.2)
           * primary : rocketride SDK, in-process  (PIPELINE_USE_ROCKETRIDE=1)
           * fallback : direct Python (extract_claims + scorer.scoring)  [always works]
      -> persist_result(job_id, user_id, verdict)  (best-effort, §4.5 results/jobs)
      -> return the §4.2 verdict verbatim

Runs fully OFFLINE by default: with no CONSUME_CREDIT_URL / PERSIST_RESULT_URL /
PIPELINE_USE_ROCKETRIDE the route still returns a real §4.2 verdict via the direct
path (reusing Track A's real scorer.scoring, not a mock). Point the SPA submit at
{SCORER_URL}/verify (contracts §4.4).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pipeline.credits import consume_credit, persist_result
from pipeline.extract_claims import extract_claims

log = logging.getLogger("graphjudge.scorer.verify")

router = APIRouter()

# path to the RocketRide pipeline definition (Track B deliverable 1).
PIPE_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "graphjudge.pipe"


class VerifyRequest(BaseModel):
    """contracts §4.4 body. job_id is optional (uuid4 minted here if absent)."""

    user_id: str
    text: str
    job_id: Optional[str] = None


# --- reference (deferred import: scorer.app includes THIS router) ---------------
def _reference() -> Any:
    """Return the process-wide reference graph.

    Deferred import breaks the app<->verify import cycle (scorer/app.py does
    `from scorer.verify import router`). Prefer scorer.app.get_reference so we
    share the app's preloaded/warmed instance; fall back to building from CSV
    when the router is exercised standalone (offline tests).
    """
    try:
        from scorer.app import get_reference

        return get_reference()
    except Exception:  # pragma: no cover - standalone/offline
        from scorer.reference import InMemoryReference

        return InMemoryReference.from_csv()


# --- pipeline execution: primary (SDK) + documented fallback (direct) ----------
def _run_direct(job_id: str, text: str) -> dict[str, Any]:
    """DIRECT-PYTHON FALLBACK (documented): extract §4.1 -> score §4.2 in-process.

    Reuses Track A's REAL scorer (scorer.scoring.score_job over the CSV reference
    graph) — not a mock. This is the guaranteed path used whenever the rocketride
    SDK path is disabled or fails, so /verify always returns a valid §4.2 verdict.
    """
    # local import keeps the module importable even if scorer deps shift.
    from scorer.models import ScoreRequest
    from scorer.scoring import score_job

    # §4.1: auto-selects OpenRouter (z-ai/glm-5.2) when OPENROUTER_API_KEY is set,
    # else the deterministic offline regex extractor (works with no key).
    payload = extract_claims(job_id, text, validate=True)
    request = ScoreRequest(job_id=job_id, claims=payload["claims"])
    verdict = score_job(request, _reference())  # §4.2 (real scoring)
    return verdict.model_dump()


def _extract_verdict(result: Any) -> Optional[dict[str, Any]]:
    """Pull the §4.2 verdict out of a rocketride PIPELINE_RESULT (shape-tolerant).

    The `respond` component's payload can surface under a few keys depending on
    runtime version; try the common ones, parsing JSON strings. Returns None if
    nothing verdict-shaped is found (caller then uses the direct fallback).
    """
    def _as_dict(obj: Any) -> Optional[dict[str, Any]]:
        if isinstance(obj, str):
            try:
                obj = json.loads(obj)
            except (ValueError, TypeError):
                return None
        if isinstance(obj, dict) and "job_id" in obj and "graph" in obj:
            return obj
        return None

    if not isinstance(result, dict):
        return None
    # direct hit
    hit = _as_dict(result)
    if hit:
        return hit
    # common containers: answers[0], output, result, data
    answers = result.get("answers")
    if isinstance(answers, list) and answers:
        hit = _as_dict(answers[0])
        if hit:
            return hit
    for key in ("output", "result", "data", "verdict"):
        hit = _as_dict(result.get(key))
        if hit:
            return hit
    return None


async def _run_via_rocketride(job_id: str, user_id: str, text: str) -> Optional[dict[str, Any]]:
    """PRIMARY PATH: run pipeline/graphjudge.pipe via the rocketride SDK in-process.

    Gated behind PIPELINE_USE_ROCKETRIDE=1 (default off). Connects to the
    self-hosted RocketRide runtime (Cloud waived, decisions #0), starts the pipe
    with `use(filepath=...)`, feeds the §4.4 body with `send`, and pulls the §4.2
    verdict from the result. Any failure -> returns None so the caller falls back
    to _run_direct. NOTE: the exact PIPELINE_RESULT lane shape is confirmed at
    integration (CHECKLIST §d); _extract_verdict is deliberately shape-tolerant.
    """
    from rocketride import RocketRideClient  # local import: optional dependency path

    body = json.dumps({"user_id": user_id, "job_id": job_id, "text": text})
    client = RocketRideClient()
    try:
        # connect() picks up runtime host/key from the client env/.env config.
        if hasattr(client, "connect"):
            await client.connect()
        started = await client.use(filepath=str(PIPE_PATH), use_existing=True)
        token = started.get("token")
        if not token:
            log.warning("rocketride use() returned no token; falling back")
            return None
        result = await client.send(token, body, mimetype="application/json")
        return _extract_verdict(result)
    finally:
        if hasattr(client, "disconnect"):
            try:
                await client.disconnect()
            except Exception:  # pragma: no cover
                pass


# --- route ---------------------------------------------------------------------
@router.post("/verify")
async def verify(req: VerifyRequest) -> JSONResponse:
    job_id = req.job_id or str(uuid4())  # §4.1 job_id is uuid4 (v1.1, decisions #1)

    gate = consume_credit(req.user_id, job_id)  # §4.5
    if not gate.get("ok"):
        return JSONResponse({"error": "insufficient_credits", "balance": gate.get("balance", 0)})

    verdict: Optional[dict[str, Any]] = None
    if os.environ.get("PIPELINE_USE_ROCKETRIDE") == "1":
        try:
            verdict = await _run_via_rocketride(job_id, req.user_id, req.text)
        except Exception as exc:  # pragma: no cover - needs live runtime
            log.warning("rocketride path failed for job_id=%s (%s); using direct fallback", job_id, exc)
            verdict = None
    if verdict is None:
        verdict = _run_direct(job_id, req.text)  # guaranteed §4.2

    persist_result(job_id, req.user_id, verdict)  # best-effort, never fatal
    return JSONResponse(verdict)


@router.get("/verify/healthz")
def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "pipe": PIPE_PATH.name,
        "rocketride": os.environ.get("PIPELINE_USE_ROCKETRIDE") == "1",
        "credit_backend": "live" if os.environ.get("CONSUME_CREDIT_URL") else "stub",
        "persist_backend": "live" if os.environ.get("PERSIST_RESULT_URL") else "noop",
    }
