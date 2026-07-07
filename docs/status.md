OPS | v0.1 | Phase1 pre-pod (A3/B2/B3-stub/C1-C3) merged→main 7d6a96b; 进入 Phase 2, A 持 pod-lock | 阻塞: 无 | 更新 20:37
OPS | 契约 v1.1 广播 (decisions #1): job_id 全链路 uuid4; §4.5 表对齐 live (uuid/ts/verdict_json); 不 drop 表 | 更新 20:37
A | v0.1 | POD-LOCK:A — A3 已合; A2 冒烟 + A4 入 Neo4j + scorer 部署 0.0.0.0:8888 进行中 | 阻塞: 无 | 更新 20:37
B | v0.1 | B2+B3-stub 已合(offline); /verify(Shape2)+B3-real 等 A 交锁 | 阻塞: B2 live 抽取等 LLM key | 更新 20:37
C | v0.1 | C1-C3 已合; SPA 活线 https://graphjudge.butterbase.dev; credit 流已验证 | 阻塞: 无 | 更新 20:37
D | v0.1 | D1-D4 done; benchmark_runner job_id→uuid4 (decisions #1) | 阻塞: 无 | 更新 18:56
SETUP | §2 ✅ + 交接: SCORER_URL=https://ohld8gp5nmkcu7-8888.proxy.runpod.net (8888 proxy 已验证); scorer 绑 0.0.0.0:8888 | 13:09
OPS | Shape 2 已裁决: pipeline 经 scorer /verify 内嵌 SDK 触发, 全系统单公网口 | 13:09
OPS | 属地豁免: /verify 归 Track B 实现, 允许 B 在 /scorer 的 app 挂载 router | 13:09
