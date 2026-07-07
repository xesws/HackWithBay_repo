#!/usr/bin/env python3
"""Benchmark runner skeleton for GraphJudge scorer-compatible services."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "data" / "bench" / "bench_ledger.csv"
DEFAULT_DOCS = ROOT / "data" / "bench" / "docs"
ATTRS = {"release_year", "param_count_b", "context_window_k"}


def sentence_for(claim: dict[str, str]) -> str:
    subject = claim["subject"]
    rel = claim["rel"]
    obj = claim["object"]
    if rel == "developed_by":
        return f"{subject} was developed by {obj}."
    if rel == "released_in":
        return f"{subject} was released in {obj}."
    if rel == "based_on":
        return f"{subject} was based on {obj}."
    if rel == "evaluated_on":
        return f"{subject} was evaluated on {obj}."
    if rel == "sota_on":
        return f"{subject} set the state of the art on {obj}."
    if rel == "authored_by":
        return f"{subject} was authored by {obj}."
    if rel == "acquired_by":
        return f"{subject} was acquired by {obj}."
    if rel == "cited_by":
        return f"{subject} was cited by {obj}."
    if rel == "release_year":
        return f"{subject} was released in {obj}."
    if rel == "param_count_b":
        return f"{subject} has {obj} billion parameters."
    if rel == "context_window_k":
        return f"{subject} has a {obj}K token context window."
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
    payload: dict[str, Any] = {
        "cid": row["cid"],
        "text": sentence_for(row),
        "subject": row["subject"],
    }
    if row["rel"] in ATTRS:
        payload.update({"kind": "attribute", "attr": row["rel"], "value": coerce_value(row["object"])})
    else:
        payload.update({"kind": "relational", "rel": row["rel"], "object": row["object"]})
    return payload


def coerce_value(value: str) -> Any:
    try:
        number = float(value)
    except ValueError:
        return value
    if number.is_integer():
        return int(number)
    return number


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


def dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        by_id.setdefault(node["id"], node)
    return list(by_id.values())


def post_score(scorer_url: str, payload: dict[str, Any], rows: list[dict[str, str]], timeout: int) -> dict[str, Any]:
    if scorer_url == "mock://local":
        return mock_score(payload["job_id"], rows)
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
            "job_id": f"bench_{doc}",
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
