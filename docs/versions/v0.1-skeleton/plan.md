# v0.1-skeleton · 目标: 四条腿各自站起来 + 冒烟测试证明判定内核
## 出口条件
- [ ] curl SCORER_URL/score 用冒烟 claims 返回预期三判定
- [ ] RocketRide hello-world .pipe 在 pod 自托管 runtime 上执行成功（cloud 豁免 receipt 已存 decisions.md）
- [ ] Butterbase: 建表完成, consume_credit 扣减可验证
- [ ] ref CSV 200+ 条入库; benchmark 台账+五篇散文落盘

## Track A（/infra /scorer）
- [ ] A1 按 SETUP.md §2 方案 α: pod 上 tarball 装 Neo4j+GDS
      (RunPod pod 内无 docker; bolt 走 localhost, 不暴露公网)
      ｜验收: cypher-shell 跑 CALL gds.version() 有返回
- [ ] A2 手写 5 节点玩具图 + 冒烟三 claim（DESIGN.md 冒烟测试:
      SUPPORTED / CONTRADICTED / UNGROUNDED+WCC 孤立）
      ｜验收: 三条判定全符合预期 —— 这是全项目的定海神针
- [ ] A3 FastAPI /score: 第一层判定 + WCC + 契约 4.2 输出
      ｜验收: curl 冒烟 claims 过
- [ ] A4 等 D 交付后 LOAD CSV 真参考图, 重跑冒烟
      ｜验收: 200+ facts, 抽查 5 条查询正确

## Track B（/pipeline）
- [ ] B1 hello-world .pipe: extension 本地构建 → pod 自托管
      runtime 执行（按 SETUP §4; 对外接线 Shape 1/2 二选一,
      定下后把 PIPELINE_WEBHOOK_URL 写进 status.md 广播）
      ｜验收: 公网 curl 该 URL 执行成功
- [ ] B2 extract_claims prompt: 样例散文 -> 契约 4.1 JSON
      ｜验收: 10 条断言 ≥8 条抽取正确, JSON schema 过校验
- [ ] B3 stub 全链路: webhook -> extract -> mock scorer -> respond
      ｜验收: curl webhook 返回 4.2 形状

## Track C（/backend /web）
- [ ] C1 Butterbase project + 三张表; 服务端查询一律按 user_id
      过滤(单 key 模型, SPA 不直连 DB; RLS 为可选加分)
      ｜验收: insert/select 通, 按 user_id 过滤结果正确
- [ ] C2 consume_credit + get_balance 两个 fn
      ｜验收: 余额 1 -> 扣成 0 -> 再扣被拒; get_balance 读数一致
- [ ] C3 SPA: auth 按 @butterbase/sdk 浏览器侧实际签名接
      (不可行则降级为最简邮箱会话) + 用 contracts 4.2 样例
      JSON 渲染星座图
      ｜验收: 登录态存在; 四色节点出现, 点击弹 evidence

## Track D（/data /eval）
- [ ] D1 附录 A prompt 生成 ref CSVs + 人工扫 + alias 表
      ｜验收: 200+ 条, 抽查 10 条无错 -> 交接给 A（status.md 喊话）
- [ ] D2 附录 B.3 腐蚀脚本 -> bench_ledger.csv
      ｜验收: 台账行数/标签分布符合 B.2 比例
- [ ] D3 附录 B.4+B.5 -> 五篇散文｜验收: 散文断言与台账一一对应, 抽查无新增事实
