# Phase-2 pod execution checklist (Track B, Shape 2 `/verify`)

Ordered steps to run **after Track A releases the scorer lock**. Design + code are
already committed on `track-b-phase2`; this is execution/debug only. No step here
was run against the pod during pre-write.

Absolute venv python: `/workspace/HackWithBay/HackWithBay_repo/.venv/bin/python`
`SCORER_URL = https://ohld8gp5nmkcu7-8888.proxy.runpod.net`
`PIPELINE_WEBHOOK_URL = {SCORER_URL}/verify`

---

## (a) Mount the router on the scorer app  — edit `scorer/app.py` (2 lines)

Add near the other imports, then after `app = FastAPI(...)`:

```python
from scorer.verify import router      # Track B, Shape 2
app.include_router(router)
```

This is the ONLY edit to `scorer/app.py`. Everything else in `/verify` is
self-contained in `scorer/verify.py` (+ `pipeline/`). The import is cycle-safe:
`verify.py` imports `scorer.app.get_reference` **lazily inside functions**, so the
top-level `from scorer.verify import router` completes before the cycle closes.

Sanity after editing:
```
cd /workspace/HackWithBay/HackWithBay_repo
.venv/bin/python -c "import scorer.app as a; print([r.path for r in a.app.routes if 'verify' in r.path])"
# expect: ['/verify', '/verify/healthz']
```

## (b) Env — append to `.env` (values only; never commit)

```
PIPELINE_WEBHOOK_URL=https://ohld8gp5nmkcu7-8888.proxy.runpod.net/verify
# credit + persist backends (Track C fn URLs — see §f). Leave UNSET to run the
# offline stub/no-op degrade; SET to go live:
# CONSUME_CREDIT_URL=<butterbase consume_credit fn URL>
# PERSIST_RESULT_URL=<butterbase persist_result fn URL>
# BUTTERBASE_API_KEY=bb_sk_...            # service secret, server-side only
# PIPELINE_USE_ROCKETRIDE=1               # opt into the SDK path (§d); omit = direct path
# OPENROUTER_API_KEY=sk-or-...            # LLM extraction upgrade (z-ai/glm-5.2 via
#                                         # OpenRouter). UNSET -> offline regex extractor
#                                         # (default; pipeline works with no LLM key).
```
`SCORER_URL`, `BUTTERBASE_URL`, `BUTTERBASE_API_KEY` already exist (contracts §4.7).
The scorer/verify direct path needs NONE of these to return a real §4.2 verdict.

## (c) Restart the scorer on 0.0.0.0:8888 (single public port)

```
cd /workspace/HackWithBay/HackWithBay_repo
# stop the current uvicorn, then:
.venv/bin/uvicorn scorer.app:app --host 0.0.0.0 --port 8888
# liveness:
curl -s http://127.0.0.1:8888/health              # Track A scorer stats
curl -s http://127.0.0.1:8888/verify/healthz       # Track B: {ok, pipe, rocketride, credit_backend, persist_backend}
```

## (d) Curl `/verify` end-to-end + assert §4.2

Use a REAL user_id that has credits in Butterbase (mint/top-up via Track C if
needed). `job_id` is optional — omit it to exercise the uuid4 minting.

```
curl -s -X POST http://127.0.0.1:8888/verify \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"<REAL_UUID_USER>","text":"Claude Sonnet 4 was developed by Google. GPT-4 was evaluated on MMLU. Llama 3 8B has 8 billion parameters."}' | tee /tmp/verify_out.json

# assert §4.2 shape + that scoring actually ran (not all-green):
.venv/bin/python - <<'PY'
import json, jsonschema, pathlib
v = json.load(open('/tmp/verify_out.json'))
schema = json.load(open('pipeline/schemas/verdict.schema.json'))
jsonschema.validate(v, schema)
assert v['job_id'] and 0.0 <= v['doc_score'] <= 1.0
assert v['graph']['nodes'] and 'CONTRADICTED' in {c['status'] for c in v['claims']}
print('verify §4.2 OK', v['job_id'], v['doc_score'], [(c['cid'],c['status']) for c in v['claims']])
PY
```
Expect `Claude developed_by Google` -> **CONTRADICTED** (real Track-A scoring).
Then the zero-credit path (a broke/real-zero user):
```
curl -s -X POST http://127.0.0.1:8888/verify -H 'Content-Type: application/json' \
  -d '{"user_id":"u_nocredit","text":"..."}'
# expect exactly: {"error":"insufficient_credits","balance":0}
```

### (d.1) OPTIONAL — enable the rocketride SDK path
Only if you want the pipe to run through the RocketRide runtime (else the direct
path is authoritative and already correct):
1. `pip install` is already done (`rocketride` 1.3.0 in venv). Start the self-hosted
   runtime per RocketRide docs (Cloud waived, decisions #0).
2. Set `pipeline/graphjudge.pipe` -> `project_id` to the real project GUID.
3. `PIPELINE_USE_ROCKETRIDE=1` in `.env`, restart, re-run the §d curl.
4. If the verdict comes back malformed, `_extract_verdict` returns None and the
   route auto-falls-back to the direct path — check logs for "rocketride path
   failed". Confirm the `PIPELINE_RESULT` lane shape from `respond` and, if
   needed, widen `_extract_verdict` in `scorer/verify.py`.
   **UNCERTAIN (pre-write):** the exact `provider` string for the custom Python
   steps in `.pipe` (guessed `"python"`) and the `respond` result lane shape.
   Confirm against `await client.get_services()` on the live runtime; the direct
   path does not depend on either.

## (e) Point the SPA submit at `/verify` + rebuild/redeploy

- In `web/` set the submit target to `PIPELINE_WEBHOOK_URL` (= `{SCORER_URL}/verify`).
  The SPA sends `{user_id, text}` (omit job_id — the route mints uuid4) and renders
  the returned §4.2 verdict directly (contracts §4.5: SPA never touches the DB;
  submit is synchronous). Balance display still uses Track C `get_balance`.
- Rebuild + redeploy the SPA (Butterbase frontend deployment, per Track C).
- Smoke: submit from the browser, confirm the constellation renders green/red/
  orange/gray and the score matches the §d curl.

## (f) consume_credit + persist wiring specifics (fn URLs + service auth)

- **consume_credit** (`backend/functions/consume_credit.ts`, deployed by Track C):
  POST body `{user_id, job_id}` -> `{ok, balance}`. Set `CONSUME_CREDIT_URL` to its
  deployed fn URL. It prefers `ctx.user.id` but accepts `body.user_id` for
  service-role (server-side) calls — which is how `/verify` calls it.
- **persist_result**: there is NO persist fn in `backend/functions/` yet. Options,
  pick one at integration and set `PERSIST_RESULT_URL` accordingly:
  1. Track C adds a `persist_result(job_id, user_id, verdict_json)` fn that upserts
     `jobs` + inserts `results` (live schema: `results.verdict_json jsonb`,
     `results.user_id`), OR
  2. the orchestrator wires persistence via Butterbase `insert_row`/`manage_schema`
     directly. Until either exists, leave `PERSIST_RESULT_URL` unset — persist is a
     logged no-op and the verdict still returns (persistence never gates the
     response).
- **service auth**: Butterbase single secret `bb_sk_` (contracts §4.7), server-side
  only. `pipeline/credits.py` sends it on BOTH `Authorization: Bearer <key>` and
  `x-butterbase-key: <key>`. Confirm which header the deployed fn checks and drop
  the unused one. **Never** expose `bb_sk_` to the browser or commit it.

---

## Post-run
- Append the actual curl outputs (3 metrics/shape + zero-credit + persist rows) to
  `docs/versions/v0.1-skeleton/dev-B.md` under a new `## [HH:MM] B-phase2 ...` entry.
- If contracts drift is discovered, STOP — file a `decisions.md` ADR (budget 1/2
  used); do not edit `docs/contracts.md` unilaterally.
