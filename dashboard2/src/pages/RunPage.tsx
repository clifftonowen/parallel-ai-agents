import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { getRun, streamRun } from "../api/client";
import PhaseBar from "../components/PhaseBar";
import type { RunPhase, SSEEvent } from "../types";
import { c, font, eyebrow } from "../theme";

const PHASES: { key: string; label: string; activeOn: RunPhase[] }[] = [
  { key: "phase1", label: "Phase 1 — Notes", activeOn: ["phase1"] },
  { key: "phase2", label: "Phase 2 — Flashcards & Video", activeOn: ["phase2"] },
  { key: "phase3", label: "Phase 3 — PDFs & Profiling", activeOn: ["phase3", "profiling"] },
];

function phaseIndex(phase: RunPhase): number {
  if (phase === "phase1") return 0;
  if (phase === "phase2") return 1;
  if (["phase3", "profiling", "done"].includes(phase)) return 2;
  return -1;
}

export default function RunPage() {
  const { run_id } = useParams<{ run_id?: string }>();
  const navigate = useNavigate();
  const [phase, setPhase] = useState<RunPhase>("starting");
  const [progress, setProgress] = useState(0);
  const [logLines, setLogLines] = useState<string[]>([]);
  const [status, setStatus] = useState("running");
  const [error, setError] = useState<string | null>(null);
  const [topic, setTopic] = useState("");
  const logRef = useRef<HTMLPreElement>(null);

  // Auto-scroll log
  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [logLines]);

  useEffect(() => {
    if (!run_id) return;

    // Get topic for header
    getRun(run_id).then((s) => setTopic(s.topic)).catch(() => {});

    const cancel = streamRun(
      run_id,
      (event: SSEEvent) => {
        if (event.log != null) setLogLines((prev) => [...prev, event.log!]);
        if (event.phase) setPhase(event.phase);
        if (event.progress_pct != null) setProgress(event.progress_pct);
      },
      async () => {
        try {
          const state = await getRun(run_id);
          setStatus(state.status);
          if (state.status === "complete") {
            setPhase("done");
            setProgress(100);
            setTimeout(() => navigate(`/results/${run_id}`), 800);
          } else if (state.status === "error") {
            setPhase("error");
            setError(state.error ?? "Unknown error");
          }
        } catch {
          setStatus("error");
          setError("Lost connection to API server.");
        }
      },
      (err) => {
        setStatus("error");
        setError(err.message);
      }
    );

    return () => cancel();
  }, [run_id, navigate]);

  const currentIdx = phaseIndex(phase);
  const statusColor = status === "complete" ? c.reagent : status === "error" ? c.flag : c.inkSoft;

  return (
    <div style={styles.container}>
      {/* Header */}
      <div style={styles.header}>
        <h1 style={styles.title}>{topic || "Running pipeline..."}</h1>
        <span style={{ ...styles.statusBadge, color: statusColor }}>{status}</span>
      </div>

      {/* Phase indicators */}
      <div style={styles.phaseRow}>
        {PHASES.map((p, i) => {
          const isDone = phase === "done" || i < currentIdx;
          const isActive = !isDone && p.activeOn.includes(phase as RunPhase);
          return (
            <PhaseBar
              key={p.key}
              label={p.label}
              state={isDone ? "done" : isActive ? "active" : "pending"}
            />
          );
        })}
      </div>

      {/* Progress bar */}
      <div style={styles.progressSection}>
        <div style={styles.progressTrack}>
          <div
            style={{
              ...styles.progressFill,
              width: `${progress}%`,
            }}
          />
        </div>
        <span style={styles.progressPct}>{progress}%</span>
      </div>

      {/* Status / error / results button */}
      {status === "error" && error ? (
        <div style={styles.errorBox}>
          <strong>Error:</strong> {error}
        </div>
      ) : status === "complete" ? (
        <button onClick={() => navigate(`/results/${run_id}`)} style={styles.resultsBtn}>
          View Results →
        </button>
      ) : (
        <p style={styles.statusText}>
          {phase === "starting" ? "Starting pipeline..." : `Running ${phase}...`}
        </p>
      )}

      {/* Log console */}
      <div style={styles.consoleWrapper}>
        <p style={eyebrow}>Live Log</p>
        <pre ref={logRef} style={styles.console}>
          {logLines.length === 0 ? (
            <span style={{ color: c.inkFaint }}>Waiting for output...</span>
          ) : (
            logLines.join("\n")
          )}
        </pre>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: 900,
    margin: "0 auto",
    padding: "20px 20px 24px",
    display: "flex",
    flexDirection: "column",
    height: "calc(100vh - 52px)",
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    marginBottom: 18,
    flexWrap: "wrap",
  },
  title: {
    fontFamily: font.display,
    fontSize: 24,
    fontWeight: 600,
    color: c.ink,
    flex: 1,
  },
  statusBadge: {
    fontFamily: font.mono,
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: "0.1em",
    textTransform: "uppercase",
    flexShrink: 0,
  },
  phaseRow: {
    display: "flex",
    gap: 8,
    marginBottom: 16,
  },
  progressSection: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    marginBottom: 16,
  },
  progressTrack: {
    flex: 1,
    height: 6,
    backgroundColor: c.ruleSoft,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    backgroundColor: c.reagent,
    transition: "width 0.4s ease",
  },
  progressPct: {
    fontFamily: font.mono,
    color: c.inkSoft,
    fontSize: 12,
    width: 38,
    textAlign: "right",
  },
  statusText: {
    color: c.inkSoft,
    fontSize: 13,
    textAlign: "center",
    marginBottom: 14,
  },
  errorBox: {
    backgroundColor: c.flagWash,
    borderLeft: `3px solid ${c.flag}`,
    padding: 12,
    color: c.ink,
    fontSize: 13,
    marginBottom: 16,
  },
  resultsBtn: {
    backgroundColor: c.reagent,
    color: c.paper,
    fontFamily: font.body,
    padding: "13px 26px",
    fontSize: 15,
    fontWeight: 600,
    marginBottom: 16,
    alignSelf: "center",
  },
  consoleWrapper: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    minHeight: 0,
    gap: 6,
  },
  console: {
    flex: 1,
    backgroundColor: c.ink,
    padding: 12,
    overflow: "auto",
    color: c.paperDeep,
    fontFamily: font.mono,
    fontSize: 11,
    lineHeight: 1.65,
    whiteSpace: "pre-wrap",
    wordBreak: "break-all",
  },
};
