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
