#!/usr/bin/env python3
"""Mechanical integrity checks for the Eval-2 personal benchmark."""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PERSONAL = ROOT / "data" / "personal"
REF_ENTITIES = PERSONAL / "ref_entities.csv"
REF_FACTS = PERSONAL / "ref_facts.csv"
BENCH_LEDGER = PERSONAL / "bench_ledger.csv"
DOCS_DIR = PERSONAL / "docs"
OLD_REF_ENTITIES = ROOT / "data" / "import" / "ref_entities.csv"

ENTITY_HEADER = [
    "id",
    "name",
    "type",
    "aliases",
    "release_year",
    "param_count_b",
    "context_window_k",
]
FACT_HEADER = [
    "src",
    "src_name",
    "src_type",
    "rel",
    "dst",
    "dst_name",
    "dst_type",
    "functional",
]
LEDGER_HEADER = [
    "doc",
    "cid",
    "subject",
    "rel",
    "object",
    "label",
    "mutation",
    "original",
]

VALID_TYPES = {"Person", "Org", "Team", "Project", "City", "Pet", "Year"}
VALID_RELS = {
    "works_at",
    "lives_in",
    "married_to",
    "manages",
    "leads_project",
    "owns_pet",
    "joined_in",
    "born_in",
}
FUNCTIONAL_RELS = {"works_at", "married_to", "born_in"}
VALID_DOCS = {"A", "B", "C", "D", "E"}
FALSE_LABELS = {"CONTRADICTED", "FABRICATED_ENTITY", "FABRICATED_CLUSTER"}


class ValidationError(Exception):
    pass


def fail(message: str) -> None:
    raise ValidationError(message)


def read_csv(path: Path, expected_header: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != expected_header:
            fail(
                f"{path.relative_to(ROOT)} header mismatch: "
                f"expected {expected_header}, got {reader.fieldnames}"
            )
        return list(reader)


def require_nonempty(value: str, label: str) -> None:
    if value is None or value == "":
        fail(f"empty required value: {label}")


def validate_ref_entities(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    if not rows:
        fail("ref_entities.csv has no rows")
    ids: set[str] = set()
    names: set[str] = set()
    surfaces: dict[str, str] = {}
    by_id: dict[str, dict[str, str]] = {}

    for line_no, row in enumerate(rows, start=2):
        ent_id = row["id"]
        name = row["name"]
        typ = row["type"]
        require_nonempty(ent_id, f"ref_entities.csv:{line_no}:id")
        require_nonempty(name, f"ref_entities.csv:{line_no}:name")
        require_nonempty(typ, f"ref_entities.csv:{line_no}:type")
        if typ not in VALID_TYPES:
            fail(f"invalid entity type at ref_entities.csv:{line_no}: {typ}")
        if ent_id in ids:
            fail(f"duplicate entity id: {ent_id}")
        if name in names:
            fail(f"duplicate entity name: {name}")
        ids.add(ent_id)
        names.add(name)
        by_id[ent_id] = row

        for attr in ("release_year", "param_count_b", "context_window_k"):
            if row[attr] != "":
                fail(f"personal benchmark must not use legacy attr column {attr} at {ent_id}")

        aliases = [alias.strip() for alias in row["aliases"].split("|") if alias.strip()]
        if row["aliases"] and len(aliases) != len(row["aliases"].split("|")):
            fail(f"empty alias segment for entity: {ent_id}")
        for surface in [name, *aliases]:
            if surface in surfaces and surfaces[surface] != ent_id:
                fail(f"ambiguous surface form: {surface}")
            surfaces[surface] = ent_id
    return by_id


def validate_ref_facts(rows: list[dict[str, str]], entities: dict[str, dict[str, str]]) -> None:
    if len(rows) < 90:
        fail(f"ref_facts.csv needs at least 90 rows for Eval-2 coverage, found {len(rows)}")

    seen: set[tuple[str, str, str]] = set()
    functional_pairs: dict[tuple[str, str], set[str]] = defaultdict(set)
    marriage_pairs: set[tuple[str, str]] = set()

    for line_no, row in enumerate(rows, start=2):
        for column in FACT_HEADER:
            require_nonempty(row[column], f"ref_facts.csv:{line_no}:{column}")
        rel = row["rel"]
        if rel not in VALID_RELS:
            fail(f"invalid rel at ref_facts.csv:{line_no}: {rel}")
        if row["functional"] not in {"true", "false"}:
            fail(f"functional must be true/false at ref_facts.csv:{line_no}")
        if row["functional"] == "true" and rel not in FUNCTIONAL_RELS:
            fail(f"functional=true is not allowed for rel {rel} at ref_facts.csv:{line_no}")
        if row["functional"] == "false" and rel in FUNCTIONAL_RELS:
            fail(f"functional rel {rel} must be marked true at ref_facts.csv:{line_no}")

        src = row["src"]
        dst = row["dst"]
        if src not in entities:
            fail(f"src foreign key missing at ref_facts.csv:{line_no}: {src}")
        if dst not in entities:
            fail(f"dst foreign key missing at ref_facts.csv:{line_no}: {dst}")
        src_ent = entities[src]
        dst_ent = entities[dst]
        if row["src_name"] != src_ent["name"] or row["src_type"] != src_ent["type"]:
            fail(f"src denormalized fields mismatch at ref_facts.csv:{line_no}: {src}")
        if row["dst_name"] != dst_ent["name"] or row["dst_type"] != dst_ent["type"]:
            fail(f"dst denormalized fields mismatch at ref_facts.csv:{line_no}: {dst}")

        key = (src, rel, dst)
        if key in seen:
            fail(f"duplicate fact row at ref_facts.csv:{line_no}: {key}")
        seen.add(key)

        if row["functional"] == "true":
            functional_pairs[(src, rel)].add(dst)
        if rel == "married_to":
            if src_ent["type"] != "Person" or dst_ent["type"] != "Person":
                fail(f"married_to must connect Person to Person at ref_facts.csv:{line_no}")
            marriage_pairs.add((src, dst))
        if rel in {"works_at", "lives_in", "owns_pet", "born_in", "joined_in"} and src_ent["type"] != "Person":
            fail(f"{rel} subject must be Person at ref_facts.csv:{line_no}")
        if rel == "works_at" and dst_ent["type"] not in {"Org", "Team"}:
            fail(f"works_at object must be Org or Team at ref_facts.csv:{line_no}")
        if rel == "lives_in" and dst_ent["type"] != "City":
            fail(f"lives_in object must be City at ref_facts.csv:{line_no}")
        if rel == "owns_pet" and dst_ent["type"] != "Pet":
            fail(f"owns_pet object must be Pet at ref_facts.csv:{line_no}")
        if rel in {"born_in", "joined_in"} and dst_ent["type"] != "Year":
            fail(f"{rel} object must be Year at ref_facts.csv:{line_no}")
        if rel == "manages" and (src_ent["type"] != "Person" or dst_ent["type"] != "Person"):
            fail(f"manages must connect Person to Person at ref_facts.csv:{line_no}")
        if rel == "leads_project" and (src_ent["type"] != "Person" or dst_ent["type"] != "Project"):
            fail(f"leads_project must connect Person to Project at ref_facts.csv:{line_no}")

    conflicts = {
        key: sorted(values)
        for key, values in functional_pairs.items()
        if len(values) > 1
    }
    if conflicts:
        fail(f"functional relation has multiple destinations: {conflicts}")

    missing_reciprocal = sorted((a, b) for a, b in marriage_pairs if (b, a) not in marriage_pairs)
    if missing_reciprocal:
        fail(f"married_to facts are not reciprocal: {missing_reciprocal}")


def build_name_index(entities: dict[str, dict[str, str]]) -> dict[str, str]:
    index: dict[str, str] = {}
    for ent_id, row in entities.items():
        names = [row["name"]]
        if row["aliases"]:
            names.extend(alias.strip() for alias in row["aliases"].split("|"))
        for name in names:
            if name in index and index[name] != ent_id:
                fail(f"ambiguous entity surface form: {name}")
            index[name] = ent_id
    return index


def validate_ledger(
    rows: list[dict[str, str]],
    entities: dict[str, dict[str, str]],
    fact_rows: list[dict[str, str]],
) -> None:
    if not rows:
        fail("bench_ledger.csv has no rows")

    seen_cids: set[str] = set()
    by_doc: dict[str, list[dict[str, str]]] = defaultdict(list)
    name_index = build_name_index(entities)
    facts = {(row["src"], row["rel"], row["dst"]) for row in fact_rows}

    def resolve(surface: str) -> str | None:
        return name_index.get(surface)

    def canonical(ent_id: str) -> str:
        return entities[ent_id]["name"]

    def true_statement_is_in_graph(row: dict[str, str]) -> bool:
        subject_id = resolve(row["subject"])
        object_id = resolve(row["object"])
        return bool(subject_id and object_id and (subject_id, row["rel"], object_id) in facts)

    for line_no, row in enumerate(rows, start=2):
        for column in ["doc", "cid", "subject", "rel", "object", "label"]:
            require_nonempty(row[column], f"bench_ledger.csv:{line_no}:{column}")
        if row["doc"] not in VALID_DOCS:
            fail(f"invalid doc at bench_ledger.csv:{line_no}: {row['doc']}")
        if row["rel"] not in VALID_RELS:
            fail(f"invalid rel at bench_ledger.csv:{line_no}: {row['rel']}")
        if row["cid"] in seen_cids:
            fail(f"duplicate cid in bench_ledger.csv: {row['cid']}")
        seen_cids.add(row["cid"])
        by_doc[row["doc"]].append(row)

        if row["label"] == "TRUE" and not true_statement_is_in_graph(row):
            fail(f"TRUE row is not backed by reference graph at bench_ledger.csv:{line_no}")

        if row["mutation"] == "tail_swap":
            subject_id = resolve(row["subject"])
            object_id = resolve(row["object"])
            original_id = resolve(row["original"])
            if row["label"] != "CONTRADICTED":
                fail(f"tail_swap row must be CONTRADICTED at bench_ledger.csv:{line_no}")
            if row["rel"] not in FUNCTIONAL_RELS:
                fail(f"tail_swap must use a functional rel at bench_ledger.csv:{line_no}")
            if not subject_id or not object_id or not original_id:
                fail(f"tail_swap endpoints must resolve at bench_ledger.csv:{line_no}")
            if (subject_id, row["rel"], original_id) not in facts:
                fail(f"tail_swap original is not the graph truth at bench_ledger.csv:{line_no}")
            if entities[object_id]["type"] != entities[original_id]["type"]:
                fail(f"tail_swap object type mismatch at bench_ledger.csv:{line_no}")
            if object_id == original_id:
                fail(f"tail_swap object equals original at bench_ledger.csv:{line_no}")

        if row["mutation"] == "numeric":
            subject_id = resolve(row["subject"])
            object_id = resolve(row["object"])
            original_id = resolve(row["original"])
            if row["label"] != "CONTRADICTED":
                fail(f"numeric row must be CONTRADICTED at bench_ledger.csv:{line_no}")
            if row["rel"] != "born_in":
                fail(f"numeric mutation must use born_in at bench_ledger.csv:{line_no}")
            if not subject_id or not object_id or not original_id:
                fail(f"numeric endpoints must resolve at bench_ledger.csv:{line_no}")
            if entities[object_id]["type"] != "Year" or entities[original_id]["type"] != "Year":
                fail(f"numeric mutation must use Year entities at bench_ledger.csv:{line_no}")
            if (subject_id, row["rel"], original_id) not in facts:
                fail(f"numeric original is not the graph truth at bench_ledger.csv:{line_no}")
            if object_id == original_id:
                fail(f"numeric object was not perturbed at bench_ledger.csv:{line_no}")
            delta = abs(int(row["object"]) - int(row["original"]))
            if not 1 <= delta <= 3:
                fail(f"numeric year perturbation must be 1-3 years at bench_ledger.csv:{line_no}")

        if row["label"] == "FABRICATED_ENTITY":
            if resolve(row["subject"]) and resolve(row["object"]):
                fail(f"fabricated entity row has no fabricated endpoint at bench_ledger.csv:{line_no}")

    missing_docs = VALID_DOCS - set(by_doc)
    if missing_docs:
        fail(f"bench_ledger.csv missing docs: {sorted(missing_docs)}")

    if any(row["label"] != "TRUE" for row in by_doc["A"]):
        fail("doc A must be pure TRUE")

    for doc in ["B", "C"]:
        rows_for_doc = by_doc[doc]
        false_count = sum(1 for row in rows_for_doc if row["label"] in FALSE_LABELS)
        true_count = sum(1 for row in rows_for_doc if row["label"] == "TRUE")
        total = len(rows_for_doc)
        if total == 0:
            fail(f"doc {doc} has no rows")
        false_ratio = false_count / total
        if not 0.20 <= false_ratio <= 0.40:
            fail(f"doc {doc} false ratio must be near 30%, got {false_ratio:.2f}")
        if true_count == 0:
            fail(f"doc {doc} needs true filler rows")

    doc_b_mutations = Counter(row["mutation"] for row in by_doc["B"])
    if doc_b_mutations["tail_swap"] != 5:
        fail(f"doc B must contain exactly 5 tail_swap rows, got {doc_b_mutations['tail_swap']}")
    if doc_b_mutations["numeric"] != 3:
        fail(f"doc B must contain exactly 3 numeric rows, got {doc_b_mutations['numeric']}")

    doc_c_labels = Counter(row["label"] for row in by_doc["C"])
    if doc_c_labels["FABRICATED_ENTITY"] != 3:
        fail(f"doc C must contain exactly 3 fabricated entity rows, got {doc_c_labels['FABRICATED_ENTITY']}")

    doc_d_rows = by_doc["D"]
    if not 5 <= len(doc_d_rows) <= 6:
        fail(f"doc D must contain 5-6 cluster rows, got {len(doc_d_rows)}")
    if any(row["label"] != "FABRICATED_CLUSTER" for row in doc_d_rows):
        fail("doc D rows must all be FABRICATED_CLUSTER")

    doc_d_names = {row["subject"] for row in doc_d_rows} | {row["object"] for row in doc_d_rows}
    real_d_names = sorted(name for name in doc_d_names if resolve(name))
    if real_d_names:
        fail(f"doc D fabricated cluster uses real entity names: {real_d_names}")
    non_d_rows = [row for doc, doc_rows in by_doc.items() if doc != "D" for row in doc_rows]
    leaked = [
        name
        for name in doc_d_names
        for row in non_d_rows
        if name in {row["subject"], row["object"]}
    ]
    if leaked:
        fail(f"doc D fabricated entity leaked outside D: {sorted(set(leaked))}")

    graph = defaultdict(set)
    for row in doc_d_rows:
        graph[row["subject"]].add(row["object"])
        graph[row["object"]].add(row["subject"])
    if len(graph) != len(doc_d_names):
        fail("doc D cluster has isolated entity names")
    start = next(iter(doc_d_names))
    stack = [start]
    seen = set()
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        stack.extend(graph[node] - seen)
    if seen != doc_d_names:
        fail("doc D fabricated cluster is not connected")
    if len(doc_d_rows) < len(doc_d_names):
        fail("doc D cluster needs enough cross-links to form an internal loop")

    doc_e_rows = by_doc["E"]
    if any(row["label"] != "TRUE" for row in doc_e_rows):
        fail("doc E must be TRUE alias-rewrite pressure only")
    alias_rows = 0
    for row in doc_e_rows:
        if row["mutation"] != "alias_rewrite":
            fail("doc E rows must use mutation=alias_rewrite")
        subject_id = resolve(row["subject"])
        object_id = resolve(row["object"])
        subject_is_alias = bool(subject_id and row["subject"] != canonical(subject_id))
        object_is_alias = bool(object_id and row["object"] != canonical(object_id))
        if subject_is_alias or object_is_alias:
            alias_rows += 1
    if alias_rows != len(doc_e_rows):
        fail("each doc E row must use at least one alias surface")


def sentence_count(text: str) -> int:
    text = text.strip()
    if not text:
        return 0
    parts = [part for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return len(parts)


def validate_docs(ledger_rows: list[dict[str, str]]) -> None:
    by_doc = Counter(row["doc"] for row in ledger_rows)
    for doc in sorted(VALID_DOCS):
        path = DOCS_DIR / f"{doc}.txt"
        if not path.exists():
            fail(f"missing benchmark prose doc: {path.relative_to(ROOT)}")
        count = sentence_count(path.read_text(encoding="utf-8"))
        expected = by_doc[doc]
        if count != expected:
            fail(f"doc {doc} sentence count {count} != ledger rows {expected}")


def load_old_surfaces() -> set[str]:
    if not OLD_REF_ENTITIES.exists():
        return set()
    surfaces: set[str] = set()
    with OLD_REF_ENTITIES.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("type") == "Year":
                continue
            for surface in [row["name"], *[a.strip() for a in row.get("aliases", "").split("|") if a.strip()]]:
                if not re.fullmatch(r"\d{4}", surface):
                    surfaces.add(surface)
    return surfaces


def validate_pollution_guard(
    entity_rows: list[dict[str, str]],
    ledger_rows: list[dict[str, str]],
) -> None:
    old_surfaces = load_old_surfaces()
    if not old_surfaces:
        return

    for row in entity_rows:
        if row["type"] == "Year":
            continue
        for surface in [row["name"], *[a.strip() for a in row["aliases"].split("|") if a.strip()]]:
            if surface in old_surfaces:
                fail(f"personal entity surface reuses Track-D surface: {surface}")

    for row in ledger_rows:
        for surface in [row["subject"], row["object"], row["original"]]:
            if surface and not re.fullmatch(r"\d{4}", surface) and surface in old_surfaces:
                fail(f"ledger surface reuses Track-D surface: {surface}")

    docs_text = "\n".join((DOCS_DIR / f"{doc}.txt").read_text(encoding="utf-8") for doc in sorted(VALID_DOCS))
    leaked = sorted(surface for surface in old_surfaces if len(surface) >= 3 and surface in docs_text)
    if leaked:
        fail(f"docs contain Track-D surfaces: {leaked[:10]}")


def main() -> int:
    try:
        entity_rows = read_csv(REF_ENTITIES, ENTITY_HEADER)
        fact_rows = read_csv(REF_FACTS, FACT_HEADER)
        ledger_rows = read_csv(BENCH_LEDGER, LEDGER_HEADER)
        entities = validate_ref_entities(entity_rows)
        validate_ref_facts(fact_rows, entities)
        validate_ledger(ledger_rows, entities, fact_rows)
        validate_docs(ledger_rows)
        validate_pollution_guard(entity_rows, ledger_rows)

        print(f"validated {len(entity_rows)} personal entities")
        print(f"validated {len(fact_rows)} personal facts")
        print(f"validated {len(ledger_rows)} personal claims")
        print("ALL CHECKS PASSED")
        return 0
    except ValidationError as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
