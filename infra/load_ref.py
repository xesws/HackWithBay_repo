#!/usr/bin/env python3
"""Load the immutable GraphJudge reference graph into Neo4j and verify it.

Runs infra/load_ref.cypher (constraint + LOAD CSV of 161 entities / 332 FACT
edges), then proves the install end-to-end:

  * MATCH (e:Entity) RETURN count(e)  -> 161
  * MATCH ()-[f:FACT]->() RETURN ...  -> 332
  * gds.version()                     -> returns
  * gds.wcc.stream over the reference graph (Entity + FACT, UNDIRECTED) ->
    component count + any orphan entities, then drops the projection.

Reads NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD from .env (never printed).

    /workspace/HackWithBay/HackWithBay_repo/.venv/bin/python infra/load_ref.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import dotenv_values
from neo4j import GraphDatabase

REPO_ROOT = Path(__file__).resolve().parents[1]
CYPHER_FILE = REPO_ROOT / "infra" / "load_ref.cypher"
_REF_GRAPH = "ref_wcc_probe"


def _split_statements(text: str) -> list[str]:
    """Split a .cypher file on ';', dropping // comments and blank lines."""
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("//")]
    body = "\n".join(lines)
    return [s.strip() for s in body.split(";") if s.strip()]


def main() -> int:
    env = dotenv_values(REPO_ROOT / ".env")
    driver = GraphDatabase.driver(
        env["NEO4J_URI"], auth=(env["NEO4J_USER"], env["NEO4J_PASSWORD"])
    )
    driver.verify_connectivity()

    statements = _split_statements(CYPHER_FILE.read_text(encoding="utf-8"))
    with driver.session() as session:
        for stmt in statements:
            session.run(stmt).consume()

        n_ent = session.run("MATCH (e:Entity) RETURN count(e) AS c").single()["c"]
        n_fact = session.run("MATCH ()-[f:FACT]->() RETURN count(f) AS c").single()["c"]
        gds_ver = session.run("RETURN gds.version() AS v").single()["v"]
        func_rels = sorted(
            r["rel"]
            for r in session.run(
                "MATCH ()-[f:FACT]->() WHERE f.functional RETURN DISTINCT f.rel AS rel"
            )
        )

        # Prove GDS works on the real reference graph: project -> wcc -> drop.
        if session.run(
            "CALL gds.graph.exists($g) YIELD exists RETURN exists", g=_REF_GRAPH
        ).single()["exists"]:
            session.run("CALL gds.graph.drop($g)", g=_REF_GRAPH).consume()
        session.run(
            "CALL gds.graph.project($g, 'Entity', "
            "{FACT: {orientation: 'UNDIRECTED'}})",
            g=_REF_GRAPH,
        ).consume()
        comp_rows = list(
            session.run(
                "CALL gds.wcc.stream($g) YIELD nodeId, componentId "
                "RETURN componentId, count(*) AS n", g=_REF_GRAPH
            )
        )
        n_components = len(comp_rows)
        # An orphan = an Entity with no FACT edge at all (its own singleton WCC).
        n_orphans = session.run(
            "MATCH (e:Entity) WHERE NOT (e)-[:FACT]-() RETURN count(e) AS c"
        ).single()["c"]
        session.run("CALL gds.graph.drop($g)", g=_REF_GRAPH).consume()

    driver.close()

    print(f"entities        = {n_ent}   (expect 161)")
    print(f"facts           = {n_fact}   (expect 332)")
    print(f"gds.version     = {gds_ver}")
    print(f"functional_rels = {func_rels}")
    print(f"wcc components  = {n_components}")
    print(f"orphan entities = {n_orphans}")

    ok = n_ent == 161 and n_fact == 332
    print("LOAD OK" if ok else "LOAD MISMATCH — check CSVs/import dir")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
