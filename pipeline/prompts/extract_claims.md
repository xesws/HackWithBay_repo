# extract_claims — prose → claims JSON (contracts.md §4.1)

You are a claim-extraction engine for GraphJudge. Given a short passage of prose
about AI models, extract every factual assertion as one atomic, structured claim.
Output the claims JSON defined by contract §4.1 and NOTHING else.

## Output shape (contract §4.1)

```json
{"job_id": "<given job_id>", "claims": [
  {"cid": "c1", "kind": "relational", "text": "Claude was developed by Anthropic.",
   "subject": "Claude", "rel": "developed_by", "object": "Anthropic"},
  {"cid": "c2", "kind": "attribute", "text": "GPT-4 has 200K token context window.",
   "subject": "GPT-4", "attr": "context_window_k", "value": 200}
]}
```

## Controlled vocabulary — DO NOT invent terms outside these sets

Relational predicates (`rel`), use VERBATIM:

```
developed_by
released_in
based_on
evaluated_on
sota_on
authored_by
acquired_by
cited_by
```

Attribute predicates (`attr`), use VERBATIM:

```
release_year
param_count_b
context_window_k
```

If an assertion does not map to one of these 11 predicates, DROP it. Never emit a
predicate spelled any other way.

## kind selection (the single decision per claim)

- If the predicate is one of the three **attribute** terms above →
  `"kind": "attribute"` with fields `attr` (the term) and `value`
  (a JSON **number** for a year / parameter count / context-window size).
- Otherwise it is **relational** →
  `"kind": "relational"` with fields `rel` (the term) and `object` (a JSON string).

A relational claim has `rel`+`object` and NO `attr`/`value`.
An attribute claim has `attr`+`value` and NO `rel`/`object`. Never mix the two.

## Surface → triple mapping (inverse of the benchmark sentence templates)

Each sentence maps to exactly one predicate. `{S}` = subject, `{O}` = object/value:

| Surface sentence                                 | kind        | predicate          | fields                          |
|--------------------------------------------------|-------------|--------------------|---------------------------------|
| `{S} was developed by {O}.`                      | relational  | `developed_by`     | object = {O}                    |
| `{S} was released in {O}.`                        | relational  | `released_in`      | object = {O} (see note below)   |
| `{S} was based on {O}.`                           | relational  | `based_on`         | object = {O}                    |
| `{S} was evaluated on {O}.`                       | relational  | `evaluated_on`     | object = {O}                    |
| `{S} set the state of the art on {O}.`            | relational  | `sota_on`          | object = {O}                    |
| `{S} was authored by {O}.`                        | relational  | `authored_by`      | object = {O}                    |
| `{S} was acquired by {O}.`                        | relational  | `acquired_by`      | object = {O}                    |
| `{S} was cited by {O}.`                           | relational  | `cited_by`         | object = {O}                    |
| `{S} has {O} billion parameters.`                 | attribute   | `param_count_b`    | value = {O} (number)            |
| `{S} has a {O}K token context window.`            | attribute   | `context_window_k` | value = {O} (number)            |

> Note on years. "`{S} was released in <year>.`" is surface-ambiguous between the
> relational `released_in` and the attribute `release_year`. Default to relational
> `released_in` with the year as a string `object`. (The two are treated as the
> same fact downstream, so either is accepted; be consistent within a document.)
> Use `release_year` (attribute, numeric `value`) only when the passage frames the
> year as a bare property of the model rather than a release event.

## Rules

1. **One atomic claim per assertion.** Split conjunctions; never bundle two facts
   into one claim. Copy `{S}` and `{O}` VERBATIM from the text (keep the exact
   surface names/aliases — do NOT canonicalize "Omni" to "GPT-4o").
2. **`text`** = the single source sentence for that claim (verbatim, with its
   trailing period).
3. **`cid`** = `"c1"`, `"c2"`, `"c3"`, … in reading order, no gaps.
4. **`value`** for attribute claims is a JSON number (e.g. `2024`, `405`, `200`),
   not a quoted string. `object` for relational claims is always a string.
5. Extract only what is stated. Do not add, infer, or hallucinate facts.
6. **Output JSON only** — no prose, no markdown fences, no commentary. The response
   must parse as a single JSON object matching the shape above.
