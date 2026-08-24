import { Link } from "react-router-dom";
import { c, font, layout, size, space } from "../theme";

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
  maxWidth: layout.shell,
  margin: "0 auto",
  padding: `${space.base}px ${layout.gutter}px 0`,
  display: "flex",
  alignItems: "baseline",
  justifyContent: "space-between",
  gap: 12,
};

const wordmark: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.small,
  fontWeight: 700,
  letterSpacing: "0.18em",
  textTransform: "uppercase",
  whiteSpace: "nowrap",
  color: c.ink,
};

const right: React.CSSProperties = {
  display: "flex",
  alignItems: "baseline",
  gap: space.base,
  flexWrap: "wrap",
};

const navLink: React.CSSProperties = {
  fontFamily: font.mono,
  fontSize: size.micro,
  fontWeight: 700,
  letterSpacing: "0.1em",
  textTransform: "uppercase",
  color: c.inkSoft,
};
