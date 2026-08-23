import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import SubmitPage from "./pages/SubmitPage";
import RunPage from "./pages/RunPage";
import PackagePage from "./pages/PackagePage";
import SignInPage from "./pages/SignInPage";
import HistoryPage from "./pages/HistoryPage";
import AppHeader from "./components/AppHeader";

function Chrome() {
  // The sign-in card is its own world — no header there. Everywhere else gets the bar.
  const { pathname } = useLocation();
  return pathname === "/signin" ? null : <AppHeader />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Chrome />
      <Routes>
        <Route path="/" element={<SubmitPage />} />
        <Route path="/run/:run_id" element={<RunPage />} />
        <Route path="/package/:run_id" element={<PackagePage />} />
        <Route path="/signin" element={<SignInPage />} />
        <Route path="/history" element={<HistoryPage />} />
      </Routes>
    </BrowserRouter>
  );
}
