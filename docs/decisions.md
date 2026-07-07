# GraphJudge 裁决记录 (decisions.md)

> ADR 式，追加不删改。契约变更全天预算 ≤2 次（见 `contracts.md` §4.8）。
> 提案格式: 动机 / 改动 / 波及 track → 人类裁决 → 更新 contracts + status 广播。

---

## #0 — RocketRide Cloud outage 豁免（decided；receipt 待补）
- **背景**: 官方 RocketRide Cloud 今日故障，sponsor 在 Discord 明确本地 runtime 即可满足要求。
- **裁决**: 采用 pod 自托管 RocketRide runtime（`pip install rocketride`），不使用 Cloud；作为评审时“为何未上 Cloud”的官方依据。
- **receipt（待人工粘贴 Discord 原文，勿由 agent 编造）**:
  - Krish Garg 11:42 — `<粘贴原文>`
  - Joe Maionchi 11:47 — `<粘贴原文>`
- **状态**: 决定生效；截图/原文 receipt 待补齐后本条即完成。

---

## #1 — Butterbase 表偏差：契约迁就现实（contract change #1，decided）
- **背景**: 预置 app `app_r1568bo1iteg` 的表与 contracts §4.5 有偏差（uuid ids / `ts` / `verdict_json` / 多一列 `results.user_id`+FK）。Track C 的 live SPA 与已验证的 credit 流建在其上，不可 drop 重建。
- **裁决（人类）**: 纸面迁就现实。`job_id` 全链路改 uuid4（SPA / pipeline / benchmark_runner 生成方均 uuid4）；列名以实际表为准（`ts`、`verdict_json`）；禁止 drop/重建表。
- **改动**: contracts v1→v1.1（§4.1/§4.2/§4.4 `job_id`=uuid4；§4.5 表定义对齐 live schema）；`eval/benchmark_runner.py` job_id→`uuid.uuid4()`；SPA/pipeline 生成方 uuid4（Phase 2 /verify 接线时落实）。
- **波及**: A（scorer 已支持任意 str job_id，无需改） / B（webhook + /verify 用 uuid job_id） / C（表不动） / D（benchmark_runner 已改）。
- **状态**: 生效。契约变更计数 1/2。

---

## #2 — rel/attr 词表开放化：支持 Eval-2 个人域（contract change #2，decided）
- **背景**: 另一 agent 在 `/data/personal` 产出无污染的**个人域**基准（虚构人物/关系，非 AI 域）。§4.1 原把 `rel` 钉死为 8 个 AI 关系、`attr` 钉死为 3 个，个人域的关系词（如 works_at / born_in / spouse_of）会被抽取校验拦截，无法跑第二张记分牌。
- **裁决（人类）**: `rel`/`attr` 改为**开放字符串**，仅保留格式校验（非空 string）。采用「放开 enum 只留格式校验」而非「配置文件词表」——更快、够用；每个域的词表在其 extraction prompt 内定义。
- **改动**: `pipeline/schemas/claims.schema.json` 去掉 rel/attr 的 `enum`，改 `{type:string,minLength:1}`（保留规范参考词表于 `$comment`）；contracts v1.1→**v1.2**（§4.1 语言更新，AI 域词表降级为“参考集”）。**scorer 无需改**：`scorer/models.py` 本就 `rel: str`，打分层 `is_functional`/`facts_for`/`attr_of` 查参考图而非白名单。
- **波及**: A（scorer 零改动，向后兼容 AI 域） / B（抽取校验放开，AI 域回归不受影响——regex/LLM 仍只产出合法词） / D（Eval-2 可用任意域词表跑 benchmark_runner + LLM-judge）。
- **未决/跟进**: 个人域若含 functional-rel 的 tail-swap（CONTRADICTED），需为该域配置 functional 关系集（当前 `functional_rels` 仅 AI 域 `developed_by/released_in`）；纯 fabricated-entity/cluster（UNGROUNDED）检测不受影响。数据落地后按 Eval-2 语料的 corruption 类型定夺。
- **状态**: 生效。契约变更计数 **2/2**（今日已达预算上限；再改需顺延至明日或人类特批）。
