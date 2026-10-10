import { NavLink, Route, Routes } from "react-router-dom";

import Builds from "./pages/Builds";
import CampaignDetail from "./pages/CampaignDetail";
import Campaigns from "./pages/Campaigns";
import FailureDetail from "./pages/FailureDetail";

function Shield() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path d="M16 2 4 7v8c0 7.5 5.1 13.7 12 15 6.9-1.3 12-7.5 12-15V7z" fill="var(--accent)" />
      <path d="m11 16 4 4 7-8" stroke="#04121d" strokeWidth="2.5" fill="none" />
    </svg>
  );
}

function Placeholder({ title }: { title: string }) {
  return (
    <div className="panel">
      <h1>{title}</h1>
      <p className="muted">Coming next.</p>
    </div>
  );
}

export default function App() {
  return (
    <>
      <header className="topbar">
        <NavLink to="/" className="brand">
          <Shield />
          Fleet Guard
        </NavLink>
        <nav>
          <NavLink to="/" end>
            Campaigns
          </NavLink>
          <NavLink to="/builds">Builds</NavLink>
        </nav>
        <div className="spacer" />
        <a href={import.meta.env.VITE_GRAFANA_URL ?? "http://localhost:3000"} target="_blank" rel="noreferrer"
          className="muted">
          Grafana
        </a>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Campaigns />} />
          <Route path="/campaigns/:id" element={<CampaignDetail />} />
          <Route path="/failures/:id" element={<FailureDetail />} />
          <Route path="/builds" element={<Builds />} />
          <Route path="*" element={<Placeholder title="Not found" />} />
        </Routes>
      </main>
    </>
  );
}
