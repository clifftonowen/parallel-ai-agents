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
        <h1 style={heading}>Nothing to request here</h1>
        <p style={intro}>
          Access decides who can spend API credits on the live deployment. This
          build has no backend and spends nothing, so there is no queue to join.
        </p>
        <p style={note}>
          The finished session and the benchmark numbers are open, and the
          source is public. If you want to see it generate something new, say so
          on the repository.
        </p>
        <a
          href={REPO_URL}
          target="_blank"
          rel="noreferrer"
          className="btn btn-primary"
          style={{ textDecoration: "none" }}
        >
          Open the repository
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
        <h1 style={heading}>You're already in</h1>
        <p style={intro}>This account can start runs. Nothing else to do here.</p>
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
        <h1 style={heading}>Request sent</h1>
        <p style={intro}>
          It's with the developer. You'll be able to start runs once it's
          approved. Sign in again later and the Generate button will work.
        </p>
        <p style={note}>
          In the meantime the Benchmark page works without access: it's the
          measurement side of the project, and the numbers there are real.
        </p>
        <Link to="/benchmark" className="btn btn-secondary" style={{ textDecoration: "none" }}>
          See the benchmarks
        </Link>
      </main>
    );
  }

  return (
    <main style={page}>
      <span style={kicker}>Access</span>
      <h1 style={heading}>Ask for a demo account</h1>
      <p style={intro}>
        Anyone can sign up and read. Starting a run calls the Anthropic and
        OpenAI APIs and costs real money, so I grant that by hand. Tell me who
        you are and I'll switch it on.
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
            Why you'd like access
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
            placeholder="A sentence is plenty."
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
          <span style={note}>Sent to the developer, not stored anywhere else.</span>
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
