"""Neo4jReference — GDS-backed reference graph (TODO stub, NOT wired).

This is the A4 backend: it will implement the SAME `ReferenceGraph` interface
as `InMemoryReference`, but back it with a self-hosted Neo4j 5.x + GDS instance
over bolt. Wiring it in is gated on the pod being provisioned and the reference
CSVs being LOAD CSV'd (see docs/versions/v0.1-skeleton/plan.md Track A: A1/A4).

DO NOT import this module or the `neo4j` driver from any mock-first runtime
path. `scorer/app.py` only imports it lazily when
`SCORER_REFERENCE_BACKEND=neo4j` is set — which must not happen until A4.

Intended implementation sketch (all queries namespaced by an immutable
reference graph; per-job projections are created and dropped around scoring):

    resolve(surface):
        MATCH (e:Entity) WHERE surface IN ([e.name] + e.aliases) RETURN e.id
        (or a dedicated alias index / full-text index for speed)

    facts_for(subject_id, rel):
        MATCH (s:Entity {id:$sid})-[f:FACT {rel:$rel}]->(o:Entity) RETURN o.id

    is_functional(rel):
        MATCH ()-[f:FACT {rel:$rel}]->() RETURN any(x IN collect(f.functional)
        WHERE x) — or a cached rel->functional map loaded once.

    attr_of(entity_id, attr):
        MATCH (e:Entity {id:$id}) RETURN e[$attr]

    connected_components / shortest_path_len (override the union-find/BFS base):
        CALL gds.graph.project('job_'+$job, ['Entity','Claim','Mention'],
             {SUBJ:{orientation:'UNDIRECTED'}, OBJ:{orientation:'UNDIRECTED'},
              FACT:{orientation:'UNDIRECTED'}});
        CALL gds.wcc.stream('job_'+$job)          // orphan / cluster detection
        MATCH p = shortestPath((c)-[:FACT*..3]-(anchor)) RETURN length(p)
        CALL gds.graph.drop('job_'+$job)          // projection is disposable

Until A4, every method raises NotImplementedError so an accidental
`SCORER_REFERENCE_BACKEND=neo4j` fails loudly instead of silently degrading.
"""

from __future__ import annotations

from typing import Iterable, Optional

from .reference import ReferenceGraph

_NOT_WIRED = (
    "Neo4jReference is a TODO stub (A4) and is not wired yet. "
    "Use the default in-memory backend (unset SCORER_REFERENCE_BACKEND)."
)


class Neo4jReference(ReferenceGraph):
    """Same interface as InMemoryReference, backed by bolt + GDS. Not implemented."""

    def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - stub
        raise NotImplementedError(_NOT_WIRED)

    @classmethod
    def from_env(cls) -> "Neo4jReference":  # pragma: no cover - stub
        # Will read NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD from the env and open
        # a driver session. Intentionally not implemented in the mock-first phase.
        raise NotImplementedError(_NOT_WIRED)

    def resolve(self, surface: str) -> Optional[str]:  # pragma: no cover - stub
        raise NotImplementedError(_NOT_WIRED)

    def facts_for(self, subject_id: str, rel: str) -> set[str]:  # pragma: no cover
        raise NotImplementedError(_NOT_WIRED)

    def is_functional(self, rel: str) -> bool:  # pragma: no cover - stub
        raise NotImplementedError(_NOT_WIRED)

    def attr_of(self, entity_id: str, attr: str) -> Optional[str]:  # pragma: no cover
        raise NotImplementedError(_NOT_WIRED)

    def canonical_name(self, entity_id: str) -> Optional[str]:  # pragma: no cover
        raise NotImplementedError(_NOT_WIRED)

    def entity_type(self, entity_id: str) -> Optional[str]:  # pragma: no cover
        raise NotImplementedError(_NOT_WIRED)

    def fact_pairs_among(
        self, entity_ids: Iterable[str]
    ) -> list[tuple[str, str, str]]:  # pragma: no cover - stub
        raise NotImplementedError(_NOT_WIRED)

    def stats(self) -> dict:  # pragma: no cover - stub
        raise NotImplementedError(_NOT_WIRED)
