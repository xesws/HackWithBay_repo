# v0.1-skeleton · review（收版稿 — 待人类签字）

> 主 agent 起草，人类签收。内容: 通过项 / 未过项及处置 / 契约变更 / 下版重点。
> 状态: **READY FOR SIGN-OFF**（截至 e2e LIVE + scoreboard 落地）。

## 一句话结论
四条 track 全部 green，端到端 demo 已上线（paste→/verify→gemini 抽取→真 Neo4j+GDS 打分→星座图渲染），
63-claim 基准 graph-vs-LLM 记分牌已出数。**可收版进 v0.2**；下附 3 项须人类拍板的残留。

## 通过项（已验证，附证据）
| Track | 验收 | 证据 |
|---|---|---|
| **A** /scorer | `POST /score` 返回 §4.2；真 Neo4j 161 实体/332 事实 + GDS wcc；三层判定四色 | `/health` → `tier=gds, entities=161, facts=332, gds_version=2.13.8`；`benchmark_runner --scorer-url http://127.0.0.1:8888` = **63/63** |
| **B** /pipeline | `/verify`(Shape 2) 挂载于 scorer app（单公网口 8888）；OpenRouter 抽取（gemini-3.5-flash，30s 超时 + regex 兜底）；直连 Python 执行路径活线 | 公网 `/verify` 返回正确 SUPPORTED/CONTRADICTED/UNGROUNDED，uuid4 job_id；`/verify/healthz` ok |
| **C** /backend /web | Butterbase 三表活线（credits_ledger/jobs/results）；`consume_credit`+`get_balance` fn 部署并验证；SPA 部署 graphjudge.butterbase.dev，登录→paste→Verify→星座图 | invoke_function 余额序列通过；SPA HTTP 200，新 bundle 已服务 |
| **D** /data /eval | 参考 CSV 161/332；63-claim 基准；benchmark_runner；graph-vs-LLM 记分牌 | `eval/scoreboard_results.md`：planted-false 检测 graph 100% / LLM 100%；3-way 精确 graph **100% vs 98.4%** |

## 记分牌关键结论（诚实标注）
- **检测率打平** 100%↔100%：干净消融下（LLM 拿到同一张结构化参考表），gemini 也能看出 doc-D 造假簇实体缺失 → 检测不占优。
- **graph 真正的护城河**：① 3-way 精确标注 100% vs 98.4%（CF002：LLM 把 fabricated-entity 误判 CONTRADICTED）；② 每条判定带**可审计 graph path 证据**（LLM 只给裸标签）；③ 核心路径无 LLM（Cypher+GDS 算术），确定性 + 成本/延迟优势。
- counterfactual/更难消融实验已按人类指示**取消**。

## 未过项 / 处置（须人类拍板 — 3 项）
1. ~~**RocketRide runtime 不在 live 路径**~~ **✅ 已验证并定案（采用 b）**：flip 测试结论 —
   `_run_via_rocketride` 在隔离测试中 **1.1s 抛 `AuthenticationException: No authorization provided`** →
   verify.py 捕获 → 回退 `_run_direct`。原因:pod 上**没有自托管 RocketRide runtime**(B1 卡在
   Shape 1/2 边界未完成)+ 无 runtime auth。故 `PIPELINE_USE_ROCKETRIDE` 保持 **off**(诚实:healthz
   rocketride:false + 无每次 1s 失败开销)。表述定为 **(b)**:"已定义 RocketRide `.pipe` + 自托管
   runtime 就绪路径,直连 Python 为 active 执行(decisions #0 Cloud 豁免)"。要真跑 runtime = 补 B1。
2. ~~**credit gate 仍 stub**~~ **✅ 已接线（LIVE）**：`/verify` 走真 `consume_credit`（JWT 转发；fn 是 auth:required 拒 service key）；fail-open 保活 demo。demo 号已 e2e 验证：`demo-999`(999→998 扣费) / `demo-empty`(insufficient_credits 拦截)。**遗留决策 → 已裁决关闭**：不做 signup 免费额度 hook;新注册号默认 0 余额(设计如此),演示一律用 `docs/DEMO.md` 提供的 demo 账号。
3. **decisions #0 的 Discord receipt** 仍为 `<粘贴原文>` 占位：sponsor-comms 属人类边界，须你粘贴 Krish Garg 11:42 / Joe Maionchi 11:47 原文。

## 契约变更记录（本版）
- **#1**（v1.1）：`job_id` 全链路 uuid4；§4.5 表对齐 live schema（`ts`/`verdict_json`）；禁止 drop 表。
- **#2**（v1.2）：`rel`/`attr` 开放化（format-only），支持 Eval-2 个人域；scorer 零改动，AI 域回归 63/63 不变。
- 今日契约变更 **2/2**，已达预算上限。

## 下版重点（v0.2）
- **Eval-2 第二张记分牌**（个人域，无污染语料，15:25 前出数）。
- **credit 闭环**：接线 `consume_credit` + demo 号（999 / 0 余额）。
- **RocketRide 表述定案**（见未过项 #1）。
- **pitch/demo 彩排**：以 graph 护城河三点（精确/证据/确定性）为叙事主线。
