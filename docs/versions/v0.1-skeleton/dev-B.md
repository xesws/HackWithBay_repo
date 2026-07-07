# dev-B（Track B · pipeline）· v0.1-skeleton

> 属地: `/pipeline`。每张任务卡完成即在此追加条目，必须含验证命令与实际输出，未验证不算完成。

<!-- 追加条目格式（OPS §5）:
## [HH:MM] B1 <标题> — done|blocked
做了: ...
验证: <命令> -> <实际输出摘要>
遗留/坑: ...
下一步: B2
-->

> 环境备注（ops 预置）: pod 已装 `rocketride` 1.3.0 + `rocketride-mcp` 1.3.0（venv `.venv`）。
> Cloud 豁免见 `decisions.md #0`。对外接线 Shape 1(8080)/Shape 2(scorer /verify) 二选一见 STETUP §4。

## [19:58] B2 extract_claims prompt + schema + harness + fixture — done (live 度量 DEFERRED)
分支: `track-b-pipeline`（自 main 起）。属地仅 `/pipeline`。

做了:
- `pipeline/prompts/extract_claims.md`: 逐字列出 §4.1 的 `rel` 词表(8)与 `attr` 词表(3);
  kind 选择规则(attr 词 → attribute+attr/value, 否则 relational+rel/object); 一断言一原子 claim;
  cid c1..cN 编号; JSON-only 输出; 用 `sentence_for()` 逆向做 surface→triple 映射表。
- `pipeline/schemas/claims.schema.json`: §4.1 的 JSON Schema (draft-07)。job_id + claims[];
  claim 用 `oneOf` 两分支(relational: rel enum+object / attribute: attr enum+value), 各分支
  `additionalProperties:false` 保证互斥。
- `pipeline/extract_claims.py`: harness。读 `data/bench/docs/{doc}.txt` → `call_model(text)->str`
  SEAM → 解析 → 校验 schema → 对 `bench_ledger.csv` 该 doc 的行做对齐打分。
  **SEAM**: `call_model` 默认=离线正则逆函数(无需 key, 确定性), `call_model_llm` 为真 LLM 占位
  (读 `GATEWAY_API_KEY`, 未接线)。released_in≡release_year 在打分时归一(同一事实, 表面歧义)。
- `pipeline/fixtures/claims_A.json`: 手写的 doc A 正确 §4.1 抽取(源自 ledger A001–A010, cid c1..c10),
  离线可测。

验证(实际命令 + 实际输出):
- `.venv/bin/python -c "import json,jsonschema; jsonschema.validate(json.load(open('pipeline/fixtures/claims_A.json')), json.load(open('pipeline/schemas/claims.schema.json'))); print('claims schema: OK')"`
  → `claims schema: OK`
- `.venv/bin/python -m pipeline.extract_claims --doc all` →
  ```
  doc A: schema OK | aligned 10/10 (extracted 10, missed=[])
  doc B: schema OK | aligned 27/27 (extracted 27, missed=[])
  doc C: schema OK | aligned 10/10 (extracted 10, missed=[])
  doc D: schema OK | aligned 6/6 (extracted 6, missed=[])
  doc E: schema OK | aligned 10/10 (extracted 10, missed=[])
  overall aligned=63/63 model=offline
  ```
  (离线正则=exact 逆函数, 必然满分; 它证明 schema+打分链路对, **不是**真模型能力度量。)
- fixture_A 对 ledger A-rows 对齐: `{'matched': 10, 'total': 10, 'missed_cids': [], 'extracted_count': 10}`。

**NEEDS-HUMAN (B2 验收 "10 断言 ≥8 正确" 的真度量 = DEFERRED)**:
无 LLM key(离线, 无 GATEWAY_API_KEY)。有可用/已充值网关后, 在 `call_model_llm` 里接入网关客户端
(读 `pipeline/prompts/extract_claims.md` 作 system, doc 文本作 user, 用 `GATEWAY_API_KEY` 鉴权,
返回模型原始文本=§4.1 JSON), 然后跑:
```
GATEWAY_API_KEY=... .venv/bin/python -m pipeline.extract_claims --doc all --model llm
```
每篇 aligned/total ≥ 8/10 即通过 B2 验收(schema 已在管线内强制)。

坑/说明: "was released in <year>" 表面在 relational `released_in` 与 attribute `release_year` 之间
歧义(sentence_for 两者同模板)。prompt 默认取 relational `released_in`; 打分对两者归一, 故任一都算对。
下一步: B3。

## [19:58] B3 stub 全链路 webhook → extract → mock scorer → §4.2 — done (离线)
做了:
- `pipeline/mock_scorer.py`: `mock_score_claims(job_id, claims)->§4.2`。CLAIMS 驱动(无 oracle,
  无 ledger); 启发式全部 SUPPORTED/green; 复用 benchmark_runner 的 dedupe+claim/entity 节点+
  SUBJ/rel 边装配形状(但判定是固定启发式, **非** `mock_score()` 那个需要标签的 oracle)。
  attribute claim 生成 `attr:...` 值节点。
- `pipeline/webhook.py`: FastAPI `POST /` 收 §4.4 body `{user_id,job_id,text}` →
  `credit_gate` stub → 离线抽取(§4.1, 校验) → `score` → 透传 §4.2。余额不足 →
  `{"error":"insufficient_credits","balance":0}`。
  **两个 SEAM**: `SCORER_URL` 环境变量置位 → `POST {SCORER_URL}/score` (真 A3); `credit_gate()`
  → 真 `consume_credit` (C2)。stub 破产用户: `u_nocredit`/`u_broke`。
- `pipeline/schemas/verdict.schema.json`: §4.2 的 JSON Schema, 断言 webhook 响应形状。

验证(实际命令 + 实际输出):
- 起服务: `.venv/bin/uvicorn pipeline.webhook:app --host 127.0.0.1 --port 8080` → `/healthz` = `{"ok":true,"scorer":"mock"}`。
- 正常路径 `POST /` body `{"user_id":"u_alice","job_id":"j_001","text":"Claude Sonnet 4 was developed by Anthropic. GPT-4o was released in 2026. Llama 3.1 405B has 810 billion parameters."}`
  → 返回 §4.2: `job_id=j_001 doc_score=1.0 n_claims=3 n_nodes=9 n_edges=6`。
  对 `verdict.schema.json` 校验 → `verdict schema: OK`;
  形状断言(top-level job_id/doc_score; claims[status,cluster_flag,grounding_ratio,dist_to_core,evidence];
  graph.nodes[id,label,kind,color]; graph.edges[src,dst,rel,status]) → OK。
- 零余额路径 `POST /` body `{"user_id":"u_nocredit","job_id":"j_002","text":"..."}`
  → `{"error":"insufficient_credits","balance":0}` (精确匹配 §4.4)。
- mock_scorer 对 doc B(relational+attribute 混合)输出经 `verdict.schema.json` 校验通过。

坑/说明: 未接 Track A scorer / Track C credit(SEAM 已就位, 离线用 stub)。POD 全程未碰。
下一步(非本轮): B1 (.pipe 上 pod) 与 B3-real(接真 SCORER_URL)。

## [Phase-2 PRE-WRITE] B1 .pipe + B2-verify /verify (Shape 2) + B3-real — done (设计+代码, 未上 pod)
分支: `track-b-phase2`(自 main 起, worktree `wt-b`)。属地 `/pipeline` + 新增 `scorer/verify.py`(territory 豁免:
自包含 APIRouter, 不改 `scorer/app.py`)。POD/部署全程未碰。

做了(4 件套):
- `pipeline/graphjudge.pipe`: RocketRide PipelineConfig(`{"pipeline":{...}}` wrapper, `use()` 自动 unwrap)。
  6 组件 `webhook_in`(源) → `credit_gate`(python) → `extract_claims`(python) → `score`(python) →
  `persist`(python) → `respond`(response)。lanes: credit_gate `ok`/`denied`(不足短路到 respond)。
  config 内标注每步的 `entry`(module:callable)、`args`(`$.field` 取字段)、`env`、LLM/HTTP seam。
- `scorer/verify.py`: `POST /verify`(§4.4)。解析 body → 缺 job_id 则 `uuid4()`(v1.1) → `consume_credit`
  (不足→`{"error":"insufficient_credits","balance":0}`) → 跑管线 → `persist_result`(best-effort) → 透传 §4.2。
  **主路径** `_run_via_rocketride`(SDK, `PIPELINE_USE_ROCKETRIDE=1` 才启, `use(filepath=.pipe)`+`send`);
  **文档化 direct fallback** `_run_direct`(复用 Track A 真 `scorer.scoring.score_job` over CSV 参考图, **非 mock**),
  任何 SDK 失败/未启用即用它 → /verify 永远返回合法 §4.2。`get_reference` 延迟 import 破除 app↔verify 循环。
  模块 docstring 内含精确 include 两行。
- `pipeline/credits.py`(新, 单一真相源): `consume_credit(user_id,job_id)` + `persist_result(job_id,user_id,verdict)`。
  env-gated: `CONSUME_CREDIT_URL`/`PERSIST_RESULT_URL` 置位→真 Butterbase HTTP(bb_sk_ 双 header, 不记日志);
  未置位→离线 stub/no-op。webhook.py 与 verify.py 共用。
- `pipeline/webhook.py`(B3-real): credit_gate seam → `pipeline.credits.consume_credit`(真/离线自动降级);
  scorer seam 仍 `POST {SCORER_URL}/score`(真)否则 mock。healthz 增 `credit_backend`。
- `pipeline/PHASE2_CHECKLIST.md`: pod 放锁后 (a)-(f) 有序步骤(改 app.py 两行 / .env / 重启 8888 /
  curl /verify 断言 §4.2 / SPA 指向 /verify 重建 / consume_credit+persist 接线)。
- **LLM provider = OpenRouter(人类裁决, 覆盖 §4.7 GATEWAY_API_KEY)**: 新增 `pipeline/llm.py`
  `openrouter_chat(messages, model="z-ai/glm-5.2")`(base `https://openrouter.ai/api/v1`, OpenAI-compatible,
  优先 `openai` client 否则 urllib, 读 `OPENROUTER_API_KEY`)。`extract_claims.call_model_llm` 改走它
  (prompt 作 system, doc 作 user); 新增 `default_model()` = key 置位→LLM 否则离线 regex;
  `extract_claims(model=None)` 自动选择; CLI 加 `--model auto`。`.pipe` extract 步 env 改 `OPENROUTER_API_KEY`
  (model=auto)。**丢弃全部 anthropic/openai 直连路径**。key 仍可空(NEEDS-HUMAN), 无 key 时离线 regex 兜底。

验证(实际命令 + 实际输出, 全部离线, 用绝对路径 venv):
- `py_compile scorer/verify.py pipeline/webhook.py pipeline/credits.py` → OK。
- `.pipe` `json.load`: OK; source=`webhook_in`∈ids; 6 组件; 所有 `input.from` 边可解析; PipelineConfig 必需字段齐。
- `claims_A.json` vs `claims.schema.json` → OK。
- `POST /verify`(TestClient, 无 job_id, body=Claude→Google/GPT-4→MMLU/Llama3→8B):
  HTTP 200 | 过 `verdict.schema.json` | job_id 为真 uuid4 | doc_score=**0.6667** |
  statuses=`[(c1,CONTRADICTED),(c2,SUPPORTED),(c3,SUPPORTED)]`(Claude developed_by Google 正确判 CONTRADICTED,
  = Track A 真打分, 非 mock) | nodes=8 edges=6。
- `POST /verify` u_nocredit → `{"error":"insufficient_credits","balance":0}`(精确匹配 §4.4)。
- `/verify/healthz` → `{ok:true, pipe:'graphjudge.pipe', rocketride:false, credit_backend:'stub', persist_backend:'noop'}`。
- webhook(B3-real)离线: `/healthz`=`{ok, scorer:'mock', credit_backend:'stub'}`; happy HTTP 200;
  u_broke → `{"error":"insufficient_credits","balance":0}`。

不确定/需集成时定案(见 CHECKLIST §d.1/§f):
- `.pipe` 自定义 Python 步的 `provider` 串(暂猜 `"python"`)与 `respond` 的 PIPELINE_RESULT lane 形状——
  按 live runtime `client.get_services()` 核对; `_extract_verdict` 已写成形状容错, 且 direct 路径不依赖二者。
- `consume_credit`/`persist_result` 的 Butterbase fn URL 与 service auth header 具体拼写(bb_sk_ 双 header 待收敛);
  `backend/functions/` 目前无 persist fn —— Track C 补 `persist_result` fn 或 orchestrator 用 insert_row, 见 §f。
- rocketride Cloud 豁免 receipt(decisions #0)待人工粘贴。
下一步(pod 放锁后): 按 PHASE2_CHECKLIST 执行 (a)-(f)。
