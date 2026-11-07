import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { myAccessState, requestAccess } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { DEMO, REPO_URL } from "../api/demo";
import type { AccessState } from "../types";
import {
  c, display, font, headingWeight, layout, muted, mutedFaint, size, space,
} from "../theme";

// Mirrors the server's caps. The server enforces them too — this is so the
// field stops accepting keystrokes rather than silently truncating on submit.
const NAME_MAX = 100;
const ORG_MAX = 100;
const MESSAGE_MAX = 1000;

export default function RequestAccessPage() {
  const navigate = useNavigate();
  const { user, ready } = useAuth();
  const [state, setState] = useState<AccessState | null>(null);
  const [name, setName] = useState("");
  const [org, setOrg] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  useEffect(() => {
    // Not in a demo build: there is no sign-in to send them to, and the page
    // below explains itself instead.
    if (!DEMO && ready && !user) {
      navigate("/signin", { state: { from: "/request-access" }, replace: true });
    }
  }, [ready, user, navigate]);

  useEffect(() => {
    if (!user) return;
    myAccessState().then(setState).catch(() => setState(null));
  }, [user]);

  if (!ready) return <p style={{ color: muted }}>One moment…</p>;

  if (DEMO) {
    return (
      <main style={page}>
        <span style={kicker}>Access</span>
        <h1 style={heading}>This demo doesn't use accounts</h1>
        <p style={intro}>
          You can explore the finished session and research results without
          signing in. This demo cannot start new runs, so there is no access to
          request here.
        </p>
        <p style={note}>
          If you would like to generate materials for your own topic, the
          repository has instructions for running the project.
        </p>
        <a
          href={REPO_URL}
          target="_blank"
          rel="noreferrer"
          className="btn btn-primary"
          style={{ textDecoration: "none" }}
        >
          View setup instructions
        </a>
      </main>
    );
  }

  if (!user) return null;

  const submit = async () => {
    if (!message.trim()) {
      setError("Add a sentence about who you are and what you'd like to see.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const res = await requestAccess(name, org, message);
      setSent(true);
      setState((s) => (s ? { ...s, pending: res.status !== "already_granted" } : s));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Couldn't send that request.");
    } finally {
      setBusy(false);
    }
  };

  if (state?.can_run) {
    return (
      <main style={page}>
        <span style={kicker}>Access</span>
        <h1 style={heading}>You can start a session</h1>
        <p style={intro}>Your account already has access to generate study materials.</p>
        <Link to="/new" className="btn btn-primary" style={{ textDecoration: "none" }}>
          Start a session
        </Link>
      </main>
    );
  }

  if (sent || state?.pending) {
    return (
      <main style={page}>
        <span style={kicker}>Access</span>
        <h1 style={heading}>Your request is in</h1>
        <p style={intro}>
          I'll review it. Once approved, you can sign in and start a new
          study session.
        </p>
        <p style={note}>
          While you wait, you can explore a finished session and read the
          research results without access.
        </p>
        <Link to="/benchmark" className="btn btn-secondary" style={{ textDecoration: "none" }}>
          Read the research results
        </Link>
      </main>
    );
  }

  return (
    <main style={page}>
      <span style={kicker}>Access</span>
      <h1 style={heading}>Request access to generate materials</h1>
      <p style={intro}>
        Anyone can read the research results. New study
        sessions use Anthropic and OpenAI API credits, so I grant access
        individually. Tell me a little about yourself and what you want to try.
      </p>

      <div style={formWrap}>
        <label style={field}>
          <span style={label}>Your name</span>
          <input
            className="input"
            value={name}
            maxLength={NAME_MAX}
            onChange={(e) => setName(e.target.value)}
            placeholder="Jane Doe"
          />
        </label>

        <label style={field}>
          <span style={label}>Company or university</span>
          <input
            className="input"
            value={org}
            maxLength={ORG_MAX}
            onChange={(e) => setOrg(e.target.value)}
            placeholder="Acme, or where you're recruiting for"
          />
        </label>

        <label style={field}>
          <span style={label}>
            What you'd like to study
            <span style={{ color: mutedFaint }}>
              {" "}
              ({MESSAGE_MAX - message.length} characters left)
            </span>
          </span>
          <textarea
            className="input"
            rows={5}
            value={message}
            maxLength={MESSAGE_MAX}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Tell me what you'd like to try. A sentence is enough."
          />
        </label>

        {error && (
          <p role="alert" style={errorLine}>
            {error}
          </p>
        )}

        <div style={{ display: "flex", gap: space.md, alignItems: "center" }}>
          <button className="btn btn-primary" onClick={submit} disabled={busy || !message.trim()}>
            {busy ? "Sending…" : "Send request"}
          </button>
          <span style={note}>I'll review your request before enabling new runs.</span>
        </div>
      </div>
    </main>
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
  margin: `0 0 ${space.xl}px`,
};

const formWrap: React.CSSProperties = { maxWidth: 560 };

const field: React.CSSProperties = {
  display: "block",
  marginBottom: space.base,
};

const label: React.CSSProperties = {
  display: "block",
  fontSize: size.small,
  color: muted,
  marginBottom: space.xs,
};

const note: React.CSSProperties = {
  fontSize: size.small,
  fontStyle: "italic",
  color: mutedFaint,
  maxWidth: layout.measure,
};

const errorLine: React.CSSProperties = {
  color: c.flagDeep,
  fontSize: size.body,
  marginBottom: space.md,
};
