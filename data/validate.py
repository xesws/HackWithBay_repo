#!/usr/bin/env python3
"""Mechanical integrity checks for Track D data assets."""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REF_ENTITIES = DATA / "import" / "ref_entities.csv"
REF_FACTS = DATA / "import" / "ref_facts.csv"
BENCH_LEDGER = DATA / "bench" / "bench_ledger.csv"
DOCS_DIR = DATA / "bench" / "docs"

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

VALID_TYPES = {"Model", "Org", "Paper", "Benchmark", "Person", "Year"}
VALID_RELS = {
    "developed_by",
    "released_in",
    "based_on",
    "evaluated_on",
    "sota_on",
    "authored_by",
    "acquired_by",
    "cited_by",
}
VALID_ATTRS = {"release_year", "param_count_b", "context_window_k"}
FUNCTIONAL_RELS = {"developed_by", "released_in"}
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


def validate_number(value: str, label: str, integer: bool = False) -> None:
    if value == "":
        return
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValidationError(f"{label} is not numeric: {value}") from exc
    if parsed < 0:
        fail(f"{label} must be non-negative: {value}")
    if integer and not parsed.is_integer():
        fail(f"{label} must be an integer: {value}")


def validate_ref_entities(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    if not rows:
        fail("ref_entities.csv has no rows")

    ids: set[str] = set()
    names: set[str] = set()
    by_id: dict[str, dict[str, str]] = {}
    for line_no, row in enumerate(rows, start=2):
        ent_id = row["id"]
        require_nonempty(ent_id, f"ref_entities.csv:{line_no}:id")
        require_nonempty(row["name"], f"ref_entities.csv:{line_no}:name")
        require_nonempty(row["type"], f"ref_entities.csv:{line_no}:type")
        if row["type"] not in VALID_TYPES:
            fail(f"invalid entity type at line {line_no}: {row['type']}")
        if ent_id in ids:
            fail(f"duplicate entity id: {ent_id}")
        if row["name"] in names:
            fail(f"duplicate entity name: {row['name']}")
        ids.add(ent_id)
        names.add(row["name"])
        by_id[ent_id] = row
        validate_number(row["release_year"], f"{ent_id}.release_year", integer=True)
        validate_number(row["param_count_b"], f"{ent_id}.param_count_b")
        validate_number(row["context_window_k"], f"{ent_id}.context_window_k", integer=True)
        if row["aliases"]:
            aliases = [alias.strip() for alias in row["aliases"].split("|")]
            if any(not alias for alias in aliases):
                fail(f"empty alias segment for entity: {ent_id}")
    return by_id


def validate_ref_facts(rows: list[dict[str, str]], entities: dict[str, dict[str, str]]) -> None:
    if len(rows) < 200:
        fail(f"ref_facts.csv needs at least 200 rows, found {len(rows)}")

    seen: set[tuple[str, str, str]] = set()
    functional_pairs: dict[tuple[str, str], set[str]] = defaultdict(set)
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

    conflicts = {
        key: sorted(values)
        for key, values in functional_pairs.items()
        if len(values) > 1
    }
    if conflicts:
        fail(f"functional relation has multiple destinations: {conflicts}")


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
        if row["rel"] in VALID_RELS:
            return bool(subject_id and object_id and (subject_id, row["rel"], object_id) in facts)
        if row["rel"] in VALID_ATTRS and subject_id:
            return entities[subject_id][row["rel"]] == row["object"]
        return False

    for line_no, row in enumerate(rows, start=2):
        for column in ["doc", "cid", "subject", "rel", "object", "label"]:
            require_nonempty(row[column], f"bench_ledger.csv:{line_no}:{column}")
        if row["doc"] not in VALID_DOCS:
            fail(f"invalid doc at bench_ledger.csv:{line_no}: {row['doc']}")
        if row["rel"] not in VALID_RELS and row["rel"] not in VALID_ATTRS:
            fail(f"invalid rel/attr at bench_ledger.csv:{line_no}: {row['rel']}")
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
            if row["label"] != "CONTRADICTED":
                fail(f"numeric row must be CONTRADICTED at bench_ledger.csv:{line_no}")
            if row["rel"] not in VALID_ATTRS:
                fail(f"numeric mutation must use an attribute at bench_ledger.csv:{line_no}")
            if not subject_id:
                fail(f"numeric subject must resolve at bench_ledger.csv:{line_no}")
            if entities[subject_id][row["rel"]] != row["original"]:
                fail(f"numeric original does not match entity property at bench_ledger.csv:{line_no}")
            if row["object"] == row["original"]:
                fail(f"numeric object was not perturbed at bench_ledger.csv:{line_no}")

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
    if not any(row["subject"] == row["object"] for row in doc_d_rows) and len(doc_d_rows) < len(doc_d_names):
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
    # The verbalizer requirement is one assertion per independent sentence or
    # clause. For mechanical checking, require one sentence per ledger row.
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


def main() -> int:
    try:
        entity_rows = read_csv(REF_ENTITIES, ENTITY_HEADER)
        fact_rows = read_csv(REF_FACTS, FACT_HEADER)
        entities = validate_ref_entities(entity_rows)
        validate_ref_facts(fact_rows, entities)

        if BENCH_LEDGER.exists():
            ledger_rows = read_csv(BENCH_LEDGER, LEDGER_HEADER)
            validate_ledger(ledger_rows, entities, fact_rows)
            validate_docs(ledger_rows)
        else:
            print("benchmark assets not present; skipped D2/D3 checks")

        print(f"validated {len(entity_rows)} entities")
        print(f"validated {len(fact_rows)} facts")
        print("ALL CHECKS PASSED")
        return 0
    except ValidationError as exc:
        print(f"VALIDATION FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
