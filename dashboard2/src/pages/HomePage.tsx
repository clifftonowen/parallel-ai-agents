import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listRuns, startRun } from "../api/client";
import type { RunMode, RunSummary } from "../types";
import { c, font, eyebrow, hairline } from "../theme";

const MODES: { label: string; value: RunMode }[] = [
  { label: "All three", value: "all" },
  { label: "Async only", value: "async" },
  { label: "ADK only", value: "adk" },
  { label: "Original only", value: "original" },
];

function statusColor(s: string) {
  if (s === "complete") return c.reagent;
  if (s === "error") return c.flag;
  return c.inkSoft;
}
function statusWord(s: string) {
  if (s === "complete") return "ready";
  if (s === "error") return "failed";
  return "working…";
}

export default function HomePage() {
  const navigate = useNavigate();
  const [topic, setTopic] = useState("");
  // Defaults to a single orchestrator. "All three" runs them sequentially,
  // which is ~36 minutes and 3x the token spend - not something a stray
  // click should start.
  const [mode, setMode] = useState<RunMode>("async");
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<RunSummary[]>([]);

  const fetchHistory = useCallback(async () => {
    try {
      const runs = await listRuns();
      setHistory(runs);
    } catch {
      // server may not be up yet
    }
  }, []);

  useEffect(() => {
    fetchHistory();
    window.addEventListener("focus", fetchHistory);
    return () => window.removeEventListener("focus", fetchHistory);
  }, [fetchHistory]);

  const handleRun = async () => {
    if (!topic.trim()) { setError("Please enter a topic."); return; }
    setError(null);
    setLaunching(true);
    try {
      const { run_id } = await startRun(topic.trim(), mode);
      navigate(`/run/${run_id}`);
    } catch (err: unknown) {
      // Only surface a detail the API actually sent; a dead backend through
      // the dev proxy yields a 5xx whose statusText is "Internal Server
      // Error", which tells the reader nothing.
      setError(
        err instanceof Error && !/internal server error|failed to fetch/i.test(err.message)
          ? err.message
          : "Couldn't reach the benchmark server. Make sure the backend is running, then try again.",
      );
    } finally {
      setLaunching(false);
    }
  };

  return (
    <main style={page}>
      {/* Masthead */}
      <header style={masthead} className="animate-rise">
        <div style={mastheadTop}>
          <span style={eyebrow}>Benchmark Dashboard</span>
          <span style={{ ...eyebrow, color: c.reagent }}>· compare orchestrators</span>
        </div>
        <div style={topRule} className="rule-draw" />
      </header>

      {/* Intake */}
      <section style={intake} className="animate-rise">
        <h1 style={intakeLead}>
          Run the pipeline,
          <br />
          <em style={{ fontStyle: "italic", color: c.reagent }}>compare</em> the results.
        </h1>
        <p style={intakeSub}>
          Generate notes, flashcards, and a narrated video — then compare wall-clock
          time and token usage across the original, ADK, and async orchestrators.
        </p>

        <div style={slip}>
          <span style={slipTick}>topic ▸</span>
          <input
            style={input}
            placeholder="e.g. machine learning basics"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleRun()}
            autoFocus
          />
        </div>

        <div style={modeRow}>
          {MODES.map((m) => (
            <button
              key={m.value}
              onClick={() => setMode(m.value)}
              style={{
                ...modeBtn,
                ...(mode === m.value ? modeBtnActive : {}),
              }}
            >
              {m.label}
            </button>
          ))}
        </div>

        {error && <p style={errorLine}>{error}</p>}

        <button
          onClick={handleRun}
          disabled={launching}
          style={{ ...cta, opacity: launching ? 0.6 : 1 }}
        >
          {launching ? "Starting…" : "Run pipeline →"}
        </button>
      </section>

      {/* History */}
      <section style={ledger}>
        <div style={ledgerHead}>
          <span style={eyebrow}>Recent Runs</span>
          <button onClick={fetchHistory} style={ledgerRefresh}>
            refresh
          </button>
        </div>

        {history.length === 0 ? (
          <p style={emptyLedger}>No runs yet. Start one above.</p>
        ) : (
          <ol style={ledgerList}>
            {history.map((item, i) => (
              <li key={item.run_id}>
                <button
                  onClick={() =>
                    navigate(item.status === "complete" ? `/results/${item.run_id}` : `/run/${item.run_id}`)
                  }
                  style={ledgerRow}
                >
                  <span style={ledgerNum}>{String(history.length - i).padStart(3, "0")}</span>
                  <span style={ledgerTopic}>{item.topic}</span>
                  <span style={ledgerMeta}>
                    {item.mode} · {new Date(item.started_at).toLocaleString()}
                  </span>
                  <span style={{ ...ledgerStatus, color: statusColor(item.status) }}>
                    {statusWord(item.status)}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        )}
      </section>
    </main>
  );
}

const page: React.CSSProperties = {
  maxWidth: 760,
  margin: "0 auto",
  padding: "24px 22px 80px",
};

const masthead: React.CSSProperties = { marginBottom: 40 };
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

const intake: React.CSSProperties = { marginBottom: 52 };

const intakeLead: React.CSSProperties = {
  display: "block",
  fontFamily: font.display,
  fontSize: "clamp(34px, 6.5vw, 54px)",
  fontWeight: 600,
  lineHeight: 1.02,
  letterSpacing: "-0.02em",
  color: c.ink,
  marginBottom: 16,
  overflowWrap: "break-word",
};

const intakeSub: React.CSSProperties = {
  fontSize: 16,
  color: c.inkSoft,
  maxWidth: 520,
  marginBottom: 24,
};

const slip: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  border: `1px solid ${c.ink}`,
  backgroundColor: c.paperCard,
  padding: "14px 18px",
};

const slipTick: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 13,
  fontWeight: 700,
  color: c.reagent,
  flexShrink: 0,
};

const input: React.CSSProperties = {
  flex: 1,
  border: "none",
  outline: "none",
  background: "transparent",
  fontFamily: font.body,
  fontSize: 17,
  color: c.ink,
};

const modeRow: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 8,
  marginTop: 14,
};

const modeBtn: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 12,
  color: c.inkSoft,
  border: `1px solid ${c.rule}`,
  padding: "9px 14px",
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
  fontSize: 13,
  marginTop: 16,
};

const cta: React.CSSProperties = {
  marginTop: 22,
  width: "100%",
  backgroundColor: c.reagent,
  color: c.paper,
  fontFamily: font.body,
  fontSize: 17,
  fontWeight: 600,
  padding: "16px 20px",
  transition: "background-color 0.15s",
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
  padding: "13px 0",
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
const ledgerMeta: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  color: c.inkFaint,
  flexShrink: 0,
};
const ledgerStatus: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  flexShrink: 0,
};
