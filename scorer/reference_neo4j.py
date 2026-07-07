"""Neo4jReference — the reference graph backed by a live Neo4j 5.x + GDS server.

Implements the SAME `ReferenceGraph` interface as `InMemoryReference`, but every
layer-1 judgement (resolve / facts_for / is_functional / attr_of / …) is a
**Cypher MATCH against the real Neo4j** over bolt — the database is actively
queried per claim, never a local mirror.

Fallback ladder (recorded in `stats()["tier"]`):

  * ``gds``    — WCC / cluster detection runs on live Neo4j via a per-request
                 GDS projection (`gds.wcc.stream`), dropped after each score.
  * ``hybrid`` — layer-1 still hits real Neo4j via Cypher, but GDS was
                 unavailable so WCC falls back to the in-process union-find
                 (base-class `connected_components`). Still fully compliant:
                 Neo4j is actively queried for every judgement.

The reference graph (`:Entity` / `:FACT`) is IMMUTABLE. The per-request WCC
projection materialises ephemeral `:_JobNode` nodes namespaced by a random gid
and DETACH DELETEs them (plus drops the projection) before returning, so a score
leaves the reference graph untouched.
"""

from __future__ import annotations

import uuid
from typing import Iterable, Optional

from dotenv import dotenv_values
from neo4j import GraphDatabase

from .reference import REPO_ROOT, ReferenceGraph


class Neo4jReference(ReferenceGraph):
    """Live Neo4j + GDS backend. Layer-1 over bolt; WCC over GDS when available."""

    def __init__(self, driver, database: Optional[str] = None) -> None:
        self._driver = driver
        self._database = database
        self._resolve_cache: dict[str, Optional[str]] = {}
        # is_functional: DESIGN §2.3 sanctions a rel->functional map loaded once.
        self._functional_rels: set[str] = self._load_functional_rels()
        self._n_entities: int = self._count("MATCH (e:Entity) RETURN count(e) AS c")
        self._n_facts: int = self._count("MATCH ()-[f:FACT]->() RETURN count(f) AS c")
        self._gds_version: Optional[str] = self._probe_gds()
        # Flips to False the first time a per-request GDS projection fails, so
        # stats() reports the honest tier (gds vs hybrid) for the run.
        self._gds_ok: bool = self._gds_version is not None

    # --- construction ---------------------------------------------------
    @classmethod
    def from_env(cls, env_path=None) -> "Neo4jReference":
        env = dotenv_values(env_path or (REPO_ROOT / ".env"))
        uri = env.get("NEO4J_URI")
        user = env.get("NEO4J_USER")
        password = env.get("NEO4J_PASSWORD")
        if not uri or not password:
            raise RuntimeError("NEO4J_URI / NEO4J_PASSWORD not set in environment")
        driver = GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()  # fail loudly if the pod is unreachable
        return cls(driver, database=env.get("NEO4J_DATABASE"))

    def close(self) -> None:  # pragma: no cover - lifecycle helper
        self._driver.close()

    # --- low-level session helpers --------------------------------------
    def _run(self, cypher: str, **params):
        with self._driver.session(database=self._database) as session:
            return list(session.run(cypher, **params))

    def _count(self, cypher: str) -> int:
        rec = self._run(cypher)
        return rec[0]["c"] if rec else 0

    def _load_functional_rels(self) -> set[str]:
        rows = self._run(
            "MATCH ()-[f:FACT]->() WHERE f.functional RETURN DISTINCT f.rel AS rel"
        )
        return {r["rel"] for r in rows}

    def _probe_gds(self) -> Optional[str]:
        try:
            rec = self._run("RETURN gds.version() AS v")
            return rec[0]["v"] if rec else None
        except Exception:  # pragma: no cover - GDS absent
            return None

    # --- data access (layer-1, live Cypher MATCH) -----------------------
    def resolve(self, surface: str) -> Optional[str]:
        if surface is None:
            return None
        if surface in self._resolve_cache:
            return self._resolve_cache[surface]
        rows = self._run(
            "MATCH (e:Entity) WHERE $s = e.name OR $s IN e.aliases "
            "RETURN e.id AS id LIMIT 1",
            s=surface,
        )
        ent_id = rows[0]["id"] if rows else None
        self._resolve_cache[surface] = ent_id
        return ent_id

    def facts_for(self, subject_id: str, rel: str) -> set[str]:
        rows = self._run(
            "MATCH (:Entity {id: $sid})-[f:FACT {rel: $rel}]->(o:Entity) "
            "RETURN o.id AS oid",
            sid=subject_id,
            rel=rel,
        )
        return {r["oid"] for r in rows}

    def is_functional(self, rel: str) -> bool:
        return rel in self._functional_rels

    def attr_of(self, entity_id: str, attr: str) -> Optional[str]:
        rows = self._run(
            "MATCH (e:Entity {id: $id}) RETURN e[$attr] AS v",
            id=entity_id,
            attr=attr,
        )
        if not rows:
            return None
        value = rows[0]["v"]
        if value is None or value == "":
            return None
        return str(value)

    def canonical_name(self, entity_id: str) -> Optional[str]:
        rows = self._run(
            "MATCH (e:Entity {id: $id}) RETURN e.name AS n", id=entity_id
        )
        return rows[0]["n"] if rows else None

    def entity_type(self, entity_id: str) -> Optional[str]:
        rows = self._run(
            "MATCH (e:Entity {id: $id}) RETURN e.type AS t", id=entity_id
        )
        return rows[0]["t"] if rows else None

    def fact_pairs_among(self, entity_ids: Iterable[str]) -> list[tuple[str, str, str]]:
        ids = list(set(entity_ids))
        if not ids:
            return []
        rows = self._run(
            "MATCH (s:Entity)-[f:FACT]->(o:Entity) "
            "WHERE s.id IN $ids AND o.id IN $ids "
            "RETURN s.id AS s, o.id AS o, f.rel AS rel",
            ids=ids,
        )
        return [(r["s"], r["o"], r["rel"]) for r in rows]

    # --- graph algorithms -----------------------------------------------
    def connected_components(
        self, node_ids: Iterable[str], edges: Iterable[tuple[str, str]]
    ) -> list[set[str]]:
        """WCC via GDS on live Neo4j, falling back to union-find (hybrid tier).

        NOTE: this overrides the base *static* method as an instance method, so
        the scorer must call it on the instance (`ref.connected_components(...)`).
        InMemoryReference keeps the base union-find unchanged.
        """
        node_list = list(node_ids)
        edge_list = [(a, b) for a, b in edges]
        if self._gds_ok:
            try:
                return self._gds_wcc(node_list, edge_list)
            except Exception:
                # GDS fought us — degrade this and future scores to hybrid.
                self._gds_ok = False
        return ReferenceGraph.connected_components(node_list, edge_list)

    def _gds_wcc(
        self, node_ids: list[str], edges: list[tuple[str, str]]
    ) -> list[set[str]]:
        """Per-request GDS WCC: materialise ephemeral nodes, project, stream, drop."""
        gid = uuid.uuid4().hex
        graph_name = f"job_{gid}"
        edge_params = [{"a": a, "b": b} for a, b in edges]
        with self._driver.session(database=self._database) as session:
            try:
                # 1. ephemeral, gid-namespaced copy of the per-job claim graph.
                session.run(
                    "UNWIND $nodes AS nid MERGE (:_JobNode {gid: $gid, nid: nid})",
                    nodes=node_ids,
                    gid=gid,
                ).consume()
                if edge_params:
                    session.run(
                        "UNWIND $edges AS e "
                        "MATCH (a:_JobNode {gid: $gid, nid: e.a}), "
                        "(b:_JobNode {gid: $gid, nid: e.b}) "
                        "MERGE (a)-[:_JOB_REL]->(b)",
                        edges=edge_params,
                        gid=gid,
                    ).consume()
                # 2. cypher projection (undirected: match returns both directions).
                session.run(
                    "CALL gds.graph.project.cypher($g, "
                    "'MATCH (n:_JobNode {gid: $gid}) RETURN id(n) AS id', "
                    "'MATCH (a:_JobNode {gid: $gid})-[:_JOB_REL]-(b:_JobNode {gid: $gid}) "
                    "RETURN id(a) AS source, id(b) AS target', "
                    "{parameters: {gid: $gid}})",
                    g=graph_name,
                    gid=gid,
                ).consume()
                # 3. WCC stream -> component id per ephemeral node.
                rows = list(
                    session.run(
                        "CALL gds.wcc.stream($g) YIELD nodeId, componentId "
                        "RETURN gds.util.asNode(nodeId).nid AS nid, componentId AS cid",
                        g=graph_name,
                    )
                )
            finally:
                # 4. always drop projection + delete ephemeral nodes (immutability).
                session.run(
                    "CALL gds.graph.drop($g, false) YIELD graphName RETURN graphName",
                    g=graph_name,
                ).consume()
                session.run(
                    "MATCH (n:_JobNode {gid: $gid}) DETACH DELETE n", gid=gid
                ).consume()

        comps: dict[int, set[str]] = {}
        for r in rows:
            comps.setdefault(r["cid"], set()).add(r["nid"])
        return list(comps.values())

    # --- stats ----------------------------------------------------------
    def stats(self) -> dict:
        return {
            "backend": "neo4j",
            "tier": "gds" if self._gds_ok else "hybrid",
            "entities": self._n_entities,
            "facts": self._n_facts,
            "functional_rels": sorted(self._functional_rels),
            "gds_version": self._gds_version,
        }
