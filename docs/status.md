OPS | v0.1 | Phase2: A ✅ (scorer live 公网, real Neo4j+GDS); B 并行预写 /verify+.pipe+B3-real; 待整合 e2e | 阻塞: 无 | 更新 20:53
OPS | 契约 v1.1 (decisions #1): job_id uuid4; §4.5 表对齐 live (uuid/ts/verdict_json); 不 drop 表 | 更新 20:37
A | v0.1 | A2+A4 ✅ tier=gds; scorer 活线 https://ohld8gp5nmkcu7-8888.proxy.runpod.net (/score real Neo4j+GDS, bench 63/63); POD-LOCK 已释放 | 阻塞: 无 | 更新 20:53
B | v0.1 | B2+B3-stub 已合; Phase2 预写中(worktree): .pipe / verify / B3-real / checklist; 待整合 | 阻塞: LLM key 空 → 记分牌 LLM-judge 基线残废(NEEDS-HUMAN) | 更新 20:53
C | v0.1 | C1-C3 已合; SPA 活线 https://graphjudge.butterbase.dev; credit 流已验证 | 阻塞: 无 | 更新 20:37
D | v0.1 | D1-D4 done; benchmark_runner job_id→uuid4 (decisions #1) | 阻塞: 无 | 更新 18:56
SETUP | §2 ✅ + 交接: SCORER_URL=https://ohld8gp5nmkcu7-8888.proxy.runpod.net (8888 proxy 已验证); scorer 绑 0.0.0.0:8888 | 13:09
OPS | Shape 2 已裁决: pipeline 经 scorer /verify 内嵌 SDK 触发, 全系统单公网口 | 13:09
OPS | 属地豁免: /verify 归 Track B 实现, 允许 B 在 /scorer 的 app 挂载 router | 13:09
