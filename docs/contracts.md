# GraphJudge — contracts v1 (frozen interfaces)

> Copied verbatim from `docs/OPS.md` §4 per OPS §0. This is the frozen interface set.
> Any change requires a `decisions.md` ADR + human ruling, then a version bump in this header.

---

### 4.1 claims JSON（抽取输出 = scorer 输入 = LLM-judge 输入）

```json
{"job_id":"j_001","claims":[
  {"cid":"c1","kind":"relational","text":"Claude was developed by Google.",
   "subject":"Claude","rel":"developed_by","object":"Google"},
  {"cid":"c2","kind":"attribute","text":"GPT-4 was released in 2022.",
   "subject":"GPT-4","attr":"release_year","value":2022}
]}
```
`rel` 只许用词表：`developed_by, released_in, based_on, evaluated_on, sota_on, authored_by, acquired_by, cited_by`；`attr` 只许：`release_year, param_count_b, context_window_k`。

### 4.2 verdict JSON（scorer 输出 = results 表内容 = 前端渲染输入）

```json
{"job_id":"j_001","doc_score":0.72,
 "claims":[{"cid":"c1","status":"CONTRADICTED","cluster_flag":false,
   "grounding_ratio":1.0,"dist_to_core":0,
   "evidence":{"type":"conflict","truth":"Anthropic",
               "path":["Claude","developed_by","Anthropic"]}}],
 "graph":{"nodes":[{"id":"ent:claude","label":"Claude","kind":"entity","color":"green"}],
          "edges":[{"src":"claim:c1","dst":"ent:google","rel":"developed_by","status":"contradicted"}]}}
```
`status ∈ {SUPPORTED, CONTRADICTED, UNGROUNDED}`；`color ∈ {green, red, gray, orange}`。**graph 字段必须是渲染就绪的**——前端不接触 Neo4j。

### 4.3 Scorer HTTP API（Track A 提供）

`POST {SCORER_URL}/score`：body = 4.1，response = 4.2，同步返回，超时 60s。
`POST {SCORER_URL}/admin/load_ref`：重载参考 CSV（仅人类调用）。

### 4.4 Pipeline webhook（Track B 提供，即产品对外 API）

`POST {PIPELINE_WEBHOOK_URL}`：body `{"user_id":"...","job_id":"...","text":"..."}`
response = 4.2 原样透传；credits 不足时返回 `{"error":"insufficient_credits","balance":0}`。

### 4.5 Butterbase（Track C 提供）

表：`credits_ledger(id, user_id, delta int, reason text, created_at)`；`jobs(job_id pk, user_id, status, created_at)`；`results(job_id pk, verdict jsonb, created_at)`；服务端查询一律按 user_id 过滤（RLS 为可选加分）。
函数：`consume_credit(user_id, job_id) -> {"ok":bool,"balance":int}`（单事务：余额>0 则 insert delta=-1 并返回 ok=true）；`get_balance(user_id) -> {"balance":int}`。充值 = insert 正 delta（payment 流触发）。
**单 key 模型推论**：SPA 不直连数据库——提交走 4.4 webhook（同步拿回 verdict），余额走 `get_balance`；per-user 数据隔离由服务端查询按 user_id 过滤保证，RLS 降级为可选加分项。auth 的浏览器侧初始化按 `@butterbase/sdk` README 实际签名为准（Track C 开工前 10 分钟定案）。

### 4.6 CSV 格式（Track D 产出）

`ref_entities.csv`: `id,name,type,aliases,release_year,param_count_b,context_window_k`（aliases 用 `|` 分隔）
`ref_facts.csv`: `src,src_name,src_type,rel,dst,dst_name,dst_type,functional`
`bench_ledger.csv`: `doc,cid,subject,rel,object,label,mutation,original`
（与 DESIGN.md 附录 A/B 一致；改列名 = 契约变更。）

### 4.7 环境变量名（值进本地 .env，不进 git）

`NEO4J_URI  NEO4J_USER  NEO4J_PASSWORD  SCORER_URL  PIPELINE_WEBHOOK_URL  BUTTERBASE_URL  BUTTERBASE_API_KEY  GATEWAY_API_KEY`
（Butterbase 是单 secret key 模型（bb_sk_），**只存在于服务端**：pipeline / serverless fn / scorer。浏览器侧永远拿不到它。）

### 4.8 变更流程

提案（decisions.md：动机/改动/波及 track）→ 人类裁决 → contracts.md 更新并把版本号 +0.1 写在文件头 → status.md 广播一行。全天预算：**契约变更 ≤2 次**。

---

