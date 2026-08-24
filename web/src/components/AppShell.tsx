import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { listRuns, stats as fetchStats } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { RunSummary, Stats } from "../types";
import {
  c, eyebrow, font, headingWeight, layout, muted, mutedFaint, size, space,
} from "../theme";

/** The four agents the pipeline actually runs, in pipeline order.
 *
 *  The design this is ported from listed "Research / Notes / Quiz / Media" with
 *  four permanently-green lights. These are the real agent classes, and the
 *  dots follow the live run instead of always claiming everything is up. */
const AGENTS = [
  { name: "Notes", phase: "phase1", detail: "structures the research into notes" },
  { name: "Flashcards", phase: "phase2", detail: "drafts recall prompts" },
  { name: "Video", phase: "phase2", detail: "narration, slides, assembly" },
  { name: "PDF", phase: "phase3", detail: "renders handouts via pandoc" },
] as const;

const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/library", label: "Library" },
  { to: "/benchmark", label: "Benchmark" },
];

const SIGNED_OUT_PATHS = ["/signin"];

function Meter({ label, value, cap, note, tone }: {
  label: string;
  value: number;
  cap: number;
  note: string;
  tone: string;
}) {
  const pct = cap > 0 ? Math.min(100, Math.round((value / cap) * 100)) : 0;
  return (
    <div style={{ marginBottom: space.md }}>
      <div style={meterHead}>
        <span>{label}</span>
        <span style={{ color: mutedFaint }}>{note}</span>
      </div>
      <div
        style={meterTrack}
        role="progressbar"
        aria-label={label}
        aria-valuenow={value}
        aria-valuemin={0}
        aria-valuemax={cap}
      >
        <div style={{ height: "100%", width: `${pct}%`, background: tone }} />
      </div>
    </div>
  );
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const [stats, setStats] = useState<Stats | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);

  const refresh = useCallback(async () => {
    try {
      const [s, r] = await Promise.all([fetchStats(), listRuns()]);
      setStats(s);
      setRuns(r);
    } catch {
      /* backend may be down; the rail degrades to zeros rather than erroring */
    }
  }, []);

  useEffect(() => {
    refresh();
    window.addEventListener("focus", refresh);
    return () => window.removeEventListener("focus", refresh);
  }, [refresh, user, pathname]);

  // The sign-in card is its own world — no rail there.
  if (SIGNED_OUT_PATHS.includes(pathname)) return <>{children}</>;

  const activeRun = runs.find((r) => r.status === "running");
  const section = NAV.find((n) => n.to === pathname)?.label
    ?? (pathname.startsWith("/session") ? "Session"
      : pathname.startsWith("/run") ? "Session"
      : pathname.startsWith("/benchmark") ? "Benchmark"
      : "Not found");

  const signOut = async () => {
    await logout();
    navigate("/");
  };

  return (
    <div className="shell">
      <aside className="shell-rail">
        <div style={{ marginBottom: space.lg }}>
          <Link to="/" style={wordmark}>UROP</Link>
          <div style={tagline}>Multi-agent content lab</div>
        </div>

        {user ? (
          <div style={account}>
            <span style={avatar}>{user.email.slice(0, 2).toUpperCase()}</span>
            <span style={{ minWidth: 0, flex: 1 }}>
              <span style={accountName}>{user.email.split("@")[0]}</span>
              <span style={accountSub}>signed in</span>
            </span>
          </div>
        ) : (
          <Link to="/signin" style={{ ...account, textDecoration: "none" }}>
            <span style={{ ...avatar, background: c.rule, color: c.inkSoft }}>?</span>
            <span style={{ minWidth: 0, flex: 1 }}>
              <span style={accountName}>Not signed in</span>
              <span style={accountSub}>sessions won't be saved</span>
            </span>
          </Link>
        )}

        <button
          className="btn btn-primary btn-block"
          style={{ marginBottom: space.xl }}
          onClick={() => navigate("/")}
        >
          New session
        </button>

        <nav className="shell-nav">
          {NAV.map((n) => {
            const on = n.to === pathname;
            return (
              <Link
                key={n.to}
                to={n.to}
                aria-current={on ? "page" : undefined}
                style={{
                  ...navItem,
                  fontWeight: on ? headingWeight : 400,
                  color: on ? c.reagentDeep : c.ink,
                  background: on ? c.reagentWash : "transparent",
                }}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>

        <div className="rail-secondary" style={{ ...eyebrow, marginBottom: space.sm }}>Agents</div>
        <div className="rail-secondary" style={agentList}>
          {AGENTS.map((a) => {
            const live = activeRun?.phase === a.phase;
            return (
              <div key={a.name} style={agentRow} title={a.detail}>
                <span
                  className={live ? "animate-pulse" : undefined}
                  style={{ ...dot, background: live ? c.reagent : c.rule }}
                />
                {a.name}
                {live && <span style={agentNote}>working</span>}
              </div>
            );
          })}
        </div>

        <div className="rail-spacer" style={{ flex: 1, minHeight: space.xl }} />

        <div className="rail-secondary" style={{ ...eyebrow, marginBottom: space.md }}>This machine</div>
        <div className="rail-secondary">
        <Meter
          label="Sessions"
          value={stats?.runs_complete ?? 0}
          cap={Math.max(stats?.runs_total ?? 0, 1)}
          note={`${stats?.runs_complete ?? 0} of ${stats?.runs_total ?? 0} finished`}
          tone={c.reagent}
        />
        <Meter
          label="Cache reuse"
          value={stats?.cache.hits ?? 0}
          cap={Math.max(stats?.cache.entries ?? 0, 1)}
          note={`${stats?.cache.hits ?? 0} hits / ${stats?.cache.entries ?? 0} topics`}
          tone={c.flag}
        />
        <p style={meterFoot}>
          Counts from this machine's database. No plan, no quota.
        </p>
        </div>

        {user && (
          <button className="btn btn-secondary btn-block" onClick={signOut}>
            Sign out
          </button>
        )}
      </aside>

      <div className="shell-main">
        <div style={topbar}>
          <div style={topbarTitle}>{section}</div>
          {activeRun && (
            <Link to={`/run/${activeRun.run_id}`} className="tag tag-accent">
              running: {activeRun.topic.slice(0, 32)}
            </Link>
          )}
        </div>
        <div style={scroller}>{children}</div>
      </div>
    </div>
  );
}

// ── styles ──────────────────────────────────────────────────────────────────



const wordmark: React.CSSProperties = {
  fontFamily: font.display,
  fontWeight: headingWeight,
  fontSize: 23,
  lineHeight: 1.1,
  color: c.ink,
  textDecoration: "none",
};

const tagline: React.CSSProperties = {
  fontSize: size.small,
  fontStyle: "italic",
  color: muted,
};

const account: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: space.sm,
  marginBottom: space.lg,
  color: c.ink,
};

const avatar: React.CSSProperties = {
  width: 32,
  height: 32,
  flex: "none",
  borderRadius: "50%",
  background: c.reagent,
  color: c.paper,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontFamily: font.display,
  fontWeight: headingWeight,
  fontSize: size.small,
};

const accountName: React.CSSProperties = {
  display: "block",
  fontWeight: headingWeight,
  fontSize: size.body,
  lineHeight: 1.2,
  whiteSpace: "nowrap",
  overflow: "hidden",
  textOverflow: "ellipsis",
};

const accountSub: React.CSSProperties = {
  display: "block",
  fontSize: size.small,
  fontStyle: "italic",
  color: muted,
};


const navItem: React.CSSProperties = {
  padding: "8px 10px",
  fontSize: size.body,
  textDecoration: "none",
  borderRadius: 2,
};

const agentList: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 7,
  fontSize: size.body,
  color: muted,
};

const agentRow: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: space.sm,
};

const dot: React.CSSProperties = {
  width: 6,
  height: 6,
  borderRadius: "50%",
  flex: "none",
};

const agentNote: React.CSSProperties = {
  fontSize: size.micro,
  fontStyle: "italic",
  color: c.reagentDeep,
};

const meterHead: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  fontSize: size.small,
  marginBottom: 5,
};

const meterTrack: React.CSSProperties = {
  height: 5,
  background: c.rule,
};

const meterFoot: React.CSSProperties = {
  fontSize: size.micro,
  fontStyle: "italic",
  color: mutedFaint,
  marginBottom: space.md,
};


const topbar: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: space.base,
  padding: `${space.xl}px ${layout.gutter}px ${space.base}px`,
};

const topbarTitle: React.CSSProperties = {
  fontFamily: font.display,
  fontSize: size.small,
  fontWeight: headingWeight,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  color: muted,
};

const scroller: React.CSSProperties = {
  flex: 1,
  padding: `0 ${layout.gutter}px ${space.section}px`,
};
