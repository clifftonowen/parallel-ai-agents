import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listRuns } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { DEMO } from "../api/demo";
import type { RunSummary } from "../types";
import {
  c, display, font, headingWeight, layout, muted, mutedFaint, size, space,
} from "../theme";

/** Every session the agents have generated, as a ruled table.
 *
 *  The back link and the page's own container are gone: the shell supplies both
 *  the nav and the padding now. */
export default function HistoryPage() {
  const { user, ready } = useAuth();
  const navigate = useNavigate();
  const [runs, setRuns] = useState<RunSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Requires an account; send anonymous visitors to sign in, remembering where to return.
  useEffect(() => {
    if (!DEMO && ready && !user) {
      navigate("/signin", { state: { from: "/library" }, replace: true });
    }
  }, [ready, user, navigate]);

  useEffect(() => {
    if (!DEMO && !user) return;
    listRuns()
      .then(setRuns)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Couldn't load your history.")
      );
  }, [user]);

  if (!ready) return <p style={{ color: muted }}>Opening your card…</p>;
  if (!DEMO && !user) return null;

  const openRun = (r: RunSummary) =>
    navigate(r.status === "complete" ? `/session/${r.run_id}` : `/run/${r.run_id}`);

  return (
    <main style={page}>
      <h1 style={heading}>Library</h1>
      <p style={intro}>
        {DEMO
          ? "One session, kept as the demo. On the live deployment this lists every session your account has generated."
          : `Every session your agents have generated, filed under ${user!.email}.`}
      </p>

      {error && <p style={errorLine}>{error}</p>}

      {runs === null ? (
        <p style={{ color: muted }}>Fetching your topics…</p>
      ) : runs.length === 0 ? (
        <div style={empty}>
          <p style={emptyLead}>Nothing filed yet.</p>
          <p style={{ color: muted, marginBottom: space.base }}>
            Study a topic and it will be kept here, ready to reopen whenever you come back.
          </p>
          <button className="btn btn-primary" onClick={() => navigate("/new")}>
            Start a session
          </button>
        </div>
      ) : (
        <div className="scroll-x">
          <table className="table" style={{ minWidth: 560 }}>
            <thead>
              <tr>
                <th>Topic</th>
                <th>Orchestrator</th>
                <th>State</th>
                <th>Contents</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id}>
                  <td style={{ fontWeight: headingWeight }}>{r.topic}</td>
                  <td>
                    <span className="tag tag-outline">{r.mode ?? "async"}</span>
                  </td>
                  <td style={{ color: statusColor(r.status) }}>{statusWord(r.status)}</td>
                  <td style={contents}>
                    {r.status === "complete"
                      ? "Notes · Flashcards · PDFs"
                      : `${r.progress_pct}% — ${r.phase}`}
                  </td>
                  <td>
                    <button className="btn btn-ghost" onClick={() => openRun(r)}>
                      Open →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}

function statusColor(s: string) {
  if (s === "complete") return c.reagentDeep;
  if (s === "error" || s === "cancelled") return c.flagDeep;
  return c.inkSoft;
}
function statusWord(s: string) {
  if (s === "complete") return "ready";
  if (s === "error") return "failed";
  if (s === "cancelled") return "stopped";
  return "working…";
}

// ── styles ──────────────────────────────────────────────────────────────────

const page: React.CSSProperties = { maxWidth: layout.shell };

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
  margin: `0 0 ${space.xl}px`,
};

const contents: React.CSSProperties = {
  color: mutedFaint,
  fontSize: size.small,
  fontStyle: "italic",
};

const errorLine: React.CSSProperties = {
  color: c.flagDeep,
  marginBottom: space.base,
};

const empty: React.CSSProperties = {
  maxWidth: layout.measure,
  paddingTop: space.base,
};

const emptyLead: React.CSSProperties = {
  fontFamily: font.display,
  fontWeight: headingWeight,
  fontSize: size.title,
  marginBottom: space.xs,
};
