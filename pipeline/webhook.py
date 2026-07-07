#!/usr/bin/env python3
"""webhook — GraphJudge product-facing API (contracts.md §4.4, Track B / card B3).

POST /  body: {"user_id": "...", "job_id": "...", "text": "..."}
    -> credit gate -> extract §4.1 claims -> score -> respond §4.2 (passed through).
    -> on insufficient credits: {"error": "insufficient_credits", "balance": 0}.

Fully OFFLINE by default:
  * credit_gate()          = in-memory stub  (SEAM -> C2 consume_credit)
  * extraction             = deterministic regex inverse of sentence_for (no LLM)
  * scoring                = mock_scorer.mock_score_claims (SEAM -> A3 scorer)

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

from pipeline.extract_claims import extract_claims
from pipeline.mock_scorer import mock_score_claims

app = FastAPI(title="GraphJudge pipeline webhook", version="0.1-skeleton")

# in-memory credit stub: default users have plenty; these are treated as broke so
# the zero-credit path is exercisable offline. (SEAM: replaced by C2 below.)
_STUB_DEFAULT_BALANCE = 100
_STUB_BROKE_USERS = {"u_nocredit", "u_broke"}


class JobRequest(BaseModel):
    user_id: str
    job_id: str
    text: str


# --- SEAM: credit gate ---------------------------------------------------------
def credit_gate(user_id: str) -> dict[str, Any]:
    """Stub for Track C `consume_credit(user_id, job_id)` (contracts §4.5).

    Real version: single-transaction call to Butterbase `consume_credit` that
    inserts delta=-1 when balance>0 and returns {"ok": bool, "balance": int}.
    Here: an in-memory heuristic so the chain runs with no backend.
    """
    if user_id in _STUB_BROKE_USERS:
        return {"ok": False, "balance": 0}
    return {"ok": True, "balance": _STUB_DEFAULT_BALANCE}


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
    gate = credit_gate(req.user_id)
    if not gate.get("ok"):
        return JSONResponse({"error": "insufficient_credits", "balance": gate.get("balance", 0)})

    payload = extract_claims(req.job_id, req.text, validate=True)  # offline §4.1
    verdict = score(req.job_id, payload["claims"])                 # §4.2 (mock or real)
    return JSONResponse(verdict)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {"ok": True, "scorer": "live" if os.environ.get("SCORER_URL") else "mock"}
