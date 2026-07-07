## [18:46] D1 reference graph — done
做了: 生成 Track D 参考图谱首版，包含 `data/import/ref_entities.csv`、`data/import/ref_facts.csv` 与 `data/validate.py`。图谱覆盖 2023-2025 主流 LLM 生态的模型、机构、论文和 benchmark；只使用冻结关系词表，`functional=true` 仅用于 `developed_by` 和 `released_in`。
验证: `python data/validate.py` ->
```
benchmark assets not present; skipped D2/D3 checks
validated 161 entities
validated 332 facts
ALL CHECKS PASSED
```
模型来源: Codex GPT-5 生成与整理；未调用外部生成模型。
遗留/坑: `docs/contracts.md` 和版本 plan 脚手架仍未存在，本次按 `docs/DESIGN.md` 附录 A/B 与 `docs/OPS.md §4.6` 执行；D1 完成后按指令等待人类抽查，不启动 D2。
下一步: 人类抽查放行后开始 D2。

## [18:56] D2 controlled-corruption ledger — done
做了: 新增 `data/generate_benchmark.py`，固定随机种子 `7`，从参考图采样真填充并生成 `data/bench/bench_ledger.csv`。doc B 包含 M1 尾实体替换 x5 与 M2 数值扰动 x3；doc A 全真；doc B/C 维持约 70/30 真/假比例；doc E 为别名改写真样本。
验证: `python data/generate_benchmark.py` ->
```
generated 63 benchmark claims with seed 7
doc A: 10 claims (TRUE=10)
doc B: 27 claims (CONTRADICTED=8, TRUE=19)
doc C: 10 claims (FABRICATED_ENTITY=3, TRUE=7)
doc D: 6 claims (FABRICATED_CLUSTER=6)
doc E: 10 claims (TRUE=10)
```
模型来源: `bench_ledger.csv` 由确定性 Python 脚本生成；脚本由 Codex GPT-5 编写，未调用外部生成模型。
遗留/坑: 无。
下一步: D3。

## [18:56] D3 fabricated cases and prose docs — done
做了: 生成 `data/bench/docs/A.txt` 到 `E.txt`。doc C 含 3 个虚构实体声明；doc D 含 6 条只互相引用的虚构集群声明，未使用真实实体名；五篇英文散文每条断言独立成句，内容仅来自台账。
验证: `python data/validate.py` ->
```
validated 161 entities
validated 332 facts
ALL CHECKS PASSED
```
模型来源: `A.txt`、`B.txt`、`C.txt`、`D.txt`、`E.txt` 均由 `data/generate_benchmark.py` 的模板 verbalizer 生成；模板由 Codex GPT-5 编写，未调用外部生成模型。
遗留/坑: 无。
下一步: D4 optional。

## [18:56] D4 eval runner skeleton — done
做了: 新增 `eval/benchmark_runner.py`，读取台账与散文目录，构造 contracts §4.3 `/score` payload；支持真实 scorer URL，也支持 `mock://local` 冒烟。新增 `eval/llm_judge_baseline_prompt.md` 作为 LLM-judge 基线 prompt 草稿。
验证: `python eval/benchmark_runner.py --scorer-url mock://local` ->
```
doc A: sent 10 claims, expected_matches=10/10
doc B: sent 27 claims, expected_matches=27/27
doc C: sent 10 claims, expected_matches=10/10
doc D: sent 6 claims, expected_matches=6/6
doc E: sent 10 claims, expected_matches=10/10
overall expected_matches=63/63
scorer_url=mock://local
```
模型来源: runner 与 baseline prompt 草稿由 Codex GPT-5 编写，未调用外部生成模型。
遗留/坑: 真实 scorer 尚未接入；当前只用 mock URL 验证 runner 形状。
下一步: A track 可加载 `data/import/ref_entities.csv` 与 `data/import/ref_facts.csv`。
