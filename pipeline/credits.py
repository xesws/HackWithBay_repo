#!/usr/bin/env python3
"""credits — Butterbase credit + persistence seams for the pipeline (Track B).

Single source of truth for the two service-side backends that both the
`/verify` route (scorer/verify.py, Shape 2) and the standalone webhook
(pipeline/webhook.py, Shape 1) call:

  * consume_credit(user_id, job_id) -> {"ok": bool, "balance": int}
        Track C `consume_credit` fn (contracts §4.5). Single-transaction debit:
        balance>0 -> insert delta=-1 and return ok=true; else ok=false.
  * persist_result(job_id, user_id, verdict) -> None
        Upsert `jobs` + insert `results(job_id, user_id, verdict_json)` (§4.5,
        live schema). Best-effort: never raises into the request path.

ENV-GATED, degrades gracefully OFFLINE (no pod, no backend):
  * CONSUME_CREDIT_URL set -> real HTTP POST to the Butterbase fn.
    unset            -> in-memory stub (broke users -> ok:false) so the whole
                        chain runs with no backend.
  * PERSIST_RESULT_URL set -> real HTTP POST (upsert jobs + insert results).
    unset            -> no-op (logged). Persistence is optional for the verdict.

Butterbase is a single service secret (`bb_sk_`, contracts §4.7) that lives ONLY
server-side. We send it on BOTH common header spellings and let the fn ignore
the one it doesn't use; confirm the exact spelling at integration (see
pipeline/PHASE2_CHECKLIST.md §f). It is never logged.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any

log = logging.getLogger("graphjudge.pipeline.credits")

# offline stub knobs (mirror webhook's original in-memory gate so the
# zero-credit path stays exercisable with no backend).
_STUB_DEFAULT_BALANCE = 100
_STUB_BROKE_USERS = {"u_nocredit", "u_broke"}


def _auth_headers() -> dict[str, str]:
    """Service-role auth for Butterbase fns. bb_sk_ never appears in logs."""
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("BUTTERBASE_API_KEY")
    if key:
        # Send both spellings; the fn honours whichever it checks. Pin the real
        # one at integration (CHECKLIST §f) and drop the other if desired.
        headers["Authorization"] = f"Bearer {key}"
        headers["x-butterbase-key"] = key
    return headers


def _post_json(url: str, body: dict[str, Any], *, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=_auth_headers(),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # pragma: no cover - needs live backend
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else {}


# --- credit gate ---------------------------------------------------------------
def consume_credit(user_id: str, job_id: str) -> dict[str, Any]:
    """Consume one credit for `user_id` (contracts §4.5 `consume_credit`).

    Returns {"ok": bool, "balance": int}. Real backend when CONSUME_CREDIT_URL is
    set; otherwise an in-memory stub so the chain runs offline.
    """
    url = os.environ.get("CONSUME_CREDIT_URL")
    if url:
        result = _post_json(url, {"user_id": user_id, "job_id": job_id})
        return {"ok": bool(result.get("ok")), "balance": int(result.get("balance", 0))}
    # offline stub
    if user_id in _STUB_BROKE_USERS:
        return {"ok": False, "balance": 0}
    return {"ok": True, "balance": _STUB_DEFAULT_BALANCE}


# --- persistence ---------------------------------------------------------------
def persist_result(job_id: str, user_id: str, verdict: dict[str, Any]) -> bool:
    """Upsert `jobs` + insert `results` for this job (contracts §4.5, live schema).

    Best-effort: returns True on success, False if skipped/failed, and NEVER
    raises into the request path (a stored verdict must not gate the response).
    Real backend when PERSIST_RESULT_URL is set; otherwise a logged no-op.
    """
    url = os.environ.get("PERSIST_RESULT_URL")
    if not url:
        log.info("persist_result: no PERSIST_RESULT_URL -> skipping persist for job_id=%s", job_id)
        return False
    body = {
        "job_id": job_id,
        "user_id": user_id,
        "status": "done",
        "verdict_json": verdict,  # results.verdict_json jsonb (live schema, §4.5)
    }
    try:
        _post_json(url, body)
        return True
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:  # pragma: no cover - needs live backend
        log.warning("persist_result failed (non-fatal) for job_id=%s: %s", job_id, exc)
        return False


__all__ = ["consume_credit", "persist_result"]
