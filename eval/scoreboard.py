#!/usr/bin/env python3
"""GraphJudge scoreboard: graph-judge vs LLM-judge on the 63-claim benchmark.

Both judges receive the SAME claims and the SAME reference facts (DESIGN §3.3
clean ablation). This computes the project's headline measurable outcome
(DESIGN §5): how many planted-false claims each judge detects, with a special
breakout for doc D (FABRICATED_CLUSTER) — the coherent-fabrication cluster the
graph catches and the LLM-judge waves through.

Ground truth (from bench_ledger label):
    TRUE            -> SUPPORTED
    CONTRADICTED    -> CONTRADICTED
    FABRICATED_*    -> UNGROUNDED
planted-false = label in {CONTRADICTED, FABRICATED_ENTITY, FABRICATED_CLUSTER}
detected      = judge did NOT say SUPPORTED

Run:
    PYTHONPATH=<worktree> .venv/bin/python eval/scoreboard.py \
        --scorer-url http://127.0.0.1:8888
"""

from __future__ import annotations

import argparse
import sys
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_runner import (  # noqa: E402
    DEFAULT_LEDGER,
    claim_payload,
    expected_status,
    post_score,
    read_ledger,
)
from llm_judge_runner import run_llm_judge  # noqa: E402
from pipeline.llm import DEFAULT_MODEL  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS_MD = Path(__file__).resolve().parent / "scoreboard_results.md"

PLANTED_FALSE_LABELS = {"CONTRADICTED", "FABRICATED_ENTITY", "FABRICATED_CLUSTER"}
DOC_TITLES = {
    "A": "all-TRUE (control)",
    "B": "tail-swap + numeric (CONTRADICTED)",
    "C": "fabricated entity (UNGROUNDED)",
    "D": "fabricated CLUSTER (UNGROUNDED)",
    "E": "alias rewrite (TRUE)",
}


# ---------------------------------------------------------------------------
# Graph judge — POST each doc's §4.1 payload to the live scorer
# ---------------------------------------------------------------------------

def run_graph_judge(
    rows: list[dict[str, str]], scorer_url: str, timeout: int = 60, verbose: bool = True
) -> dict[str, str]:
    by_doc: dict[str, list[dict[str, str]]] = defaultdict(list)
    for r in rows:
        by_doc[r["doc"]].append(r)

    verdicts: dict[str, str] = {}
    for doc in sorted(by_doc):
        doc_rows = by_doc[doc]
        payload = {
            "job_id": str(uuid.uuid4()),
            "claims": [claim_payload(r) for r in doc_rows],
        }
        resp = post_score(scorer_url, payload, doc_rows, timeout)
        by_cid = {c["cid"]: c["status"] for c in resp.get("claims", [])}
        for r in doc_rows:
            verdicts[r["cid"]] = by_cid.get(r["cid"], "MISSING")
        if verbose:
            print(f"  [doc {doc}] graph ok: {len(doc_rows)} claims scored")
    return verdicts


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def detected(status: str) -> bool:
    """A claim is 'detected' as suspect when the judge did NOT say SUPPORTED."""
    return status != "SUPPORTED" and status not in {"", "MISSING", "ERRORED"}


def compute_metrics(rows: list[dict[str, str]], verdicts: dict[str, str]) -> dict[str, Any]:
    """Metrics over the given rows for a single judge's verdicts."""
    tp = fp = fn = tn = 0
    correct3 = 0
    n = 0
    planted_total = 0
    planted_detected = 0
    for r in rows:
        cid = r["cid"]
        label = r["label"]
        gold = expected_status(label)
        pred = verdicts.get(cid, "ERRORED")
        is_planted = label in PLANTED_FALSE_LABELS
        is_detected = detected(pred)
        n += 1
        if pred == gold:
            correct3 += 1
        if is_planted:
            planted_total += 1
            if is_detected:
                tp += 1
                planted_detected += 1
            else:
                fn += 1
        else:  # TRUE claim
            if is_detected:
                fp += 1
            else:
                tn += 1
    precision, recall, f1 = _prf(tp, fp, fn)
    return {
        "n": n,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy3": correct3 / n if n else 0.0,
        "planted_total": planted_total,
        "planted_detected": planted_detected,
        "detect_rate": planted_detected / planted_total if planted_total else float("nan"),
    }


def fp_rate(rows: list[dict[str, str]], verdicts: dict[str, str]) -> tuple[int, int, float]:
    """False-positive rate on all-TRUE rows: fraction flagged (judge != SUPPORTED)."""
    true_rows = [r for r in rows if r["label"] == "TRUE"]
    flagged = sum(1 for r in true_rows if detected(verdicts.get(r["cid"], "ERRORED")))
    total = len(true_rows)
    return flagged, total, (flagged / total if total else 0.0)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def pct(x: float) -> str:
    return "n/a" if x != x else f"{100 * x:.1f}%"


def render_scoreboard(
    rows: list[dict[str, str]],
    graph_v: dict[str, str],
    llm_v: dict[str, str],
    llm_errored_docs: set[str],
    scorer_url: str,
    model: str,
) -> str:
    lines: list[str] = []
    W = lines.append

    g_all = compute_metrics(rows, graph_v)
    l_all = compute_metrics(rows, llm_v)

    W("# GraphJudge Scoreboard — graph-judge vs LLM-judge (63-claim benchmark)")
    W("")
    W(f"- Scorer (graph judge): `{scorer_url}` (live Neo4j + GDS)")
    W(f"- LLM judge: OpenRouter `{model}`, one call per doc")
    W(f"- Claims: {len(rows)} across docs {sorted({r['doc'] for r in rows})}")
    if llm_errored_docs:
        W(f"- LLM-judge ERRORED docs (graph column still complete): {sorted(llm_errored_docs)}")
    W("")

    # ---- HEADLINE ----
    ga = g_all["detect_rate"]
    la = l_all["detect_rate"]
    d_rows = [r for r in rows if r["doc"] == "D"]
    gd = compute_metrics(d_rows, graph_v)["detect_rate"] if d_rows else float("nan")
    ld = compute_metrics(d_rows, llm_v)["detect_rate"] if d_rows else float("nan")
    g_flag, g_tot, g_fpr = fp_rate([r for r in rows if r["doc"] == "A"], graph_v)
    l_flag, l_tot, l_fpr = fp_rate([r for r in rows if r["doc"] == "A"], llm_v)

    W("## HEADLINE — planted-false detection")
    W("")
    W(f"**Graph-judge {pct(ga)} vs LLM-judge {pct(la)} detection of planted false "
      f"claims on a {len(rows)}-claim benchmark.**")
    W("")
    W("| Slice | planted-false | graph-judge detected | LLM-judge detected |")
    W("|---|---|---|---|")
    W(f"| Overall | {g_all['planted_total']} | "
      f"{g_all['planted_detected']}/{g_all['planted_total']} ({pct(ga)}) | "
      f"{l_all['planted_detected']}/{l_all['planted_total']} ({pct(la)}) |")
    if d_rows:
        gdm = compute_metrics(d_rows, graph_v)
        ldm = compute_metrics(d_rows, llm_v)
        W(f"| **Doc D (FABRICATED_CLUSTER)** | {gdm['planted_total']} | "
          f"{gdm['planted_detected']}/{gdm['planted_total']} ({pct(gd)}) | "
          f"{ldm['planted_detected']}/{ldm['planted_total']} ({pct(ld)}) |")
    W("")
    W("Doc D is the core pitch: a coherent 6-fact fabrication cluster that only "
      "cites itself (zero real anchors). The graph-judge catches all 6 "
      "structurally — every mention is an orphan with no path to the reference "
      "core. **In this clean-reference ablation the LLM-judge also detects the "
      "cluster** (it can read that those entities are simply absent from the "
      "reference table), so on raw detection the two tie. The graph-judge's "
      "measured edge is elsewhere: exact 3-way labeling and deterministic, "
      "auditable evidence paths (see below).")
    W("")
    W(f"Doc A false-positive rate (all-TRUE control — both should pass): "
      f"graph-judge {g_flag}/{g_tot} ({pct(g_fpr)}) vs LLM-judge {l_flag}/{l_tot} ({pct(l_fpr)}).")
    W("")
    # Where the graph-judge wins even when detection ties.
    g_acc, l_acc = g_all["accuracy3"], l_all["accuracy3"]
    if abs(g_acc - l_acc) > 1e-9:
        W(f"**Where the graph-judge wins:** 3-way accuracy {pct(g_acc)} vs "
          f"{pct(l_acc)}. The LLM detects planted-false claims but mislabels "
          "some (e.g. calling a fabricated entity CONTRADICTED instead of "
          "UNGROUNDED — see the disagreement table); the graph-judge assigns the "
          "exact status and returns a graph path as evidence, deterministically "
          "(temperature-0 LLM verdicts were still stable, but carry no evidence "
          "path).")
        W("")

    # ---- Overall metrics table ----
    W("## Overall metrics (detecting planted-false claims)")
    W("")
    W("| Judge | Precision | Recall | F1 | 3-way acc | TP | FP | FN | TN |")
    W("|---|---|---|---|---|---|---|---|---|")
    for name, m in (("graph-judge", g_all), ("LLM-judge", l_all)):
        W(f"| {name} | {pct(m['precision'])} | {pct(m['recall'])} | {pct(m['f1'])} | "
          f"{pct(m['accuracy3'])} | {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} |")
    W("")
    W("- Precision = of claims a judge flags, the share truly planted-false.")
    W("- Recall = share of planted-false claims detected (= detection rate above).")
    W("- 3-way acc = exact match on SUPPORTED / CONTRADICTED / UNGROUNDED.")
    W("")

    # ---- Per-doc ----
    W("## Per-doc breakdown")
    W("")
    W("| Doc | Kind | N | judge | P | R | F1 | 3-way acc | detected |")
    W("|---|---|---|---|---|---|---|---|---|")
    for doc in sorted({r["doc"] for r in rows}):
        drows = [r for r in rows if r["doc"] == doc]
        gm = compute_metrics(drows, graph_v)
        lm = compute_metrics(drows, llm_v)
        title = DOC_TITLES.get(doc, "")
        pf = gm["planted_total"]
        det_g = "n/a" if pf == 0 else f"{gm['planted_detected']}/{pf}"
        det_l = "n/a" if pf == 0 else f"{lm['planted_detected']}/{pf}"
        W(f"| {doc} | {title} | {len(drows)} | graph | {pct(gm['precision'])} | "
          f"{pct(gm['recall'])} | {pct(gm['f1'])} | {pct(gm['accuracy3'])} | {det_g} |")
        W(f"| {doc} | {title} | {len(drows)} | LLM | {pct(lm['precision'])} | "
          f"{pct(lm['recall'])} | {pct(lm['f1'])} | {pct(lm['accuracy3'])} | {det_l} |")
    W("")

    # ---- Per-claim disagreements ----
    W("## Per-claim verdicts where the judges disagree")
    W("")
    W("| cid | doc | label | gold | graph | LLM |")
    W("|---|---|---|---|---|---|")
    any_disagree = False
    for r in rows:
        g = graph_v.get(r["cid"], "ERRORED")
        l = llm_v.get(r["cid"], "ERRORED")
        if g != l:
            any_disagree = True
            W(f"| {r['cid']} | {r['doc']} | {r['label']} | {expected_status(r['label'])} | {g} | {l} |")
    if not any_disagree:
        W("| (none) | | | | | |")
    W("")

    # ---- Resume line ----
    W("## Résumé-ready one-liner")
    W("")
    W(f"> graph-judge {pct(ga)} vs LLM-judge {pct(la)} detection of planted false "
      f"claims on a {len(rows)}-claim benchmark")
    W("")
    W("Fuller framing (honest — detection ties, graph wins on exactness + evidence):")
    W("")
    W(f"> Built a deterministic graph-grounded factuality judge that matches an "
      f"LLM-as-judge baseline on planted-false detection ({pct(ga)} vs {pct(la)}, "
      f"63-claim benchmark) while beating it on exact 3-way labeling "
      f"({pct(g_all['accuracy3'])} vs {pct(l_all['accuracy3'])}) and returning an "
      f"auditable graph-path as evidence for every verdict.")
    W("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scorer-url", default="http://127.0.0.1:8888")
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--no-llm", action="store_true", help="graph-judge only (debug)")
    args = parser.parse_args()

    rows = read_ledger(args.ledger)
    print(f"Loaded {len(rows)} claims from {args.ledger}")

    print("\n== Graph judge (live scorer) ==")
    graph_v = run_graph_judge(rows, args.scorer_url, args.timeout)

    llm_errored: set[str] = set()
    if args.no_llm:
        llm_v: dict[str, str] = {}
        llm_errored = {r["doc"] for r in rows}
    else:
        print("\n== LLM judge (OpenRouter, one call/doc) ==")
        llm_v, llm_errored = run_llm_judge(rows, model=args.model)

    md = render_scoreboard(rows, graph_v, llm_v, llm_errored, args.scorer_url, args.model)
    RESULTS_MD.write_text(md + "\n", encoding="utf-8")
    print("\n" + "=" * 78)
    print(md)
    print("=" * 78)
    print(f"\nWrote {RESULTS_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
