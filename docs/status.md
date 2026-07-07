OPS | v0.1 | Phase2 e2e ✅ LIVE: SPA→/verify→gemini 抽取→real Neo4j+GDS 打分→星座图渲染; scoreboard 进行中 | 阻塞: 无 | 更新 21:23
OPS | 契约 v1.1 (decisions #1): job_id uuid4; §4.5 表对齐 live; 不 drop 表。LLM 一律 OpenRouter/google-gemini-3.5-flash | 更新 21:23
A | v0.1 | A2+A4 ✅ tier=gds; scorer 活线 :8888 (/score + /verify, real Neo4j+GDS, CORS, bench 63/63) | 阻塞: 无 | 更新 21:23
B | v0.1 | /verify(Shape2) 挂载 + B3-real + OpenRouter 抽取(30s超时+regex兜底) 已整合上线; credit gate=stub(可选接线) | 阻塞: 无 | 更新 21:23
C | v0.1 | SPA 重部署 https://graphjudge.butterbase.dev: paste→Verify→星座图 已接 /verify(§4.4) | 阻塞: 无 | 更新 21:23
D | v0.1 | D1-D4 done; scoreboard(graph-judge vs LLM-judge) worker 进行中 | 阻塞: 无 | 更新 21:23
SETUP | §2 ✅ + 交接: SCORER_URL=https://ohld8gp5nmkcu7-8888.proxy.runpod.net; scorer 绑 0.0.0.0:8888 | 13:09
OPS | Shape 2 已裁决 + /verify 属地豁免(B 在 scorer app 挂 router) | 13:09
