#!/usr/bin/env python3
"""Generate the controlled-corruption benchmark deterministically."""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ENTITIES_PATH = DATA / "import" / "ref_entities.csv"
FACTS_PATH = DATA / "import" / "ref_facts.csv"
LEDGER_PATH = DATA / "bench" / "bench_ledger.csv"
DOCS_DIR = DATA / "bench" / "docs"
SEED = 7

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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load_ref() -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    entities = {row["id"]: row for row in read_csv(ENTITIES_PATH)}
    facts = read_csv(FACTS_PATH)
    return entities, facts


def fact_lookup(facts: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    return {(row["src_name"], row["rel"], row["dst_name"]): row for row in facts}


def row(
    doc: str,
    cid: str,
    subject: str,
    rel: str,
    obj: str,
    label: str,
    mutation: str,
    original: str = "",
) -> dict[str, str]:
    return {
        "doc": doc,
        "cid": cid,
        "subject": subject,
        "rel": rel,
        "object": obj,
        "label": label,
        "mutation": mutation,
        "original": original,
    }


def true_row(doc: str, cid: str, fact: dict[str, str]) -> dict[str, str]:
    return row(doc, cid, fact["src_name"], fact["rel"], fact["dst_name"], "TRUE", "truth")


def select_true_facts(facts: list[dict[str, str]], count: int, used: set[tuple[str, str, str]]) -> list[dict[str, str]]:
    rng = random.Random(SEED)
    eligible = [
        fact
        for fact in facts
        if fact["rel"] in {"developed_by", "released_in", "evaluated_on", "authored_by"}
        and (fact["src_name"], fact["rel"], fact["dst_name"]) not in used
    ]
    rng.shuffle(eligible)
    selected = []
    for fact in eligible:
        key = (fact["src_name"], fact["rel"], fact["dst_name"])
        if key in used:
            continue
        selected.append(fact)
        used.add(key)
        if len(selected) == count:
            return selected
    raise RuntimeError(f"not enough eligible true facts for count={count}")


def interleave(true_rows: list[dict[str, str]], false_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    result = []
    true_iter = iter(true_rows)
    false_iter = iter(false_rows)
    while True:
        for _ in range(2):
            try:
                result.append(next(true_iter))
            except StopIteration:
                break
        try:
            result.append(next(false_iter))
        except StopIteration:
            result.extend(true_iter)
            return result


def sentence_for(claim: dict[str, str]) -> str:
    subject = claim["subject"]
    rel = claim["rel"]
    obj = claim["object"]
    if rel == "developed_by":
        return f"{subject} was developed by {obj}."
    if rel == "released_in":
        return f"{subject} was released in {obj}."
    if rel == "based_on":
        return f"{subject} was based on {obj}."
    if rel == "evaluated_on":
        return f"{subject} was evaluated on {obj}."
    if rel == "sota_on":
        return f"{subject} set the state of the art on {obj}."
    if rel == "authored_by":
        return f"{subject} was authored by {obj}."
    if rel == "acquired_by":
        return f"{subject} was acquired by {obj}."
    if rel == "cited_by":
        return f"{subject} was cited by {obj}."
    if rel == "release_year":
        return f"{subject} was released in {obj}."
    if rel == "param_count_b":
        return f"{subject} has {obj} billion parameters."
    if rel == "context_window_k":
        return f"{subject} has a {obj}K token context window."
    raise ValueError(f"unsupported rel: {rel}")


def write_docs(rows: list[dict[str, str]]) -> None:
    by_doc: dict[str, list[dict[str, str]]] = defaultdict(list)
    for claim in rows:
        by_doc[claim["doc"]].append(claim)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    for doc in ["A", "B", "C", "D", "E"]:
        text = " ".join(sentence_for(claim) for claim in by_doc[doc])
        (DOCS_DIR / f"{doc}.txt").write_text(text + "\n", encoding="utf-8")


def build_rows() -> list[dict[str, str]]:
    entities, facts = load_ref()
    lookup = fact_lookup(facts)
    used: set[tuple[str, str, str]] = set()
    output: list[dict[str, str]] = []

    for idx, fact in enumerate(select_true_facts(facts, 10, used), start=1):
        output.append(true_row("A", f"A{idx:03d}", fact))

    b_true = [true_row("B", f"BT{idx:03d}", fact) for idx, fact in enumerate(select_true_facts(facts, 19, used), start=1)]
    b_false = [
        row("B", "BF001", "Claude 3 Opus", "developed_by", "Google DeepMind", "CONTRADICTED", "tail_swap", "Anthropic"),
        row("B", "BF002", "GPT-4o", "developed_by", "Anthropic", "CONTRADICTED", "tail_swap", "OpenAI"),
        row("B", "BF003", "Gemini 1.5 Pro", "developed_by", "OpenAI", "CONTRADICTED", "tail_swap", "Google DeepMind"),
        row("B", "BF004", "Llama 3.1 405B", "developed_by", "Mistral AI", "CONTRADICTED", "tail_swap", "Meta"),
        row("B", "BF005", "DeepSeek-R1", "developed_by", "Cohere", "CONTRADICTED", "tail_swap", "DeepSeek"),
        row("B", "BF006", "GPT-4o", "release_year", "2026", "CONTRADICTED", "numeric", entities["gpt_4o"]["release_year"]),
        row("B", "BF007", "Llama 3.1 405B", "param_count_b", "810", "CONTRADICTED", "numeric", entities["llama_3_1_405b"]["param_count_b"]),
        row("B", "BF008", "Claude 3.5 Sonnet", "context_window_k", "100", "CONTRADICTED", "numeric", entities["claude_3_5_sonnet"]["context_window_k"]),
    ]
    output.extend(interleave(b_true, b_false))

    c_true = [true_row("C", f"CT{idx:03d}", fact) for idx, fact in enumerate(select_true_facts(facts, 7, used), start=1)]
    c_false = [
        row("C", "CF001", "AstraLM-9B", "developed_by", "Anthropic", "FABRICATED_ENTITY", "fabricated_entity"),
        row("C", "CF002", "GPT-4o", "developed_by", "Vesper Labs", "FABRICATED_ENTITY", "fabricated_entity"),
        row("C", "CF003", "Claude 3 Opus", "evaluated_on", "Northstar Eval", "FABRICATED_ENTITY", "fabricated_entity"),
    ]
    output.extend(interleave(c_true, c_false))

    output.extend(
        [
            row("D", "D001", "NebulaForge 42B", "developed_by", "Argent Loop Labs", "FABRICATED_CLUSTER", "fabricated_cluster"),
            row("D", "D002", "NebulaForge 42B", "released_in", "Cycle Year 2044", "FABRICATED_CLUSTER", "fabricated_cluster"),
            row("D", "D003", "NebulaForge 42B", "evaluated_on", "OrbitalBench", "FABRICATED_CLUSTER", "fabricated_cluster"),
            row("D", "D004", "NebulaForge 42B", "based_on", "The NebulaForge Report", "FABRICATED_CLUSTER", "fabricated_cluster"),
            row("D", "D005", "The NebulaForge Report", "authored_by", "Mira Solven", "FABRICATED_CLUSTER", "fabricated_cluster"),
            row("D", "D006", "OrbitalBench", "cited_by", "The NebulaForge Report", "FABRICATED_CLUSTER", "fabricated_cluster"),
        ]
    )

    alias_specs = [
        ("Omni", "developed_by", "OpenAI", lookup[("GPT-4o", "developed_by", "OpenAI")]),
        ("4o mini", "released_in", "2024", lookup[("GPT-4o mini", "released_in", "2024")]),
        ("Opus", "developed_by", "Anthropic", lookup[("Claude 3 Opus", "developed_by", "Anthropic")]),
        ("Sonnet 4", "released_in", "2025", lookup[("Claude Sonnet 4", "released_in", "2025")]),
        ("Gemini Pro 2.5", "developed_by", "Google DeepMind", lookup[("Gemini 2.5 Pro", "developed_by", "Google DeepMind")]),
        ("Llama-3.1-405B", "developed_by", "Meta AI", lookup[("Llama 3.1 405B", "developed_by", "Meta")]),
        ("Mixtral-8x7B", "developed_by", "Mistral", lookup[("Mixtral 8x7B", "developed_by", "Mistral AI")]),
        ("Qwen 2.5 72B", "developed_by", "Tongyi Qianwen", lookup[("Qwen2.5-72B", "developed_by", "Alibaba Cloud")]),
        ("DeepSeek R1", "released_in", "2025", lookup[("DeepSeek-R1", "released_in", "2025")]),
        ("DBRX", "developed_by", "Databricks Mosaic Research", lookup[("DBRX", "developed_by", "Databricks")]),
    ]
    for idx, (subject, rel, obj, fact) in enumerate(alias_specs, start=1):
        output.append(
            row(
                "E",
                f"E{idx:03d}",
                subject,
                rel,
                obj,
                "TRUE",
                "alias_rewrite",
                f"{fact['src_name']} {fact['rel']} {fact['dst_name']}",
            )
        )

    return output


def write_ledger(rows: list[dict[str, str]]) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=LEDGER_HEADER)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    rows = build_rows()
    write_ledger(rows)
    write_docs(rows)
    counts = defaultdict(int)
    labels = defaultdict(lambda: defaultdict(int))
    for claim in rows:
        counts[claim["doc"]] += 1
        labels[claim["doc"]][claim["label"]] += 1
    print(f"generated {len(rows)} benchmark claims with seed {SEED}")
    for doc in ["A", "B", "C", "D", "E"]:
        label_summary = ", ".join(f"{label}={count}" for label, count in sorted(labels[doc].items()))
        print(f"doc {doc}: {counts[doc]} claims ({label_summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
