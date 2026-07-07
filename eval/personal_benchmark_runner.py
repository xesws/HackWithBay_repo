#!/usr/bin/env python3
"""Eval-2 personal benchmark runner.

This runner mirrors eval/benchmark_runner.py but defaults to data/personal and
the personal-domain relation vocabulary. It can score against:

* mock://local       - oracle statuses from the ledger, no scorer needed
* local://personal  - existing scorer logic over personal CSVs, no HTTP
* http(s)://...     - POST /score for the contract-changed scorer
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import uuid
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PERSONAL = ROOT / "data" / "personal"
DEFAULT_LEDGER = PERSONAL / "bench_ledger.csv"
DEFAULT_DOCS = PERSONAL / "docs"
DEFAULT_ENTITIES = PERSONAL / "ref_entities.csv"
DEFAULT_FACTS = PERSONAL / "ref_facts.csv"


def sentence_for(claim: dict[str, str]) -> str:
    subject = claim["subject"]
    rel = claim["rel"]
    obj = claim["object"]
    if rel == "works_at":
        return f"{subject} works at {obj}."
    if rel == "lives_in":
        return f"{subject} lives in {obj}."
    if rel == "married_to":
        return f"{subject} is married to {obj}."
    if rel == "manages":
        return f"{subject} manages {obj}."
    if rel == "leads_project":
        return f"{subject} leads {obj}."
    if rel == "owns_pet":
        return f"{subject} owns a pet named {obj}."
    if rel == "joined_in":
        return f"{subject} joined in {obj}."
    if rel == "born_in":
        return f"{subject} was born in {obj}."
    raise ValueError(f"unsupported rel: {rel}")


def read_ledger(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def expected_status(label: str) -> str:
    if label == "TRUE":
        return "SUPPORTED"
    if label == "CONTRADICTED":
        return "CONTRADICTED"
    return "UNGROUNDED"


def claim_payload(row: dict[str, str]) -> dict[str, Any]:
    return {
        "cid": row["cid"],
        "kind": "relational",
        "text": sentence_for(row),
        "subject": row["subject"],
        "rel": row["rel"],
        "object": row["object"],
    }


def dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        by_id.setdefault(node["id"], node)
    return list(by_id.values())


def mock_score(job_id: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    claims = []
    nodes = []
    edges = []
    for row in rows:
        status = expected_status(row["label"])
        color = {"SUPPORTED": "green", "CONTRADICTED": "red", "UNGROUNDED": "orange"}[status]
        claims.append(
            {
                "cid": row["cid"],
                "status": status,
                "cluster_flag": row["label"] == "FABRICATED_CLUSTER",
                "grounding_ratio": 1.0 if status != "UNGROUNDED" else 0.0,
                "dist_to_core": 0 if status != "UNGROUNDED" else None,
                "evidence": {"type": "mock", "truth": row["original"], "path": []},
            }
        )
        claim_node = f"claim:{row['cid']}"
        subject_node = f"ent:{row['subject']}"
        object_node = f"ent:{row['object']}"
        nodes.extend(
            [
                {"id": claim_node, "label": row["cid"], "kind": "claim", "color": color},
                {"id": subject_node, "label": row["subject"], "kind": "entity", "color": color},
                {"id": object_node, "label": row["object"], "kind": "entity", "color": color},
            ]
        )
        edges.append({"src": claim_node, "dst": subject_node, "rel": "SUBJ", "status": status.lower()})
        edges.append({"src": claim_node, "dst": object_node, "rel": row["rel"], "status": status.lower()})
    return {
        "job_id": job_id,
        "doc_score": sum(1 for c in claims if c["status"] == "SUPPORTED") / max(len(claims), 1),
        "claims": claims,
        "graph": {"nodes": dedupe_nodes(nodes), "edges": edges},
    }


def local_personal_score(payload: dict[str, Any]) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT))
    from scorer.models import ScoreRequest
    from scorer.reference import InMemoryReference
    from scorer.scoring import score_job

    ref = InMemoryReference.from_csv(DEFAULT_ENTITIES, DEFAULT_FACTS)
    request = ScoreRequest(**payload)
    response = score_job(request, ref)
    if hasattr(response, "model_dump"):
        return response.model_dump()
    return response.dict()


def post_score(scorer_url: str, payload: dict[str, Any], rows: list[dict[str, str]], timeout: int) -> dict[str, Any]:
    if scorer_url == "mock://local":
        return mock_score(payload["job_id"], rows)
    if scorer_url == "local://personal":
        return local_personal_score(payload)
    url = f"{scorer_url.rstrip('/')}/score"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"failed to POST {url}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scorer-url", default="mock://local")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--docs-dir", type=Path, default=DEFAULT_DOCS)
    parser.add_argument("--doc", choices=["A", "B", "C", "D", "E", "all"], default="all")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    rows = read_ledger(args.ledger)
    if args.doc != "all":
        rows = [row for row in rows if row["doc"] == args.doc]
    if args.limit:
        rows = rows[: args.limit]
    if not rows:
        print("no benchmark rows selected", file=sys.stderr)
        return 1

    by_doc: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        doc_path = args.docs_dir / f"{row['doc']}.txt"
        if not doc_path.exists():
            print(f"missing prose doc: {doc_path}", file=sys.stderr)
            return 1
        by_doc[row["doc"]].append(row)

    total = 0
    matched = 0
    for doc, doc_rows in sorted(by_doc.items()):
        payload = {
            "job_id": str(uuid.uuid4()),
            "claims": [claim_payload(row) for row in doc_rows],
        }
        verdict = post_score(args.scorer_url, payload, doc_rows, args.timeout)
        by_cid = {claim["cid"]: claim for claim in verdict.get("claims", [])}
        doc_matches = 0
        for row in doc_rows:
            total += 1
            expected = expected_status(row["label"])
            actual = by_cid.get(row["cid"], {}).get("status")
            if actual == expected:
                matched += 1
                doc_matches += 1
        print(f"doc {doc}: sent {len(doc_rows)} claims, expected_matches={doc_matches}/{len(doc_rows)}")

    print(f"overall expected_matches={matched}/{total}")
    print(f"scorer_url={args.scorer_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
