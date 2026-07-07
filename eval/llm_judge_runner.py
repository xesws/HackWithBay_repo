#!/usr/bin/env python3
"""LLM-judge baseline runner (DESIGN §3.3 clean ablation).

The LLM judge receives the SAME atomic claims and the SAME reference facts that
the graph judge sees, then returns a per-claim status in
{SUPPORTED, CONTRADICTED, UNGROUNDED}.

Efficiency: exactly ONE OpenRouter call per doc (all of that doc's claims in a
single request) — ~5 calls for the whole 63-claim benchmark. The reply is parsed
robustly (```json fences stripped, first-brace/last-brace fallback, one retry).
On a hard parse failure the doc's LLM verdicts are marked errored so the
scoreboard can still emit the graph-judge column.

Run standalone:
    PYTHONPATH=<worktree> .venv/bin/python eval/llm_judge_runner.py
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load the OpenRouter key from the live repo's .env (absolute path, per task).
load_dotenv("/workspace/HackWithBay/HackWithBay_repo/.env")

# Local imports (this file's dir is on sys.path when run as a script; also works
# when imported by scoreboard.py which shares the eval/ directory).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_runner import read_ledger, sentence_for  # noqa: E402

from pipeline.llm import openrouter_chat, DEFAULT_MODEL  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "data" / "bench" / "bench_ledger.csv"
REF_ENTITIES = ROOT / "data" / "import" / "ref_entities.csv"
REF_FACTS = ROOT / "data" / "import" / "ref_facts.csv"
PROMPT_PATH = Path(__file__).resolve().parent / "llm_judge_baseline_prompt.md"

VALID_STATUSES = {"SUPPORTED", "CONTRADICTED", "UNGROUNDED"}


# ---------------------------------------------------------------------------
# Reference serialization — the SAME graph the scorer queries (161 ent / 332 fact)
# ---------------------------------------------------------------------------

def load_reference_entities(path: Path = REF_ENTITIES) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            entry: dict[str, Any] = {
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "aliases": row.get("aliases", ""),
            }
            for attr in ("release_year", "param_count_b", "context_window_k"):
                val = row.get(attr, "")
                if val:
                    entry[attr] = val
            out.append(entry)
    return out


def load_reference_facts(path: Path = REF_FACTS) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [
            {
                "src_name": row["src_name"],
                "rel": row["rel"],
                "dst_name": row["dst_name"],
                "functional": row.get("functional", ""),
            }
            for row in csv.DictReader(fh)
        ]


def claim_for_llm(row: dict[str, str]) -> dict[str, str]:
    """Claim in the prompt's Input shape: cid, text, subject, rel, object."""
    return {
        "cid": row["cid"],
        "text": sentence_for(row),
        "subject": row["subject"],
        "rel": row["rel"],
        "object": row["object"],
    }


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def build_messages(
    doc_rows: list[dict[str, str]],
    entities: list[dict[str, Any]],
    facts: list[dict[str, str]],
    system_prompt: str,
) -> list[dict[str, str]]:
    payload = {
        "claims": [claim_for_llm(r) for r in doc_rows],
        "reference_entities": entities,
        "reference_facts": facts,
    }
    user = (
        "Judge every claim below. Use ONLY the reference_entities and "
        "reference_facts provided; do not use outside knowledge.\n\n"
        + json.dumps(payload, ensure_ascii=False)
        + '\n\nReturn JSON only: {"claims": [{"cid": "...", "status": '
        '"SUPPORTED|CONTRADICTED|UNGROUNDED"}]}'
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user},
    ]


# ---------------------------------------------------------------------------
# Robust JSON parsing
# ---------------------------------------------------------------------------

def parse_verdicts(reply: str) -> dict[str, str]:
    """Return {cid: status}. Raises ValueError if nothing parseable."""
    text = reply.strip()
    # Strip ```json ... ``` (or plain ```) fences.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # Fallback: slice from the first { to the last }.
    if not text.startswith("{"):
        first, last = text.find("{"), text.rfind("}")
        if first != -1 and last != -1 and last > first:
            text = text[first : last + 1]
    data = json.loads(text)
    claims = data.get("claims", data if isinstance(data, list) else [])
    out: dict[str, str] = {}
    for c in claims:
        cid = c.get("cid")
        status = str(c.get("status", "")).strip().upper()
        if cid and status in VALID_STATUSES:
            out[cid] = status
    if not out:
        raise ValueError("no valid verdicts parsed from reply")
    return out


# ---------------------------------------------------------------------------
# Per-doc judging (one call, one retry)
# ---------------------------------------------------------------------------

def judge_doc(
    doc: str,
    doc_rows: list[dict[str, str]],
    entities: list[dict[str, Any]],
    facts: list[dict[str, str]],
    system_prompt: str,
    model: str = DEFAULT_MODEL,
    verbose: bool = True,
) -> tuple[dict[str, str], bool]:
    """Return ({cid: status}, errored). One LLM call, retry once on parse failure."""
    messages = build_messages(doc_rows, entities, facts, system_prompt)
    last_err: Exception | None = None
    for attempt in (1, 2):
        try:
            reply = openrouter_chat(messages, model=model, temperature=0.0, timeout=90)
            verdicts = parse_verdicts(reply)
            # Backfill any cid the model omitted as UNGROUNDED-errored? No — mark missing.
            missing = [r["cid"] for r in doc_rows if r["cid"] not in verdicts]
            if missing and verbose:
                print(f"  [doc {doc}] warning: model omitted {missing}", file=sys.stderr)
            if verbose:
                print(f"  [doc {doc}] LLM ok (attempt {attempt}): {len(verdicts)} verdicts")
            return verdicts, False
        except Exception as exc:  # parse or transport failure
            last_err = exc
            if verbose:
                print(f"  [doc {doc}] attempt {attempt} failed: {exc}", file=sys.stderr)
    if verbose:
        print(f"  [doc {doc}] ERRORED after retry: {last_err}", file=sys.stderr)
    return {}, True


def run_llm_judge(
    rows: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    verbose: bool = True,
) -> tuple[dict[str, str], set[str]]:
    """Judge all rows, batched one call per doc.

    Returns ({cid: status}, errored_docs).
    """
    entities = load_reference_entities()
    facts = load_reference_facts()
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    by_doc: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        by_doc[r["doc"]].append(r)

    verdicts: dict[str, str] = {}
    errored_docs: set[str] = set()
    for doc in sorted(by_doc):
        doc_verdicts, errored = judge_doc(
            doc, by_doc[doc], entities, facts, system_prompt, model=model, verbose=verbose
        )
        verdicts.update(doc_verdicts)
        if errored:
            errored_docs.add(doc)
    return verdicts, errored_docs


def main() -> int:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY not set", file=sys.stderr)
        return 1
    rows = read_ledger(DEFAULT_LEDGER)
    verdicts, errored = run_llm_judge(rows)
    print(f"\nLLM judge: {len(verdicts)} verdicts, errored docs={sorted(errored) or 'none'}")
    for r in rows:
        print(f"  {r['cid']:6s} label={r['label']:18s} llm={verdicts.get(r['cid'], 'ERRORED')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
