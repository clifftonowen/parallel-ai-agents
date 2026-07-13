import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { c, font } from "../theme";

// A quiet, consistent top bar. Left: the wordmark (home). Right: sign in, or your
// email + history + sign out. Signing in is never required — this is just the door.
export default function AppHeader() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const signOut = async () => {
    await logout();
    navigate("/");
  };

  return (
    <div style={bar}>
      <Link to="/" style={wordmark}>
        Study Bench
      </Link>

      <nav style={right}>
        {user ? (
          <>
            <Link to="/history" style={navLink}>
              History
            </Link>
            <span style={emailChip} title={user.email}>
              {user.email}
            </span>
            <button onClick={signOut} style={navBtn}>
              Sign out
            </button>
          </>
        ) : (
          <Link to="/signin" style={signInLink}>
            Sign in
          </Link>
        )}
      </nav>
    </div>
  );
}

const bar: React.CSSProperties = {
  maxWidth: 820,
  margin: "0 auto",
  padding: "18px 22px 0",
  display: "flex",
  alignItems: "baseline",
  justifyContent: "space-between",
  gap: 12,
};

const wordmark: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 12,
  fontWeight: 700,
  letterSpacing: "0.18em",
  textTransform: "uppercase",
  color: c.ink,
};

const right: React.CSSProperties = { display: "flex", alignItems: "baseline", gap: 14, flexWrap: "wrap" };

const linkBase: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
};

const navLink: React.CSSProperties = { ...linkBase, color: c.inkSoft };
const navBtn: React.CSSProperties = { ...linkBase, color: c.inkSoft };
const signInLink: React.CSSProperties = { ...linkBase, color: c.reagent };

const emailChip: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  color: c.inkFaint,
  maxWidth: 180,
  overflow: "hidden",
  textOverflow: "ellipsis",
  whiteSpace: "nowrap",
};
