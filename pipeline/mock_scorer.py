#!/usr/bin/env python3
"""mock_scorer — claims (§4.1) -> verdict (§4.2), fully offline (Track B / card B3).

This is the STUB that stands in for the real Track-A scorer (`POST {SCORER_URL}/score`)
until it exists. It is CLAIMS-DRIVEN (no ground-truth ledger, no oracle): every
claim is heuristically marked SUPPORTED/green so the full webhook chain can be
exercised and its §4.2 output shape asserted offline.

Graph assembly (dedupe + claim/entity nodes + SUBJ/rel edges) mirrors the shape
in eval/benchmark_runner.py, but the judgement here is a fixed heuristic — NOT
benchmark_runner.mock_score(), which is an oracle needing ledger labels.
"""

from __future__ import annotations

import re
from typing import Any

# heuristic verdict for the stub: treat every extracted claim as grounded/true.
_STUB_STATUS = "SUPPORTED"
_STATUS_COLOR = {"SUPPORTED": "green", "CONTRADICTED": "red", "UNGROUNDED": "orange"}
_STATUS_GRAY = "gray"  # reserved (contract color vocab) for future stub statuses


def _slug(prefix: str, text: str) -> str:
    body = re.sub(r"[^a-z0-9]+", "_", str(text).strip().casefold()).strip("_")
    return f"{prefix}:{body or 'x'}"


def _predicate(claim: dict[str, Any]) -> str:
    return claim["attr"] if claim.get("kind") == "attribute" else claim["rel"]


def _object(claim: dict[str, Any]) -> Any:
    return claim["value"] if claim.get("kind") == "attribute" else claim["object"]


def mock_score_claims(job_id: str, claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a fully-valid §4.2 verdict for the given §4.1 claims."""
    status = _STUB_STATUS
    color = _STATUS_COLOR[status]
    edge_status = status.lower()

    claim_verdicts: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for claim in claims:
        cid = claim["cid"]
        subject = claim["subject"]
        pred = _predicate(claim)
        obj = _object(claim)
        is_attr = claim.get("kind") == "attribute"

        claim_verdicts.append({
            "cid": cid,
            "status": status,
            "cluster_flag": False,
            "grounding_ratio": 1.0,
            "dist_to_core": 0,
            "evidence": {"type": "mock", "truth": None,
                         "path": [str(subject), str(pred), str(obj)]},
        })

        claim_node = f"claim:{cid}"
        subject_node = _slug("ent", subject)
        object_node = (_slug("attr", f"{subject}_{pred}") if is_attr else _slug("ent", obj))
        nodes.extend([
            {"id": claim_node, "label": cid, "kind": "claim", "color": color},
            {"id": subject_node, "label": str(subject), "kind": "entity", "color": color},
            {"id": object_node, "label": str(obj),
             "kind": "attribute" if is_attr else "entity", "color": color},
        ])
        edges.append({"src": claim_node, "dst": subject_node, "rel": "SUBJ", "status": edge_status})
        edges.append({"src": claim_node, "dst": object_node, "rel": pred, "status": edge_status})

    supported = sum(1 for c in claim_verdicts if c["status"] == "SUPPORTED")
    return {
        "job_id": job_id,
        "doc_score": round(supported / max(len(claim_verdicts), 1), 4),
        "claims": claim_verdicts,
        "graph": {"nodes": _dedupe_nodes(nodes), "edges": edges},
    }


def _dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        by_id.setdefault(node["id"], node)
    return list(by_id.values())
