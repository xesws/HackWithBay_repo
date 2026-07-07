#!/usr/bin/env python3
"""webhook — GraphJudge product-facing API (contracts.md §4.4, Track B / card B3).

POST /  body: {"user_id": "...", "job_id": "...", "text": "..."}
    -> credit gate -> extract §4.1 claims -> score -> respond §4.2 (passed through).
    -> on insufficient credits: {"error": "insufficient_credits", "balance": 0}.

B3-real: both seams call the real backends when configured, and degrade OFFLINE:
  * credit_gate  -> pipeline.credits.consume_credit  (Track C §4.5 fn when
                    CONSUME_CREDIT_URL is set; in-memory stub otherwise)
  * scoring      -> POST {SCORER_URL}/score  (real Track A scorer §4.3 when
                    SCORER_URL is set; mock_scorer.mock_score_claims otherwise)
  * extraction   -> deterministic regex inverse of sentence_for (no LLM key)

NOTE: Shape 2 (the shipped product API) is scorer/verify.py's `POST /verify`.
This standalone webhook (Shape 1) is kept as an offline-friendly harness / the
alternate single-purpose deployment; it shares the credit seam with /verify.

Run:  uvicorn pipeline.webhook:app --host 127.0.0.1 --port 8080
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pipeline.credits import consume_credit
from pipeline.extract_claims import extract_claims
from pipeline.mock_scorer import mock_score_claims

app = FastAPI(title="GraphJudge pipeline webhook", version="0.1-skeleton")


class JobRequest(BaseModel):
    user_id: str
    job_id: str
    text: str


# --- SEAM: credit gate (B3-real -> pipeline.credits.consume_credit) ------------
def credit_gate(user_id: str, job_id: str) -> dict[str, Any]:
    """Consume one credit (contracts §4.5).

    Delegates to pipeline.credits.consume_credit: the real Butterbase fn when
    CONSUME_CREDIT_URL is set, else an in-memory stub so the chain runs offline.
    """
    return consume_credit(user_id, job_id)


# --- SEAM: scorer --------------------------------------------------------------
def score(job_id: str, claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Score §4.1 claims into a §4.2 verdict.

    If SCORER_URL is set -> POST {SCORER_URL}/score (the real Track-A scorer,
    contracts §4.3). Otherwise -> offline mock_score_claims stub.
    """
    scorer_url = os.environ.get("SCORER_URL")
    if scorer_url:
        payload = {"job_id": job_id, "claims": claims}
        request = urllib.request.Request(
            f"{scorer_url.rstrip('/')}/score",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:  # pragma: no cover - needs live scorer
            return json.loads(response.read().decode("utf-8"))
    return mock_score_claims(job_id, claims)


@app.post("/")
def handle(req: JobRequest) -> JSONResponse:
    gate = credit_gate(req.user_id, req.job_id)
    if not gate.get("ok"):
        return JSONResponse({"error": "insufficient_credits", "balance": gate.get("balance", 0)})

    payload = extract_claims(req.job_id, req.text, validate=True)  # offline §4.1
    verdict = score(req.job_id, payload["claims"])                 # §4.2 (mock or real)
    return JSONResponse(verdict)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "scorer": "live" if os.environ.get("SCORER_URL") else "mock",
        "credit_backend": "live" if os.environ.get("CONSUME_CREDIT_URL") else "stub",
    }
