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
    swap in a live model via `call_model_llm()` below, which routes through
    OpenRouter (pipeline/llm.py, model z-ai/glm-5.2) using OPENROUTER_API_KEY.
    Select it with  --model llm  (or  --model auto , which uses the LLM when
    OPENROUTER_API_KEY is set and the offline regex otherwise). Without a key this
    measurement is DEFERRED (see dev-B.md NEEDS-HUMAN).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable, Optional

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
DEFAULT_LEDGER = ROOT / "data" / "bench" / "bench_ledger.csv"
DEFAULT_DOCS = ROOT / "data" / "bench" / "docs"
CLAIMS_SCHEMA = HERE / "schemas" / "claims.schema.json"
# Domain-selectable extraction prompt (contracts §4.1 v1.2 / decisions #2): each
# domain defines its own vocab in its prompt. EXTRACT_PROMPT_PATH overrides the
# default AI-domain prompt (e.g. prompts/extract_claims_personal.md for Eval-2).


def prompt_path() -> Path:
    override = os.environ.get("EXTRACT_PROMPT_PATH")
    if override:
        p = Path(override)
        return p if p.is_absolute() else (ROOT / p)
    return HERE / "prompts" / "extract_claims.md"


PROMPT_PATH = HERE / "prompts" / "extract_claims.md"  # default (AI domain)

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
    # --- personal domain (Eval-2): all relational, object is a string (years too) ---
    (re.compile(r"^(?P<s>.+?) works at (?P<o>.+)$"), "relational", "works_at", False),
    (re.compile(r"^(?P<s>.+?) lives in (?P<o>.+)$"), "relational", "lives_in", False),
    (re.compile(r"^(?P<s>.+?) is married to (?P<o>.+)$"), "relational", "married_to", False),
    (re.compile(r"^(?P<s>.+?) manages (?P<o>.+)$"), "relational", "manages", False),
    (re.compile(r"^(?P<s>.+?) owns a pet named (?P<o>.+)$"), "relational", "owns_pet", False),
    (re.compile(r"^(?P<s>.+?) joined in (?P<o>.+)$"), "relational", "joined_in", False),
    (re.compile(r"^(?P<s>.+?) was born in (?P<o>.+)$"), "relational", "born_in", False),
    (re.compile(r"^(?P<s>.+?) leads (?P<o>.+)$"), "relational", "leads_project", False),
    (re.compile(r"^(?P<s>.+?) is (?:a|an|the) (?P<o>.+)$"), "relational", "is_a", False),
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

    DEFAULT = offline deterministic extractor. Use `call_model_llm` (OpenRouter)
    via --model llm / --model auto once OPENROUTER_API_KEY is set.
    """
    return json.dumps({"claims": regex_extract(text)})


def call_model_llm(text: str) -> str:  # pragma: no cover - needs a live key
    """Real-LLM extractor via OpenRouter (pipeline/llm.py, model z-ai/glm-5.2).

    Sends the §4.1 extraction prompt (pipeline/prompts/extract_claims.md) as the
    system message and `text` as the user message; returns the model's raw text
    (must be §4.1 JSON only). Requires OPENROUTER_API_KEY — raises without one, so
    the offline regex extractor stays the default (see dev-B.md NEEDS-HUMAN).
    """
    from pipeline.llm import openrouter_chat  # local import: only needed on the LLM path

    prompt = prompt_path().read_text(encoding="utf-8")  # domain-selectable (EXTRACT_PROMPT_PATH)
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text},
    ]
    return openrouter_chat(messages)


def default_model() -> Callable[[str], str]:
    """Auto-select the extractor: OpenRouter LLM when OPENROUTER_API_KEY is set,
    otherwise the deterministic offline regex extractor (no key needed)."""
    return call_model_llm if os.environ.get("OPENROUTER_API_KEY") else call_model


MODELS: dict[str, Callable[[str], str]] = {"offline": call_model, "llm": call_model_llm}


# --- extraction + validation ---------------------------------------------------
def load_schema() -> dict[str, Any]:
    return json.loads(CLAIMS_SCHEMA.read_text(encoding="utf-8"))


def extract_claims(job_id: str, text: str, model: Optional[Callable[[str], str]] = None,
                   validate: bool = True) -> dict[str, Any]:
    """Run the model, coerce to the §4.1 envelope, and (optionally) validate.

    `model=None` auto-selects via default_model(): OpenRouter LLM when
    OPENROUTER_API_KEY is set, else the offline regex extractor. Pass an explicit
    callable (e.g. call_model) to pin a specific extractor.
    """
    if model is None:
        model = default_model()

    def _run(m: Callable[[str], str]) -> dict[str, Any]:
        parsed = json.loads(m(text))
        payload = {"job_id": job_id,
                   "claims": parsed.get("claims", parsed if isinstance(parsed, list) else [])}
        if validate:
            jsonschema.validate(payload, load_schema())
        return payload

    try:
        payload = _run(model)
        if model is not call_model and not payload["claims"]:
            fallback = _run(call_model)
            if fallback["claims"]:
                return fallback
        return payload
    except Exception:
        if model is call_model:  # already the deterministic extractor; nothing to fall back to
            raise
        # robust fallback: LLM path failed (timeout / API error / bad output) -> regex.
        return _run(call_model)


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
    parser.add_argument("--model", choices=[*sorted(MODELS), "auto"], default="offline",
                        help="'offline'=regex inverse (no key); 'llm'=OpenRouter z-ai/glm-5.2 "
                             "(needs OPENROUTER_API_KEY); 'auto'=llm when OPENROUTER_API_KEY set, else offline")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--docs-dir", type=Path, default=DEFAULT_DOCS)
    parser.add_argument("--print-claims", action="store_true")
    args = parser.parse_args()

    model = default_model() if args.model == "auto" else MODELS[args.model]
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
