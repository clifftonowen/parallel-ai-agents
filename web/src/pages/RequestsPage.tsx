import { useEffect, useState } from "react";
import { accessRequestQueue, myAccessState } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { AccessRequestRow } from "../types";
import {
  c, display, font, headingWeight, layout, muted, mutedFaint, size, space,
} from "../theme";

/**
 * The access-request queue.
 *
 * Everything shown here was typed by somebody asking for access, and the person
 * reading it holds the grant — which makes them the highest-value XSS target in
 * the system. So every requester-supplied string is rendered as a React text
 * child, which escapes it. This page must never use `Markdown`, and never
 * `dangerouslySetInnerHTML`.
 *
 * It is read-only. Granting has no HTTP route at all; it is
 * `scripts/grant_access.py`, run locally.
 */
export default function RequestsPage() {
  const { user, ready } = useAuth();
  const [rows, setRows] = useState<AccessRequestRow[] | null>(null);
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [status, setStatus] = useState<"pending" | "granted">("pending");

  useEffect(() => {
    if (!user) return;
    myAccessState()
      .then((s) => setAllowed(s.is_admin))
      .catch(() => setAllowed(false));
  }, [user]);

  useEffect(() => {
    if (!allowed) return;
    setRows(null);
    accessRequestQueue(status)
      .then(setRows)
      .catch(() => setRows([]));
  }, [allowed, status]);

  if (!ready) return <p style={{ color: muted }}>One moment…</p>;

  // Same shape as the server's 404: to a non-admin this page does not exist.
  if (allowed === false || !user) {
    return (
      <main style={page}>
        <p style={{ fontFamily: font.mono, fontSize: size.small, color: muted }}>404</p>
        <h1 style={heading}>No page here</h1>
        <p style={intro}>That address doesn't match anything in the app.</p>
      </main>
    );
  }

  return (
    <main style={page}>
      <span style={kicker}>Admin</span>
      <h1 style={heading}>Access requests</h1>
      <p style={intro}>
        Read-only. To let somebody in, run{" "}
        <code>python scripts/grant_access.py --grant their@email</code> on the
        machine holding the database.
      </p>

      <div className="seg" style={{ marginBottom: space.xl }}>
        {(["pending", "granted"] as const).map((s) => (
          <button
            key={s}
            className="seg-opt"
            aria-pressed={status === s}
            onClick={() => setStatus(s)}
          >
            {s === "pending" ? "Pending" : "Granted"}
          </button>
        ))}
      </div>

      {rows === null ? (
        <p style={{ color: muted }}>Loading…</p>
      ) : rows.length === 0 ? (
        <p style={{ color: muted }}>
          {status === "pending" ? "Nothing waiting." : "Nobody granted yet."}
        </p>
      ) : (
        <div style={list}>
          {rows.map((r) => (
            <article key={r.id} className="card elev-sm" style={card}>
              <div style={cardHead}>
                {/* Text children, not markup. See the note at the top. */}
                <span style={who}>{r.name || "(no name given)"}</span>
                <span style={when}>{r.created_at.slice(0, 16).replace("T", " ")}</span>
              </div>
              <div style={metaLine}>
                {r.email}
                {r.org ? ` · ${r.org}` : ""}
              </div>
              <p style={messageStyle}>{r.message}</p>
              {status === "pending" && (
                <code style={grantHint}>
                  python scripts/grant_access.py --grant {r.email}
                </code>
              )}
            </article>
          ))}
        </div>
      )}
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

const list: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: space.base,
  maxWidth: 720,
};

const card: React.CSSProperties = { gap: space.sm };

const cardHead: React.CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  justifyContent: "space-between",
  gap: space.md,
};

const who: React.CSSProperties = {
  fontFamily: font.display,
  fontWeight: headingWeight,
  fontSize: size.lead,
};

const when: React.CSSProperties = {
  fontSize: size.small,
  fontStyle: "italic",
  color: mutedFaint,
  flex: "none",
};

const metaLine: React.CSSProperties = {
  fontSize: size.small,
  color: muted,
  // A long unbroken email must not push the card sideways.
  overflowWrap: "anywhere",
};

const messageStyle: React.CSSProperties = {
  margin: 0,
  fontSize: size.body,
  lineHeight: 1.5,
  // Preserve the requester's line breaks without letting them escape the card.
  whiteSpace: "pre-wrap",
  overflowWrap: "anywhere",
};

const grantHint: React.CSSProperties = {
  fontSize: size.micro,
  color: mutedFaint,
  overflowWrap: "anywhere",
};
