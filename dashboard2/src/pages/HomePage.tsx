import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listRuns, startRun } from "../api/client";
import type { RunMode, RunSummary } from "../types";

const MODES: { label: string; value: RunMode }[] = [
  { label: "All three", value: "all" },
  { label: "Async only", value: "async" },
  { label: "ADK only", value: "adk" },
  { label: "Original only", value: "original" },
];

const STATUS_COLORS: Record<string, string> = {
  running: "#f59e0b",
  complete: "#22c55e",
  error: "#ef4444",
};

export default function HomePage() {
  const navigate = useNavigate();
  const [topic, setTopic] = useState("");
  const [mode, setMode] = useState<RunMode>("all");
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
      setError(err instanceof Error ? err.message : "Failed to start run. Is the API server running on port 8000?");
    } finally {
      setLaunching(false);
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        {/* Header */}
        <h1 style={styles.title}>AI Study Generator</h1>
        <p style={styles.subtitle}>
          Generate notes, flashcards, and a narrated video — then compare orchestrator performance.
        </p>

        {/* Topic input */}
        <input
          style={styles.input}
          placeholder="e.g. machine learning basics"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleRun()}
          autoFocus
        />

        {/* Mode toggle */}
        <div style={styles.modeRow}>
          {MODES.map((m) => (
            <button
              key={m.value}
              onClick={() => setMode(m.value)}
              style={{
                ...styles.modeBtn,
                ...(mode === m.value ? styles.modeBtnActive : {}),
              }}
            >
              {m.label}
            </button>
          ))}
        </div>

        {error && <p style={styles.error}>{error}</p>}

        {/* Run button */}
        <button
          onClick={handleRun}
          disabled={launching}
          style={{ ...styles.runBtn, ...(launching ? styles.runBtnDisabled : {}) }}
        >
          {launching ? "Starting..." : "▶  Run Pipeline"}
        </button>
      </div>

      {/* History */}
      <div style={styles.historySection}>
        <div style={styles.historyHeader}>
          <h2 style={styles.historyTitle}>Recent Runs</h2>
          <button onClick={fetchHistory} style={styles.refreshBtn}>↻ Refresh</button>
        </div>

        {history.length === 0 ? (
          <p style={styles.emptyText}>No runs yet. Start one above!</p>
        ) : (
          <div>
            {history.map((item) => (
              <div
                key={item.run_id}
                onClick={() =>
                  navigate(item.status === "complete" ? `/results/${item.run_id}` : `/run/${item.run_id}`)
                }
                style={styles.historyCard}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={styles.historyTopic}>{item.topic}</p>
                  <p style={styles.historyMeta}>
                    {item.mode} · {new Date(item.started_at).toLocaleString()}
                  </p>
                </div>
                <span
                  style={{
                    ...styles.statusBadge,
                    backgroundColor: STATUS_COLORS[item.status] ?? "#475569",
                  }}
                >
                  {item.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: 680,
    margin: "0 auto",
    padding: "32px 20px",
  },
  card: {
    backgroundColor: "#1e293b",
    borderRadius: 12,
    padding: 28,
    border: "1px solid #334155",
    marginBottom: 28,
  },
  title: {
    fontSize: 26,
    fontWeight: 800,
    color: "#f1f5f9",
    marginBottom: 8,
  },
  subtitle: {
    color: "#94a3b8",
    fontSize: 14,
    lineHeight: 1.6,
    marginBottom: 22,
  },
  input: {
    width: "100%",
    backgroundColor: "#0f172a",
    color: "#f1f5f9",
    border: "1px solid #334155",
    borderRadius: 8,
    padding: "13px 16px",
    fontSize: 15,
    outline: "none",
    marginBottom: 14,
  },
  modeRow: {
    display: "flex",
    gap: 8,
    marginBottom: 14,
  },
  modeBtn: {
    flex: 1,
    backgroundColor: "#0f172a",
    color: "#64748b",
    border: "1px solid #334155",
    borderRadius: 8,
    padding: "10px 0",
    fontSize: 13,
    fontWeight: 600,
    transition: "all 0.15s",
  },
  modeBtnActive: {
    backgroundColor: "#6366f1",
    color: "#fff",
    borderColor: "#6366f1",
  },
  error: {
    color: "#f87171",
    fontSize: 13,
    marginBottom: 12,
  },
  runBtn: {
    width: "100%",
    backgroundColor: "#6366f1",
    color: "#fff",
    border: "none",
    borderRadius: 10,
    padding: "15px 0",
    fontSize: 16,
    fontWeight: 700,
    letterSpacing: "0.2px",
  },
  runBtnDisabled: {
    opacity: 0.6,
    cursor: "not-allowed",
  },
  historySection: {
    backgroundColor: "#1e293b",
    borderRadius: 12,
    padding: 24,
    border: "1px solid #334155",
  },
  historyHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14,
  },
  historyTitle: {
    fontSize: 16,
    fontWeight: 700,
    color: "#f1f5f9",
  },
  refreshBtn: {
    backgroundColor: "transparent",
    color: "#6366f1",
    border: "none",
    fontSize: 14,
    fontWeight: 600,
  },
  emptyText: {
    color: "#475569",
    textAlign: "center",
    padding: "16px 0",
  },
  historyCard: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    backgroundColor: "#0f172a",
    borderRadius: 8,
    padding: 14,
    marginBottom: 8,
    border: "1px solid #1e293b",
    cursor: "pointer",
    transition: "border-color 0.15s",
  },
  historyTopic: {
    color: "#f1f5f9",
    fontWeight: 600,
    fontSize: 14,
    marginBottom: 2,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  historyMeta: {
    color: "#64748b",
    fontSize: 12,
  },
  statusBadge: {
    borderRadius: 6,
    padding: "3px 9px",
    fontSize: 11,
    fontWeight: 700,
    color: "#fff",
    flexShrink: 0,
  },
};
