import { Link } from "react-router-dom";
import { c, font } from "../theme";

// A quiet, consistent top bar, mirroring study-bench/src/components/AppHeader.tsx.
// Left: the wordmark (home). Right: a cross-link to the learner app, which runs
// as a separate Vite dev server (port 5174) so it's a plain <a>, not a <Link>.
export default function AppHeader() {
  return (
    <div style={bar}>
      <Link to="/" style={wordmark}>
        Study Bench · Dashboard
      </Link>

      <nav style={right}>
        <a href="http://localhost:5274" style={navLink}>
          Learner App →
        </a>
      </nav>
    </div>
  );
}

const bar: React.CSSProperties = {
  maxWidth: 900,
  margin: "0 auto",
  padding: "18px 20px 0",
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

const right: React.CSSProperties = { display: "flex", alignItems: "baseline", gap: 14 };

const navLink: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  color: c.reagent,
};
