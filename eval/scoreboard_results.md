# GraphJudge Scoreboard — graph-judge vs LLM-judge (63-claim benchmark)

- Scorer (graph judge): `http://127.0.0.1:8888` (live Neo4j + GDS)
- LLM judge: OpenRouter `google/gemini-3.5-flash`, one call per doc
- Claims: 63 across docs ['A', 'B', 'C', 'D', 'E']

## HEADLINE — planted-false detection

**Graph-judge 100.0% vs LLM-judge 100.0% detection of planted false claims on a 63-claim benchmark.**

| Slice | planted-false | graph-judge detected | LLM-judge detected |
|---|---|---|---|
| Overall | 17 | 17/17 (100.0%) | 17/17 (100.0%) |
| **Doc D (FABRICATED_CLUSTER)** | 6 | 6/6 (100.0%) | 6/6 (100.0%) |

Doc D is the core pitch: a coherent 6-fact fabrication cluster that only cites itself (zero real anchors). The graph-judge catches all 6 structurally — every mention is an orphan with no path to the reference core. **In this clean-reference ablation the LLM-judge also detects the cluster** (it can read that those entities are simply absent from the reference table), so on raw detection the two tie. The graph-judge's measured edge is elsewhere: exact 3-way labeling and deterministic, auditable evidence paths (see below).

Doc A false-positive rate (all-TRUE control — both should pass): graph-judge 0/10 (0.0%) vs LLM-judge 0/10 (0.0%).

**Where the graph-judge wins:** 3-way accuracy 100.0% vs 98.4%. The LLM detects planted-false claims but mislabels some (e.g. calling a fabricated entity CONTRADICTED instead of UNGROUNDED — see the disagreement table); the graph-judge assigns the exact status and returns a graph path as evidence, deterministically (temperature-0 LLM verdicts were still stable, but carry no evidence path).

## Overall metrics (detecting planted-false claims)

| Judge | Precision | Recall | F1 | 3-way acc | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|---|
| graph-judge | 100.0% | 100.0% | 100.0% | 100.0% | 17 | 0 | 0 | 46 |
| LLM-judge | 100.0% | 100.0% | 100.0% | 98.4% | 17 | 0 | 0 | 46 |

- Precision = of claims a judge flags, the share truly planted-false.
- Recall = share of planted-false claims detected (= detection rate above).
- 3-way acc = exact match on SUPPORTED / CONTRADICTED / UNGROUNDED.

## Per-doc breakdown

| Doc | Kind | N | judge | P | R | F1 | 3-way acc | detected |
|---|---|---|---|---|---|---|---|---|
| A | all-TRUE (control) | 10 | graph | 0.0% | 0.0% | 0.0% | 100.0% | n/a |
| A | all-TRUE (control) | 10 | LLM | 0.0% | 0.0% | 0.0% | 100.0% | n/a |
| B | tail-swap + numeric (CONTRADICTED) | 27 | graph | 100.0% | 100.0% | 100.0% | 100.0% | 8/8 |
| B | tail-swap + numeric (CONTRADICTED) | 27 | LLM | 100.0% | 100.0% | 100.0% | 100.0% | 8/8 |
| C | fabricated entity (UNGROUNDED) | 10 | graph | 100.0% | 100.0% | 100.0% | 100.0% | 3/3 |
| C | fabricated entity (UNGROUNDED) | 10 | LLM | 100.0% | 100.0% | 100.0% | 90.0% | 3/3 |
| D | fabricated CLUSTER (UNGROUNDED) | 6 | graph | 100.0% | 100.0% | 100.0% | 100.0% | 6/6 |
| D | fabricated CLUSTER (UNGROUNDED) | 6 | LLM | 100.0% | 100.0% | 100.0% | 100.0% | 6/6 |
| E | alias rewrite (TRUE) | 10 | graph | 0.0% | 0.0% | 0.0% | 100.0% | n/a |
| E | alias rewrite (TRUE) | 10 | LLM | 0.0% | 0.0% | 0.0% | 100.0% | n/a |

## Per-claim verdicts where the judges disagree

| cid | doc | label | gold | graph | LLM |
|---|---|---|---|---|---|
| CF002 | C | FABRICATED_ENTITY | UNGROUNDED | UNGROUNDED | CONTRADICTED |

## Résumé-ready one-liner

> graph-judge 100.0% vs LLM-judge 100.0% detection of planted false claims on a 63-claim benchmark

Fuller framing (honest — detection ties, graph wins on exactness + evidence):

> Built a deterministic graph-grounded factuality judge that matches an LLM-as-judge baseline on planted-false detection (100.0% vs 100.0%, 63-claim benchmark) while beating it on exact 3-way labeling (100.0% vs 98.4%) and returning an auditable graph-path as evidence for every verdict.

