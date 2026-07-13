import { BrowserRouter, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import ResultsPage from "./pages/ResultsPage";
import RunPage from "./pages/RunPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/run/:run_id" element={<RunPage />} />
        <Route path="/results/:run_id" element={<ResultsPage />} />
      </Routes>
    </BrowserRouter>
  );
}
