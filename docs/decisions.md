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
