import { BrowserRouter, Link, Route, Routes, useLocation } from "react-router-dom";
import SubmitPage from "./pages/SubmitPage";
import RunPage from "./pages/RunPage";
import PackagePage from "./pages/PackagePage";
import ResultsPage from "./pages/ResultsPage";
import SignInPage from "./pages/SignInPage";
import HistoryPage from "./pages/HistoryPage";
import AppHeader from "./components/AppHeader";
import { c, font, layout, size, space } from "./theme";

function Chrome() {
  // The sign-in card is its own world — no header there. Everywhere else gets the bar.
  const { pathname } = useLocation();
  return pathname === "/signin" ? null : <AppHeader />;
}

/** Anything that isn't a route. Without this a typo renders a blank page with
 *  no clue that the URL was the problem, which is also how a misconfigured
 *  static host fails once this is deployed. */
function NotFound() {
  return (
    <main style={notFound}>
      <p style={{ fontFamily: font.mono, fontSize: size.small, color: c.inkFaint }}>404</p>
      <h1 style={{ fontFamily: font.display, fontSize: size.head, margin: `${space.sm}px 0` }}>
        No page here
      </h1>
      <p style={{ color: c.inkSoft, marginBottom: space.lg }}>
        That address doesn't match anything in the app.
      </p>
      <Link to="/">← Back to the dashboard</Link>
    </main>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Chrome />
      <Routes>
        <Route path="/" element={<SubmitPage />} />
        <Route path="/library" element={<HistoryPage />} />
        <Route path="/run/:run_id" element={<RunPage />} />
        <Route path="/session/:run_id" element={<PackagePage />} />
        {/* Benchmark for one run. Step 4 adds the cross-run view at /benchmark. */}
        <Route path="/benchmark/:run_id" element={<ResultsPage />} />
        <Route path="/signin" element={<SignInPage />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </BrowserRouter>
  );
}

const notFound: React.CSSProperties = {
  maxWidth: layout.shell,
  margin: "0 auto",
  padding: `${space.section}px ${layout.gutter}px`,
};
