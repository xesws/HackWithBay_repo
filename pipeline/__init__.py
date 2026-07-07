"""GraphJudge Track B — pipeline (product-facing webhook + claim extraction).

Public seams (see contracts.md §4.1 / §4.2 / §4.4):
  extract_claims.call_model(text) -> str   # swap-in point for a real LLM
  webhook.credit_gate(user_id)   -> dict    # swap-in point for C2 consume_credit
  webhook: SCORER_URL env        -> real A3 scorer POST {SCORER_URL}/score
"""
