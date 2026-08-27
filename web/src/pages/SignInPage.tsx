import { useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { DEMO, DEMO_RUN_ID, REPO_URL } from "../api/demo";
import { c, font, eyebrow, layout, size, displaySmall } from "../theme";

// ── Sign in ─────────────────────────────────────────────────────────────────
// A login page is where generic templates take over (centered box, two inputs, a
// Google button). Signing in is what makes a session survive a restart, so the
// copy says that rather than selling an account. The card is the one bold element; everything
// else on the page stays quiet.

type Mode = "in" | "up";

export default function SignInPage() {
  const { user, login, signup } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/";

  const [mode, setMode] = useState<Mode>("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Already signed in? There's nothing to do here.
  useEffect(() => {
    if (user) navigate(from, { replace: true });
  }, [user, navigate, from]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "up") await signup(email, password);
      else await login(email, password);
      navigate(from, { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "That didn't work. Try again.");
      setBusy(false);
    }
  };

  if (DEMO) {
    return (
      <main style={page}>
        <button onClick={() => navigate("/")} style={backLink}>
          ← back to the front page
        </button>

        <div style={card} className="animate-rise">
          <div style={cardHead}>
            <span style={eyebrow}>UROP</span>
            <span style={{ ...eyebrow, color: c.inkFaint }}>· demo build</span>
          </div>
          <div style={cardRule} />

          <h1 style={cardTitle}>No accounts here</h1>
          <p style={cardSub}>
            Accounts live on the deployment that has a backend behind it. This
            one is static files, so there is nothing to sign in to.
          </p>
          <p style={cardSub}>
            The <Link to={`/session/${DEMO_RUN_ID}`}>finished session</Link> and
            the <Link to="/benchmark">benchmark numbers</Link> are open anyway.
          </p>

          <a
            href={REPO_URL}
            target="_blank"
            rel="noreferrer"
            style={{ ...primary, display: "block", textAlign: "center", textDecoration: "none" }}
          >
            Run it yourself
          </a>
        </div>
      </main>
    );
  }

  return (
    <main style={page}>
      <button onClick={() => navigate("/")} style={backLink}>
        ← back to the front page
      </button>

      <div style={card} className="animate-rise">
        {/* Card header — stamped like a catalog card. */}
        <div style={cardHead}>
          <span style={eyebrow}>UROP</span>
          <span style={{ ...eyebrow, color: c.inkFaint }}>· sign in</span>
        </div>
        <div style={cardRule} />

        <h1 style={cardTitle}>
          {mode === "in" ? "Sign in" : "Create an account"}
        </h1>
        <p style={cardSub}>
          {mode === "in"
            ? "Your studied topics are filed here, waiting for you."
            : "An account keeps every session in one place, private to you."}
        </p>

        <form onSubmit={submit} noValidate>
          <label style={fieldLabel} htmlFor="email">
            Email
          </label>
          <input
            id="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            autoFocus
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@email.com"
            style={field}
          />

          <label style={fieldLabel} htmlFor="password">
            Password
          </label>
          <input
            id="password"
            type="password"
            autoComplete={mode === "up" ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={mode === "up" ? "at least 8 characters" : "your password"}
            style={field}
          />

          {error && (
            <p role="alert" aria-live="polite" style={errorLine}>
              {error}
            </p>
          )}

          <button type="submit" disabled={busy} style={{ ...primary, opacity: busy ? 0.6 : 1 }}>
            {busy ? "One moment…" : mode === "in" ? "Sign in" : "Create account"}
          </button>
        </form>

        {/* Deferred Google — honest: it's clearly not ready, not a dead button pretending. */}
        <button type="button" disabled style={googleBtn} title="Not available yet">
          Continue with Google
          <span style={soonTag}>soon</span>
        </button>

        {/* Footer: what signing in is actually for, and the mode switch. */}
        <div style={cardFoot}>
          <span style={issuedLine}>Reading is open; running needs an account</span>
          <button
            type="button"
            onClick={() => {
              setMode((m) => (m === "in" ? "up" : "in"));
              setError(null);
            }}
            style={switchLink}
          >
            {mode === "in" ? "New here? Create an account" : "Already have an account? Sign in"}
          </button>
        </div>
      </div>
    </main>
  );
}

// ── styles ────────────────────────────────────────────────────────────────────

const page: React.CSSProperties = { maxWidth: layout.narrow, margin: "0 auto", padding: "40px 22px 80px" };

const backLink: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.small,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  color: c.inkSoft,
  marginBottom: 28,
  display: "inline-block",
};

// The card itself: heavier ink border + a faint top "tab" reads as an index card.
const card: React.CSSProperties = {
  border: `1.5px solid ${c.ink}`,
  backgroundColor: c.paperCard,
  padding: "26px 26px 20px",
  boxShadow: `6px 6px 0 ${c.paperDeep}`,
};

const cardHead: React.CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  gap: 8,
  marginBottom: 10,
};
const cardRule: React.CSSProperties = { height: 2, backgroundColor: c.ink, marginBottom: 20 };

const cardTitle: React.CSSProperties = {
  fontFamily: font.display,
  fontSize: displaySmall,
  fontWeight: 600,
  lineHeight: 1.05,
  letterSpacing: "-0.015em",
  color: c.ink,
};
const cardSub: React.CSSProperties = { fontSize: size.body, color: c.inkSoft, marginTop: 8, marginBottom: 22 };

const fieldLabel: React.CSSProperties = {
  display: "block",
  fontFamily: font.mono,
  fontSize: size.micro,
  fontWeight: 700,
  letterSpacing: "0.16em",
  textTransform: "uppercase",
  color: c.inkFaint,
  marginBottom: 6,
};

// Fields are ruled lines, not boxes — you write on the card.
const field: React.CSSProperties = {
  width: "100%",
  border: "none",
  borderBottom: `1px solid ${c.rule}`,
  background: "transparent",
  padding: "8px 2px",
  marginBottom: 18,
  fontFamily: font.body,
  fontSize: size.lead,
  color: c.ink,
  outline: "none",
};

const errorLine: React.CSSProperties = {
  color: c.flag,
  fontFamily: font.mono,
  fontSize: size.small,
  marginBottom: 14,
};

const primary: React.CSSProperties = {
  width: "100%",
  backgroundColor: c.reagent,
  color: c.paper,
  fontFamily: font.body,
  fontSize: size.lead,
  fontWeight: 600,
  padding: "13px 20px",
};

const googleBtn: React.CSSProperties = {
  width: "100%",
  marginTop: 12,
  border: `1px solid ${c.rule}`,
  color: c.inkFaint,
  backgroundColor: "transparent",
  fontFamily: font.body,
  fontSize: size.body,
  fontWeight: 500,
  padding: "11px 20px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  gap: 8,
  cursor: "not-allowed",
};
const soonTag: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.micro,
  fontWeight: 700,
  letterSpacing: "0.14em",
  textTransform: "uppercase",
  border: `1px solid ${c.rule}`,
  padding: "1px 5px",
  color: c.inkFaint,
};

const cardFoot: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "baseline",
  gap: 12,
  marginTop: 22,
  paddingTop: 14,
  borderTop: `1px solid ${c.ruleSoft}`,
  flexWrap: "wrap",
};
const issuedLine: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.micro,
  letterSpacing: "0.08em",
  color: c.inkFaint,
};
const switchLink: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.micro,
  fontWeight: 700,
  letterSpacing: "0.06em",
  color: c.reagent,
  textTransform: "uppercase",
};
