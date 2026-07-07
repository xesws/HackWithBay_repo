#!/usr/bin/env python3
"""extract_claims — prose -> contracts.md §4.1 claims JSON (Track B / card B2).

Pipeline: read data/bench/docs/{doc}.txt -> call_model(text) -> parse JSON ->
validate against pipeline/schemas/claims.schema.json -> score alignment vs the
ground-truth rows in data/bench/bench_ledger.csv for that doc.

SEAM — call_model(text) -> str:
    The ONLY place that talks to a model. The default implementation is a
    deterministic OFFLINE extractor (regex inverse of the benchmark
    `sentence_for()` templates) so the whole harness runs with no LLM key and
    proves the schema + scoring path end-to-end.

    To measure the REAL card-B2 metric ("10 assertions, >=8 extracted correctly")
    you must swap in a live model: fill in `call_model_llm()` below (it reads the
    prompt from pipeline/prompts/extract_claims.md and would POST to the gateway
    using GATEWAY_API_KEY) and select it via  --model llm . Without a funded key
    this measurement is DEFERRED (see dev-B.md NEEDS-HUMAN).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
DEFAULT_LEDGER = ROOT / "data" / "bench" / "bench_ledger.csv"
DEFAULT_DOCS = ROOT / "data" / "bench" / "docs"
CLAIMS_SCHEMA = HERE / "schemas" / "claims.schema.json"
PROMPT_PATH = HERE / "prompts" / "extract_claims.md"

ATTRS = {"release_year", "param_count_b", "context_window_k"}

# --- surface -> triple: inverse of eval/benchmark_runner.py sentence_for() ------
# (pattern, kind, predicate, value_is_number). First match wins per sentence.
_PATTERNS: list[tuple[re.Pattern[str], str, str, bool]] = [
    (re.compile(r"^(?P<s>.+?) was developed by (?P<o>.+)$"), "relational", "developed_by", False),
    (re.compile(r"^(?P<s>.+?) was based on (?P<o>.+)$"), "relational", "based_on", False),
    (re.compile(r"^(?P<s>.+?) was evaluated on (?P<o>.+)$"), "relational", "evaluated_on", False),
    (re.compile(r"^(?P<s>.+?) set the state of the art on (?P<o>.+)$"), "relational", "sota_on", False),
    (re.compile(r"^(?P<s>.+?) was authored by (?P<o>.+)$"), "relational", "authored_by", False),
    (re.compile(r"^(?P<s>.+?) was acquired by (?P<o>.+)$"), "relational", "acquired_by", False),
    (re.compile(r"^(?P<s>.+?) was cited by (?P<o>.+)$"), "relational", "cited_by", False),
    (re.compile(r"^(?P<s>.+?) has a (?P<o>\d+)K token context window$"), "attribute", "context_window_k", True),
    (re.compile(r"^(?P<s>.+?) has (?P<o>\d+) billion parameters$"), "attribute", "param_count_b", True),
    # "was released in <year>" is surface-ambiguous; default to relational released_in.
    (re.compile(r"^(?P<s>.+?) was released in (?P<o>.+)$"), "relational", "released_in", False),
]


def _sentences(text: str) -> list[str]:
    """Split prose into sentences, stripping the single trailing period."""
    out: list[str] = []
    for frag in re.split(r"(?<=\.)\s+", text.strip()):
        frag = frag.strip()
        if not frag:
            continue
        if frag.endswith("."):
            frag = frag[:-1]
        out.append(frag.strip())
    return out


def regex_extract(text: str) -> list[dict[str, Any]]:
    """Deterministic offline extractor (inverse of sentence_for). No LLM."""
    claims: list[dict[str, Any]] = []
    for sent in _sentences(text):
        for pattern, kind, pred, is_num in _PATTERNS:
            m = pattern.match(sent)
            if not m:
                continue
            subject = m.group("s").strip()
            obj = m.group("o").strip()
            cid = f"c{len(claims) + 1}"
            claim: dict[str, Any] = {"cid": cid, "kind": kind, "text": sent + ".", "subject": subject}
            if kind == "attribute":
                claim["attr"] = pred
                claim["value"] = int(obj) if is_num else obj
            else:
                claim["rel"] = pred
                claim["object"] = obj
            claims.append(claim)
            break
    return claims


# --- SEAM ----------------------------------------------------------------------
def call_model(text: str) -> str:
    """Return a §4.1 claims JSON *string* for `text`.

    DEFAULT = offline deterministic extractor. Swap `call_model_llm` in here (or
    pass --model llm on the CLI) once a funded gateway key exists.
    """
    return json.dumps({"claims": regex_extract(text)})


def call_model_llm(text: str) -> str:  # pragma: no cover - needs a live key
    """Real-LLM extractor. NOT wired: no GATEWAY_API_KEY available offline.

    Intended shape (kept as a spec so a human can drop in a key later):
        prompt = PROMPT_PATH.read_text(encoding="utf-8")
        POST {GATEWAY}/... with system=prompt, user=text, GATEWAY_API_KEY auth
        return the model's raw text (must be §4.1 JSON only)
    """
    if not os.environ.get("GATEWAY_API_KEY"):
        raise RuntimeError(
            "call_model_llm requires GATEWAY_API_KEY; none set. This is the "
            "DEFERRED / NEEDS-HUMAN measurement — see dev-B.md."
        )
    raise NotImplementedError("wire the gateway client here once a key exists")


MODELS: dict[str, Callable[[str], str]] = {"offline": call_model, "llm": call_model_llm}


# --- extraction + validation ---------------------------------------------------
def load_schema() -> dict[str, Any]:
    return json.loads(CLAIMS_SCHEMA.read_text(encoding="utf-8"))


def extract_claims(job_id: str, text: str, model: Callable[[str], str] = call_model,
                   validate: bool = True) -> dict[str, Any]:
    """Run the model, coerce to the §4.1 envelope, and (optionally) validate."""
    raw = model(text)
    parsed = json.loads(raw)
    payload = {"job_id": job_id, "claims": parsed.get("claims", parsed if isinstance(parsed, list) else [])}
    if validate:
        jsonschema.validate(payload, load_schema())
    return payload


# --- scoring vs ledger ---------------------------------------------------------
def _canon_pred(pred: str) -> str:
    # released_in (relational) and release_year (attribute) share a surface form
    # and denote the same fact downstream -> collapse for alignment scoring.
    return "released_in" if pred in {"released_in", "release_year"} else pred


def _canon(value: Any) -> str:
    return str(value).strip().casefold()


def _ledger_fact(row: dict[str, str]) -> tuple[str, str, str]:
    return (_canon(row["subject"]), _canon_pred(row["rel"]), _canon(row["object"]))


def _claim_fact(claim: dict[str, Any]) -> tuple[str, str, str]:
    if claim["kind"] == "attribute":
        return (_canon(claim["subject"]), _canon_pred(claim["attr"]), _canon(claim["value"]))
    return (_canon(claim["subject"]), _canon_pred(claim["rel"]), _canon(claim["object"]))


def score_alignment(claims: list[dict[str, Any]], rows: list[dict[str, str]]) -> dict[str, Any]:
    """How many ground-truth ledger facts did the extraction recover?"""
    extracted = {_claim_fact(c) for c in claims}
    matched, misses = 0, []
    for row in rows:
        if _ledger_fact(row) in extracted:
            matched += 1
        else:
            misses.append(row["cid"])
    return {"matched": matched, "total": len(rows), "missed_cids": misses,
            "extracted_count": len(claims)}


def read_ledger(path: Path) -> list[dict[str, str]]:
    import csv
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    parser = argparse.ArgumentParser(description="extract §4.1 claims from a benchmark doc and score vs the ledger")
    parser.add_argument("--doc", choices=["A", "B", "C", "D", "E", "all"], default="A")
    parser.add_argument("--model", choices=sorted(MODELS), default="offline",
                        help="'offline'=regex inverse (no key); 'llm'=live gateway (needs GATEWAY_API_KEY)")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--docs-dir", type=Path, default=DEFAULT_DOCS)
    parser.add_argument("--print-claims", action="store_true")
    args = parser.parse_args()

    model = MODELS[args.model]
    rows = read_ledger(args.ledger)
    docs = ["A", "B", "C", "D", "E"] if args.doc == "all" else [args.doc]

    grand_matched = grand_total = 0
    for doc in docs:
        doc_path = args.docs_dir / f"{doc}.txt"
        if not doc_path.exists():
            print(f"missing prose doc: {doc_path}", file=sys.stderr)
            return 1
        text = doc_path.read_text(encoding="utf-8")
        doc_rows = [r for r in rows if r["doc"] == doc]
        payload = extract_claims(f"bench_{doc}", text, model=model, validate=True)
        report = score_alignment(payload["claims"], doc_rows)
        grand_matched += report["matched"]
        grand_total += report["total"]
        print(f"doc {doc}: schema OK | aligned {report['matched']}/{report['total']} "
              f"(extracted {report['extracted_count']}, missed={report['missed_cids']})")
        if args.print_claims:
            print(json.dumps(payload, indent=2, ensure_ascii=False))

    print(f"overall aligned={grand_matched}/{grand_total} model={args.model}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
