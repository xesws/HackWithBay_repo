# GraphJudge — Demo 使用说明（评审/演示用）

> 一句话:粘贴一段关于「人」的文字(谁在哪工作、住哪、管谁、做什么项目),
> GraphJudge 用**知识图谱的拓扑结构**判定每条事实,渲染成一张「事实星座图」
> (绿=有据 / 红=矛盾 / 灰=孤儿 / 橙=编造集群)。

## 1. 打开

**https://graphjudge.butterbase.dev**

## 2. 登录(用下面现成的账号,**不要注册新号**)

登录页顶部有两个 tab:**「Sign in」** 和「Create account」。
默认可能停在「Create account」——请手动点到 **「Sign in」**,用现成账号登录。

| 账号 (email) | 密码 | 余额 | 用途 |
|---|---|---|---|
| `demo-999@graphjudge.demo` | `GraphJudge!2026` | **999 credits** | 主演示号,每次 Verify 扣 1 |
| `demo-empty@graphjudge.demo` | `GraphJudge!2026` | **0 credits** | 演示「余额不足」拦截(付费闭环) |

> ⚠️ **别自己注册新账号**:新号默认 0 余额,Verify 会返回 “insufficient credits”
> ——这是**设计如此**的付费闭环(裁决:不做 signup 免费额度 hook)。**演示一律用上面
> 提供的 demo 账号。**
>
> 这两个是一次性 demo 账号密码(演示道具,非机密;真正的 `bb_sk_` 服务密钥与
> 用户 JWT 仍只在服务端/`.env`,禁止入库)。

## 3. 演示(用 `demo-999` 登录后)

把下面这段**原样粘贴**进输入框,点 **Verify**:

```
Corwin Mavik manages Jessa Minlow. Arlen Veyro owns a pet named Bramble. Gavo Rellin lives in Dovemarsh. Della Quorin was born in 1992. Brisa Nalore is married to Corwin Mavik. Mira Vell works at Aster Quay Group. Zavren Pell works at Cindrel Motive Office. Ostia Kel works at Cindrel Motive Office. Zavren Pell manages Ostia Kel. Ostia Kel leads Project Sablewick. Noll Varen leads Project Sablewick. Noll Varen manages Zavren Pell.
```

会得到 **3 绿 / 2 红 / 1 灰 / 6 橙**(doc_score ≈ 0.58):

| 颜色 | 状态 | 例子 | 为什么 |
|---|---|---|---|
| 🟢 绿 | SUPPORTED | Corwin 管理 Jessa;Arlen 养 Bramble;Gavo 住 Dovemarsh | 图里有据 |
| 🔴 红 | CONTRADICTED | 「Della 生于 1992」(真值 **1990**);「Brisa 嫁给 Corwin」(真值 **Arlen Veyro**) | functional 关系冲突 |
| ⚪ 灰 | UNGROUNDED | 「Mira Vell 在 Aster Quay Group 工作」 | 人是编造的,但挂在一个真实机构上(孤儿,非集群) |
| 🟠 橙 | UNGROUNDED(集群) | Cindrel Motive Office / Project Sablewick 那一圈(Zavren/Ostia/Noll) | 6 条事实只互相引用、与真实图零连接 → **编造集群**(核心卖点) |

**点任意节点** → 右侧看该判定的证据(图路径 / 真值)。

## 4. 演示「余额不足」拦截(可选)

用 `demo-empty@graphjudge.demo` 登录,粘同样的文字点 Verify →
返回 **“insufficient credits”**,星座图不渲染。这展示了「按次计费」的服务端信用闸。

## 5. 底下发生了什么(30 秒讲解)

```
粘贴文字
  → SPA 带 JWT POST /verify (RunPod:8888)
  → 服务端 consume_credit 扣 1 信用 (Butterbase fn)
  → gemini-3.5-flash 抽取原子 claim (个人域 prompt)
  → 真 Neo4j + GDS 打分:直连 Cypher 匹配 + gds.wcc 检测孤儿/集群
  → 返回 §4.2 verdict → 前端渲染星座图
```

核心主张:**我们用图判 LLM,而不是用 LLM 判 LLM** —— 判定确定性、可审计
(每条判定带图路径证据)、核心链路无 LLM。

## 6. 故障自救:Verify 报错 / 连不上服务器

打分服务(scorer)跑在 pod 的 `:8888`。若 Verify 一直转圈或报网络错,多半是
scorer 挂了(比如 pod 重启)。**一条命令拉起来**(在 Claude Code 输入框里前面加 `!`,
或直接在 pod 终端跑):

```
! bash scripts/run_scorer.sh
```

看到 `scorer UP: {... "entities":51,"facts":107 ...}` 就恢复了(个人域已就位)。
日志在 `scorer.log`。健康检查:`curl -s http://127.0.0.1:8888/health`。

> scorer 用 `setsid`+`nohup` 独立会话启动,正常情况下会随 pod 一直活着;
> 上面这条只是万一它没了时的一键重启。

---

*参考图当前载入的是 Eval-2「个人域」基准(51 实体 / 107 事实)。AI 域记分牌
(graph 100% vs LLM 100% 检测,graph 独赢 3-way 精确)见 `eval/scoreboard_results.md`。*
