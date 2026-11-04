import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, HashRouter, NavLink, Route, Routes } from "react-router-dom";
import { isStatic, STATIC } from "./api";
import "leaflet/dist/leaflet.css";
import "./styles.css";
import MissionControl from "./pages/MissionControl";
import Explorer from "./pages/Explorer";
import Viewer from "./pages/Viewer";
import Candidates from "./pages/Candidates";
import CandidateDetail from "./pages/CandidateDetail";
import Console from "./pages/Console";
import Validation from "./pages/Validation";

const I = {
  mission: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/></svg>,
  map: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18"/></svg>,
  viewer: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/></svg>,
  list: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M8 6h13M8 12h13M8 18h13"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/></svg>,
  console: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3M13 15h4"/></svg>,
  check: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M9 12l2 2 4-4"/><path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z"/></svg>,
};

function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark" />
          <div>
            <div className="brand-name">MARSWATCH</div>
            <div className="brand-sub">surface change detection</div>
          </div>
        </div>
        <nav className="nav">
          <NavLink to="/" end>{I.mission}Mission Control</NavLink>
          <NavLink to="/explorer">{I.map}Mars Explorer</NavLink>
          <NavLink to="/viewer">{I.viewer}Before / After</NavLink>
          <NavLink to="/candidates">{I.list}Candidates</NavLink>
          <NavLink to="/validation">{I.check}Validation</NavLink>
          <NavLink to="/console">{I.console}Processing Console</NavLink>
        </nav>
        <div className="sidebar-foot">
          Imagery: NASA/JPL/University of Arizona HiRISE (PDS), USGS Astrogeology analysis-ready COGs.
          <br />
          Detections are candidates, not confirmed discoveries.
          {isStatic && <><br /><br /><b style={{ color: "var(--warn)" }}>Offline snapshot</b> exported {STATIC.exported_at}. Read-only.</>}
        </div>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<MissionControl />} />
          <Route path="/explorer" element={<Explorer />} />
          <Route path="/viewer" element={<Viewer />} />
          <Route path="/viewer/:runId" element={<Viewer />} />
          <Route path="/candidates" element={<Candidates />} />
          <Route path="/candidates/:id" element={<CandidateDetail />} />
          <Route path="/validation" element={<Validation />} />
          <Route path="/console" element={<Console />} />
        </Routes>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {isStatic ? <HashRouter><App /></HashRouter> : <BrowserRouter><App /></BrowserRouter>}
  </React.StrictMode>,
);
