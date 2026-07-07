"""Three-layer claim scoring (DESIGN.md §3.1) over a `ReferenceGraph`.

Layer 1 - direct match
  relational (s, rel, o):
    SUPPORTED    if (s, rel, o) is a reference fact.
    CONTRADICTED if `rel` is functional, s has a true object for `rel`, and the
                 claimed object *resolves to a real, different entity*.
                 (A fabricated/unresolvable object is NOT a contradiction — it
                  is unverifiable, so it falls through to UNGROUNDED. This is
                  what keeps doc-C fabricated-entity rows out of CONTRADICTED.)
  attribute (s.attr = v):
    year: exact match; other numerics: within +-5% -> SUPPORTED else CONTRADICTED.
    Entity missing that attribute -> UNGROUNDED.
  everything else -> UNGROUNDED (candidate).

Layer 2 - structure (over the UNGROUNDED set, but computed for every claim)
  Build the per-job claim graph (Entity / Claim / Mention nodes; SUBJ / OBJ /
  FACT undirected edges), run WCC (union-find):
    grounding_ratio = fraction of the claim's endpoints resolved to real entities
    dist_to_core    = BFS hops from the claim node to the nearest grounded
                      :Entity anchor, minus 1 (a directly-grounded claim -> 0;
                      null if its component has no anchor)
    cluster_flag    = the claim's WCC component contains ZERO resolved :Entity
                      anchors  (deterministic R6 rule; replaces GDS Louvain)

Layer 3 - aggregate
  doc_score = 1 - (w1*|CONTRADICTED| + w2*|flagged UNGROUNDED|) / N   (clamped)

Colors: SUPPORTED->green, CONTRADICTED->red, UNGROUNDED&cluster_flag->orange,
        UNGROUNDED&not->gray. Grounded :Entity nodes are green regardless.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional, Union

from .models import (
    AttributeClaim,
    Claim,
    ClaimVerdict,
    Evidence,
    GraphEdge,
    GraphNode,
    GraphPayload,
    RelationalClaim,
    ScoreRequest,
    ScoreResponse,
)
from .reference import ReferenceGraph

# doc_score weights (DESIGN §3.1 layer 3). A hard contradiction weighs a full
# point; a flagged fabricated cluster weighs half. Plain (gray) UNGROUNDED does
# NOT reduce the score -- "UNGROUNDED != FALSE" (DESIGN §3.1 honest framing).
W_CONTRADICTED = 1.0
W_FLAGGED = 0.5

YEAR_ATTR = "release_year"
NUMERIC_TOLERANCE = 0.05

_STATUS_COLOR = {
    "SUPPORTED": "green",
    "CONTRADICTED": "red",
}


def _slug(surface: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "-", surface.strip().lower()).strip("-")
    return s or "x"


def _coerce_number(value: Union[str, int, float]) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_truth(stored: str) -> Union[str, int, float]:
    """Present a stored attribute value as int/float/str for evidence.truth."""
    num = _coerce_number(stored)
    if num is None:
        return stored
    return int(num) if num.is_integer() else num


def _claim_color(status: str, cluster_flag: bool) -> str:
    if status in _STATUS_COLOR:
        return _STATUS_COLOR[status]
    return "orange" if cluster_flag else "gray"


class _Judged:
    """Layer-1 result plus graph bookkeeping for a single claim."""

    __slots__ = (
        "claim",
        "status",
        "evidence",
        "grounding_ratio",
        "claim_node",
        "endpoint_nodes",
        "entity_nodes",
    )

    def __init__(self, claim: Claim) -> None:
        self.claim = claim
        self.status: str = "UNGROUNDED"
        self.evidence: Optional[Evidence] = None
        self.grounding_ratio: float = 0.0
        self.claim_node: str = f"claim:{claim.cid}"
        # node id -> (label, kind, resolved-entity-id or None)
        self.endpoint_nodes: dict[str, tuple[str, str, Optional[str]]] = {}
        self.entity_nodes: set[str] = set()


def _add_endpoint(
    judged: _Judged, surface: str, ref: ReferenceGraph
) -> tuple[str, Optional[str]]:
    """Register a subject/object endpoint node; return (node_id, entity_id)."""
    ent_id = ref.resolve(surface)
    if ent_id is not None:
        node_id = f"ent:{ent_id}"
        label = ref.canonical_name(ent_id) or surface
        judged.endpoint_nodes[node_id] = (label, "entity", ent_id)
        judged.entity_nodes.add(node_id)
    else:
        node_id = f"mention:{_slug(surface)}"
        judged.endpoint_nodes[node_id] = (surface, "mention", None)
    return node_id, ent_id


def _judge_relational(
    judged: _Judged, claim: RelationalClaim, ref: ReferenceGraph
) -> None:
    subj_node, s_id = _add_endpoint(judged, claim.subject, ref)
    obj_node, o_id = _add_endpoint(judged, claim.object, ref)
    judged.grounding_ratio = (int(s_id is not None) + int(o_id is not None)) / 2.0

    if s_id and o_id and o_id in ref.facts_for(s_id, claim.rel):
        judged.status = "SUPPORTED"
        truth = ref.canonical_name(o_id)
        judged.evidence = Evidence(
            type="support", truth=truth, path=[claim.subject, claim.rel, truth or claim.object]
        )
        return

    # CONTRADICTED requires: functional rel, subject has a known true object,
    # and the claimed object RESOLVES to a real (different) entity.
    if s_id and o_id and ref.is_functional(claim.rel):
        truths = ref.facts_for(s_id, claim.rel)
        if truths and o_id not in truths:
            truth_id = sorted(truths)[0]  # functional rel -> single true object
            truth_name = ref.canonical_name(truth_id) or truth_id
            judged.status = "CONTRADICTED"
            judged.evidence = Evidence(
                type="conflict",
                truth=truth_name,
                path=[claim.subject, claim.rel, truth_name],
            )
            return

    judged.status = "UNGROUNDED"
    judged.evidence = Evidence(type="ungrounded", truth=None, path=[])


def _judge_attribute(
    judged: _Judged, claim: AttributeClaim, ref: ReferenceGraph
) -> None:
    subj_node, s_id = _add_endpoint(judged, claim.subject, ref)
    judged.grounding_ratio = 1.0 if s_id is not None else 0.0

    stored = ref.attr_of(s_id, claim.attr) if s_id else None
    if s_id is None or stored is None:
        judged.status = "UNGROUNDED"
        judged.evidence = Evidence(type="ungrounded", truth=None, path=[])
        return

    truth_val = _coerce_truth(stored)
    stored_num = _coerce_number(stored)
    claim_num = _coerce_number(claim.value)

    if claim.attr == YEAR_ATTR:
        matched = (
            stored_num is not None
            and claim_num is not None
            and int(stored_num) == int(claim_num)
        )
    elif stored_num is not None and claim_num is not None:
        if stored_num == 0:
            matched = claim_num == 0
        else:
            matched = abs(claim_num - stored_num) <= NUMERIC_TOLERANCE * abs(stored_num)
    else:
        matched = str(claim.value) == str(stored)

    if matched:
        judged.status = "SUPPORTED"
        judged.evidence = Evidence(
            type="support", truth=truth_val, path=[claim.subject, claim.attr, str(truth_val)]
        )
    else:
        judged.status = "CONTRADICTED"
        judged.evidence = Evidence(
            type="conflict", truth=truth_val, path=[claim.subject, claim.attr, str(truth_val)]
        )


def score_job(request: ScoreRequest, ref: ReferenceGraph) -> ScoreResponse:
    # ---- Layer 1: judge each claim, collect nodes/endpoints ------------
    judged_list: list[_Judged] = []
    for claim in request.claims:
        judged = _Judged(claim)
        if isinstance(claim, RelationalClaim):
            _judge_relational(judged, claim, ref)
        else:
            _judge_attribute(judged, claim, ref)
        judged_list.append(judged)

    # ---- Build the per-job graph (Entity/Claim/Mention + SUBJ/OBJ/FACT) -
    job_nodes: set[str] = set()
    wcc_edges: list[tuple[str, str]] = []
    # node id -> (label, kind); merged across claims (mentions keyed by surface).
    node_meta: dict[str, tuple[str, str]] = {}
    present_entities: set[str] = set()  # entity ids present as endpoints
    # render edges from claims: (src, dst, rel, owning-judged)
    claim_edges: list[tuple[str, str, str, _Judged]] = []

    for judged in judged_list:
        job_nodes.add(judged.claim_node)
        node_meta[judged.claim_node] = (judged.claim.cid, "claim")
        for node_id, (label, kind, ent_id) in judged.endpoint_nodes.items():
            job_nodes.add(node_id)
            node_meta.setdefault(node_id, (label, kind))
            if ent_id is not None:
                present_entities.add(ent_id)
            wcc_edges.append((judged.claim_node, node_id))
        # render edges: SUBJ then OBJ (relational) in claim order
        claim = judged.claim
        subj_node = next(iter(judged.endpoint_nodes))  # subject added first
        if isinstance(claim, RelationalClaim):
            nodes = list(judged.endpoint_nodes)
            subj_node = nodes[0]
            obj_node = nodes[1] if len(nodes) > 1 else nodes[0]
            claim_edges.append((judged.claim_node, subj_node, "SUBJ", judged))
            claim_edges.append((judged.claim_node, obj_node, claim.rel, judged))
        else:
            claim_edges.append((judged.claim_node, subj_node, "SUBJ", judged))

    # FACT edges among co-present real entities -> the grounded green core.
    fact_pairs = ref.fact_pairs_among(present_entities)
    for src, dst, _rel in fact_pairs:
        wcc_edges.append((f"ent:{src}", f"ent:{dst}"))

    # ---- Layer 2: WCC + dist_to_core (union-find + BFS) ----------------
    anchors = {n for n in job_nodes if n.startswith("ent:")}
    # Instance dispatch: Neo4jReference overrides this to run WCC on live GDS
    # (falling back to union-find as "hybrid"); InMemoryReference inherits the
    # base static union-find unchanged.
    components = ref.connected_components(job_nodes, wcc_edges)
    comp_of: dict[str, int] = {}
    comp_has_anchor: dict[int, bool] = {}
    for idx, comp in enumerate(components):
        has_anchor = any(n in anchors for n in comp)
        comp_has_anchor[idx] = has_anchor
        for n in comp:
            comp_of[n] = idx

    adjacency: dict[str, set[str]] = defaultdict(set)
    for a, b in wcc_edges:
        adjacency[a].add(b)
        adjacency[b].add(a)

    # ---- Assemble per-claim verdicts -----------------------------------
    verdicts: list[ClaimVerdict] = []
    n_contradicted = 0
    n_flagged = 0
    claim_color: dict[str, str] = {}

    for judged in judged_list:
        comp_idx = comp_of.get(judged.claim_node)
        has_anchor = comp_has_anchor.get(comp_idx, False)
        cluster_flag = not has_anchor

        if has_anchor:
            bfs = ReferenceGraph.shortest_path_len(adjacency, judged.claim_node, anchors)
            dist_to_core: Optional[int] = None if bfs is None else max(bfs - 1, 0)
        else:
            dist_to_core = None

        status = judged.status
        color = _claim_color(status, cluster_flag)
        claim_color[judged.claim_node] = color
        if status == "CONTRADICTED":
            n_contradicted += 1
        elif status == "UNGROUNDED" and cluster_flag:
            n_flagged += 1

        verdicts.append(
            ClaimVerdict(
                cid=judged.claim.cid,
                text=judged.claim.text,
                status=status,
                cluster_flag=cluster_flag,
                grounding_ratio=round(judged.grounding_ratio, 4),
                dist_to_core=dist_to_core,
                evidence=judged.evidence,
            )
        )

    # ---- Render graph (nodes + edges), colors per contract -------------
    # Mention color derives from the claims that reference it (worst-severity).
    mention_claim_colors: dict[str, list[str]] = defaultdict(list)
    for judged in judged_list:
        c_color = claim_color[judged.claim_node]
        for node_id, (_label, kind, _ent) in judged.endpoint_nodes.items():
            if kind == "mention":
                mention_claim_colors[node_id].append(c_color)

    def mention_color(node_id: str) -> str:
        colors = mention_claim_colors.get(node_id, [])
        for pref in ("red", "orange", "gray", "green"):
            if pref in colors:
                return pref
        return "gray"

    nodes: list[GraphNode] = []
    for node_id, (label, kind) in node_meta.items():
        if kind == "entity":
            color = "green"  # grounded entities stay green regardless
        elif kind == "claim":
            color = claim_color[node_id]
        else:
            color = mention_color(node_id)
        nodes.append(GraphNode(id=node_id, label=label, kind=kind, color=color))

    edges: list[GraphEdge] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def add_edge(src: str, dst: str, rel: str, status: str) -> None:
        key = (src, dst, rel)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append(GraphEdge(src=src, dst=dst, rel=rel, status=status))

    for src, dst, rel, judged in claim_edges:
        add_edge(src, dst, rel, judged.status.lower())
    for src, dst, rel in fact_pairs:  # grounded core
        add_edge(f"ent:{src}", f"ent:{dst}", rel, "supported")

    # ---- Layer 3: aggregate --------------------------------------------
    n = len(request.claims)
    if n:
        penalty = (W_CONTRADICTED * n_contradicted + W_FLAGGED * n_flagged) / n
        doc_score = round(max(0.0, min(1.0, 1.0 - penalty)), 4)
    else:
        doc_score = 1.0

    return ScoreResponse(
        job_id=request.job_id,
        doc_score=doc_score,
        claims=verdicts,
        graph=GraphPayload(nodes=nodes, edges=edges),
    )
