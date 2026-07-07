# GraphJudge 环境设置 Checklist（docs/SETUP.md）
### 目标：≤50 分钟全绿，然后才给 agents 发 kickoff prompt。每项都有验证命令，没跑验证不算勾。

> ⚠️ **约束更新：只用 RunPod。** 注意 RunPod 的坑：pod 本身就是容器，**里面没有 docker daemon**，不能在 pod 里再 docker run。所以首选方案是**单 pod 全家桶**——1×4090 上用 tarball 直装 Neo4j+GDS（不走 docker），scorer 同机，Neo4j 与 scorer 之间走 localhost、bolt 永远不暴露公网，唯一的公网面是 scorer 的 HTTP 端口（走 RunPod 自带 proxy）。备选是双 pod stock 镜像方案。

---

## 0. 账号与密钥（10 min）

- [ ] **Butterbase**：project 已 provision（不是 org 空壳）；`BUTTERBASE_URL` + `BUTTERBASE_API_KEY`（bb_sk_ 开头的 secret key）抄进 `.env`
      ｜验证：dashboard 里能看到 database/auth 控制台
- [ ] **Butterbase credits**：workshop 上问到的兑码结果落实；若仍是 $0 → 直接启用 R8（直连 key），别再耗时间
      ｜验证：AI models 页发一条测试请求，或直连 key 就绪
- [ ] **RocketRide**：VS Code extension 装好；cloud.rocketride.ai 账号注册并在 extension 里登录
      ｜验证：extension 内能看到 deploy 目标
- [ ] **直连 API keys（R8 兜底）**：`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` 至少一个进 `.env`
      ｜验证：一条最小 completion 请求返回 200
- [ ] **RunPod**：余额确认即可，**先不租卡**（vLLM/GNN 触发时再租）
- [ ] **Daytona**：跳过，除非 H6 前全部完成（stretch 纪律）

## 1. Repo + docs 脚手架（5 min）

- [ ] `git init graphjudge && cd graphjudge && mkdir -p infra scorer pipeline backend web data eval`
- [ ] 拷入 `docs/DESIGN.md`、`docs/OPS.md`；跑 OPS §2 脚手架；OPS §4 拷成 `docs/contracts.md`；OPS §6 拷成 `docs/versions/v0.1-skeleton/plan.md`
      ｜验证：`find docs -type f | sort` 与 OPS §2 目录树一致
- [ ] 建 `.env`（模板见文末），`echo ".env" >> .gitignore`
- [ ] 首次 commit：`git add -A && git commit -m "[ops] scaffold"`

## 2. 图数据库宿主（核心，20 min）—— RunPod-only

**方案 α · 单 pod 全家桶（首选）**：1×4090，**On-Demand（今天禁用 Spot——中断 = demo 猝死）**，RunPod PyTorch 模板，部署时在 Expose HTTP Ports 里**加上 8000**（scorer 用）；所有东西装进 `/workspace`（pod 重启不丢盘）。

- [ ] 租卡：4090 · On-Demand · PyTorch 模板 · HTTP ports: 8888,8000
- [ ] Web terminal / SSH 进 pod，装 Neo4j + GDS（整段贴给 agent 代劳）：

```bash
export NEO4J_PASSWORD='<与 .env 里同一个密码>'   # pod 上没有你的 .env, 先手动 export
cd /workspace && apt update && apt install -y openjdk-17-jre-headless wget unzip
wget -q https://dist.neo4j.org/neo4j-community-5.26.0-unix.tar.gz
tar xf neo4j-community-*.tar.gz && mv neo4j-community-* neo4j
# GDS 插件: 先试与 5.26 配套的 2.13.x; 若报版本不符, 按官方兼容矩阵换版本号
wget -q https://graphdatascience.ninja/neo4j-graph-data-science-2.13.2.zip
unzip -q neo4j-graph-data-science-*.zip -d neo4j/plugins/
echo 'dbms.security.procedures.unrestricted=gds.*' >> neo4j/conf/neo4j.conf
neo4j/bin/neo4j-admin dbms set-initial-password "$NEO4J_PASSWORD"
neo4j/bin/neo4j start && sleep 15
```

- [ ] **定海神针**：`/workspace/neo4j/bin/cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "CALL gds.version()"` → 返回版本号。此项不绿，后面全停。
- [ ] pod 上装 scorer 依赖：`pip install fastapi uvicorn neo4j pandas python-dotenv`
- [ ] **proxy 验证（现在就做，别等 scorer 写完）**：pod 上 `python -m http.server 8000 &`，本机 `curl https://<POD_ID>-8000.proxy.runpod.net` 有响应即通，然后 kill 掉。`SCORER_URL` 就是这个 URL。
- [ ] CSV 一律放 `/workspace/neo4j/import/`，Cypher 里用 `file:///xxx.csv`
- [ ] `.env`：`NEO4J_URI=bolt://localhost:7687`（scorer 与 Neo4j 同机，不变）
- [ ] 部署回路：pod 上 `git clone` 你的 repo；之后更新 = pod 上 `git pull` + 重启 uvicorn（agent 经 SSH 可代劳）
- [ ] 安装卡壳 >25 分钟（Java/GDS 版本纠缠）→ 切方案 β

**方案 β · 双 pod stock 镜像（零安装，α 卡死时用）**

- [ ] Pod N：custom template，镜像 `neo4j:5`，env：`NEO4J_AUTH=neo4j/<pw>`、`NEO4J_PLUGINS=["graph-data-science"]`、`NEO4J_dbms_security_procedures_unrestricted=gds.*`；Expose **TCP 7687**（记下 RunPod 分配的公网 ip:port → `NEO4J_URI=bolt://<ip>:<port>`）
- [ ] Pod S：PyTorch 模板跑 scorer（HTTP 8000 同上）
- [ ] 验证不走 Neo4j Browser（proxy 下 bolt websocket 会断）：直接在 Pod S 用 python driver 连公网 bolt 跑 `CALL gds.version()`
- [ ] 若两 pod 在同数据中心且账号有 Global Networking：改用 `<pod-id>.runpod.internal` 私网连，免公网 TCP

## 3. Python / Node 工具链（5 min）

- [ ] `python -m venv .venv && source .venv/bin/activate`
- [ ] `pip install fastapi uvicorn neo4j pandas requests python-dotenv anthropic openai`
      ｜验证：`python -c "import fastapi, neo4j, pandas; print('ok')"`
- [ ] `node -v`（SPA 用；没有就 `brew install node`）

## 4. RocketRide 冒烟（与 Track B 的 B1 同一件事，10 min）

- [ ] extension 里建最小 pipeline（chat/webhook source → 一个 LLM 节点 → respond）
- [ ] 本地跑通一次
- [ ] **一键部署到 cloud.rocketride.ai** —— 今天全场最不可预测的一步，务必在发 kickoff 前趟完
      ｜验证：`curl -X POST <endpoint>` 返回 200；把 URL 形态记进 `.env` 的 `PIPELINE_WEBHOOK_URL` 注释
- [ ] 卡住 >15 分钟 → 立刻抓 mentor（产品 3 周新，他们自己人就在场，这是最快解法）

## 5. Butterbase 连通性（5 min）

- [ ] Claude Code 里 Butterbase plugin/MCP 已连到你的 project
      ｜验证：让 agent 列一次 tables（空的也行）
- [ ] 用 `BUTTERBASE_API_KEY` 做一次任意表的写读（agent 代劳即可）
      ｜验证：insert → select 回来
- [ ] AI gateway 冒烟：经 gateway 发一条 completion；credits 仍为 $0 就在 `.env` 标注 `# R8 ACTIVE`，extract/judge 全走直连 key，别恋战

## 6. 绿板（全勾才发 kickoff prompt）

- [ ] `CALL gds.version()` 返回 ✅
- [ ] runpod proxy 已验证（http.server 8000 测试 curl 通），`SCORER_URL` 定型 ✅
- [ ] RocketRide cloud endpoint curl 200 ✅
- [ ] Butterbase 读写一次成功，keys 在 `.env` ✅
- [ ] LLM 调用通（gateway 或直连，二选一即可）✅
- [ ] docs 树就位，contracts.md 冻结 ✅
- [ ] `.env` 每个变量：有值，或标 `TBD-<owner>`（如 `SCORER_URL=TBD-A`）✅

绿板即刻：给 4 个 CLI 贴 OPS §7 kickoff prompt，开跑 v0.1。

---

## 附：`.env` 模板

```
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<现在就设一个强密码>
SCORER_URL=TBD-A            # https://<POD_ID>-8000.proxy.runpod.net
PIPELINE_WEBHOOK_URL=TBD-B  # B1 部署后填
BUTTERBASE_URL=
BUTTERBASE_API_KEY=         # bb_sk_ 开头 = secret key: 只进服务端, 永不进浏览器/git/prompt
GATEWAY_API_KEY=            # credits 到账后填
ANTHROPIC_API_KEY=          # R8 兜底
OPENAI_API_KEY=             # R8 兜底
```

## 附：常见坑速查

| 症状 | 原因 | 解 |
|---|---|---|
| `gds.version()` 报 unknown procedure | GDS jar 没进 plugins/ 或版本不配 | 确认 jar 在 `/workspace/neo4j/plugins/`；按官方兼容矩阵换 GDS 版本；改完 `neo4j restart` |
| LOAD CSV 找不到文件 | CSV 不在 import 目录 | 放 `/workspace/neo4j/import/`，Cypher 用 `file:///xxx.csv` |
| RocketRide 部署后 curl 超时 | scorer 还没就绪，pipeline 卡在 step3 | 先用 mock scorer（B3 本来就是 stub），SCORER_URL 就绪后再切 |
| proxy.runpod.net 返回 502/524 | scorer 没监听 0.0.0.0，或 8000 没在模板暴露 | `uvicorn app:app --host 0.0.0.0 --port 8000`；模板补端口需重启 pod |
| pod 重启后 Neo4j 没了 | 进程不自启 | 都装在 /workspace，数据没丢：`/workspace/neo4j/bin/neo4j start` 拉起来即可 |
| pod 半路被回收 | 用了 Spot | 今天全用 On-Demand，别省这几刀 |