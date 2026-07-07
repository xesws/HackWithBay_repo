// GraphJudge SPA — data seam (contracts.md §4.2 / §4.4 / §4.5).
import sample from "./sample_verdict.json";
import { getToken } from "./auth";
import { FN_BASE } from "./config";

export type Verdict = typeof sample;

// SEAM: today returns the static §4.2 sample verdict so the constellation is
// fully renderable without the backend. LATER this becomes:
//   POST {PIPELINE_WEBHOOK_URL} { user_id, job_id, text }  (§4.4)
// which returns a §4.2 verdict verbatim (credits consumed server-side).
export async function fetchVerdict(_text?: string): Promise<Verdict> {
  return sample as Verdict;
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
