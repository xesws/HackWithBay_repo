#!/usr/bin/env python3
"""Generate the Eval-2 contamination-free personal benchmark.

The universe is deliberately fictional and closed. All generated facts live
under data/personal so this benchmark can be loaded independently from the
LLM-ecosystem Track-D benchmark.
"""

from __future__ import annotations

import csv
import random
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "personal"
DOCS_DIR = DATA_DIR / "docs"
ENTITIES_PATH = DATA_DIR / "ref_entities.csv"
FACTS_PATH = DATA_DIR / "ref_facts.csv"
LEDGER_PATH = DATA_DIR / "bench_ledger.csv"
SEED = 17

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

FUNCTIONAL_RELS = {"works_at", "married_to", "born_in"}


def entity(ent_id: str, name: str, typ: str, aliases: str = "") -> dict[str, str]:
    return {
        "id": ent_id,
        "name": name,
        "type": typ,
        "aliases": aliases,
        "release_year": "",
        "param_count_b": "",
        "context_window_k": "",
    }


PERSONS = [
    ("p_arlen_veyro", "Arlen Veyro", "Arlen V|AVeyro"),
    ("p_brisa_nalore", "Brisa Nalore", "Brisa N|BNalore"),
    ("p_corwin_mavik", "Corwin Mavik", "Corwin M|CMavik"),
    ("p_della_quorin", "Della Quorin", "Della Q|DQuorin"),
    ("p_eron_pellis", "Eron Pellis", "Eron P|EPellis"),
    ("p_fia_selwick", "Fia Selwick", "Fia S|FSelwick"),
    ("p_gavo_rellin", "Gavo Rellin", "Gavo R|GRellin"),
    ("p_hessa_torvane", "Hessa Torvane", "Hessa T|HTorvane"),
    ("p_ivo_caldrin", "Ivo Caldrin", "Ivo C|ICaldrin"),
    ("p_jessa_minlow", "Jessa Minlow", "Jessa M|JMinlow"),
    ("p_kellan_orvix", "Kellan Orvix", "Kellan O|KOrvix"),
    ("p_luma_rennic", "Luma Rennic", "Luma R|LRennic"),
    ("p_maro_veskin", "Maro Veskin", "Maro V|MVeskin"),
    ("p_nira_tavro", "Nira Tavro", "Nira T|NTavro"),
    ("p_oren_halix", "Oren Halix", "Oren H|OHalix"),
]

ORGS = [
    ("org_aster_quay_group", "Aster Quay Group", "Org", "Aster Quay|AQG"),
    ("org_brindle_nacre_works", "Brindle Nacre Works", "Org", "Brindle Nacre|BNW"),
    ("team_velora_signal", "Velora Signal Team", "Team", "Velora Signal|VST"),
    ("team_northpass_loom", "Northpass Loom Cooperative", "Team", "Northpass Loom|NLC"),
]

PROJECTS = [
    ("project_tallowmere", "Project Tallowmere", "Tallowmere"),
    ("project_glasskite", "Project Glasskite", "Glasskite"),
    ("project_emberfold", "Project Emberfold", "Emberfold"),
    ("project_rivetspool", "Project Rivetspool", "Rivetspool"),
    ("project_moonquill", "Project Moonquill", "Moonquill"),
]

CITIES = [
    ("city_dovemarsh", "Dovemarsh", "Dove Marsh"),
    ("city_larkhollow", "Larkhollow", "Lark Hollow"),
    ("city_orison_vale", "Orison Vale", "Orison"),
    ("city_quillbay", "Quillbay", "Quill Bay"),
    ("city_vesperfield", "Vesperfield", "Vesper Field"),
]

PETS = [
    ("pet_bramble", "Bramble", "Little Bramble"),
    ("pet_tiko", "Tiko", "Tiny Tiko"),
    ("pet_nema", "Nema", "Nema Kit"),
    ("pet_ruffle", "Ruffle", "Little Ruffle"),
    ("pet_pavo", "Pavo", "Pavo Pup"),
    ("pet_quince", "Quince", "Quince Cat"),
]

YEARS = [
    1984,
    1986,
    1988,
    1990,
    1992,
    1994,
    1996,
    1998,
    2000,
    2002,
    2020,
    2021,
    2022,
    2023,
    2024,
    2025,
]


WORKS_AT = {
    "p_arlen_veyro": "org_aster_quay_group",
    "p_brisa_nalore": "org_brindle_nacre_works",
    "p_corwin_mavik": "team_velora_signal",
    "p_della_quorin": "team_northpass_loom",
    "p_eron_pellis": "org_aster_quay_group",
    "p_fia_selwick": "team_velora_signal",
    "p_gavo_rellin": "org_brindle_nacre_works",
    "p_hessa_torvane": "team_northpass_loom",
    "p_ivo_caldrin": "org_aster_quay_group",
    "p_jessa_minlow": "team_velora_signal",
    "p_kellan_orvix": "org_brindle_nacre_works",
    "p_luma_rennic": "team_northpass_loom",
    "p_maro_veskin": "org_aster_quay_group",
    "p_nira_tavro": "team_velora_signal",
    "p_oren_halix": "org_brindle_nacre_works",
}

LIVES_IN = {
    "p_arlen_veyro": "city_dovemarsh",
    "p_brisa_nalore": "city_larkhollow",
    "p_corwin_mavik": "city_quillbay",
    "p_della_quorin": "city_vesperfield",
    "p_eron_pellis": "city_orison_vale",
    "p_fia_selwick": "city_quillbay",
    "p_gavo_rellin": "city_dovemarsh",
    "p_hessa_torvane": "city_larkhollow",
    "p_ivo_caldrin": "city_orison_vale",
    "p_jessa_minlow": "city_vesperfield",
    "p_kellan_orvix": "city_quillbay",
    "p_luma_rennic": "city_dovemarsh",
    "p_maro_veskin": "city_larkhollow",
    "p_nira_tavro": "city_orison_vale",
    "p_oren_halix": "city_vesperfield",
}

BORN_IN = {
    "p_arlen_veyro": "year_1984",
    "p_brisa_nalore": "year_1986",
    "p_corwin_mavik": "year_1988",
    "p_della_quorin": "year_1990",
    "p_eron_pellis": "year_1992",
    "p_fia_selwick": "year_1994",
    "p_gavo_rellin": "year_1996",
    "p_hessa_torvane": "year_1998",
    "p_ivo_caldrin": "year_2000",
    "p_jessa_minlow": "year_2002",
    "p_kellan_orvix": "year_1984",
    "p_luma_rennic": "year_1986",
    "p_maro_veskin": "year_1988",
    "p_nira_tavro": "year_1990",
    "p_oren_halix": "year_1992",
}

JOINED_IN = {
    "p_arlen_veyro": "year_2020",
    "p_brisa_nalore": "year_2021",
    "p_corwin_mavik": "year_2022",
    "p_della_quorin": "year_2023",
    "p_eron_pellis": "year_2024",
    "p_fia_selwick": "year_2025",
    "p_gavo_rellin": "year_2020",
    "p_hessa_torvane": "year_2021",
    "p_ivo_caldrin": "year_2022",
    "p_jessa_minlow": "year_2023",
    "p_kellan_orvix": "year_2024",
    "p_luma_rennic": "year_2025",
    "p_maro_veskin": "year_2020",
    "p_nira_tavro": "year_2021",
    "p_oren_halix": "year_2022",
}

OWNS_PET = {
    "p_arlen_veyro": "pet_bramble",
    "p_brisa_nalore": "pet_tiko",
    "p_corwin_mavik": "pet_nema",
    "p_della_quorin": "pet_quince",
    "p_eron_pellis": "pet_pavo",
    "p_fia_selwick": "pet_ruffle",
    "p_gavo_rellin": "pet_bramble",
    "p_hessa_torvane": "pet_tiko",
    "p_ivo_caldrin": "pet_nema",
    "p_jessa_minlow": "pet_quince",
    "p_kellan_orvix": "pet_pavo",
    "p_luma_rennic": "pet_ruffle",
    "p_maro_veskin": "pet_bramble",
    "p_nira_tavro": "pet_tiko",
    "p_oren_halix": "pet_nema",
}

MARRIAGES = [
    ("p_arlen_veyro", "p_brisa_nalore"),
    ("p_corwin_mavik", "p_della_quorin"),
    ("p_eron_pellis", "p_fia_selwick"),
    ("p_gavo_rellin", "p_hessa_torvane"),
    ("p_ivo_caldrin", "p_jessa_minlow"),
    ("p_kellan_orvix", "p_luma_rennic"),
]

MANAGES = [
    ("p_arlen_veyro", "p_eron_pellis"),
    ("p_arlen_veyro", "p_ivo_caldrin"),
    ("p_arlen_veyro", "p_maro_veskin"),
    ("p_brisa_nalore", "p_gavo_rellin"),
    ("p_brisa_nalore", "p_oren_halix"),
    ("p_corwin_mavik", "p_fia_selwick"),
    ("p_corwin_mavik", "p_jessa_minlow"),
    ("p_corwin_mavik", "p_nira_tavro"),
    ("p_della_quorin", "p_hessa_torvane"),
    ("p_della_quorin", "p_luma_rennic"),
]

LEADS_PROJECT = [
    ("p_arlen_veyro", "project_tallowmere"),
    ("p_brisa_nalore", "project_glasskite"),
    ("p_corwin_mavik", "project_emberfold"),
    ("p_della_quorin", "project_rivetspool"),
    ("p_eron_pellis", "project_tallowmere"),
    ("p_fia_selwick", "project_glasskite"),
    ("p_hessa_torvane", "project_rivetspool"),
    ("p_nira_tavro", "project_moonquill"),
    ("p_maro_veskin", "project_moonquill"),
    ("p_jessa_minlow", "project_emberfold"),
]


def build_entities() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    rows.extend(entity(ent_id, name, "Person", aliases) for ent_id, name, aliases in PERSONS)
    rows.extend(entity(ent_id, name, typ, aliases) for ent_id, name, typ, aliases in ORGS)
    rows.extend(entity(ent_id, name, "Project", aliases) for ent_id, name, aliases in PROJECTS)
    rows.extend(entity(ent_id, name, "City", aliases) for ent_id, name, aliases in CITIES)
    rows.extend(entity(ent_id, name, "Pet", aliases) for ent_id, name, aliases in PETS)
    rows.extend(entity(f"year_{year}", str(year), "Year") for year in YEARS)
    return rows


def fact(src: str, rel: str, dst: str, entities: dict[str, dict[str, str]]) -> dict[str, str]:
    src_ent = entities[src]
    dst_ent = entities[dst]
    return {
        "src": src,
        "src_name": src_ent["name"],
        "src_type": src_ent["type"],
        "rel": rel,
        "dst": dst,
        "dst_name": dst_ent["name"],
        "dst_type": dst_ent["type"],
        "functional": "true" if rel in FUNCTIONAL_RELS else "false",
    }


def build_facts(entities: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for src, dst in WORKS_AT.items():
        rows.append(fact(src, "works_at", dst, entities))
    for src, dst in LIVES_IN.items():
        rows.append(fact(src, "lives_in", dst, entities))
    for src, dst in BORN_IN.items():
        rows.append(fact(src, "born_in", dst, entities))
    for src, dst in JOINED_IN.items():
        rows.append(fact(src, "joined_in", dst, entities))
    for src, dst in OWNS_PET.items():
        rows.append(fact(src, "owns_pet", dst, entities))
    for a, b in MARRIAGES:
        rows.append(fact(a, "married_to", b, entities))
        rows.append(fact(b, "married_to", a, entities))
    for src, dst in MANAGES:
        rows.append(fact(src, "manages", dst, entities))
    for src, dst in LEADS_PROJECT:
        rows.append(fact(src, "leads_project", dst, entities))
    return rows


def ledger_row(
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


def true_row(doc: str, cid: str, fact_row: dict[str, str]) -> dict[str, str]:
    return ledger_row(
        doc,
        cid,
        fact_row["src_name"],
        fact_row["rel"],
        fact_row["dst_name"],
        "TRUE",
        "truth",
    )


def fact_lookup(facts: list[dict[str, str]]) -> dict[tuple[str, str, str], dict[str, str]]:
    return {(row["src_name"], row["rel"], row["dst_name"]): row for row in facts}


def select_true_facts(
    facts: list[dict[str, str]],
    count: int,
    used: set[tuple[str, str, str]],
) -> list[dict[str, str]]:
    rng = random.Random(SEED)
    eligible = [
        fact_row
        for fact_row in facts
        if (fact_row["src_name"], fact_row["rel"], fact_row["dst_name"]) not in used
    ]
    rng.shuffle(eligible)
    selected = []
    for fact_row in eligible:
        key = (fact_row["src_name"], fact_row["rel"], fact_row["dst_name"])
        if key in used:
            continue
        selected.append(fact_row)
        used.add(key)
        if len(selected) == count:
            return selected
    raise RuntimeError(f"not enough unused true facts for count={count}")


def interleave(true_rows: list[dict[str, str]], false_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    true_iter = iter(true_rows)
    false_iter = iter(false_rows)
    while True:
        for _ in range(2):
            try:
                output.append(next(true_iter))
            except StopIteration:
                break
        try:
            output.append(next(false_iter))
        except StopIteration:
            output.extend(true_iter)
            return output


def build_ledger(facts: list[dict[str, str]]) -> list[dict[str, str]]:
    lookup = fact_lookup(facts)
    alias_specs = [
        ("Arlen V", "works_at", "AQG", lookup[("Arlen Veyro", "works_at", "Aster Quay Group")]),
        ("Brisa N", "married_to", "Arlen V", lookup[("Brisa Nalore", "married_to", "Arlen Veyro")]),
        ("Corwin M", "lives_in", "Quill Bay", lookup[("Corwin Mavik", "lives_in", "Quillbay")]),
        ("Della Q", "joined_in", "2023", lookup[("Della Quorin", "joined_in", "2023")]),
        ("Eron P", "leads_project", "Tallowmere", lookup[("Eron Pellis", "leads_project", "Project Tallowmere")]),
        ("Fia S", "owns_pet", "Little Ruffle", lookup[("Fia Selwick", "owns_pet", "Ruffle")]),
        ("Hessa T", "works_at", "Northpass Loom", lookup[("Hessa Torvane", "works_at", "Northpass Loom Cooperative")]),
        ("Nira T", "leads_project", "Moonquill", lookup[("Nira Tavro", "leads_project", "Project Moonquill")]),
    ]
    used = {
        (fact_row["src_name"], fact_row["rel"], fact_row["dst_name"])
        for _subject, _rel, _obj, fact_row in alias_specs
    }

    rows: list[dict[str, str]] = []

    for idx, fact_row in enumerate(select_true_facts(facts, 8, used), start=1):
        rows.append(true_row("A", f"A{idx:03d}", fact_row))

    b_true = [
        true_row("B", f"BT{idx:03d}", fact_row)
        for idx, fact_row in enumerate(select_true_facts(facts, 16, used), start=1)
    ]
    b_false = [
        ledger_row("B", "BF001", "Arlen Veyro", "works_at", "Brindle Nacre Works", "CONTRADICTED", "tail_swap", "Aster Quay Group"),
        ledger_row("B", "BF002", "Corwin Mavik", "works_at", "Northpass Loom Cooperative", "CONTRADICTED", "tail_swap", "Velora Signal Team"),
        ledger_row("B", "BF003", "Brisa Nalore", "married_to", "Corwin Mavik", "CONTRADICTED", "tail_swap", "Arlen Veyro"),
        ledger_row("B", "BF004", "Eron Pellis", "married_to", "Hessa Torvane", "CONTRADICTED", "tail_swap", "Fia Selwick"),
        ledger_row("B", "BF005", "Ivo Caldrin", "works_at", "Brindle Nacre Works", "CONTRADICTED", "tail_swap", "Aster Quay Group"),
        ledger_row("B", "BF006", "Della Quorin", "born_in", "1992", "CONTRADICTED", "numeric", "1990"),
        ledger_row("B", "BF007", "Fia Selwick", "born_in", "1996", "CONTRADICTED", "numeric", "1994"),
        ledger_row("B", "BF008", "Jessa Minlow", "born_in", "2000", "CONTRADICTED", "numeric", "2002"),
    ]
    rows.extend(interleave(b_true, b_false))

    c_true = [
        true_row("C", f"CT{idx:03d}", fact_row)
        for idx, fact_row in enumerate(select_true_facts(facts, 7, used), start=1)
    ]
    c_false = [
        ledger_row("C", "CF001", "Mira Vell", "works_at", "Aster Quay Group", "FABRICATED_ENTITY", "fabricated_entity"),
        ledger_row("C", "CF002", "Arlen Veyro", "owns_pet", "Saffo", "FABRICATED_ENTITY", "fabricated_entity"),
        ledger_row("C", "CF003", "Luma Rennic", "leads_project", "Project Sunspindle", "FABRICATED_ENTITY", "fabricated_entity"),
    ]
    rows.extend(interleave(c_true, c_false))

    rows.extend(
        [
            ledger_row("D", "D001", "Zavren Pell", "works_at", "Cindrel Motive Office", "FABRICATED_CLUSTER", "fabricated_cluster"),
            ledger_row("D", "D002", "Ostia Kel", "works_at", "Cindrel Motive Office", "FABRICATED_CLUSTER", "fabricated_cluster"),
            ledger_row("D", "D003", "Zavren Pell", "manages", "Ostia Kel", "FABRICATED_CLUSTER", "fabricated_cluster"),
            ledger_row("D", "D004", "Ostia Kel", "leads_project", "Project Sablewick", "FABRICATED_CLUSTER", "fabricated_cluster"),
            ledger_row("D", "D005", "Noll Varen", "leads_project", "Project Sablewick", "FABRICATED_CLUSTER", "fabricated_cluster"),
            ledger_row("D", "D006", "Noll Varen", "manages", "Zavren Pell", "FABRICATED_CLUSTER", "fabricated_cluster"),
        ]
    )

    for idx, (subject, rel, obj, fact_row) in enumerate(alias_specs, start=1):
        rows.append(
            ledger_row(
                "E",
                f"E{idx:03d}",
                subject,
                rel,
                obj,
                "TRUE",
                "alias_rewrite",
                f"{fact_row['src_name']} {fact_row['rel']} {fact_row['dst_name']}",
            )
        )

    return rows


def sentence_for(claim: dict[str, str]) -> str:
    subject = claim["subject"]
    rel = claim["rel"]
    obj = claim["object"]
    if rel == "works_at":
        return f"{subject} works at {obj}."
    if rel == "lives_in":
        return f"{subject} lives in {obj}."
    if rel == "married_to":
        return f"{subject} is married to {obj}."
    if rel == "manages":
        return f"{subject} manages {obj}."
    if rel == "leads_project":
        return f"{subject} leads {obj}."
    if rel == "owns_pet":
        return f"{subject} owns a pet named {obj}."
    if rel == "joined_in":
        return f"{subject} joined in {obj}."
    if rel == "born_in":
        return f"{subject} was born in {obj}."
    raise ValueError(f"unsupported rel: {rel}")


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)


def write_docs(rows: list[dict[str, str]]) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    by_doc: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_doc[row["doc"]].append(row)
    for doc in ["A", "B", "C", "D", "E"]:
        text = " ".join(sentence_for(row) for row in by_doc[doc])
        (DOCS_DIR / f"{doc}.txt").write_text(text + "\n", encoding="utf-8")


def main() -> int:
    entity_rows = build_entities()
    entities = {row["id"]: row for row in entity_rows}
    fact_rows = build_facts(entities)
    ledger_rows = build_ledger(fact_rows)

    write_csv(ENTITIES_PATH, ENTITY_HEADER, entity_rows)
    write_csv(FACTS_PATH, FACT_HEADER, fact_rows)
    write_csv(LEDGER_PATH, LEDGER_HEADER, ledger_rows)
    write_docs(ledger_rows)

    counts: dict[str, int] = defaultdict(int)
    labels: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in ledger_rows:
        counts[row["doc"]] += 1
        labels[row["doc"]][row["label"]] += 1

    print(f"generated {len(entity_rows)} personal entities")
    print(f"generated {len(fact_rows)} personal facts")
    print(f"generated {len(ledger_rows)} personal benchmark claims with seed {SEED}")
    for doc in ["A", "B", "C", "D", "E"]:
        label_summary = ", ".join(f"{label}={count}" for label, count in sorted(labels[doc].items()))
        print(f"doc {doc}: {counts[doc]} claims ({label_summary})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
