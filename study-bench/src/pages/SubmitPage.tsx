import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listRuns, startRun } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { RunSummary } from "../types";
import { c, font, eyebrow, hairline } from "../theme";

const EXAMPLES = [
  "How logistic regression actually works",
  "The French Revolution, cause to consequence",
  "Photosynthesis for a first exam",
  "What a Fourier transform is doing",
];

export default function SubmitPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [topic, setTopic] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<RunSummary[]>([]);
  const taRef = useRef<HTMLTextAreaElement>(null);

  const fetchHistory = useCallback(async () => {
    try {
      setHistory(await listRuns());
    } catch {
      /* backend may be down; the ledger just stays empty */
    }
  }, []);

  // Refetch when the signed-in user changes so the list reflects whose topics these are.
  useEffect(() => {
    fetchHistory();
    window.addEventListener("focus", fetchHistory);
    return () => window.removeEventListener("focus", fetchHistory);
  }, [fetchHistory, user]);

  const submit = async () => {
    const t = topic.trim();
    if (!t) {
      setError("Type a topic first — a sentence works better than a single word.");
      taRef.current?.focus();
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const { run_id } = await startRun(t);
      navigate(`/run/${run_id}`);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Couldn't reach the study server. Check it's running on port 8000, then try again."
      );
      setSubmitting(false);
    }
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
  };

  return (
    <main style={page}>
      {/* Masthead — the product names itself, drawn as a ruled header. */}
      <header style={masthead} className="animate-rise">
        <div style={mastheadTop}>
          <span style={eyebrow}>Study Bench</span>
          <span style={{ ...eyebrow, color: c.reagent }}>· learn anything</span>
        </div>
        <div style={topRule} className="rule-draw" />
      </header>

      {/* The intake — the focal object of the page: a requisition slip for a topic. */}
      <section style={intake} className="animate-rise">
        <label htmlFor="topic" style={intakeLead}>
          What do you want to
          <br />
          <em style={{ fontStyle: "italic", color: c.reagent }}>understand</em> today?
        </label>

        <p style={intakeSub}>
          Give one topic and you'll get a full study set back — clear notes, flashcards to
          test yourself, and a short narrated video. Ready in a few minutes.
        </p>

        <div style={slip}>
          <span style={slipTick}>topic ▸</span>
          <textarea
            id="topic"
            ref={taRef}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="e.g. How does gradient descent find a minimum?"
            rows={2}
            autoFocus
            style={textarea}
          />
        </div>

        <div style={exampleRow}>
          {EXAMPLES.map((ex) => (
            <button key={ex} onClick={() => setTopic(ex)} style={chip}>
              {ex}
            </button>
          ))}
        </div>

        {error && (
          <p role="alert" style={errorLine}>
            {error}
          </p>
        )}

        <button onClick={submit} disabled={submitting} style={{ ...cta, opacity: submitting ? 0.6 : 1 }}>
          {submitting ? "Starting…" : "Study this →"}
          <span style={ctaHint}>⌘↵</span>
        </button>
      </section>

      {/* Recent topics — quiet, structural, numbered because it IS a sequence.
          When signed in it's your saved history; signed out it's this session's runs. */}
      <section style={ledger}>
        <div style={ledgerHead}>
          <span style={eyebrow}>{user ? "Your topics" : "Recent topics"}</span>
          {user ? (
            <button onClick={() => navigate("/history")} style={ledgerRefresh}>
              see all
            </button>
          ) : (
            <button onClick={fetchHistory} style={ledgerRefresh}>
              refresh
            </button>
          )}
        </div>

        {history.length === 0 ? (
          <p style={emptyLedger}>
            {user
              ? "Nothing here yet. The topics you study are saved to your account."
              : "Nothing here yet. Sign in to keep your studied topics across visits."}
          </p>
        ) : (
          <ol style={ledgerList}>
            {history.map((r, i) => (
              <li key={r.run_id}>
                <button
                  onClick={() =>
                    navigate(r.status === "complete" ? `/package/${r.run_id}` : `/run/${r.run_id}`)
                  }
                  style={ledgerRow}
                >
                  <span style={ledgerNum}>{String(history.length - i).padStart(3, "0")}</span>
                  <span style={ledgerTopic}>{r.topic}</span>
                  <span style={{ ...ledgerStatus, color: statusColor(r.status) }}>{statusWord(r.status)}</span>
                </button>
              </li>
            ))}
          </ol>
        )}
      </section>
    </main>
  );
}

function statusColor(s: string) {
  if (s === "complete") return c.reagent;
  if (s === "error") return c.flag;
  return c.inkSoft; // running or cancelled
}
function statusWord(s: string) {
  if (s === "complete") return "ready";
  if (s === "error") return "failed";
  if (s === "cancelled") return "stopped";
  return "working…";
}

// ── styles ────────────────────────────────────────────────────────────────────

const page: React.CSSProperties = {
  maxWidth: 760,
  margin: "0 auto",
  padding: "40px 22px 80px",
};

const masthead: React.CSSProperties = { marginBottom: 44 };
const mastheadTop: React.CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  gap: 8,
  marginBottom: 10,
};
const topRule: React.CSSProperties = {
  height: 2,
  backgroundColor: c.ink,
  transformOrigin: "left",
};

const intake: React.CSSProperties = { marginBottom: 56 };

const intakeLead: React.CSSProperties = {
  display: "block",
  fontFamily: font.display,
  fontSize: "clamp(40px, 8vw, 68px)",
  fontWeight: 600,
  lineHeight: 0.98,
  letterSpacing: "-0.02em",
  color: c.ink,
  marginBottom: 18,
  overflowWrap: "break-word",
};

const intakeSub: React.CSSProperties = {
  fontSize: 16,
  color: c.inkSoft,
  maxWidth: 520,
  marginBottom: 26,
};

const slip: React.CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  gap: 12,
  border: `1px solid ${c.ink}`,
  backgroundColor: c.paperCard,
  padding: "16px 18px",
};

const slipTick: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 13,
  fontWeight: 700,
  color: c.reagent,
  paddingTop: 4,
  flexShrink: 0,
};

const textarea: React.CSSProperties = {
  flex: 1,
  border: "none",
  outline: "none",
  resize: "none",
  background: "transparent",
  fontFamily: font.body,
  fontSize: 19,
  lineHeight: 1.4,
  color: c.ink,
};

const exampleRow: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 8,
  marginTop: 14,
};

const chip: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 12,
  color: c.inkSoft,
  border: `1px solid ${c.rule}`,
  padding: "9px 12px",
  lineHeight: 1.3,
  transition: "border-color 0.15s, color 0.15s",
};

const errorLine: React.CSSProperties = {
  color: c.flag,
  fontFamily: font.mono,
  fontSize: 13,
  marginTop: 18,
};

const cta: React.CSSProperties = {
  marginTop: 26,
  width: "100%",
  backgroundColor: c.reagent,
  color: c.paper,
  fontFamily: font.body,
  fontSize: 17,
  fontWeight: 600,
  padding: "16px 20px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 10,
  transition: "background-color 0.15s",
};

const ctaHint: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 12,
  opacity: 0.7,
};

const ledger: React.CSSProperties = { borderTop: hairline, paddingTop: 22 };
const ledgerHead: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "baseline",
  marginBottom: 12,
};
const ledgerRefresh: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: c.reagent,
};
const emptyLedger: React.CSSProperties = { color: c.inkFaint, fontSize: 14, padding: "8px 0" };

const ledgerList: React.CSSProperties = { listStyle: "none" };
const ledgerRow: React.CSSProperties = {
  width: "100%",
  display: "flex",
  alignItems: "center",
  gap: 14,
  padding: "11px 0",
  borderBottom: `1px solid ${c.ruleSoft}`,
  textAlign: "left",
};
const ledgerNum: React.CSSProperties = { fontFamily: font.mono, fontSize: 12, color: c.inkFaint, flexShrink: 0 };
const ledgerTopic: React.CSSProperties = {
  flex: 1,
  minWidth: 0,
  fontSize: 15,
  color: c.ink,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};
const ledgerStatus: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  flexShrink: 0,
};
