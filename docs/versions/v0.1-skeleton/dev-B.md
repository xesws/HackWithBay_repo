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
