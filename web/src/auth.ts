// GraphJudge SPA — email/password auth (contracts.md §4.5 / §4.7).
//
// Uses the Butterbase auth REST endpoints (/auth/{app_id}/login|signup) with a
// localStorage-persisted session — the "simplest email session" path sanctioned
// by the Track C card. (The official @butterbase/sdk was evaluated but it
// transitively imports node:crypto `randomUUID`, which does not build for the
// browser under Vite/Rollup; this REST wrapper is a drop-in that hits the same
// Butterbase auth service and yields a real end-user JWT.)
//
// The browser NEVER holds the server-side bb_sk_ secret (§4.7) — only the public
// app_id + api base and the end-user's own JWT.
import { AUTH_BASE } from "./config";

export type Session = {
  access_token: string;
  refresh_token?: string;
  user: { id: string; email: string; email_verified?: boolean };
};

const SESSION_KEY = "graphjudge.session";

function save(s: Session | null) {
  if (s) localStorage.setItem(SESSION_KEY, JSON.stringify(s));
  else localStorage.removeItem(SESSION_KEY);
}

export function getSession(): Session | null {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY) || "null");
  } catch {
    return null;
  }
}

export function getToken(): string | null {
  return getSession()?.access_token ?? null;
}

async function post(path: string, body: unknown) {
  const r = await fetch(`${AUTH_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await r.json().catch(() => ({}));
  return { ok: r.ok, status: r.status, data } as const;
}

export async function signIn(email: string, password: string): Promise<Session> {
  const { ok, status, data } = await post("/login", { email, password });
  if (!ok) throw new Error(data?.error?.message || data?.message || `login failed (${status})`);
  const s: Session = { access_token: data.access_token, refresh_token: data.refresh_token, user: data.user };
  save(s);
  return s;
}

export async function signUp(email: string, password: string): Promise<Session> {
  const { ok, status, data } = await post("/signup", { email, password });
  // 409 = account already exists → fall through to sign-in.
  if (!ok && status !== 409) {
    throw new Error(data?.error?.message || data?.message || `signup failed (${status})`);
  }
  // Butterbase issues tokens on login (not signup); login works without email
  // verification, so sign the new user straight in.
  return signIn(email, password);
}

export async function signOut(): Promise<void> {
  const token = getToken();
  if (token) {
    // best-effort server-side revoke; ignore failures
    fetch(`${AUTH_BASE}/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {});
  }
  save(null);
}
