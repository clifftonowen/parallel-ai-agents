import { BrowserRouter, Link, Route, Routes } from "react-router-dom";
import AppShell from "./components/AppShell";
import SubmitPage from "./pages/SubmitPage";
import RunPage from "./pages/RunPage";
import PackagePage from "./pages/PackagePage";
import ResultsPage from "./pages/ResultsPage";
import BenchmarkPage from "./pages/BenchmarkPage";
import RequestAccessPage from "./pages/RequestAccessPage";
import RequestsPage from "./pages/RequestsPage";
import SignInPage from "./pages/SignInPage";
import HistoryPage from "./pages/HistoryPage";
import { c, font, muted, size, space } from "./theme";

/** Anything that isn't a route. Without this a typo renders a blank page with
 *  no clue that the URL was the problem, which is also how a misconfigured
 *  static host fails once this is deployed. */
function NotFound() {
  return (
    <main>
      <p style={{ fontFamily: font.mono, fontSize: size.small, color: muted }}>404</p>
      <h1 style={{ fontSize: size.head, margin: `${space.sm}px 0`, color: c.ink }}>
        No page here
      </h1>
      <p style={{ color: muted, marginBottom: space.base }}>
        That address doesn't match anything in the app.
      </p>
      <Link to="/">← Back to the dashboard</Link>
    </main>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<SubmitPage />} />
          <Route path="/library" element={<HistoryPage />} />
          <Route path="/run/:run_id" element={<RunPage />} />
          <Route path="/session/:run_id" element={<PackagePage />} />
          <Route path="/benchmark" element={<BenchmarkPage />} />
          <Route path="/benchmark/:run_id" element={<ResultsPage />} />
          <Route path="/request-access" element={<RequestAccessPage />} />
          <Route path="/requests" element={<RequestsPage />} />
          <Route path="/signin" element={<SignInPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </AppShell>
    </BrowserRouter>
  );
}
