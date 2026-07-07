"""Reference-graph abstraction for the GraphJudge scorer.

`ReferenceGraph` is the interface the scorer depends on. `InMemoryReference`
implements it from the Track-D CSVs (`data/import/ref_entities.csv` +
`ref_facts.csv`) with **zero** database access — the scorer is mock-first and
MUST NOT import the neo4j driver in any runtime path. A future
`Neo4jReference` (see `reference_neo4j.py`) will implement the same interface
via bolt + GDS; the scoring code never needs to change.

Entity resolution / alias handling reuses `data/validate.py:build_name_index`
verbatim (loaded by file path so we don't depend on `data` being a package).

Graph algorithms are pure-Python: WCC via **union-find** and shortest-path via
BFS — no networkx. They live on the base class as overridable helpers so a
GDS-backed subclass can swap in `gds.wcc` / `gds.shortestPath` later.
"""

from __future__ import annotations

import csv
import importlib.util
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from pathlib import Path
from typing import Iterable, Optional

# scorer/reference.py -> parents[1] is the repo (or worktree) root.
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENTITIES = REPO_ROOT / "data" / "import" / "ref_entities.csv"
DEFAULT_FACTS = REPO_ROOT / "data" / "import" / "ref_facts.csv"
_VALIDATE_PATH = REPO_ROOT / "data" / "validate.py"


def _load_build_name_index():
    """Load `build_name_index` from data/validate.py by file path.

    Importing the module only defines functions/constants (its CLI lives under
    `if __name__ == "__main__"`), so this has no side effects.
    """
    spec = importlib.util.spec_from_file_location("gj_validate", _VALIDATE_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load validate module from {_VALIDATE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_name_index


build_name_index = _load_build_name_index()


class ReferenceGraph(ABC):
    """The trusted reference graph the scorer judges claims against.

    Concrete backends implement the data-access methods. The graph-algorithm
    helpers (`connected_components`, `shortest_path_len`) are generic and shared
    but may be overridden (e.g. to call Neo4j GDS).
    """

    # --- data access (backend-specific) ---------------------------------
    @abstractmethod
    def resolve(self, surface: str) -> Optional[str]:
        """Map a surface form (name or alias) to a canonical entity id, or None."""

    @abstractmethod
    def facts_for(self, subject_id: str, rel: str) -> set[str]:
        """Object ids o such that (subject_id, rel, o) is a reference fact."""

    @abstractmethod
    def is_functional(self, rel: str) -> bool:
        """Whether `rel` is functional (at most one true object per subject)."""

    @abstractmethod
    def attr_of(self, entity_id: str, attr: str) -> Optional[str]:
        """Stored value of a numeric/year attribute, or None if unset/unknown."""

    @abstractmethod
    def canonical_name(self, entity_id: str) -> Optional[str]:
        """Canonical display name for an entity id."""

    @abstractmethod
    def entity_type(self, entity_id: str) -> Optional[str]:
        """Entity type (Model/Org/Year/...) for an entity id."""

    @abstractmethod
    def fact_pairs_among(self, entity_ids: Iterable[str]) -> list[tuple[str, str, str]]:
        """Reference (src, dst, rel) fact edges whose BOTH endpoints are in the set.

        Used to draw the grounded green core inside a per-job graph.
        """

    @abstractmethod
    def stats(self) -> dict:
        """Small dict of backend stats for /health and /admin/load_ref."""

    # --- graph algorithms (generic, overridable) ------------------------
    @staticmethod
    def connected_components(
        node_ids: Iterable[str], edges: Iterable[tuple[str, str]]
    ) -> list[set[str]]:
        """Weakly-connected components via union-find. Pure Python, no networkx."""
        parent: dict[str, str] = {n: n for n in node_ids}

        def find(x: str) -> str:
            root = x
            while parent[root] != root:
                root = parent[root]
            # path compression
            while parent[x] != root:
                parent[x], x = root, parent[x]
            return root

        for a, b in edges:
            if a in parent and b in parent:
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[ra] = rb

        comps: dict[str, set[str]] = defaultdict(set)
        for n in parent:
            comps[find(n)].add(n)
        return list(comps.values())

    @staticmethod
    def shortest_path_len(
        adjacency: dict[str, set[str]], source: str, targets: set[str]
    ) -> Optional[int]:
        """BFS hop count from `source` to the nearest node in `targets`.

        Returns 0 if source is itself a target, None if none is reachable.
        """
        if source in targets:
            return 0
        seen = {source}
        queue: deque[tuple[str, int]] = deque([(source, 0)])
        while queue:
            node, dist = queue.popleft()
            for nb in adjacency.get(node, ()):  # type: ignore[arg-type]
                if nb in seen:
                    continue
                if nb in targets:
                    return dist + 1
                seen.add(nb)
                queue.append((nb, dist + 1))
        return None


class InMemoryReference(ReferenceGraph):
    """CSV-backed reference graph. No database, no neo4j import."""

    def __init__(
        self,
        entities: dict[str, dict[str, str]],
        fact_rows: list[dict[str, str]],
    ) -> None:
        self._entities = entities
        self._name_index = build_name_index(entities)  # surface -> entity id

        self._facts_set: set[tuple[str, str, str]] = set()
        self._facts_by_subject_rel: dict[tuple[str, str], set[str]] = defaultdict(set)
        self._functional_rels: set[str] = set()
        # (src, dst, rel) fact edges, for drawing the grounded core.
        self._fact_pairs: list[tuple[str, str, str]] = []

        for row in fact_rows:
            src, rel, dst = row["src"], row["rel"], row["dst"]
            self._facts_set.add((src, rel, dst))
            self._facts_by_subject_rel[(src, rel)].add(dst)
            self._fact_pairs.append((src, dst, rel))
            if row.get("functional") == "true":
                self._functional_rels.add(rel)

        self._n_facts = len(fact_rows)

    # --- construction ---------------------------------------------------
    @classmethod
    def from_csv(
        cls,
        entities_path: Path = DEFAULT_ENTITIES,
        facts_path: Path = DEFAULT_FACTS,
    ) -> "InMemoryReference":
        entities: dict[str, dict[str, str]] = {}
        with Path(entities_path).open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                entities[row["id"]] = row
        with Path(facts_path).open(newline="", encoding="utf-8") as fh:
            fact_rows = list(csv.DictReader(fh))
        return cls(entities, fact_rows)

    # --- data access ----------------------------------------------------
    def resolve(self, surface: str) -> Optional[str]:
        if surface is None:
            return None
        return self._name_index.get(surface)

    def facts_for(self, subject_id: str, rel: str) -> set[str]:
        return set(self._facts_by_subject_rel.get((subject_id, rel), ()))

    def is_functional(self, rel: str) -> bool:
        return rel in self._functional_rels

    def attr_of(self, entity_id: str, attr: str) -> Optional[str]:
        row = self._entities.get(entity_id)
        if row is None:
            return None
        value = row.get(attr)
        if value is None or value == "":
            return None
        return value

    def canonical_name(self, entity_id: str) -> Optional[str]:
        row = self._entities.get(entity_id)
        return row["name"] if row else None

    def entity_type(self, entity_id: str) -> Optional[str]:
        row = self._entities.get(entity_id)
        return row["type"] if row else None

    def fact_pairs_among(self, entity_ids: Iterable[str]) -> list[tuple[str, str, str]]:
        ids = set(entity_ids)
        return [(s, d, r) for (s, d, r) in self._fact_pairs if s in ids and d in ids]

    def stats(self) -> dict:
        return {
            "backend": "memory",
            "entities": len(self._entities),
            "facts": self._n_facts,
            "functional_rels": sorted(self._functional_rels),
            "surface_forms": len(self._name_index),
        }
