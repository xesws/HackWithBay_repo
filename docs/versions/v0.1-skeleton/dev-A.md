# dev-A（Track A · graph-core）· v0.1-skeleton

> 属地: `/infra` `/scorer`。每张任务卡完成即在此追加条目，必须含验证命令与实际输出，未验证不算完成。

<!-- 追加条目格式（OPS §5）:
## [HH:MM] A1 <标题> — done|blocked
做了: ...
验证: <命令> -> <实际输出摘要>
遗留/坑: ...
下一步: A2
-->

> 环境备注（ops 预置）: Neo4j 5.26.12 + GDS 2.13.8 已在 `/workspace/neo4j` 运行（bolt `localhost:7687`，
> 已验证 `CALL gds.version()`=2.13.8 且 WCC 可执行）。参考 CSV 已放入 `/workspace/neo4j/import/`
> （`ref_entities.csv` `ref_facts.csv`，Cypher 用 `file:///`）。`.env` 的 `NEO4J_PASSWORD` 已校正为真实密码。

---

## [A3] FastAPI scorer: 第一层判定 + WCC 孤儿/集群 + 契约 4.2 输出 — done

工作分支: `track-a-scorer`（隔离 worktree `.claude/worktrees/track-a`，off local HEAD `e25de27`）。
**mock-first**：全程不连 Neo4j、不 import `neo4j` driver。用主 venv 绝对路径跑
`/workspace/HackWithBay/HackWithBay_repo/.venv/bin/python`。

做了（新建 `/scorer`）:
- `scorer/models.py` — pydantic v2。请求按 `kind` 判别联合（relational=`rel`+`object`，
  attribute=`attr`+`value`），精确匹配 `benchmark_runner.py:claim_payload()` 产出。响应 = 契约 4.2。
- `scorer/reference.py` — `ReferenceGraph` ABC（`resolve/facts_for/is_functional/attr_of/
  canonical_name/entity_type/fact_pairs_among` + 通用 `connected_components`(union-find)、
  `shortest_path_len`(BFS)）。`InMemoryReference.from_csv()` 读 `data/import/*.csv`；ER 复用
  `data/validate.py:build_name_index()`（importlib 按文件路径载入，无副作用）。**无 networkx、无 neo4j**。
- `scorer/scoring.py` — 三层判定：
  - L1 relational: SUPPORTED 若 `(s,rel,o)` 在事实集；CONTRADICTED 仅当 `is_functional(rel)`
    且 `facts_for(s,rel)` 非空且**宾语解析为真实且不同的实体**（虚构/解析不了的宾语→UNGROUNDED，
    这是让 doc-C `CF002`=GPT-4o developed_by Vesper Labs 正确落 UNGROUNDED 而非 CONTRADICTED 的关键）。
    证据 `{type:conflict, truth:<真宾语规范名>, path:[s,rel,truth]}`。
  - L1 attribute: `release_year` 精确；数值 ±5% 容差；超差→CONTRADICTED；实体无该属性→UNGROUNDED。
  - L2: 建 per-job 图（Entity/Claim/Mention + SUBJ/OBJ/FACT 无向），mention 按 surface 键化
    （doc D 虚构名跨行共享→塌成一个连通分量）。WCC→`grounding_ratio`（端点解析比例）、
    `dist_to_core`=BFS(claim→最近 anchor)−1（直接锚定=0，无 anchor=null）、
    `cluster_flag`=分量内零个 `:Entity` anchor（确定性 R6，替代 GDS Louvain）。
  - 颜色: SUPPORTED→green / CONTRADICTED→red / UNGROUNDED&cluster→orange / UNGROUNDED&非→gray；
    grounded `:Entity` 恒 green。doc_score=1−(1·|CONTRA|+0.5·|flagged UNGROUNDED|)/N。
- `scorer/app.py` — `POST /score`、`POST /admin/load_ref`、`GET /health`；`get_reference()` 工厂
  默认 `InMemoryReference`，留 `SCORER_REFERENCE_BACKEND=neo4j` env 钩子。
- `scorer/reference_neo4j.py` — 同接口的**文档化 TODO stub**（bolt+GDS），未接线，每个方法 raise。

启动命令:
```
PYTHONPATH=<worktree> .venv/bin/python -m uvicorn scorer.app:app --host 127.0.0.1 --port 8000
```
`GET /health` -> `{"status":"ok","reference":{"backend":"memory","entities":161,"facts":332,
"functional_rels":["developed_by","released_in"],"surface_forms":352}}`

### 验证 1 · 定海神针 smoke（curl 3 claims，实测输出）
选真 functional 边 `gpt_4,GPT-4,Model,developed_by,openai,OpenAI,Org,true`（SUPPORTED/CONTRADICTED），
虚构名 `Zephyrion-X99 / Nimbus Robotics Collective`（两 CSV grep 计数=0，确为图外）。
`POST /score` 返回:
- `S1` GPT-4 developed_by OpenAI → **SUPPORTED**, color green, grounding_ratio 1.0, dist_to_core 0,
  evidence `{type:support, truth:"OpenAI", path:["GPT-4","developed_by","OpenAI"]}`
- `C1` GPT-4 developed_by Anthropic → **CONTRADICTED**, color red,
  evidence `{type:conflict, truth:"OpenAI", path:["GPT-4","developed_by","OpenAI"]}`
- `U1` Zephyrion-X99 developed_by Nimbus Robotics Collective → **UNGROUNDED**,
  `grounding_ratio 0.0`(<1), `dist_to_core null`, `cluster_flag true`, color **orange**
- 图含 FACT 绿核心边 `ent:gpt_4 -developed_by-> ent:openai` status=supported。

⚠️ **规格不一致（非代码缺陷，需人裁）**: 验收文案要求「UNGROUNDED(**gray**) 且 `grounding_ratio<1` 且
`dist_to_core=null`」。但按冻结规则三者不能同真：`dist_to_core=null` ⟺ 分量零 anchor ⟺
`cluster_flag=true` ⟺ **orange**；gray(`cluster_flag=false`) 必有可达 anchor 故 `dist_to_core` 有限(=0)。
已按冻结的 R6/颜色规则实现，并补一条 curl 证明 gray：
`AstraLM-9B developed_by Anthropic`（虚构主语+真实宾语，半锚定）→ UNGROUNDED, `cluster_flag false`,
`grounding_ratio 0.5`, `dist_to_core 0`, color **gray**。四色全部覆盖（green/red/orange/gray）。

### 验证 2 · 全量 benchmark（对活服务，非 mock）
`.venv/bin/python eval/benchmark_runner.py --scorer-url http://127.0.0.1:8000` 实测:
```
doc A: sent 10 claims, expected_matches=10/10
doc B: sent 27 claims, expected_matches=27/27
doc C: sent 10 claims, expected_matches=10/10
doc D: sent 6 claims, expected_matches=6/6
doc E: sent 10 claims, expected_matches=10/10
overall expected_matches=63/63
scorer_url=http://127.0.0.1:8000
```
这是**真跑分**（scorer 逐条判定得出，非 mock 直接读 label）：doc B 8 条 CONTRADICTED（5 tail_swap +
3 numeric）+ 19 条 SUPPORTED 全中；doc C/D 虚构全落 UNGROUNDED；doc A 全 SUPPORTED。
doc E 10/10 已核验为真：全部别名（含 `Tongyi Qianwen`→Alibaba Cloud、`Mistral`→Mistral AI、
`Databricks Mosaic Research`→Databricks）经 `build_name_index` 解析成功且事实存在 → 真 SUPPORTED。
Track D 的 alias 表覆盖完整，故未出现预想中的 doc E 别名欠配。验证后已 kill uvicorn。

遗留/坑:
- 上面的 gray-vs-null 规格不一致点需你裁决（我按冻结规则实现，未改 contracts）。
- `dist_to_core` 定义为 BFS−1（直接锚定=0），对齐契约 4.2 样例里 grounded claim 的 `dist_to_core:0`。
- A4（Neo4jReference 实装 + LOAD CSV）是 pod territory，未做（护栏内 gated）。stub 已就位、接口对齐。

下一步: 等编排指令；A4 待 pod 放行。
