import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { cancelRun, getRun, streamRun } from "../api/client";
import type { RunPhase, RunState, SSEEvent } from "../types";
import { c, font, eyebrow } from "../theme";

// The learner waits here while their materials are made. This screen's only job is
// to reassure — so it speaks in deliverables ("your flashcards are ready"), never in
// pipeline stages. Nothing here exposes how the work is done.

const STATUS_LINE: Record<RunPhase, string> = {
  starting: "Getting started on your topic…",
  phase1: "Reading up and writing your notes.",
  phase2: "Making your flashcards and recording your video.",
  phase3: "Preparing clean copies you can print.",
  profiling: "Almost done.",
  done: "Everything's ready.",
  error: "Something stopped before it finished.",
};

// The four things the learner is about to receive, and the phase after which each
// is genuinely ready. This is honest: it reflects real completion, not a fake timer.
type Deliverable = { key: string; label: string; blurb: string; readyAfter: number };
const DELIVERABLES: Deliverable[] = [
  { key: "notes", label: "Notes", blurb: "the topic, written out clearly", readyAfter: 1 },
  { key: "flashcards", label: "Flashcards", blurb: "quick prompts to test yourself", readyAfter: 2 },
  { key: "video", label: "Video", blurb: "a short narrated walkthrough", readyAfter: 2 },
  { key: "print", label: "Print-ready copies", blurb: "notes & cards as PDFs", readyAfter: 3 },
];

function phaseRank(p: RunPhase): number {
  switch (p) {
    case "starting":
      return 0;
    case "phase1":
      return 1;
    case "phase2":
      return 2;
    case "phase3":
    case "profiling":
      return 3;
    case "done":
      return 4;
    default:
      return -1;
  }
}

function elapsedText(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export default function RunPage() {
  const { run_id } = useParams<{ run_id?: string }>();
  const navigate = useNavigate();
  const [phase, setPhase] = useState<RunPhase>("starting");
  const [status, setStatus] = useState<RunState["status"]>("running");
  const [topic, setTopic] = useState("");
  // Whether this run is making a video. Read from the run rather than assumed,
  // so the checklist promises only what will actually exist.
  const [hasVideo, setHasVideo] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [confirmingStop, setConfirmingStop] = useState(false);
  const [stopping, setStopping] = useState(false);
  const startRef = useRef<number>(Date.now());
  const closeStreamRef = useRef<(() => void) | null>(null);
  const stoppingRef = useRef(false);

  useEffect(() => {
    if (status !== "running") return;
    const id = setInterval(() => setElapsed(Date.now() - startRef.current), 1000);
    return () => clearInterval(id);
  }, [status]);

  useEffect(() => {
    if (!run_id) return;
    getRun(run_id)
      .then((s) => {
        setTopic(s.topic);
        setHasVideo(s.include_video !== false);
        if (s.started_at) startRef.current = new Date(s.started_at).getTime();
      })
      .catch(() => {});

    const closeStream = streamRun(
      run_id,
      (e: SSEEvent) => {
        if (e.phase) setPhase(e.phase);
      },
      async () => {
        if (stoppingRef.current) return; // we're cancelling and leaving; ignore stream close
        try {
          const s = await getRun(run_id);
          setStatus(s.status);
          if (s.status === "complete") {
            setPhase("done");
            setTimeout(() => navigate(`/package/${run_id}`), 1100);
          } else if (s.status === "error" || s.status === "cancelled") {
            setPhase("error");
            setError(s.error ?? "The session ended before it finished.");
          }
        } catch {
          setStatus("error");
          setError("Lost the connection to the study server.");
        }
      },
      (err) => {
        if (stoppingRef.current) return;
        setStatus("error");
        setError(err.message);
      }
    );
    closeStreamRef.current = closeStream;
    return () => closeStream();
  }, [run_id, navigate]);

  const handleStop = async () => {
    if (!run_id) return;
    stoppingRef.current = true;
    setStopping(true);
    closeStreamRef.current?.(); // stop listening immediately
    try {
      await cancelRun(run_id);
    } catch {
      /* even if the stop call fails, honor the user's intent to leave */
    }
    navigate("/");
  };

  const cancelled = status === "cancelled";
  const errored = status === "error" || cancelled;
  const rank = phaseRank(phase);
  // A --skip-video run produces no video, so promising one and then
  // ticking it 'ready' would be the UI lying about what exists.
  const deliverables = DELIVERABLES.filter((d) => d.key !== "video" || hasVideo);
  const readyCount = errored ? 0 : deliverables.filter((d) => rank >= d.readyAfter + 1 || phase === "done").length;

  return (
    <main style={page}>
      <header style={head}>
        <button onClick={() => navigate("/")} style={backLink}>
          ← new topic
        </button>
        <div style={{ ...eyebrow, color: errored ? c.flag : c.reagent }}>
          {cancelled ? "· stopped" : status === "error" ? "· didn't finish" : status === "complete" ? "· ready" : "· preparing"}
        </div>
        <span style={clock}>{elapsedText(elapsed)}</span>
      </header>

      {/* Stop control — quiet by default; canceling throws away in-progress work, so it
          asks once before doing it. Only offered while the work is actually running. */}
      {status === "running" && (
        <div style={stopBar}>
          {confirmingStop ? (
            <>
              <span style={confirmText}>Stop now? You'll lose what's been made so far.</span>
              <span style={confirmActions}>
                <button onClick={() => setConfirmingStop(false)} style={keepBtn} disabled={stopping}>
                  Keep going
                </button>
                <button onClick={handleStop} style={confirmStopBtn} disabled={stopping}>
                  {stopping ? "Stopping…" : "Stop & go home"}
                </button>
              </span>
            </>
          ) : (
            <button onClick={() => setConfirmingStop(true)} style={stopLink}>
              Stop generating
            </button>
          )}
        </div>
      )}

      {/* Quiet focal element: an ink mark "developing" while we wait. Calm, single. */}
      {!errored && (
        <div style={focalWrap} aria-hidden="true">
          <span className={status === "running" ? "animate-develop" : undefined} style={focalDot} />
        </div>
      )}

      <h1 style={title} className="animate-rise">
        {cancelled ? "Stopped" : status === "error" ? "We hit a snag" : topic || "Preparing your study materials"}
      </h1>
      <p style={statusLine}>
        {cancelled
          ? "You stopped this one. Start a new topic whenever you're ready."
          : status === "error"
          ? error ?? STATUS_LINE.error
          : STATUS_LINE[phase]}
      </p>

      {errored ? (
        <div style={errorBox} role="alert">
          <button onClick={() => navigate("/")} style={retryBtn}>
            Try another topic
          </button>
        </div>
      ) : (
        <>
          <div style={progressNote}>
            <span style={eyebrow}>
              {phase === "done" ? "All set" : `${readyCount} of ${deliverables.length} ready`}
            </span>
          </div>

          {/* Preparing checklist — deliverables, ticking to "ready" as they truly finish. */}
          <ul style={list}>
            {deliverables.map((d) => {
              const ready = phase === "done" || rank >= d.readyAfter + 1;
              const working = !ready && rank >= d.readyAfter; // being made right now
              return (
                <li key={d.key} style={row}>
                  <span
                    style={{
                      ...mark,
                      borderColor: ready ? c.reagent : c.rule,
                      backgroundColor: ready ? c.reagent : "transparent",
                    }}
                    className={working ? "animate-pulse" : undefined}
                  >
                    {ready ? "✓" : ""}
                  </span>
                  <span style={{ flex: 1, minWidth: 0 }}>
                    <span style={{ ...rowLabel, color: ready ? c.ink : c.inkSoft }}>{d.label}</span>
                    <span style={rowBlurb}>{d.blurb}</span>
                  </span>
                  <span style={{ ...rowState, color: ready ? c.reagent : c.inkFaint }}>
                    {ready ? "ready" : working ? "making…" : "next"}
                  </span>
                </li>
              );
            })}
          </ul>

          {status === "complete" && (
            <button onClick={() => navigate(`/package/${run_id}`)} style={openBtn}>
              Open your study materials →
            </button>
          )}
        </>
      )}
    </main>
  );
}

// ── styles ────────────────────────────────────────────────────────────────────

const page: React.CSSProperties = { maxWidth: 640, margin: "0 auto", padding: "40px 22px 90px" };

const head: React.CSSProperties = { display: "flex", alignItems: "baseline", gap: 10, marginBottom: 16 };
const backLink: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 12,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  color: c.inkSoft,
};

// Stop control lives just under the header, quiet until asked to commit.
const stopBar: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  alignItems: "center",
  gap: 12,
  minHeight: 34,
  marginBottom: 24,
};
const stopLink: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.12em",
  textTransform: "uppercase",
  color: c.inkFaint,
  borderBottom: `1px solid ${c.rule}`,
  paddingBottom: 2,
};
const confirmText: React.CSSProperties = { fontSize: 14, color: c.ink, flex: 1, minWidth: 180 };
const confirmActions: React.CSSProperties = { display: "flex", gap: 8, flexShrink: 0 };
const keepBtn: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  border: `1px solid ${c.ink}`,
  color: c.ink,
  padding: "8px 12px",
};
const confirmStopBtn: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  backgroundColor: c.flag,
  color: c.paper,
  padding: "8px 12px",
};
const clock: React.CSSProperties = {
  marginLeft: "auto",
  fontFamily: font.mono,
  fontSize: 14,
  fontWeight: 700,
  color: c.ink,
};

const focalWrap: React.CSSProperties = {
  display: "flex",
  justifyContent: "center",
  marginBottom: 28,
};
const focalDot: React.CSSProperties = {
  width: 18,
  height: 18,
  borderRadius: "50%",
  backgroundColor: c.reagent,
  display: "inline-block",
};

const title: React.CSSProperties = {
  fontFamily: font.display,
  fontSize: "clamp(30px, 5.5vw, 46px)",
  fontWeight: 600,
  lineHeight: 1.04,
  letterSpacing: "-0.015em",
  color: c.ink,
  textAlign: "center",
};
const statusLine: React.CSSProperties = {
  fontSize: 16,
  color: c.inkSoft,
  marginTop: 12,
  textAlign: "center",
};

const progressNote: React.CSSProperties = { marginTop: 40, marginBottom: 12, textAlign: "center" };

const list: React.CSSProperties = { listStyle: "none", borderTop: `1px solid ${c.rule}` };
const row: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 14,
  padding: "16px 2px",
  borderBottom: `1px solid ${c.ruleSoft}`,
};
const mark: React.CSSProperties = {
  width: 22,
  height: 22,
  border: "1.5px solid",
  borderRadius: "50%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  color: c.paper,
  fontSize: 12,
  fontWeight: 700,
  flexShrink: 0,
};
const rowLabel: React.CSSProperties = {
  fontFamily: font.display,
  fontSize: 20,
  fontWeight: 600,
  display: "block",
  lineHeight: 1.15,
};
const rowBlurb: React.CSSProperties = { fontSize: 13.5, color: c.inkFaint };
const rowState: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  flexShrink: 0,
};

const openBtn: React.CSSProperties = {
  marginTop: 32,
  width: "100%",
  backgroundColor: c.reagent,
  color: c.paper,
  fontFamily: font.body,
  fontSize: 17,
  fontWeight: 600,
  padding: "16px 20px",
};

const errorBox: React.CSSProperties = { marginTop: 28, textAlign: "center" };
const retryBtn: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 12,
  fontWeight: 700,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  border: `1px solid ${c.ink}`,
  padding: "10px 18px",
  color: c.ink,
};
