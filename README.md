<div align="center">

<img src="docs/assets/logo.svg" alt="GraphJudge — graph-as-judge factuality evaluation" width="720">

**Everyone judges LLMs with LLMs. We judge them with graphs.**

[Live demo](https://graphjudge.butterbase.dev) · [Design](docs/DESIGN.md) · [Demo script](docs/DEMO.md) · [Contracts](docs/contracts.md)

</div>

---

GraphJudge is a graph-grounded factuality judge for LLM output, built for HackwithBay 3.0. A user pastes generated text, GraphJudge extracts atomic claims, anchors them to a trusted Neo4j reference graph, and returns a verdict for each claim with graph evidence.

## What It Does

GraphJudge turns prose into a render-ready fact constellation:

- Green nodes: `SUPPORTED`, backed by the reference graph.
- Red nodes or edges: `CONTRADICTED`, conflicting with a functional reference fact.
- Gray nodes: `UNGROUNDED`, not supported by the reference graph.
- Orange nodes: `UNGROUNDED` fabricated cluster, a group of claims that only point to each other and do not connect to the trusted graph core.

The core claim is that relationship structure is useful for evaluation. A fluent but fake cluster may look plausible in text, but in a graph it becomes a disconnected component with no trusted anchor.

## Why This Isn't Just Graph RAG

The most common question is: "why not just build a Graph RAG that retrieves the subgraph and checks the claim?" GraphJudge and Graph RAG operate on opposite sides of generation and answer different questions.

- **Graph RAG runs upstream of generation.** It retrieves context and feeds it into an LLM so the LLM *generates* a better, grounded answer. The LLM is still the author and still the judge.
- **GraphJudge runs downstream of generation.** It takes already-generated text and asks whether it is true. It is a verifier, a gate, and an eval layer — not a generator.

Four differences make this more than a rebrand of retrieval:

1. **The verdict is made by the graph, not by an LLM.** `born_in` is a functional (single-valued) relationship; the reference graph pins `Della -> 1990`; a claim of `1992` is `CONTRADICTED` by a deterministic Cypher/arithmetic check. An LLM is used only to *parse* prose into structured claims, never to *decide* truth. We removed the LLM from exactly the step where a checker would otherwise hallucinate its own verdict.

2. **Absence is a first-class signal, and this is where RAG breaks.** Retrieve `Cindrel Motive Office` from a fabricated cluster and you get nothing back. To a RAG pipeline "retrieved nothing" is a null, so the LLM falls back to its parametric prior and guesses — the checker starts hallucinating. GraphJudge instead reads the *shape* of the miss: a WCC component with zero trusted anchors is a fabricated cluster (orange). The topology of the absence is the evidence.

3. **Deterministic, reproducible, auditable.** The same input yields the same verdict every time, because the reference graph is a fixed, inspectable source of truth rather than model weights. Each verdict carries a graph path that *is* the computation, not a post-hoc citation an LLM might contradict. The core judgment path runs on Cypher + GDS + arithmetic, so there is no per-claim LLM token cost or latency on the decision.

4. **We sit on top of any generator, including a Graph RAG one.** GraphJudge is not a competitor to RAG; it is the quality gate a RAG system should pass its own output through before showing a user. The more you trust a generator, the more you need a judge that does not itself rely on an LLM.

One-line framing: **Graph RAG uses the graph to help an LLM generate; GraphJudge uses the graph to judge what an LLM generated — and the judgment is made by graph topology, not by a model.**

## HackwithBay 3.0 Requirement Fit

| Requirement | How GraphJudge Uses It |
|---|---|
| Butterbase backend | Butterbase hosts auth, credit ledger tables, result/job persistence, serverless credit functions, and the deployed frontend at `graphjudge.butterbase.dev`. |
| Butterbase auth | Users sign in through Butterbase auth. The frontend forwards the end-user JWT to the verification endpoint. |
| Butterbase database | `credits_ledger`, `jobs`, and `results` store credit activity, job status, and verdict JSON. |
| Butterbase payment / metering | Every verification is credit-gated through `consume_credit`; `get_balance` powers the balance UI. This is the implemented pay-per-verification loop. External Stripe rails were intentionally omitted for hackathon scope. |
| Neo4j graph | The reference facts are modeled as `(:Entity)-[:FACT {rel, functional}]->(:Entity)` property graph data, not flat rows. |
| Neo4j active querying | Scoring resolves entities, checks functional contradictions, reads facts, and computes graph structure through Cypher and Neo4j GDS. |
| Neo4j GDS | WCC-style component analysis identifies orphan claims and fabricated clusters. |
| RocketRide workflow | `pipeline/graphjudge.pipe` defines the verification pipeline: webhook, credit gate, claim extraction, scoring, persistence, and response. |
| RocketRide Cloud note | The official problem statement asks for RocketRide Cloud. This repo records an official same-day RocketRide Cloud outage waiver in `docs/decisions.md`, so the shipped demo uses the self-hosted/runtime path documented there. Do not claim a Cloud deployment unless one is actually added later. |
| Daytona bonus | Not used. |
| Cognee bonus | Not used. |

## Architecture

```text
Browser SPA
  -> Butterbase auth and get_balance
  -> POST /verify with user JWT
  -> credit gate via Butterbase consume_credit
  -> extract claims from prose
  -> score claims against Neo4j + GDS
  -> persist jobs/results in Butterbase
  -> return verdict JSON
  -> render fact constellation
```

Important services and files:

- Frontend: `web/`, Vite + React + `react-force-graph-2d`.
- Product endpoint: `POST {PIPELINE_WEBHOOK_URL}/verify`, currently mounted by `scorer/verify.py`.
- Scorer endpoint: `POST {SCORER_URL}/score`, implemented by `scorer/app.py`.
- Neo4j loader: `infra/load_ref.py` and `infra/load_ref.cypher`.
- Pipeline definition: `pipeline/graphjudge.pipe`.
- Frozen contracts: `docs/contracts.md`.
- Demo script: `docs/DEMO.md`.
- Evaluation scoreboard: `eval/scoreboard_results.md`.

## Live Demo

Open:

```text
https://graphjudge.butterbase.dev
```

Use the existing demo accounts. Do not create a new account during the judged demo, because new accounts start with zero credits.

| Email | Password | Purpose |
|---|---|---|
| `demo-999@graphjudge.demo` | `GraphJudge!2026` | Main demo account with credits. |
| `demo-empty@graphjudge.demo` | `GraphJudge!2026` | Zero-credit account for the insufficient-balance path. |

After signing in with `demo-999`, paste a sample input and click **Verify**. Each verification consumes one credit. Click nodes in the constellation to inspect evidence.

To demo the payment/credit gate, sign in with `demo-empty`, paste any sample, and click **Verify**. The response should be `insufficient credits`, and no constellation should be rendered.

## Demo Sample Inputs

### 1. Full Mixed Demo

Expected result: 3 green, 2 red, 1 gray, 6 orange, with `doc_score` around `0.58`.

```text
Corwin Mavik manages Jessa Minlow. Arlen Veyro owns a pet named Bramble. Gavo Rellin lives in Dovemarsh. Della Quorin was born in 1992. Brisa Nalore is married to Corwin Mavik. Mira Vell works at Aster Quay Group. Zavren Pell works at Cindrel Motive Office. Ostia Kel works at Cindrel Motive Office. Zavren Pell manages Ostia Kel. Ostia Kel leads Project Sablewick. Noll Varen leads Project Sablewick. Noll Varen manages Zavren Pell.
```

What to point out:

- Supported facts: Corwin manages Jessa, Arlen owns Bramble, Gavo lives in Dovemarsh.
- Contradictions: Della was born in 1992, Brisa is married to Corwin.
- Singleton ungrounded claim: Mira Vell at Aster Quay Group.
- Fabricated cluster: Zavren, Ostia, Noll, Cindrel Motive Office, and Project Sablewick.

### 2. Mostly Supported Smoke Test

Expected result: mostly green.

```text
Corwin Mavik manages Jessa Minlow. Arlen Veyro owns a pet named Bramble. Gavo Rellin lives in Dovemarsh.
```

Use this when you want a fast proof that the reference graph is loaded and direct fact matching works.

### 3. Contradiction-Only Demo

Expected result: red contradiction verdicts with truth evidence in the side panel.

```text
Della Quorin was born in 1992. Brisa Nalore is married to Corwin Mavik.
```

Use this to show functional relationship checking: birth year and spouse facts have one trusted value, so a different value is a contradiction.

### 4. Ungrounded Singleton Demo

Expected result: gray ungrounded claim.

```text
Mira Vell works at Aster Quay Group.
```

Use this to explain that `UNGROUNDED` does not mean false. It means the trusted graph cannot support the claim.

### 5. Fabricated Cluster Demo

Expected result: orange ungrounded cluster.

```text
Zavren Pell works at Cindrel Motive Office. Ostia Kel works at Cindrel Motive Office. Zavren Pell manages Ostia Kel. Ostia Kel leads Project Sablewick. Noll Varen leads Project Sablewick. Noll Varen manages Zavren Pell.
```

Use this to show GraphJudge's main graph-specific behavior: the claims are internally coherent but disconnected from the trusted core.

### 6. Credit Gate Demo

Use any sample input while signed in as:

```text
demo-empty@graphjudge.demo
```

Expected result: `insufficient credits`. This proves verification is gated server-side and cannot be bypassed by the frontend.

## Local Setup

The repo is configured for the hackathon RunPod environment, but the commands below describe the moving parts clearly enough to reproduce locally.

### 1. Python Environment

Use the repo venv when it exists:

```bash
.venv/bin/python --version
```

If starting fresh:

```bash
python -m venv .venv
.venv/bin/pip install fastapi uvicorn neo4j pandas requests python-dotenv anthropic openai jsonschema
```

### 2. Node Frontend

```bash
cd web
npm install
npm run dev
```

Build production assets:

```bash
cd web
npm run build
```

### 3. Environment Variables

Create a local `.env`. Do not commit it.

```text
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<neo4j-password>
SCORER_URL=http://127.0.0.1:8888
PIPELINE_WEBHOOK_URL=http://127.0.0.1:8888/verify
BUTTERBASE_URL=<butterbase-api-base>
BUTTERBASE_API_KEY=<server-side-bb_sk-key>
CONSUME_CREDIT_URL=<butterbase-consume-credit-function-url>
PERSIST_RESULT_URL=<butterbase-persist-result-function-url>
OPENROUTER_API_KEY=<optional-llm-extraction-key>
EXTRACT_PROMPT_PATH=pipeline/prompts/extract_claims_personal.md
SCORER_REFERENCE_BACKEND=neo4j
PIPELINE_USE_ROCKETRIDE=0
```

Browser code must never receive `BUTTERBASE_API_KEY` or any `bb_sk_` secret.

### 4. Neo4j + GDS

GraphJudge expects Neo4j 5.x with the Graph Data Science plugin available. In the hackathon environment, Neo4j runs on the same RunPod host as the scorer, and Bolt is kept private on `localhost:7687`.

Verify Neo4j and GDS:

```bash
/workspace/neo4j/neo4jctl.sh status
/workspace/neo4j/neo4jctl.sh shell "RETURN gds.version()"
```

Load the personal-domain demo graph:

```bash
cp data/personal/ref_entities.csv /workspace/neo4j/import/ref_entities.csv
cp data/personal/ref_facts.csv /workspace/neo4j/import/ref_facts.csv
.venv/bin/python infra/load_ref.py
```

To load the AI-domain benchmark graph instead:

```bash
cp data/import/ref_entities.csv /workspace/neo4j/import/ref_entities.csv
cp data/import/ref_facts.csv /workspace/neo4j/import/ref_facts.csv
.venv/bin/python infra/load_ref.py
```

Note: `infra/load_ref.py` currently prints the original AI-domain expected counts. The live demo uses the personal-domain graph described in `docs/DEMO.md`.

### 5. Run the Scorer and Product Endpoint

```bash
.venv/bin/uvicorn scorer.app:app --host 0.0.0.0 --port 8888
```

Health checks:

```bash
curl http://127.0.0.1:8888/health
curl http://127.0.0.1:8888/verify/healthz
```

Score claims directly:

```bash
curl -s http://127.0.0.1:8888/score \
  -H 'Content-Type: application/json' \
  -d '{"job_id":"550e8400-e29b-41d4-a716-446655440000","claims":[{"cid":"c1","kind":"relational","text":"Corwin Mavik manages Jessa Minlow.","subject":"Corwin Mavik","rel":"manages","object":"Jessa Minlow"}]}'
```

Run the product path:

```bash
curl -s http://127.0.0.1:8888/verify \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"u_demo","text":"Corwin Mavik manages Jessa Minlow. Arlen Veyro owns a pet named Bramble."}'
```

When `CONSUME_CREDIT_URL` is unset, the credit gate uses an offline stub. In production/demo mode, `/verify` should forward the Butterbase user JWT and call the real `consume_credit` function.

## API Contracts

The source of truth is `docs/contracts.md`.

### Product API

```text
POST {PIPELINE_WEBHOOK_URL}/verify
```

Body:

```json
{
  "user_id": "user-id",
  "job_id": "optional-uuid4",
  "text": "Prose to verify."
}
```

Successful response: verdict JSON with `job_id`, `doc_score`, per-claim verdicts, and a render-ready `graph`.

Insufficient credits:

```json
{
  "error": "insufficient_credits",
  "balance": 0
}
```

### Scorer API

```text
POST {SCORER_URL}/score
```

Body:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "claims": [
    {
      "cid": "c1",
      "kind": "relational",
      "text": "Corwin Mavik manages Jessa Minlow.",
      "subject": "Corwin Mavik",
      "rel": "manages",
      "object": "Jessa Minlow"
    }
  ]
}
```

Response: the same verdict JSON shape consumed by the frontend.

## Evaluation

Validate generated data:

```bash
.venv/bin/python data/validate.py
.venv/bin/python data/personal/validate.py
```

Run the graph judge benchmark:

```bash
.venv/bin/python eval/benchmark_runner.py --scorer-url http://127.0.0.1:8888
```

Run the personal-domain benchmark:

```bash
.venv/bin/python eval/personal_benchmark_runner.py --scorer-url http://127.0.0.1:8888
```

The recorded scoreboard is in `eval/scoreboard_results.md`. At the time of the hackathon run, GraphJudge matched the LLM judge on planted-false detection and beat it on exact three-way labeling:

```text
graph-judge: 100.0% planted-false detection, 100.0% 3-way accuracy
LLM judge:   100.0% planted-false detection, 98.4% 3-way accuracy
```

## RocketRide Notes

`pipeline/graphjudge.pipe` is the portable workflow definition for the verification path:

```text
webhook -> credit_gate -> extract_claims -> score -> persist -> respond
```

The hackathon problem statement originally required RocketRide Cloud. The project records an official Cloud outage waiver in `docs/decisions.md`, so the implemented path uses the self-hosted/runtime route and the `/verify` FastAPI mount. If RocketRide Cloud is restored and a Cloud endpoint is added later, update this README with the actual deployed URL and remove the waiver wording only after verifying the Cloud endpoint.

## Submission Checklist

For HackwithBay 3.0 submission, include:

- Working demo: `https://graphjudge.butterbase.dev`.
- Source code repository.
- Project description: GraphJudge is a graph-as-judge factuality evaluation service.
- Graph model: Neo4j `Entity` nodes and `FACT` relationships with functional relationship metadata.
- Butterbase integration: auth, credit ledger, job/result storage, and serverless credit functions.
- RocketRide integration: `graphjudge.pipe` workflow plus documented outage waiver/self-hosted runtime path.
- Optional bonus note: Daytona and Cognee were not used.

Final submission phrase from the hackathon instructions:

```text
Submit my project to the hackathon. Submission code: ENJOY0707 Hackathon slug: HackwithBay-0707
```

## Internal Docs

Start here when developing:

- `docs/README.md`: internal docs navigation.
- `docs/DESIGN.md`: system design and product rationale.
- `docs/contracts.md`: frozen JSON/API contracts.
- `docs/DEMO.md`: judge demo script.
- `docs/OPS.md`: parallel development process.
- `docs/decisions.md`: architecture decisions and waivers.
