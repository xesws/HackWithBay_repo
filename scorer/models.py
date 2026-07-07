"""Pydantic models for the scorer HTTP surface.

Request  = contracts.md §4.1 (claims JSON). A claim is a discriminated union on
           `kind`: `relational` carries `rel`+`object`, `attribute` carries
           `attr`+`value`. Field shapes match exactly what
           `eval/benchmark_runner.py:claim_payload()` emits.
Response = contracts.md §4.2 (verdict JSON), including the render-ready `graph`.

contracts.md is FROZEN; these models mirror it and must not drift.
"""

from __future__ import annotations

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# §4.1 request
# ---------------------------------------------------------------------------


class RelationalClaim(BaseModel):
    """e.g. {"cid":"c1","kind":"relational","text":"...","subject":"Claude",
    "rel":"developed_by","object":"Google"}"""

    cid: str
    kind: Literal["relational"]
    subject: str
    rel: str
    object: str
    text: Optional[str] = None


class AttributeClaim(BaseModel):
    """e.g. {"cid":"c2","kind":"attribute","text":"...","subject":"GPT-4",
    "attr":"release_year","value":2022}"""

    cid: str
    kind: Literal["attribute"]
    subject: str
    attr: str
    # benchmark_runner.coerce_value() emits int | float | str.
    value: Union[int, float, str]
    text: Optional[str] = None


Claim = Annotated[
    Union[RelationalClaim, AttributeClaim],
    Field(discriminator="kind"),
]


class ScoreRequest(BaseModel):
    job_id: str
    claims: List[Claim]


# ---------------------------------------------------------------------------
# §4.2 response
# ---------------------------------------------------------------------------

Status = Literal["SUPPORTED", "CONTRADICTED", "UNGROUNDED"]
Color = Literal["green", "red", "gray", "orange"]


class Evidence(BaseModel):
    # type ∈ {support, conflict, ungrounded}
    type: str
    truth: Optional[Union[str, int, float]] = None
    path: List[str] = Field(default_factory=list)


class ClaimVerdict(BaseModel):
    cid: str
    status: Status
    cluster_flag: bool
    grounding_ratio: float
    dist_to_core: Optional[int]
    evidence: Optional[Evidence] = None


class GraphNode(BaseModel):
    id: str
    label: str
    kind: str  # entity | claim | mention
    color: Color


class GraphEdge(BaseModel):
    src: str
    dst: str
    rel: str
    status: str


class GraphPayload(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


class ScoreResponse(BaseModel):
    job_id: str
    doc_score: float
    claims: List[ClaimVerdict]
    graph: GraphPayload
