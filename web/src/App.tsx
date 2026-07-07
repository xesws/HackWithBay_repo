import { useEffect, useState } from "react";
import Constellation from "./Constellation";
import { fetchVerdict, fetchBalance, type Verdict } from "./api";
import { getSession, signIn, signUp, signOut, type Session } from "./auth";

const LEGEND = [
  { hex: "#22c55e", label: "SUPPORTED", sub: "grounded core" },
  { hex: "#ef4444", label: "CONTRADICTED", sub: "conflict edge" },
  { hex: "#9ca3af", label: "UNGROUNDED", sub: "orphan node" },
  { hex: "#f59e0b", label: "UNGROUNDED", sub: "fabricated cluster" },
];

function cidOf(node: any): string | null {
  const id = node?.id ?? "";
  return id.startsWith("claim:") ? id.slice("claim:".length) : null;
}

function LoginView({ onSession }: { onSession: (s: Session) => void }) {
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const s = mode === "in" ? await signIn(email, pw) : await signUp(email, pw);
      onSession(s);
    } catch (ex: any) {
      setErr(ex?.message || "authentication failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-shell">
      <form className="card login-card" onSubmit={submit}>
        <h1 className="brand">GraphJudge</h1>
        <p className="tagline">Graph-structural factuality evaluation.</p>
        <div className="tabs">
          <button type="button" className={mode === "in" ? "tab active" : "tab"} onClick={() => setMode("in")}>
            Sign in
          </button>
          <button type="button" className={mode === "up" ? "tab active" : "tab"} onClick={() => setMode("up")}>
            Create account
          </button>
        </div>
        <label>Email</label>
        <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required placeholder="you@example.com" />
        <label>Password</label>
        <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} required placeholder="••••••••" />
        {err && <div className="err">{err}</div>}
        <button className="primary" type="submit" disabled={busy}>
          {busy ? "…" : mode === "in" ? "Sign in" : "Create account"}
        </button>
        <p className="hint">Password: 8+ chars incl. upper, lower, number, special.</p>
      </form>
    </div>
  );
}

function EvidencePanel({ verdict, selected }: { verdict: Verdict; selected: any }) {
  const claims: any[] = (verdict as any).claims ?? [];

  if (!selected) {
    return (
      <div className="panel-empty">
        <p>Click a node in the constellation to inspect its evidence.</p>
      </div>
    );
  }

  const cid = cidOf(selected);
  const claim = cid ? claims.find((c) => c.cid === cid) : null;

  // For entity nodes, gather the claims that touch this entity via graph edges.
  let related: any[] = [];
  if (!claim) {
    const edges: any[] = (verdict as any).graph?.edges ?? [];
    const set = new Set<string>();
    for (const e of edges) {
      const other = e.src === selected.id ? e.dst : e.dst === selected.id ? e.src : null;
      if (other && String(other).startsWith("claim:")) set.add(String(other).slice("claim:".length));
    }
    related = [...set].map((c) => claims.find((x) => x.cid === c)).filter(Boolean);
  }

  return (
    <div className="panel">
      <div className="panel-head">
        <span className={`swatch swatch-${selected.color}`} />
        <div>
          <div className="panel-title">{selected.label ?? selected.id}</div>
          <div className="panel-sub">{selected.kind} · {selected.id}</div>
        </div>
      </div>

      {claim && <ClaimEvidence claim={claim} />}

      {!claim && related.length > 0 && (
        <>
          <div className="section-label">Claims involving this entity</div>
          {related.map((c: any) => (
            <ClaimEvidence key={c.cid} claim={c} compact />
          ))}
        </>
      )}

      {!claim && related.length === 0 && (
        <p className="muted">No claim evidence attached to this entity node.</p>
      )}
    </div>
  );
}

function ClaimEvidence({ claim, compact }: { claim: any; compact?: boolean }) {
  const ev = claim.evidence ?? {};
  const statusClass = claim.status?.toLowerCase();
  return (
    <div className={compact ? "claim compact" : "claim"}>
      <div className="claim-text">“{claim.text}”</div>
      <div className="badges">
        <span className={`badge status-${statusClass}`}>{claim.status}</span>
        {claim.cluster_flag && <span className="badge cluster">fabricated cluster</span>}
        <span className="badge dim">grounding {claim.grounding_ratio}</span>
      </div>
      <div className="ev-grid">
        <div className="ev-key">type</div>
        <div className="ev-val">{ev.type ?? "—"}</div>
        <div className="ev-key">truth</div>
        <div className="ev-val">{ev.truth ?? "—"}</div>
        <div className="ev-key">path</div>
        <div className="ev-val path">
          {(ev.path ?? []).map((p: string, i: number) => (
            <span key={i}>
              {i > 0 && <span className="arrow"> → </span>}
              <span className="hop">{p}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState<Session | null>(getSession());
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [selected, setSelected] = useState<any>(null);
  const [balance, setBalance] = useState<number | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  async function verify() {
    if (!text.trim() || !session) return;
    setBusy(true);
    setErr("");
    try {
      const v = await fetchVerdict(text, session.user.id);
      setVerdict(v);
      setSelected(null);
      fetchBalance(session.user.id).then(setBalance).catch(() => {});
    } catch (ex: any) {
      setErr(ex?.message || "verify failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!session) return;
    fetchVerdict().then(setVerdict);
    fetchBalance(session.user.id)
      .then(setBalance)
      .catch(() => setBalance(null));
  }, [session]);

  if (!session) return <LoginView onSession={setSession} />;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand-row">
          <span className="dot" />
          <strong>GraphJudge</strong>
          <span className="muted">fact constellation</span>
        </div>
        <div className="topbar-right">
          <span className="balance">
            credits: <b>{balance ?? "—"}</b>
          </span>
          <span className="muted email">{session.user.email}</span>
          <button
            className="ghost"
            onClick={() => {
              signOut();
              setSession(null);
              setVerdict(null);
              setSelected(null);
              setBalance(null);
            }}
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="legend">
        {LEGEND.map((l, i) => (
          <span className="legend-item" key={i}>
            <span className="swatch" style={{ background: l.hex }} />
            <b>{l.label}</b>
            <span className="muted">· {l.sub}</span>
          </span>
        ))}
        {verdict && (
          <span className="doc-score">
            doc_score <b>{(verdict as any).doc_score}</b>
          </span>
        )}
      </div>

      <section style={{ padding: "0 20px 12px", display: "flex", flexDirection: "column", gap: 8 }}>
        <textarea
          placeholder="Paste an LLM answer about the AI industry (with planted errors), then Verify…"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          style={{ width: "100%", background: "#0f1117", color: "#e5e7eb", border: "1px solid #333", borderRadius: 8, padding: 10, fontFamily: "inherit", fontSize: 14, resize: "vertical", boxSizing: "border-box" }}
        />
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <button className="primary" onClick={verify} disabled={busy || !text.trim()} style={{ width: "auto", padding: "8px 18px" }}>
            {busy ? "scoring…" : "Verify"}
          </button>
          {err && <span className="err">{err}</span>}
        </div>
      </section>

      <main className="stage">
        <section className="graph-col">
          {verdict ? (
            <Constellation verdict={verdict} selectedId={selected?.id ?? null} onSelect={setSelected} />
          ) : (
            <div className="loading">loading verdict…</div>
          )}
        </section>
        <aside className="side-col">
          {verdict && <EvidencePanel verdict={verdict} selected={selected} />}
        </aside>
      </main>
    </div>
  );
}
