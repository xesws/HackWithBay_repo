# dev-C（Track C · product）· v0.1-skeleton

> 属地: `/backend` `/web`。每张任务卡完成即在此追加条目，必须含验证命令与实际输出，未验证不算完成。

<!-- 追加条目格式（OPS §5）:
## [HH:MM] C1 <标题> — done|blocked
做了: ...
验证: <命令> -> <实际输出摘要>
遗留/坑: ...
下一步: C2
-->

> 环境备注（ops 预置）: `BUTTERBASE_API_KEY`(bb_sk_) 已在 `.env`（仅服务端用）。`BUTTERBASE_URL` 待填。
> Node 22 就位；SPA 星座图用 force-graph 渲染 verdict JSON（前端不接触 Neo4j，见 contracts §4.2）。

> **app_id = `app_r1568bo1iteg`**（ops 预置，全程复用，未新建）。api_base = `https://api.butterbase.ai/v1/app_r1568bo1iteg`。live SPA = `https://graphjudge.butterbase.dev`。

## [20:20] C1 Butterbase 三表 + 隔离验证 — done（含 NEEDS-HUMAN）
做了:
- 发现 app 已被预置了**偏离契约**的三表：`user_id`/`job_id` 为 **uuid**、`credits_ledger.ts`（契约/卡片要 `created_at`）、`results.verdict_json`（契约要 `verdict`）、多一列 `results.user_id` + uuid 外键。
- 本卡片 + contracts §4.5 要的是 text id（好让 §4.1 的 `job_id="j_001"`、§4.4 的任意 user_id 能落库）、`created_at`、`verdict`。已把**目标 schema**（source of truth）落盘 `backend/schema/tables.json`。
- 用 `manage_schema dry_run` 预览：把 uuid→text 需要 drop 重建；`apply` DROP 三表被 **Claude Code 权限分类器拦截**（[Cloud Storage Mass Delete]，删共享表需人类明确授权）。**未强行绕过**，改为在现存（uuid）schema 上验证隔离，并升级为 NEEDS-HUMAN。
验证:
- `insert_row credits_ledger {user_id:"u1",...}` → 报错 `pg_code 22P02`（uuid 列拒收字符串 id）——坐实偏离。
- 用哨兵 uuid（u1=`1111...1111`）：`insert_row {user_id:"1111...",delta:5,reason:"seed"}` → 成功（返回列名是 `ts`，再次坐实偏离）。
- `select_rows filter user_id=eq.1111...` → 返回该行；`filter user_id=eq.2222...`（u2）→ `[]`。**按 user_id 过滤隔离 OK**。
遗留/坑:
- **NEEDS-HUMAN（schema 对齐）**: 现网表与 contracts §4.5 列名/类型不符（uuid vs text；ts vs created_at；verdict_json vs verdict）。对齐需 DROP 空的共享表（分类器已拦，需人类授权）。表都是空的，对齐无数据损失。二选一决策：(a) 人类授权按 `backend/schema/tables.json` drop+重建对齐契约；(b) 反过来修契约/其它 track 采用 uuid+ts+verdict_json（但 uuid 会让 `job_id="j_001"` 落不了库）。**建议 (a)**。
- RLS `create_user_isolation`（§4.5 可选加分）**暂缓**：等 schema 对齐后再做，避免在待重建的表上白做一遍。当前 per-user 隔离由服务端 `WHERE user_id` + fn 内 `ctx.user.id`（JWT 派生）保证，符合 §4.5「服务端按 user_id 过滤」的口径。
下一步: C2

## [20:20] C2 consume_credit + get_balance — done
做了:
- `deploy_function` 部署两个 http fn（`auth:required`）：
  - `consume_credit(body {user_id,job_id})`：**单条 SQL 语句**（数据修改型 CTE）完成「读余额+条件插入 delta=-1 reason='consume'」，天然单事务；加 `pg_advisory_xact_lock`（按 user 串行）防并发双花。fn 内优先用 `ctx.user.id`（JWT，防伪造），无 JWT（服务端 service 调用）才回退 `body.user_id`。
  - `get_balance(body {user_id})`：`COALESCE(SUM(delta),0)`。
- 踩坑修复：(1) `ctx.db.query` 参数化下 uuid 列 vs text 参数 → `operator does not exist: uuid = text`；(2) SQL 注释里的反引号提前闭合了 JS 模板串。最终用**两个参数**（$1 只出现在 `user_id=$1`/INSERT，由列类型推断；$2 仅供 `hashtext($2)`），对 uuid（现网）与 text（对齐后）都成立。
验证（真实浏览器路径：`/fn/*` + 用户 JWT；test 用户 `graphjudge-c-verify@example.com` / uuid `c170f96d-...`，seed +1）:
```
get_balance (pre)   -> {"balance":1}
consume_credit #1   -> {"ok":true,"balance":0}
consume_credit #2   -> {"ok":false,"balance":0}   # 余额 0，双花被拒
get_balance (post)  -> {"balance":0}
```
遗留/坑: fn 用 `auth:required`；MCP `invoke_function` 走匿名故 401，改用 curl 带用户 JWT 调 `/fn/*`（即 SPA 实际路径）。app `access_mode=public`，安全边界靠 fn 的 `auth:required` + `ctx.user.id`。
下一步: C3

## [20:20] C3 Vite SPA + 星座图 + auth + 部署 — done
做了:
- `web/`（Vite+React18+TS）。`web/src/sample_verdict.json` 手写 §4.2 verdict：**四色齐全**（green SUPPORTED / red CONTRADICTED / gray UNGROUNDED-orphan / orange UNGROUNDED-cluster，含 c4/c5/c6 自洽编造集群），每条 claim 带 evidence(type,truth,path)。
- `Constellation.tsx` 用 `react-force-graph-2d` 渲染 `verdict.graph.nodes/edges`，节点色=`node.color`（claim 画菱形/entity 画圆），点击节点→右侧 evidence 面板读 `verdict.claims[cid].evidence`（type/truth/path），entity 节点则列出相关 claim。含图例 + doc_score。
- `api.ts:fetchVerdict()` 现返回静态 sample（SEAM 注释指向后续 §4.4 webhook）；`fetchBalance()` 调 `get_balance` fn（带 JWT）。
- `auth.ts`：邮箱/密码走 Butterbase auth REST（`/auth/{app_id}/login|signup`）+ localStorage 会话（卡片许可的最简会话回退）。**@butterbase/sdk 评估后弃用**——它 transitive import `node:crypto` 的 `randomUUID`，浏览器 Vite/Rollup 构建报错；REST 包装打同一 auth 服务、拿真 end-user JWT。浏览器**从不**持有 bb_sk_（§4.7）。
验证:
```
node scripts/check_sample.mjs ->
  distinct node colors: gray, green, orange, red (count=4)
  claim statuses: CONTRADICTED, SUPPORTED, UNGROUNDED
  clickable evidence nodes (claim:* with evidence): 6 / 6
  graph nodes: 17 edges: 14 ; CHECK PASSED
npm run build -> ✓ built dist/ (index.html + assets/*.js 342kB + css)
create_frontend_deployment + PUT zip(HTTP 200) + start_deployment -> {url: https://graphjudge.butterbase.dev, status: READY}
update_cors -> allowed_origins += https://graphjudge.butterbase.dev
GET https://graphjudge.butterbase.dev -> HTTP 200（title/JS asset 均 200）
CORS preflight(OPTIONS) get_balance from deployed origin -> access-control-allow-origin: https://graphjudge.butterbase.dev
login + get_balance (Origin=deployed) -> {"balance":0} HTTP 200  # 全链路（登录→余额）从线上域名可用
```
遗留/坑: 无阻塞。build 脚本用 `vite build`（esbuild 转译，不做 tsc 类型检查）以避第三方类型噪音。
新增文件:
- backend/schema/tables.json
- backend/functions/consume_credit.ts, backend/functions/get_balance.ts
- web/（index.html, package.json, package-lock.json, vite.config.ts, tsconfig.json, .gitignore,
  src/{main.tsx,App.tsx,Constellation.tsx,auth.ts,api.ts,config.ts,styles.css,vite-env.d.ts,sample_verdict.json},
  scripts/check_sample.mjs）  ← node_modules/ 与 dist/ 已 gitignore，勿提交
下一步: 待人类裁 schema 对齐（NEEDS-HUMAN）；之后 fetchVerdict 换成 §4.4 webhook、可选补 RLS。
