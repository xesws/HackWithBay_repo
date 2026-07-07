// GraphJudge Track C — consume_credit (contracts.md §4.5)
//
// POST body: { user_id: string, job_id: string }
// Returns:   { ok: boolean, balance: number }
//
// Semantics: balance = SUM(delta) WHERE user_id. If balance > 0, insert a
// debit row (delta = -1, reason = 'consume') and return { ok: true, balance-1 };
// otherwise return { ok: false, balance }.
//
// Atomicity / no double-spend: the read + conditional insert are performed in a
// SINGLE SQL statement (one implicit transaction). A per-user transaction-scoped
// advisory lock (pg_advisory_xact_lock) serializes concurrent consumes for the
// same user, so two requests can never both observe balance > 0 and each debit.
// A data-modifying CTE always runs to completion, so `ins` fires exactly when
// bal.balance > 0.
export default async function handler(req: Request, ctx: any): Promise<Response> {
  const json = (data: unknown, status = 200) =>
    new Response(JSON.stringify(data), {
      status,
      headers: { "Content-Type": "application/json" },
    });

  let body: any;
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid_json" }, 400);
  }

  // Prefer the authenticated end-user id when present (can't be spoofed via body);
  // fall back to body.user_id for service-role (server-side pipeline) calls.
  const userId = ctx.user?.id ?? body?.user_id;
  const jobId = body?.job_id;
  if (!userId || !jobId) {
    return json({ error: "missing_user_id_or_job_id" }, 400);
  }

  const sql = `
    WITH lk AS (
      -- $2 is the user id as an explicit text param, used only for hashing so
      -- the advisory lock never constrains $1's type. $1 is used only in the
      -- "user_id = $1" / INSERT contexts, so it is inferred as the column type
      -- (uuid on the live schema, text after contract reconciliation) and the
      -- statement works against either. Both params receive the same value.
      SELECT pg_advisory_xact_lock(hashtext($2)) AS locked
    ),
    bal AS (
      SELECT COALESCE(SUM(delta), 0) AS balance
      FROM credits_ledger, lk
      WHERE user_id = $1
    ),
    ins AS (
      INSERT INTO credits_ledger (user_id, delta, reason)
      SELECT $1, -1, 'consume'
      FROM bal
      WHERE bal.balance > 0
      RETURNING 1
    )
    SELECT bal.balance AS balance, (EXISTS (SELECT 1 FROM ins)) AS consumed
    FROM bal;
  `;

  const result = await ctx.db.query(sql, [userId, userId]);
  const row = result.rows[0];
  const oldBalance = Number(row.balance);
  const consumed = row.consumed === true || row.consumed === "t" || row.consumed === "true";

  return consumed
    ? json({ ok: true, balance: oldBalance - 1 })
    : json({ ok: false, balance: oldBalance });
}
