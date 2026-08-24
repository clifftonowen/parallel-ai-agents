import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listRuns } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { RunSummary } from "../types";
import { c, font, hairline } from "../theme";

// Your filed topics. A ruled ledger — numbered because it's a real sequence over time.
export default function HistoryPage() {
  const { user, ready } = useAuth();
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Requires an account; send anonymous visitors to sign in, remembering where to return.
  useEffect(() => {
    if (ready && !user) navigate("/signin", { state: { from: "/history" }, replace: true });
  }, [ready, user, navigate]);

  useEffect(() => {
    if (!user) return;
    listRuns()
      .then(setRuns)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Couldn't load your history."));
  }, [user]);

  if (!ready) {
    return (
      <main style={page}>
        <p style={sub}>Opening your card…</p>
      </main>
    );
  }
  if (!user) return null;

  const openRun = (r: RunSummary) =>
    navigate(r.status === "complete" ? `/package/${r.run_id}` : `/run/${r.run_id}`);

  return (
    <main style={page}>
      <button onClick={() => navigate("/")} style={backLink}>
        ← study something new
      </button>

      <h1 style={title} className="animate-rise">
        Your topics
      </h1>
      <p style={sub}>Everything you've studied, filed under {user.email}.</p>

      {error && <p style={errorLine}>{error}</p>}

      {runs === null ? (
        <p style={sub}>Fetching your topics…</p>
      ) : runs.length === 0 ? (
        <div style={emptyBox}>
          <p style={emptyLead}>Your card is empty for now.</p>
          <p style={emptyBody}>
            Study a topic and it'll be filed here — ready to reopen whenever you come back.
          </p>
          <button onClick={() => navigate("/")} style={emptyCta}>
            Study a topic →
          </button>
        </div>
      ) : (
        <ol style={list}>
          {(runs ?? []).map((r, i) => (
            <li key={r.run_id}>
              <button onClick={() => openRun(r)} style={row}>
                <span style={num}>{String((runs?.length ?? 0) - i).padStart(3, "0")}</span>
                <span style={topic}>{r.topic}</span>
                <span style={{ ...state, color: statusColor(r.status) }}>{statusWord(r.status)}</span>
              </button>
            </li>
          ))}
        </ol>
      )}
    </main>
  );
}

function statusColor(s: string) {
  if (s === "complete") return c.reagent;
  if (s === "error") return c.flag;
  return c.inkSoft;
}
function statusWord(s: string) {
  if (s === "complete") return "ready";
  if (s === "error") return "failed";
  if (s === "cancelled") return "stopped";
  return "working…";
}

// ── styles ────────────────────────────────────────────────────────────────────

const page: React.CSSProperties = { maxWidth: 680, margin: "0 auto", padding: "34px 22px 90px" };
const backLink: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 12,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  color: c.inkSoft,
  marginBottom: 24,
  display: "inline-block",
};
const title: React.CSSProperties = {
  fontFamily: font.display,
  fontSize: "clamp(32px, 6vw, 48px)",
  fontWeight: 600,
  lineHeight: 1.02,
  letterSpacing: "-0.02em",
  color: c.ink,
};
const sub: React.CSSProperties = { fontSize: 15, color: c.inkSoft, marginTop: 10 };
const errorLine: React.CSSProperties = { color: c.flag, fontFamily: font.mono, fontSize: 13, marginTop: 16 };

const list: React.CSSProperties = { listStyle: "none", marginTop: 30, borderTop: hairline };
const row: React.CSSProperties = {
  width: "100%",
  display: "flex",
  alignItems: "center",
  gap: 14,
  padding: "15px 2px",
  borderBottom: `1px solid ${c.ruleSoft}`,
  textAlign: "left",
};
const num: React.CSSProperties = { fontFamily: font.mono, fontSize: 12, color: c.inkFaint, flexShrink: 0 };
const topic: React.CSSProperties = {
  flex: 1,
  minWidth: 0,
  fontSize: 16,
  color: c.ink,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};
const state: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  flexShrink: 0,
};

const emptyBox: React.CSSProperties = { marginTop: 40, borderTop: hairline, paddingTop: 28 };
const emptyLead: React.CSSProperties = {
  fontFamily: font.display,
  fontSize: 24,
  fontWeight: 600,
  color: c.ink,
};
const emptyBody: React.CSSProperties = { fontSize: 15, color: c.inkSoft, marginTop: 8, maxWidth: 420 };
const emptyCta: React.CSSProperties = {
  marginTop: 20,
  backgroundColor: c.reagent,
  color: c.paper,
  fontFamily: font.body,
  fontSize: 15,
  fontWeight: 600,
  padding: "12px 22px",
};
