# GraphJudge — 系统设计报告
### HackwithBay 3.0 · 2026-07-07 · 项目 #3（事实图谱幻觉检测 / Graph-as-Judge）

项目代号 **GraphJudge**（可随时改名）。Tagline：**"Everyone judges LLMs with LLMs. We judge them with graphs."**

---

## 0. 背景故事

### 0.1 我们做的是个什么项目？

一个**基于图结构的事实性评估服务（factuality evaluation harness）**：

用户（或另一个 AI 系统）把一段 LLM 输出 / 文档提交给 GraphJudge，系统会：
1. 把文本拆解成原子事实声明（atomic claims），写入 Neo4j 事实图谱；
2. 把这些 claim 锚定（anchor）到一张**可信参考图谱**上；
3. 用**图拓扑结构本身**做裁判——连通性、社区结构、矛盾边——标记出幻觉和矛盾；
4. 返回逐条 claim 的判定 + 证据路径，并在前端渲染成一张"事实星座图"：**绿色的 grounded 核心、红色的矛盾边、灰色的孤儿节点、橙色的"编造集群"**——幻觉在视觉上就是那个断开的节点。

产品定位不是"又一个 fact-checker demo"，而是 **eval 基础设施**：graph-as-judge 是 LLM-as-judge 的结构化替代/互补方案，按次计费（pay-per-verification credits）。这同时是你求职 Evals 支柱的 Phase 1 开源项目 v0。

### 0.2 用什么方法？为什么用这个方法？

**方法链**：claim decomposition（LLM 抽取原子三元组）→ entity resolution（对齐到参考图谱实体）→ 图锚定 → 结构化打分（三层判定：SUPPORTED / CONTRADICTED / UNGROUNDED）→ 与 LLM-as-judge 基线做同台对照。

**为什么是图，而不是（只是）LLM-as-judge：**
1. **错误模式正交**。LLM-judge 和被评估的 LLM 共享先验，"流利但错误"的内容容易一起骗过去（GraphCheck ACL 2025、FactCG、KG-Guard 这条研究线的核心动机）。图判定是符号化、结构化的——它不会被"写得像真的"说服。
2. **"连贯编造"是图的独有猎物**。一组互相自洽的假 claim（编一个模型、再编它的 benchmark 成绩和作者）能骗过逐句 NLI 和 LLM-judge，但在图上它就是一个**挂不到 grounded 核心上的孤立社区**——Louvain/WCC 一跑就现形。这是本项目的研究卖点。
3. **可解释性免费送**。证据 = 图上的路径；矛盾 = 一条显式的 CONTRADICTS 边。评委能看见"为什么"。
4. **赛制契合**。WCC、Louvain、shortestPath 都是 GDS 图算法——Neo4j 以最高标准满足"load-bearing、不许当 KV store"的硬性要求。

**关键设计决定：两个裁判共享同一套 claim 抽取**。graph-as-judge 和 LLM-as-judge 收到完全相同的 claims 和完全相同的参考事实（一个以图结构形式、一个以序列化文本形式）——唯一变量是"裁判机制"。这让对照实验干净成立（clean ablation），面试和 blog 里都站得住。

### 0.3 要达到什么样的期待和效果？

**Demo 四拍**（按演示顺序）：
1. **现场粘贴**一段关于 AI 行业的、看起来很像样的 LLM 回答（内含预埋错误）→ 星座图渲染：绿核心 / 红矛盾边 / 灰孤儿 / 橙色编造集群，点击任一 flagged claim 展示证据路径。
2. **记分牌**：在 planted-claims benchmark（约 50 条人工标注 claim）上，graph-as-judge vs LLM-as-judge 的 precision/recall 对比表——**重点讲"连贯编造集群"那一栏：LLM-judge 放行、图抓住**。这是全场其他队不会有的 measurable outcome。
3. **付费闭环**：每次 verification 扣一个 credit，余额不足 → 充值 → 继续。payment 是核心动作的计量单位，不是贴上去的。
4. **（Stretch）Daytona**：代码类 claim（"这段代码返回 X"）丢进沙箱真实执行来判定——顺手接上 RLVR verifier 的叙事。

**赛后沉淀**（求职）：
- 简历句式预埋：*Built GraphJudge, a graph-structural factuality evaluation harness (Neo4j GDS + LLM pipeline on RocketRide Cloud) achieving __X__% detection of planted false claims vs __Y__% for an LLM-as-judge baseline on a 50-claim benchmark.*
- Blog 选题：《Graph-as-Judge：为什么图结构能抓住 LLM-as-judge 漏掉的幻觉》。

### 0.4 约束条件（Constraints）

| 约束 | 内容 | 设计应对 |
|---|---|---|
| 时间 | 8 小时赛制（估），10:15 有 workshop，有效构建约 6.5h；今晚已近午夜，赛前准备 ≤45 分钟 | 所有关键决策在本文档预先拍板；现场只执行 |
| 人力 | 默认 solo | 砍掉一切非关键路径功能（见 §9） |
| 算力 | RunPod 可租 6–8×RTX 4090；**若训练，1–2 小时内** | **关键路径零训练**。实际只需 **1 张卡**（见 §8） |
| Neo4j | ⚠️ **AuraDB Free 不带 GDS**（gds.graph.project 在 free tier 直接报错，2026-02 社区帖实锤；GDS 需 AuraDS/付费 Graph Analytics 或自托管） | **Docker 自托管 Neo4j + GDS 插件**，跑在 RunPod 盒子上，暴露 bolt 端口——绕开全场最大的隐形坑 |
| Butterbase | payment 的具体 API 形态是文档最薄的一块 | 10:15 workshop 第一个问题；Stripe test-mode 兜底（§7 R1） |
| RocketRide | 产品上线仅 3 周，Cloud 部署摩擦未知；Python 节点能否装 neo4j driver 未知 | H1 先部署 hello-world 验证路径；scorer 侧车服务兜底（§7 R2/R3） |
| 模型访问 | Butterbase AI gateway 限流未知 | 备直连 API key + 可选 vLLM 自托管抽取 |
| 数据 | 参考图谱必须 1 小时内可构建、且评委一眼能读懂 | 领域选 AI 行业事实（§2.1），LLM 半自动策划 + 人工抽查 |
| 规则 | pre-existing code 限制未确认 | 今晚只带**设计/schema/prompt**，代码现场写；早上问清 |

---

## 1. 系统架构总览

```
[Browser SPA]  登录 / 提交文本 / 星座图 / credits 余额
    |  (Butterbase JS SDK: auth + 读结果)
    v
[Butterbase]  Auth · Postgres(users, credits_ledger, jobs, results)
              · Payment(充值 credits) · AI Gateway · serverless fn: consume_credit
    |   ^ 结果写回
    v   |
[RocketRide Cloud pipeline]   (webhook source, 部署在 cloud.rocketride.ai)
    step1  credit_gate      -> 调 Butterbase fn, 原子扣减, 余额不足即拒
    step2  extract_claims   -> LLM 经 Butterbase AI gateway, 输出 claims JSON
    step3  score            -> 理想: Python 节点直连 Neo4j; 兜底: HTTP 调 Scorer 侧车
    step4  respond+persist  -> 返回 verdict JSON + 写回 Butterbase
    |                                   \
    v                                    v (仅 code-claim, stretch)
[RunPod 盒子 · 1×4090]                 [Daytona sandbox]
  - Neo4j 5.x Docker + GDS 插件          执行代码类 claim -> PASS/FAIL
    (bolt 7687 经 RunPod TCP 暴露)
  - Scorer 服务 (FastAPI: ER + Cypher + GDS 调用)
  - 可选: vLLM Qwen2.5-7B (抽取兜底)
```

集成深度自检：Butterbase 三项全 load-bearing（auth 门禁、Postgres 账本、payment 即计量单位，外加 AI gateway）；Neo4j 跑真算法；RocketRide 是唯一的业务编排入口且部署在 Cloud。

---

## 2. 数据设计

### 2.1 领域选择：AI 行业事实（models / orgs / papers / benchmarks）

理由：(a) 评委全是 AI 开发者，"GPT-4 是 Google 2022 年发的"这种错误**零解释成本**；(b) 参考数据你自己就能人工校验，1 小时可成；(c) "用图谱给 LLM 关于 LLM 的回答挑错"有自指趣味，pitch 好讲。备选兜底：国家/首都/货币（Wikidata 子集，无聊但数据零风险）。

### 2.2 图 Schema

```
(:Entity {id, name, type, aliases:[..],            // 参考图谱实体(不可变)
          release_year?, param_count_b?, context_window_k?})
(:Entity)-[:FACT {rel, functional:bool}]->(:Entity) // 参考事实边
(:Claim  {job_id, cid, text, rel, value?, status}) // 每次任务的声明
(:Mention {name})                                   // 未解析实体
(:Claim)-[:SUBJ]->(:Entity|:Mention)
(:Claim)-[:OBJ ]->(:Entity|:Mention)
(:Claim)-[:CONTRADICTS {evidence}]->(:Entity)       // 判定后写入(红边)
```

关系词表（先固定 8–10 个，抽取 prompt 里枚举）：`developed_by, released_in, based_on, cited_by, evaluated_on, sota_on, authored_by, acquired_by`；数值属性走 Entity property 对比。`functional=true` 的关系（如 developed_by, released_in）是矛盾检测的钩子。

### 2.3 参考图谱构建（H1–H2，目标 200–300 条三元组）

1. 让 LLM 按固定词表生成候选三元组 CSV（prompt 见附录 A）；
2. 人工快速扫一遍（这是你自己的领域，10 分钟能扫完）；
3. `LOAD CSV` 入库 + 唯一约束 + alias 表（"GPT-4o"↔"Omni"、"Claude"↔"Anthropic Claude"…）。

```cypher
CREATE CONSTRAINT ent_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE;
LOAD CSV WITH HEADERS FROM 'file:///ref_facts.csv' AS r
MATCH (s:Entity {id:r.src}), (o:Entity {id:r.dst})
MERGE (s)-[f:FACT {rel:r.rel}]->(o) SET f.functional = r.functional='true';
```

---

## 3. 核心判定逻辑（Scorer）

### 3.1 三层判定（每条 claim）

```
第一层 · 直接匹配
  relational (s, rel, o):
    SUPPORTED    若参考图存在 (s)-[:FACT{rel}]->(o)
    CONTRADICTED 若 rel.functional 且存在 (s)-[:FACT{rel}]->(o') 且 o'≠o
  attribute (s.attr = v):
    年份精确匹配; 数值 ±5% 容差; 超差 = CONTRADICTED
  其余 -> 进入第二层, 标 UNGROUNDED(候选)

第二层 · 结构评分 (对 UNGROUNDED 集合)
  grounding_ratio = 该 claim 实体解析成功比例
  dist_to_core    = 到最近 grounded 锚点的最短路径长度
  cluster_flag    = Louvain 社区内不含任何 :Entity 锚点  -> "编造集群"

第三层 · 聚合
  doc_score = 1 - (w1·|CONTRADICTED| + w2·|flagged UNGROUNDED|) / N
  每条 claim 附证据: 支持路径 / 矛盾边 / 社区编号
```

诚实框架（写进 pitch）：**UNGROUNDED ≠ FALSE**，它的语义是"参考图谱无法背书、需要引用"——这恰恰是 evals 语境下正确的输出（比二值化的 true/false 更负责）。

### 3.2 GDS 调用（判定的图算法内核）

```cypher
CALL gds.graph.project('job_'+$job,
  ['Entity','Claim','Mention'],
  {SUBJ:{orientation:'UNDIRECTED'}, OBJ:{orientation:'UNDIRECTED'},
   FACT:{orientation:'UNDIRECTED'}});
CALL gds.wcc.stream('job_'+$job)     // 连通分量 -> 孤儿检测
CALL gds.louvain.stream('job_'+$job) // 社区 -> 编造集群检测
// 证据路径:
MATCH p = shortestPath((c_ent)-[:FACT*..3]-(anchor)) RETURN p
// 用完即删投影, 参考图不可变, claim 带 job_id 命名空间
```

兜底：若 Louvain 在小图上不稳定（分辨率问题），退化为"WCC 中不含任何 :Entity 的分量 = 编造集群"——确定性、不会翻车（§7 R6）。

### 3.3 LLM-as-judge 基线（对照组）

同一份 claims + 参考三元组序列化成文本，一条 prompt 让同一个 gateway 模型逐条判 true/false/unverifiable。**信息完全对等，差异只在结构 vs 散文**。如果某些类别上 LLM-judge 赢了——照实报告，这反而是 evals 工程师的可信度（§7 R7）。

---

## 4. 三件套 + Daytona 集成细节

**Butterbase**
- 表：`users`（auth 托管）、`credits_ledger(user_id, delta, reason, ts)`、`jobs(job_id, user_id, status)`、`results(job_id, verdict_json)`；RLS 按 user_id。
- serverless fn `consume_credit(user_id, job_id)`：单事务校验余额并扣减（服务端执行，防前端绕过）。
- payment：注册送 N credits（promo 叙事）+ 充值按钮 → Butterbase payment 原语（workshop 确认形态）；兜底 = Stripe test-mode checkout → webhook → fn 给 ledger 加账——payment 仍是"active use"。
- AI gateway：extract_claims 与 LLM-judge 都走它（加深集成 + 统一计量）。

**RocketRide Cloud**
- H1 先部署一条 hello-world pipeline 验证"本地构建 → 一键上 Cloud"全路径；真 pipeline H5 重新部署。
- 理想态 step3 用 Python 节点直连 Neo4j；若依赖装不上 → pipeline 保持编排位，HTTP 调 RunPod 上的 Scorer FastAPI（合规性不受影响：Cloud 上跑的是业务工作流本体）。

**Daytona（stretch，默认第一个砍）**
- claim.type == 'code' → 沙箱执行 → 执行结果覆盖判定。价值：demo 里一句话点出"scorer 和 RLVR verifiable reward 是同一块肌肉"。

---

## 5. 对照实验（Benchmark）设计 —— 你的 measurable outcome

5 篇文档 × ~10 claims ≈ 50 条。标签由受控腐蚀自动产生（构建方法、腐蚀脚本与三个 prompt 见附录 B），人工只做抽查：

| 文档 | 设计目的 | 预期胜负 |
|---|---|---|
| A · 全真 | **假阳性对照**（eval 卫生，别人不会做这步） | 两者都应通过 |
| B · 直接矛盾（"Claude 是 Google 开发的"） | 基线能力 | 两者都该抓到 |
| C · 貌似合理的 ungrounded 实体 | 图的锚定优势 | 图占优 |
| D · **连贯编造集群**（虚构模型+它的成绩+作者，互相自洽） | 本项目核心卖点 | **图明显占优** |
| E · 别名/改写压力（"Omni"指 GPT-4o） | ER 弱点的诚实测试 | 可能 LLM 占优——照实报 |

产出：precision / recall / F1 总表 + 分类别表 + doc A 假阳性率。X vs Y 填进简历句式与 demo 记分牌。

---

## 6. 执行时间表

**今晚（≤45 分钟，然后必须睡）**
1. dashboard.butterbase.ai 注册 + provision + billing 兑 `ENJOY0707`，装 Claude Code plugin/MCP；
2. RunPod 余额确认（不用开机器）；
3. `git clone` rocketride-workshops 扫 5 分钟；
4. 把附录 A（参考图 prompt）与附录 B（腐蚀脚本 + 虚构/verbalizer prompt）存成笔记（设计不算代码）。
**不写代码**（规则风险 + 你需要睡眠这个算力）。

**比赛日（H0 = 开赛）**

| 时段 | 任务 | 出口条件 |
|---|---|---|
| H0–1 | workshop（问清 §7 三个开放问题）；开 RunPod 1×4090；`docker run neo4j` + GDS 插件 + 暴露 bolt；RocketRide hello-world **部署上 Cloud** | Cloud endpoint 通、`CALL gds.version()` 有返回 |
| H1–2 | 参考图谱：LLM 生成 CSV → 人工扫 → LOAD CSV；alias 表 | 200+ 三元组入库，抽查 10 条无错 |
| H2–3.5 | 按附录 B 生成 benchmark（台账 + 五篇散文，~25 min）；extract_claims prompt 调通（结构化 JSON）；ER + claim upsert；单例端到端（本地） | 台账落盘；一段样例文本 → 图里出现带判定的 claims |
| H3.5–4.5 | 三层判定 + GDS 调用 + 证据路径 + verdict JSON | doc B/D 的错误被正确标记 |
| H4.5–5.5 | 真 pipeline 组装 → **重新部署 Cloud**；credit_gate 接通 | webhook 一发，全链路回 verdict |
| H5.5–6.5 | Butterbase auth + payment 闭环；SPA + 星座图（force-graph 渲染 verdict JSON） | 登录→扣费→提交→图渲染 |
| H6.5–7.5 | **跑 benchmark 出 X vs Y**；LLM-judge 基线；demo 彩排 | 记分牌数字落定 |
| H7.5–8 | 提交（paste-to-agent 流程）+ 截图/视频 | 完成 |

砍功能顺序（时间不够时从左往右砍）：Daytona → doc E → 星座图动效 → LLM-judge 只跑 B/D 两篇。**benchmark 数字和红边可视化是死守项。**

---

## 7. 风险清单

| # | 风险 | 兜底 |
|---|---|---|
| R1 | Butterbase payment 原语形态未知 | workshop 第一问；Stripe test-mode → webhook → ledger |
| R2 | RocketRide Python 节点装不了 neo4j driver | Scorer FastAPI 侧车，pipeline 保持编排位 |
| R3 | RocketRide Cloud 部署摩擦（产品 3 周新） | H1 hello-world 先趟路；卡住立刻抓 mentor |
| R4 | ER 质量拉胯 | 领域 alias 表 + embedding 阈值；demo 输入除 doc E 外用规范名 |
| R5 | Aura Free 无 GDS | **已在设计层规避**（Docker+GDS）——顺便可以在 pitch 里当工程判断力讲 |
| R6 | Louvain 小图不稳 | 退化为 WCC 零锚点分量法（确定性） |
| R7 | LLM-judge 基线太强 | 照实报告；D/C 类是结构优势区；输赢都写进 blog——这是 evals 可信度 |
| R8 | AI gateway 限流 | 直连 API key；再兜底 vLLM Qwen2.5-7B 自托管抽取 |

---

## 8. GPU 使用建议（直接回答你的 RunPod 问题）

**结论：关键路径零训练，1 张 4090 足够，不需要 6–8 张。**

那张卡的用途：(a) 跑 Neo4j Docker + GDS（其实 CPU 活，蹭这台机器）；(b) 可选 vLLM Qwen2.5-7B-AWQ 做抽取兜底；(c) 唯一可能的训练是 stretch 中的 stretch——GraphSAGE 节点分类当第三个裁判（synthetic 腐蚀图上训 30–40 分钟，1 卡即可，天然满足你的 1–2 小时上限）——**默认砍掉**，只有 H6 前全部完成才考虑。省下来的预算和心智带宽比多 7 张卡值钱。真正的 GPU 大餐留给第 6–10 周的 TinyZero/GRPO。

---

## 9. 明确不做 + 赛后路径

**不做**：多领域支持、用户自传参考图谱、完整 calibration UI、CI gating、GNN 裁判（默认砍）、任何移动端适配。

**赛后 2–3 周（= 求职 Phase 1 交付物补全）**：judge calibration（对齐 human labels，报 TPR/TNR）→ GitHub Action CI gating → drift 检测 → README 补失败案例分析 → blog《Graph-as-Judge》。届时这个 repo 就是完整的 evals harness 开源项目。

---

### 附录 A · 参考图谱抽取 prompt（产物 1：全真参考图）

```
你是知识图谱构建助手。请生成关于 2023-2026 主流 LLM 生态的事实三元组 CSV，
列: src_id,src_name,src_type,rel,dst_id,dst_name,dst_type,functional
关系词表(只许用这些): developed_by, released_in, based_on, evaluated_on,
sota_on, authored_by, acquired_by, cited_by
实体类型: Model, Org, Paper, Benchmark, Person, Year
要求: 150 条; 只输出你高度确定的事实; functional 标 true 的仅限
developed_by/released_in; 不确定的宁可不写。只输出 CSV, 无其他文字。
```

---

### 附录 B · Benchmark 生成：confounding facts 的受控构建（补齐的另一半）

#### B.1 原则：三份产物，泾渭分明

```
产物 1  参考图谱        全真, 入 Neo4j, 是裁判的"法典" —— 永不掺假
产物 2  benchmark 台账  claim 级 CSV, 自动带标签(真/假/变异类型) —— ground truth
产物 3  五篇散文 docs   verbalizer 从台账写出, 即"被测 LLM 回答" —— 提交给系统的输入
```

假信息**只存在于产物 2/3**，由产物 1 **受控腐蚀（controlled corruption）**而来。顺序：真图先行 → 从真图采样 → 施加变异算子 → 台账 → 散文。好处：(1) 标签自动成立（腐蚀是我们干的，不需要人工判真假，只需抽查腐蚀执行是否正确）；(2) 每条假信息保证"原则上可检出"（真相就躺在参考图里、functional 钩子在位）；(3) confounding fact 有了精确定义——**同类型、图内、真实存在的错误宾语**。解剖一条标准样本：`(Claude, developed_by, Google)`——Google 是真机构、类型正确、就在图里，所以像真的；但 developed_by 是 functional 且真边指向 Anthropic，所以必被抓。

#### B.2 变异算子 → 文档映射

| 算子 | 操作 | 进哪篇 | 预期判定 |
|---|---|---|---|
| M1 尾实体替换 | functional 边的宾语换成**图内同类型**其他实体 | doc B | CONTRADICTED |
| M2 数值扰动 | release_year ±1~3 / 参数量 ×2 / 上下文 ÷2 | doc B | CONTRADICTED（超容差） |
| M3 实体虚构 | 编图外实体，可与真实体搭配（虚构模型 developed_by 真机构） | doc C | UNGROUNDED（灰·孤儿/半锚定） |
| M4 集群虚构 | 虚构模型 + 5~6 条互相咬合的事实，**只引用彼此、零真实体** | doc D | UNGROUNDED + cluster_flag（橙） |
| M5 别名改写 | 真事实，实体用绰号/描述指代 | doc E | TRUE（考 ER 的假阳性测试） |

组成比例：每篇被腐蚀 doc ≈ **70% 真填充 + 30% 植入错误**（贴近真实幻觉分布）；真填充**必须采样自图内事实**，否则"真话但图没覆盖"会污染标签。doc A 全部为真填充（假阳性对照）。doc D 的"互相咬合"在图上的体现 = 共享同一批 Mention 节点 → 自然长成独立连通分量，WCC/Louvain 必然单拎出来。

#### B.3 腐蚀脚本（doc B，确定性，~15 行）

```python
import pandas as pd
ref = pd.read_csv('ref_facts.csv')
targets = ref[ref.functional == 'true'].sample(5, random_state=7)   # M1
pool = ref[['dst','dst_name','dst_type']].drop_duplicates()
rows = []
for _, f in targets.iterrows():
    cand = pool[(pool.dst_type == f.dst_type) & (pool.dst != f.dst)].sample(1, random_state=7).iloc[0]
    rows.append(dict(doc='B', subject=f.src_name, rel=f.rel,
                     object=cand.dst_name, label='CONTRADICTED',
                     mutation='tail_swap', original=f.dst_name))
# M2: 另抽 3 个带 release_year 的实体, 年份 +2, label='CONTRADICTED', mutation='numeric'
# 真填充: ref.sample(7*4) 摊进 A/B/C/E, label='TRUE'
pd.DataFrame(rows).to_csv('bench_ledger.csv', index=False)
```

#### B.4 虚构 prompt（doc C/D 素材）

```
[把 ref_entities.csv 的实体名单贴在此处 —— 仅用于避免你编的名字撞车]
任务一(doc C): 虚构 3 个不存在、但命名风格以假乱真的实体
(1 个模型、1 个机构、1 个 benchmark)。为每个虚构实体写 1 条声明,
关系只许用词表; 声明可以把虚构实体与【真实实体】搭配
(例如: 虚构模型 developed_by 真实机构)。
任务二(doc D): 虚构 1 个模型及其完整故事: 它的(虚构)开发机构、
发布年份、在 1 个(虚构)benchmark 上的成绩、(虚构)论文与作者,
共 5~6 条声明。这些声明只许引用本任务内虚构的实体,
严禁出现任何真实实体名; 必须互相咬合、自洽。
输出 CSV: doc,cid,subject,rel,object,label
(doc C 行 label=FABRICATED_ENTITY; doc D 行 label=FABRICATED_CLUSTER)
只输出 CSV, 无其他文字。
```

#### B.5 Verbalizer prompt（台账 → 五篇散文）

```
下面是 benchmark 台账 CSV。把每个 doc 的全部声明写成一段流畅、
自信、典型 LLM 助手语气的英文散文(评委读英文):
1. 只许表达台账中的断言; 过渡句自由, 但严禁新增任何事实性内容
   (新的数字、日期、名字、关系一律不得出现)
2. 每条断言独立成句或独立分句, 顺序可打乱
3. 真假混排, 语气完全一致, 不得对任何断言表达不确定或做暗示
4. 输出: 每个 doc 一段, 以 [doc_id] 开头。只输出散文。
```

#### B.6 方法论备注（README 各写一句 = evals 加分项）

1. **污染隔离**：doc B 的腐蚀用脚本做（确定性、独立于任何 LLM）；C/D 虚构与 verbalizer 使用 gateway 里**与 judge 不同的模型**（如 Gemini 造、GPT 判），避免"裁判认出自己笔迹"。
2. **对齐**：断言独立成句 → 抽取结果按 (subject, rel) 对齐台账；50 行人工抽查约 10 分钟（排在 H6.5 benchmark 跑分前）。
3. **时间挂点**：整套生成挂在 H2 尾巴，约 20–30 分钟（脚本 5 分钟 + 两个 prompt 各一发 + 人工扫一遍）。