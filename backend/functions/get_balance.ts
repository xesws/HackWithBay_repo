// GraphJudge Track C — get_balance (contracts.md §4.5)
//
// POST body: { user_id: string }
// Returns:   { balance: number }   where balance = SUM(delta) WHERE user_id.
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

  // Prefer the authenticated end-user id when present; fall back to body.user_id
  // for service-role calls.
  const userId = ctx.user?.id ?? body?.user_id;
  if (!userId) {
    return json({ error: "missing_user_id" }, 400);
  }

  const result = await ctx.db.query(
    `SELECT COALESCE(SUM(delta), 0) AS balance FROM credits_ledger WHERE user_id = $1`,
    [userId],
  );
  const balance = Number(result.rows[0].balance);
  return json({ balance });
}
