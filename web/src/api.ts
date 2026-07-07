// GraphJudge SPA — data seam (contracts.md §4.2 / §4.4 / §4.5).
import sample from "./sample_verdict.json";
import { getToken } from "./auth";
import { FN_BASE, VERIFY_URL } from "./config";

export type Verdict = typeof sample;

// POST {VERIFY_URL} {user_id, text} -> §4.2 verdict (contracts §4.4; credits
// consumed server-side). No text (initial load) -> the static sample so the
// constellation renders immediately.
export async function fetchVerdict(text?: string, userId?: string): Promise<Verdict> {
  if (!text || !text.trim()) return sample as Verdict;
  const r = await fetch(VERIFY_URL, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId ?? "anonymous", text }),
  });
  if (!r.ok) throw new Error(`verify failed (${r.status})`);
  const d = await r.json();
  if ((d as any).error === "insufficient_credits") throw new Error("insufficient credits — top up to verify");
  if ((d as any).error) throw new Error(String((d as any).error));
  return d as Verdict;
}

// Balance via the get_balance serverless function (§4.5), authed with the
// end-user JWT. The browser never calls the DB directly.
export async function fetchBalance(userId: string): Promise<number> {
  const token = getToken();
  const r = await fetch(`${FN_BASE}/get_balance`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!r.ok) throw new Error(`get_balance failed (${r.status})`);
  const d = await r.json();
  return d.balance;
}
