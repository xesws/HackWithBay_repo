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
