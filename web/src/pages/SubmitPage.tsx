import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listRuns, startRun } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { RunMode, RunSummary } from "../types";
import { c, font, eyebrow, hairline, layout, size, space, display } from "../theme";

// Which orchestrator runs the pipeline. Carried over from the benchmark
// dashboard, which was the only place this could be chosen before the two
// front-ends merged. "All three" runs them in sequence — roughly 36 minutes
// and 3x the token spend — so it is never the default.
const MODES: { value: RunMode; label: string; note: string }[] = [
  { value: "async", label: "Async", note: "asyncio — the default path" },
  { value: "adk", label: "ADK", note: "Google ADK agent graph" },
  { value: "original", label: "Threads", note: "ThreadPoolExecutor baseline" },
  { value: "all", label: "All three", note: "sequential — slow and expensive" },
];

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
  // Video assembly is single-threaded ffmpeg and ~80% of a run's wall time.
  // Off by default: notes, flashcards and both PDFs land in about two minutes
  // instead of ten, which is the difference between watching it work and
  // walking away.
  const [includeVideo, setIncludeVideo] = useState(false);
  const [mode, setMode] = useState<RunMode>("async");
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
      const { run_id } = await startRun(t, includeVideo, mode);
      navigate(`/run/${run_id}`);
    } catch (err: unknown) {
      setError(
        err instanceof Error
          ? err.message
          : "Couldn't reach the study server. Make sure the backend is running, then try again."
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
          <span style={{ ...eyebrow, color: c.inkFaint }}>· learn anything</span>
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

        <div style={modeRow} role="radiogroup" aria-label="Orchestrator">
          {MODES.map((m) => (
            <button
              key={m.value}
              onClick={() => setMode(m.value)}
              title={m.note}
              aria-pressed={mode === m.value}
              style={{ ...modeBtn, ...(mode === m.value ? modeBtnActive : {}) }}
            >
              {m.label}
            </button>
          ))}
        </div>

        <label style={videoToggle}>
          <input
            type="checkbox"
            checked={includeVideo}
            onChange={(e) => setIncludeVideo(e.target.checked)}
          />
          <span>
            Include narrated video
            <span style={videoToggleHint}>
              {includeVideo ? " — adds roughly 8 minutes" : " — about 2 minutes without it"}
            </span>
          </span>
        </label>
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
            <button onClick={() => navigate("/library")} style={ledgerRefresh}>
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
                    navigate(r.status === "complete" ? `/session/${r.run_id}` : `/run/${r.run_id}`)
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
  maxWidth: layout.shell,
  margin: "0 auto",
  padding: `${space.lg}px ${layout.gutter}px ${space.page}px`,
};

const masthead: React.CSSProperties = { marginBottom: space.xxl };
const mastheadTop: React.CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  gap: space.sm,
  marginBottom: space.md,
};
const topRule: React.CSSProperties = {
  height: 2,
  backgroundColor: c.ink,
  transformOrigin: "left",
};

const intake: React.CSSProperties = { marginBottom: space.section };

const intakeLead: React.CSSProperties = {
  display: "block",
  fontFamily: font.display,
  fontSize: display,
  fontWeight: 600,
  lineHeight: 0.98,
  letterSpacing: "-0.02em",
  color: c.ink,
  marginBottom: space.base,
  overflowWrap: "break-word",
};

const intakeSub: React.CSSProperties = {
  fontSize: size.lead,
  color: c.inkSoft,
  maxWidth: layout.measure,
  marginBottom: space.lg,
};

const slip: React.CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  gap: space.md,
  border: `1px solid ${c.ink}`,
  backgroundColor: c.paperCard,
  padding: `${space.base}px ${space.base}px`,
};

const slipTick: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.small,
  fontWeight: 700,
  color: c.inkFaint,
  paddingTop: space.xs,
  flexShrink: 0,
};

const textarea: React.CSSProperties = {
  flex: 1,
  border: "none",
  outline: "none",
  resize: "none",
  background: "transparent",
  fontFamily: font.body,
  fontSize: size.title,
  lineHeight: 1.4,
  color: c.ink,
};

const exampleRow: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: space.sm,
  marginTop: space.base,
};

const chip: React.CSSProperties = {
  fontFamily: font.body,
  fontSize: size.body,
  color: c.inkSoft,
  border: `1px solid ${c.rule}`,
  padding: `${space.sm}px ${space.md}px`,
  lineHeight: 1.3,
  transition: "border-color 0.15s, color 0.15s",
};

const modeRow: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: space.sm,
  marginTop: space.base,
};

const modeBtn: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.small,
  color: c.inkSoft,
  border: `1px solid ${c.rule}`,
  padding: `${space.sm}px ${space.md}px`,
  transition: "border-color 0.15s, color 0.15s, background-color 0.15s",
};

const modeBtnActive: React.CSSProperties = {
  backgroundColor: c.reagent,
  color: c.paper,
  borderColor: c.reagent,
};

const errorLine: React.CSSProperties = {
  color: c.flag,
  fontFamily: font.mono,
  fontSize: size.small,
  marginTop: space.base,
};

const videoToggle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: space.sm,
  margin: `${space.base}px 0 ${space.xs}px`,
  fontFamily: font.body,
  fontSize: size.body,
  color: c.inkSoft,
  cursor: "pointer",
};

const videoToggleHint: React.CSSProperties = {
  color: c.inkFaint,
};

const cta: React.CSSProperties = {
  marginTop: space.lg,
  backgroundColor: c.reagent,
  color: c.paper,
  fontFamily: font.body,
  fontSize: size.lead,
  fontWeight: 600,
  padding: `${space.md}px ${space.xl}px`,
  display: "inline-flex",
  alignItems: "center",
  gap: space.md,
  transition: "background-color 0.15s",
};

const ctaHint: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.small,
  opacity: 0.7,
};

const ledger: React.CSSProperties = { borderTop: hairline, paddingTop: space.lg };
const ledgerHead: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "baseline",
  marginBottom: space.md,
};
const ledgerRefresh: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.micro,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: c.inkSoft,
};
const emptyLedger: React.CSSProperties = {
  color: c.inkFaint,
  fontSize: size.body,
  padding: `${space.sm}px 0`,
};

const ledgerList: React.CSSProperties = { listStyle: "none" };
const ledgerRow: React.CSSProperties = {
  width: "100%",
  display: "flex",
  alignItems: "center",
  gap: space.base,
  padding: `${space.md}px 0`,
  borderBottom: `1px solid ${c.ruleSoft}`,
  textAlign: "left",
};
const ledgerNum: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.small,
  color: c.inkFaint,
  flexShrink: 0,
};
const ledgerTopic: React.CSSProperties = {
  flex: 1,
  minWidth: 0,
  fontSize: size.body,
  color: c.ink,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};
const ledgerStatus: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.micro,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  flexShrink: 0,
};
