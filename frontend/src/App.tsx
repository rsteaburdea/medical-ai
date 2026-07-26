import { NavLink, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import ClinicalPage from "./pages/ClinicalPage";
import ClinicalProgressPage from "./pages/ClinicalProgressPage";
import MatcherPage from "./pages/MatcherPage";
import PubMedChatPage from "./pages/PubMedChatPage";

export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to="/" className="brand">
          <strong>MedTrain AI</strong>
          <span>Clinical stations & PubMed agents</span>
        </NavLink>
        <nav className="nav-links">
          <NavLink to="/" end>
            Agents
          </NavLink>
          <NavLink to="/clinical" end>
            CST Station
          </NavLink>
          <NavLink to="/clinical/progress">CST Progress</NavLink>
          <NavLink to="/matcher">Article Match</NavLink>
          <NavLink to="/pubmed-chat">Literature Chat</NavLink>
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/clinical" element={<ClinicalPage />} />
        <Route path="/clinical/progress" element={<ClinicalProgressPage />} />
        <Route path="/matcher" element={<MatcherPage />} />
        <Route path="/pubmed-chat" element={<PubMedChatPage />} />
      </Routes>
    </div>
  );
}
