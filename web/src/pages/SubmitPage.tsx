import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listRuns, startRun } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { RunMode, RunSummary } from "../types";
import {
  c, display, font, headingWeight, layout, muted, mutedFaint, size, space,
} from "../theme";

// Which orchestrator runs the pipeline. This was the one thing only the old
// benchmark dashboard could set. "All three" runs them in sequence — roughly
// 36 minutes and 3x the token spend — so it is never the default.
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
      /* backend may be down; the list just stays empty */
    }
  }, []);

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

  const recent = history.slice(0, 6);

  return (
    <main style={page}>
      <section className="animate-rise">
        <span style={kicker}>New session</span>
        <h1 style={heading}>What do you want to understand today?</h1>
        <p style={intro}>
          Describe a topic. Four agents run in parallel — notes, flashcards,
          video and PDF — and hand back a full study set.
        </p>

        <div style={composer}>
          <textarea
            id="topic"
            className="input"
            ref={taRef}
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="e.g. How does gradient descent find a minimum?"
            rows={3}
            autoFocus
            style={{ fontSize: size.lead }}
          />

          <div style={chipRow}>
            {EXAMPLES.map((ex) => (
              <button key={ex} onClick={() => setTopic(ex)} className="tag tag-neutral" style={chip}>
                {ex}
              </button>
            ))}
          </div>

          {error && (
            <p role="alert" style={errorLine}>
              {error}
            </p>
          )}

          <div style={controls}>
            <div className="seg" role="group" aria-label="Orchestrator">
              {MODES.map((m) => (
                <button
                  key={m.value}
                  className="seg-opt"
                  onClick={() => setMode(m.value)}
                  title={m.note}
                  aria-pressed={mode === m.value}
                >
                  {m.label}
                </button>
              ))}
            </div>

            <button
              className="btn btn-primary"
              onClick={submit}
              disabled={submitting || !topic.trim()}
            >
              {submitting ? "Starting…" : "Generate"}
            </button>
          </div>

          <label style={videoToggle}>
            <input
              type="checkbox"
              checked={includeVideo}
              onChange={(e) => setIncludeVideo(e.target.checked)}
            />
            <span>
              Include narrated video
              <span style={{ color: mutedFaint }}>
                {includeVideo
                  ? " — adds roughly 8 minutes of ffmpeg"
                  : " — about 2 minutes without it"}
              </span>
            </span>
          </label>
        </div>
      </section>

      <div style={figures}>
        <Figure value={String(history.length)} label="Sessions generated" />
        <Figure value="3" label="Orchestrators compared" />
        <Figure value="4" label="Outputs per session" />
      </div>

      <div style={recentHead}>
        <h3 style={recentTitle}>Recent sessions</h3>
        <button className="btn btn-ghost" onClick={() => navigate("/library")}>
          View library →
        </button>
      </div>

      {recent.length === 0 ? (
        <p style={{ color: muted }}>
          {user
            ? "Nothing here yet. The topics you study are saved to your account."
            : "Nothing here yet. Sign in to keep your studied topics across visits."}
        </p>
      ) : (
        <div style={grid}>
          {recent.map((r) => (
            <button
              key={r.run_id}
              className="card elev-sm card-link"
              onClick={() =>
                navigate(r.status === "complete" ? `/session/${r.run_id}` : `/run/${r.run_id}`)
              }
            >
              <div className="card-kicker">
                {r.mode ?? "async"} · {r.status === "complete" ? "ready" : r.status}
              </div>
              <div className="card-title">{r.topic}</div>
              <p className="card-body">
                {r.status === "complete"
                  ? "Notes, flashcards and PDFs are ready to open."
                  : `${r.progress_pct}% — ${r.phase}`}
              </p>
            </button>
          ))}
        </div>
      )}
    </main>
  );
}

function Figure({ value, label }: { value: string; label: string }) {
  return (
    <div>
      <div style={figureValue}>{value}</div>
      <div style={figureLabel}>{label}</div>
    </div>
  );
}

// ── styles ──────────────────────────────────────────────────────────────────

const page: React.CSSProperties = { maxWidth: layout.shell };

const kicker: React.CSSProperties = {
  display: "block",
  fontSize: size.small,
  fontStyle: "italic",
  color: c.reagentDeep,
  marginBottom: space.sm,
};

const heading: React.CSSProperties = {
  fontFamily: font.display,
  fontWeight: headingWeight,
  fontSize: display,
  lineHeight: 1.05,
  margin: `0 0 ${space.sm}px`,
};

const intro: React.CSSProperties = {
  fontSize: size.lead,
  color: muted,
  maxWidth: layout.measure,
  margin: `0 0 ${space.lg}px`,
};

const composer: React.CSSProperties = { maxWidth: 680 };

const chipRow: React.CSSProperties = {
  display: "flex",
  gap: space.sm,
  flexWrap: "wrap",
  marginTop: space.md,
};

const chip: React.CSSProperties = {
  cursor: "pointer",
  border: "none",
  fontSize: size.small,
  padding: "6px 12px",
};

const controls: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  flexWrap: "wrap",
  gap: space.md,
  marginTop: space.base,
};

const videoToggle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: space.sm,
  marginTop: space.md,
  fontSize: size.body,
  color: muted,
  cursor: "pointer",
};

const errorLine: React.CSSProperties = {
  color: c.flagDeep,
  fontSize: size.body,
  marginTop: space.md,
};

const figures: React.CSSProperties = {
  display: "flex",
  gap: space.section,
  flexWrap: "wrap",
  margin: `${space.page}px 0 ${space.section}px`,
};

const figureValue: React.CSSProperties = {
  fontFamily: font.display,
  fontWeight: headingWeight,
  fontSize: size.hero,
  lineHeight: 1,
};

const figureLabel: React.CSSProperties = {
  fontSize: size.micro,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: c.reagentDeep,
  marginTop: space.xs,
};

const recentHead: React.CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  justifyContent: "space-between",
  gap: space.base,
  marginBottom: space.md,
};

const recentTitle: React.CSSProperties = {
  fontFamily: font.display,
  fontWeight: headingWeight,
  fontSize: size.title,
  margin: 0,
};

const grid: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
  gap: space.base,
};
