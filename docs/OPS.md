# GraphJudge 并行开发规范（docs-ops）
### 供多个 coding agent CLI 并行作业 · 配套《GraphJudge-系统设计报告》使用

---

## 0. 使用方式（30 秒）

1. 开赛 repo init 后，把《系统设计报告》拷入 `docs/DESIGN.md`，本文件拷入 `docs/OPS.md`；
2. 把《环境设置 Checklist》拷入 `docs/SETUP.md` 并先执行到全绿——**SETUP §6 绿板是发 kickoff 的硬性前置**（唯一例外：Track D 零基础设施依赖，可先于绿板启动）；随后跑 §2 的脚手架脚本生成 /docs 树；把 §4 全文拷成 `docs/contracts.md`，§6 拷成 `docs/versions/v0.1-skeleton/plan.md`；
3. 给每个 CLI 贴 §7 的 kickoff prompt（替换 track 字母）；
4. 你自己只干四件事：**维护 contracts.md、仲裁 decisions.md、收版写 review.md、跟主办方对接**。

---

## 1. 分工模型：4 tracks × 4 versions

**Tracks（并行维度，每个 agent 一条）**

| Track | 使命 | 代码属地（只许改这里） |
|---|---|---|
| **A · graph-core** | Neo4j+GDS 基建、参考图入库、三层判定 Scorer 服务 | `/infra` `/scorer` |
| **B · pipeline** | RocketRide 抽取与编排、**pod 上自托管 runtime**（Cloud 今日故障，sponsor 官方豁免，receipt 在 decisions.md）、webhook 入口 | `/pipeline` |
| **C · product** | Butterbase（auth / 表 / credit+balance fn）+ payment 闭环（**充值 rail 待 R1 裁决**：Butterbase 原语或 Stripe test-mode，账本无论如何在 Butterbase）+ SPA 星座图 | `/backend` `/web` |
| **D · data-eval** | 参考图 CSV、受控腐蚀 benchmark、跑分器、LLM-judge 基线 | `/data` `/eval` |

只有 3 个 CLI 时：C 最晚启动（它只依赖 contracts，不依赖别人代码），前 2 小时由主 agent 兼任 C1/C2。

**Versions（时间维度，= 集成检查点）**

| Version | 时段 | 出口条件 |
|---|---|---|
| v0.1-skeleton | H0–3.5 | 四 track 验收全绿；D→A 数据交接完成（见 §6） |
| v0.2-pipeline | H3.5–5.5 | 真 pipeline 跑在 pod 的 RocketRide runtime 上且公网可调；credit gate 通；webhook→verdict 端到端 |
| v0.3-product | H5.5–6.5 | 登录→扣费→提交→星座图渲染全闭环 |
| v0.4-eval-ship | H6.5–8 | benchmark X vs Y 落定；彩排；提交 |

Version 边界 = **10 分钟同步仪式**：人类读 4 份 dev 文件 → 跑验收 → 写 `review.md`（通过/遗留/滚入下版）→ 从模板实例化下一版 `plan.md`（任务卡基本照抄 DESIGN.md §6）。tracks 之间平时**不直接对话**，一切经 contracts + 版本同步。

**跨 track 依赖只有 4 条**（全部走冻结契约，无需等人）：
D --(ref CSVs, ~H1.5)--> A；A --(/score API)--> B；B --(webhook API)--> C；C --(consume_credit fn)--> B。
在依赖就绪前，下游一律用 contracts.md 里的 canonical 样例做 mock，**任何人不许空等**。

---

## 2. /docs 目录规范 + 脚手架

```
docs/
  README.md            # 导航 + agent 必读顺序（脚手架自动生成）
  DESIGN.md            # 系统设计报告（只读）
  OPS.md               # 本文件（只读）
  contracts.md         # 冻结接口 v1 —— 修改必须走 decisions.md
  status.md            # 全局看板，每 track 一行，随手更
  decisions.md         # 变更提案与裁决记录（ADR 式，追加不删改）
  versions/
    v0.1-skeleton/
      plan.md          # 版本目标 + 按 track 任务卡 + 验收（版本开始时冻结）
      dev-A.md  dev-B.md  dev-C.md  dev-D.md   # 各 agent 只写自己的
      review.md        # 收版时由人类/主 agent 写
    v0.2-pipeline/ ... # 同构
```

```bash
mkdir -p docs/versions/v0.1-skeleton && cd docs
printf '必读顺序: OPS.md -> contracts.md -> versions/<当前版>/plan.md 中你的 track 段 -> 你的 dev-X.md 末尾\n' > README.md
touch contracts.md status.md decisions.md
cd versions/v0.1-skeleton && touch plan.md review.md dev-A.md dev-B.md dev-C.md dev-D.md
```

**为什么 dev 按 track 拆而不是共用一个 dev.md**：多个 CLI 并发写同一文件必然产生写冲突；拆开后"每个 version 有清晰的 plan 与 dev"依然成立——plan 是版本级的一份，dev 是版本级的四份，review 收拢。

---

## 3. Agent 行为守则（十条，kickoff prompt 会引用）

1. **开工仪式**：读 README 指定的四样，别的不读（省上下文）。
2. **属地纪律**：代码只改自己 track 的目录；docs 只写自己的 `dev-X.md` + `status.md` 自己那一行。
3. **三不碰**：`contracts.md`、`DESIGN.md`/`OPS.md`、别人的 dev 文件。
4. **dev 条目格式**（见 §5 模板）：没有"验证方式+实际输出"的条目不算完成。
5. **契约变更**：发现接口必须改 → 停手，`decisions.md` 写提案，`status.md` 标 blocked，等人类裁决。**不许静默改契约然后通知别人适配。**
6. **升级阈值**：track 内部的歧义自行决断（顺序：contracts > DESIGN.md > 合理猜测并在 dev 里注明）；只有跨 track 冲突/契约问题才升级人类——参考 PiPlan 的路由协议，只升级真正的指令冲突。
7. **卡壳限时**：单任务卡阻塞 >25 分钟 → 记 blocker，切下一张卡。
8. **Mock 优先**：依赖未就绪就按 contracts 样例造 mock 继续推进。
9. **Git**：单 repo 直推 main；commit message 前缀 `[A]/[B]/[C]/[D]`；push 前 `pull --rebase`；小步频提。属地纪律保证了基本不冲突。
10. **秘密**：密钥只进本地 `.env`（变量名见 contracts §4.7），永不进 git / docs / prompt / 对话记录。

---

## 4. contracts.md v1（冻结接口——以下全文拷入 `docs/contracts.md`）

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

## 5. 模板

**plan.md（版本级）**
```
# vX.Y-<name> · 目标一句话
## 出口条件（收版验收，可执行）
- [ ] ...
## Track A 任务卡
- [ ] A1 <动作> ｜验收: <命令 + 预期输出>
- [ ] A2 ...
## Track B / C / D 任务卡（同构）
## 本版已知风险与兜底（引用 DESIGN.md §7 的 R#）
```

**dev-X.md（追加式日志，每卡一条）**
```
## [HH:MM] A1 <标题> — done|blocked
做了: ...
验证: <命令> -> <实际输出摘要>
遗留/坑: ...
下一步: A2
```

**status.md（每 track 一行，随时覆写自己那行）**
```
A | v0.1 | A2 进行中 | 阻塞: 无        | 更新 HH:MM
B | v0.1 | B1 done   | 阻塞: 等场地wifi | 更新 HH:MM
```

**review.md（收版时写）**：通过项 / 未过项及处置（滚入下版|砍掉）/ 契约变更记录 / 下版重点。

---

## 6. v0.1-skeleton 的 plan.md（已写好，直接拷用）

```
# v0.1-skeleton · 目标: 四条腿各自站起来 + 冒烟测试证明判定内核
## 出口条件
- [ ] curl SCORER_URL/score 用冒烟 claims 返回预期三判定
- [ ] RocketRide hello-world .pipe 在 pod 自托管 runtime 上执行成功（cloud 豁免 receipt 已存 decisions.md）
- [ ] Butterbase: 建表完成, consume_credit 扣减可验证
- [ ] ref CSV 200+ 条入库; benchmark 台账+五篇散文落盘

## Track A（/infra /scorer）
- [ ] A1 按 SETUP.md §2 方案 α: pod 上 tarball 装 Neo4j+GDS
      (RunPod pod 内无 docker; bolt 走 localhost, 不暴露公网)
      ｜验收: cypher-shell 跑 CALL gds.version() 有返回
- [ ] A2 手写 5 节点玩具图 + 冒烟三 claim（DESIGN.md 冒烟测试:
      SUPPORTED / CONTRADICTED / UNGROUNDED+WCC 孤立）
      ｜验收: 三条判定全符合预期 —— 这是全项目的定海神针
- [ ] A3 FastAPI /score: 第一层判定 + WCC + 契约 4.2 输出
      ｜验收: curl 冒烟 claims 过
- [ ] A4 等 D 交付后 LOAD CSV 真参考图, 重跑冒烟
      ｜验收: 200+ facts, 抽查 5 条查询正确

## Track B（/pipeline）
- [ ] B1 hello-world .pipe: extension 本地构建 → pod 自托管
      runtime 执行（按 SETUP §4; 对外接线 Shape 1/2 二选一,
      定下后把 PIPELINE_WEBHOOK_URL 写进 status.md 广播）
      ｜验收: 公网 curl 该 URL 执行成功
- [ ] B2 extract_claims prompt: 样例散文 -> 契约 4.1 JSON
      ｜验收: 10 条断言 ≥8 条抽取正确, JSON schema 过校验
- [ ] B3 stub 全链路: webhook -> extract -> mock scorer -> respond
      ｜验收: curl webhook 返回 4.2 形状

## Track C（/backend /web）
- [ ] C1 Butterbase project + 三张表; 服务端查询一律按 user_id
      过滤(单 key 模型, SPA 不直连 DB; RLS 为可选加分)
      ｜验收: insert/select 通, 按 user_id 过滤结果正确
- [ ] C2 consume_credit + get_balance 两个 fn
      ｜验收: 余额 1 -> 扣成 0 -> 再扣被拒; get_balance 读数一致
- [ ] C3 SPA: auth 按 @butterbase/sdk 浏览器侧实际签名接
      (不可行则降级为最简邮箱会话) + 用 contracts 4.2 样例
      JSON 渲染星座图
      ｜验收: 登录态存在; 四色节点出现, 点击弹 evidence

## Track D（/data /eval）
- [ ] D1 附录 A prompt 生成 ref CSVs + 人工扫 + alias 表
      ｜验收: 200+ 条, 抽查 10 条无错 -> 交接给 A（status.md 喊话）
- [ ] D2 附录 B.3 腐蚀脚本 -> bench_ledger.csv
      ｜验收: 台账行数/标签分布符合 B.2 比例
- [ ] D3 附录 B.4+B.5 -> 五篇散文｜验收: 散文断言与台账一一对应, 抽查无新增事实
```

---

## 7. Kickoff prompt（贴给每个 CLI，替换 {X}）

```
你是 GraphJudge 项目的 Track {X} 开发 agent（项目背景: 8 小时
hackathon, 图结构幻觉检测 eval 服务, 详见 docs/DESIGN.md, 按需
查阅勿全文精读）。
开工顺序: 1) docs/README.md  2) docs/contracts.md（接口已冻结,
你无权修改） 3) docs/versions/v0.1-skeleton/plan.md 里 Track {X}
段落  4) docs/versions/v0.1-skeleton/dev-{X}.md 末尾。
铁律: 代码只改你的属地目录; 文档只写 dev-{X}.md 和 status.md
你那一行; 每张任务卡完成即在 dev-{X}.md 追加条目, 必须含验证
命令与实际输出, 未验证不算完成; 依赖未就绪用 contracts 样例
mock, 不许空等; 卡壳超 25 分钟记 blocker 换卡; 要改接口 -> 停手
写 decisions.md 提案并在 status.md 标 blocked, 等人类裁决。
commit 前缀 [{X}], push 前 pull --rebase。
现在从任务卡 {X}1 开始。
```

---

*本规范与 DESIGN.md 冲突时，以 DESIGN.md 的工程判断为准、以本规范的流程为准；两者都覆盖不到的，agent 合理猜测并在 dev 里留痕。*