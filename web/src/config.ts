// GraphJudge SPA config. NOTE (contracts.md §4.7): the browser NEVER holds the
// server-side bb_sk_ secret. It uses only the public app_id + api base and an
// end-user JWT obtained via email/password auth.
export const APP_ID = "app_r1568bo1iteg";
export const API_URL = "https://api.butterbase.ai";
export const AUTH_BASE = `${API_URL}/auth/${APP_ID}`;
export const FN_BASE = `${API_URL}/v1/${APP_ID}/fn`;
// Track B /verify (Shape 2) — the product webhook (contracts §4.4). The SPA POSTs
// {user_id, text} and renders the returned §4.2 verdict (credits consumed server-side).
export const VERIFY_URL = "https://ohld8gp5nmkcu7-8888.proxy.runpod.net/verify";
