# GraphJudge docs 导航

必读顺序: `OPS.md` -> `contracts.md` -> `versions/<当前版>/plan.md` 中你的 track 段 -> 你的 `dev-X.md` 末尾

## 文件
- `DESIGN.md` — 系统设计报告（只读）
- `OPS.md` — 并行开发规范（只读）
- `STETUP.md` — 环境设置 checklist（文件名沿用现拼写；OPS 中称其为 `SETUP.md`）
- `contracts.md` — 冻结接口 v1（改动必须走 `decisions.md` 裁决）
- `status.md` — 全局看板，每 track 一行
- `decisions.md` — 变更提案与裁决记录（ADR 式，追加不删改）
- `versions/v0.1-skeleton/` — `plan.md`(版本级) · `dev-A/B/C/D.md`(各 track) · `review.md`(收版)

## 属地纪律
- Track A → `/infra` `/scorer` ｜ Track B → `/pipeline` ｜ Track C → `/backend` `/web` ｜ Track D → `/data` `/eval`
- 代码只改自己 track 目录；文档只写自己的 `dev-X.md` + `status.md` 自己那一行；不碰 `contracts.md`/`DESIGN.md`/`OPS.md`/别人的 dev 文件。
