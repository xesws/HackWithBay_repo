#!/usr/bin/env python3
"""Runtime helpers for the live GraphJudge RocketRide proof.

These functions are deliberately thin and production-facing:
  * credit_gate -> live Butterbase consume_credit when strict=True
  * extract_claims_runtime -> same extractor used by /verify direct path
  * score_http -> POST {SCORER_URL}/score, not in-process scorer

They are importable both from `pipeline/graphjudge.pipe` custom Python steps and
from `scripts/run_rocketride_live.py`, which records the proof artifacts.
"""

from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path
from typing import Any, Callable

import jsonschema

from pipeline.credits import consume_credit, persist_result
from pipeline.extract_claims import extract_claims

VERDICT_SCHEMA = Path(__file__).resolve().parent / "schemas" / "verdict.schema.json"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _post_json(url: str, body: dict[str, Any], *, timeout: int = 60) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "GraphJudge-RocketRide-Proof/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else {}


def load_verdict_schema() -> dict[str, Any]:
    return json.loads(VERDICT_SCHEMA.read_text(encoding="utf-8"))


def validate_verdict(verdict: dict[str, Any]) -> dict[str, Any]:
    jsonschema.validate(verdict, load_verdict_schema())
    return verdict


def extract_verdict_from_result(result: Any) -> dict[str, Any] | None:
    """Find a section 4.2 verdict in common RocketRide response shapes."""

    def as_verdict(obj: Any) -> dict[str, Any] | None:
        if isinstance(obj, str):
            try:
                obj = json.loads(obj)
            except (TypeError, ValueError):
                for line in reversed([part.strip() for part in obj.splitlines() if part.strip()]):
                    try:
                        parsed = json.loads(line)
                    except (TypeError, ValueError):
                        continue
                    hit = as_verdict(parsed)
                    if hit is not None:
                        return hit
                return None
        if isinstance(obj, dict) and "job_id" in obj and "graph" in obj:
            return obj
        return None

    hit = as_verdict(result)
    if hit is not None:
        return hit
    if not isinstance(result, dict):
        return None

    for key in ("verdict", "output", "result", "data", "body", "text", "answers", "documents", "questions"):
        hit = as_verdict(result.get(key))
        if hit is not None:
            return hit

    for key in ("answers", "text", "documents", "questions"):
        value = result.get(key)
        if isinstance(value, list):
            for item in value:
                hit = as_verdict(item)
                if hit is not None:
                    return hit
    return None


def credit_gate(
    user_id: str,
    job_id: str,
    bearer: str | None = None,
    strict: bool = False,
    credit_already_consumed: bool = False,
) -> dict[str, Any]:
    """Run or intentionally skip the live credit gate."""
    if _as_bool(credit_already_consumed):
        return {"ok": True, "balance": -1, "already_consumed": True}
    return consume_credit(user_id, job_id, bearer=bearer, strict=_as_bool(strict))


def extract_claims_runtime(job_id: str, text: str, validate: bool = True) -> dict[str, Any]:
    """Extract section 4.1 claims with the same behavior as the direct /verify path.

    `extract_claims()` uses OpenRouter when configured, then falls back to the
    deterministic personal-domain extractor when the model fails or returns no
    claims for a template-shaped sentence. Keeping RocketRide on this helper
    prevents demo drift such as `Corwin Mavik manages XXXX.` producing an empty
    graph only on the RocketRide path.
    """
    return extract_claims(job_id, text, validate=_as_bool(validate))


def score_http(job_id: str, claims: list[dict[str, Any]], scorer_url: str | None = None) -> dict[str, Any]:
    """Score claims through the public scorer HTTP endpoint."""
    base = (scorer_url or os.environ.get("SCORER_URL") or "").rstrip("/")
    if not base:
        raise RuntimeError("SCORER_URL is not set; live proof requires POST {SCORER_URL}/score")
    verdict = _post_json(f"{base}/score", {"job_id": job_id, "claims": claims}, timeout=60)
    return validate_verdict(verdict)


def persist_passthrough(job_id: str, user_id: str, verdict: dict[str, Any]) -> dict[str, Any]:
    persist_result(job_id, user_id, verdict)
    return verdict


def run_production_steps(
    *,
    user_id: str,
    job_id: str,
    text: str,
    bearer: str | None,
    log_step: Callable[[str, Any], None] | None = None,
    credit_already_consumed: bool = False,
) -> dict[str, Any]:
    """Execute the graphjudge.pipe steps against live production endpoints."""

    def log(name: str, **fields: Any) -> None:
        if log_step is not None:
            log_step(name, fields)

    log("credit_gate.start", backend="live", already_consumed=credit_already_consumed)
    gate = credit_gate(
        user_id=user_id,
        job_id=job_id,
        bearer=bearer,
        strict=True,
        credit_already_consumed=credit_already_consumed,
    )
    log("credit_gate.done", ok=gate.get("ok"), balance=gate.get("balance"), degraded=gate.get("degraded", False))
    if not gate.get("ok"):
        raise RuntimeError(f"consume_credit denied the run: balance={gate.get('balance', 0)}")

    log("extract_claims.start", backend="OpenRouter+deterministic-fallback")
    claims_payload = extract_claims_runtime(job_id, text, validate=True)
    log("extract_claims.done", claims=len(claims_payload["claims"]))

    log("score.start", scorer_url_set=bool(os.environ.get("SCORER_URL")))
    verdict = score_http(job_id, claims_payload["claims"])
    log(
        "score.done",
        doc_score=verdict.get("doc_score"),
        claims=len(verdict.get("claims", [])),
        nodes=len(verdict.get("graph", {}).get("nodes", [])),
        edges=len(verdict.get("graph", {}).get("edges", [])),
    )

    log("persist.start", backend="live" if os.environ.get("PERSIST_RESULT_URL") else "noop")
    persist_passthrough(job_id, user_id, verdict)
    log("persist.done")

    return validate_verdict(verdict)
