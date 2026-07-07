OPS | v0.1 | Phase2 e2e ✅ LIVE + **demo 切到个人域(Eval-2)**: Neo4j 换 51ent/107fact 个人图, 个人 extraction prompt, SPA 个人 sample; paste→/verify→3绿2红1灰6橙 已验证 | 阻塞: 无 | 更新 22:14
OPS | 契约 v1.1 (decisions #1): job_id uuid4; §4.5 表对齐 live; 不 drop 表。LLM 一律 OpenRouter/google-gemini-3.5-flash | 更新 21:23
A | v0.1 | A2+A4 ✅ tier=gds; scorer 活线 :8888 (/score + /verify, real Neo4j+GDS, CORS, bench 63/63) | 阻塞: 无 | 更新 21:23
B | v0.1 | /verify(Shape2)+B3-real+OpenRouter 抽取(30s超时+regex兜底); **credit gate=LIVE**(consume_credit 接线, JWT 转发, fail-open); demo 号 999/0 已 e2e 验证 | 阻塞: 无 | 更新 22:00
C | v0.1 | SPA 重部署 https://graphjudge.butterbase.dev: paste→Verify→星座图 已接 /verify(§4.4) | 阻塞: 无 | 更新 21:23
D | v0.1 | D1-D4 done; scoreboard ✅ (eval/scoreboard_results.md): planted-false 检测 graph 100% vs LLM 100%; graph 独赢 3-way 精确 100% vs 98.4% + 可审计 path | 阻塞: 无 | 更新 21:41
SETUP | §2 ✅ + 交接: SCORER_URL=https://ohld8gp5nmkcu7-8888.proxy.runpod.net; scorer 绑 0.0.0.0:8888 | 13:09
OPS | Shape 2 已裁决 + /verify 属地豁免(B 在 scorer app 挂 router) | 13:09
