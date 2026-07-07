"""GraphJudge scorer (Track A) — graph-structural factuality judgement.

Mock-first: judges claims against an in-memory reference graph built from the
Track-D CSVs. No neo4j import in any runtime path (see reference_neo4j.py for
the future GDS-backed backend, which is not wired yet).
"""
