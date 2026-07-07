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
1. **RocketRide runtime 不在 live 路径**：`/verify` 当前跑**纯 Python**（`_run_direct`），非 `.pipe` 经 runtime 执行。
   证据：`/verify/healthz → rocketride:false`；`PIPELINE_USE_ROCKETRIDE` 未设；代码 gate 默认 off。
   `.pipe` 已写、rocketride SDK 已装、`_run_via_rocketride` 已编码但**从未对活 runtime 验证过**。
   处置选项 → 人类定：(a) 打开并验证真 runtime 路径；(b) 诚实表述“已定义 RocketRide pipeline + 自托管 runtime 可用，直连执行为 active fallback”（decisions #0 已豁免 Cloud）。**建议 (b)**（低风险，不动活 demo）。
2. **credit gate 仍 stub**：`/verify` 的 `consume_credit` 未接线（`credit_backend:stub`）——接线 + demo 号预充中（本轮进行）。
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
