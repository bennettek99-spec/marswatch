import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, asset, isStatic, CandidateRow, CATEGORY_LABEL, fmt, STATUS_LABEL } from "../api";
import { CategoryTag, Loading, ScoreBar, StatusBadge } from "../components/ui";

const COLS: { key: string; label: string; sortable?: boolean; num?: boolean }[] = [
  { key: "chip", label: "" },
  { key: "id", label: "ID", sortable: true, num: true },
  { key: "score", label: "Score", sortable: true },
  { key: "classification", label: "Status" },
  { key: "category", label: "Category" },
  { key: "eq_diameter_m", label: "Size (m)", sortable: true, num: true },
  { key: "area_m2", label: "Area (m²)", sortable: true, num: true },
  { key: "lat", label: "Lat °N", sortable: true, num: true },
  { key: "lon", label: "Lon °E", sortable: true, num: true },
  { key: "registration_quality", label: "Reg. q", sortable: true, num: true },
  { key: "pair_id", label: "Pair (before__after)" },
  { key: "methods", label: "Methods" },
];

export default function Candidates() {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [kind, setKind] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [sort, setSort] = useState("score");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(0);
  const [data, setData] = useState<{ total: number; items: CandidateRow[] }>();
  const [err, setErr] = useState<string>();
  const per = 50;

  useEffect(() => {
    const t = setTimeout(() => {
      api.candidates({ q, status, category, kind, min_score: minScore, sort, order, limit: per, offset: page * per })
        .then(setData).catch((e) => setErr(e.message));
    }, 200);
    return () => clearTimeout(t);
  }, [q, status, category, kind, minScore, sort, order, page]);

  const toggleSort = (k: string) => {
    if (sort === k) setOrder(order === "desc" ? "asc" : "desc");
    else { setSort(k); setOrder("desc"); }
  };
  const exportUrl = (fmt: string) => isStatic ? `data/candidates.${fmt}`
    : `/api/export/candidates.${fmt}?${new URLSearchParams({ ...(status && { status }), ...(kind && { kind }) })}`;

  return (
    <div className="page" style={{ maxWidth: "none" }}>
      <div className="page-head">
        <div>
          <h1>Candidate Database</h1>
          <p>Every detection with its heuristic score, status and provenance. Scores rank candidates; they are not probabilities.</p>
        </div>
        <div className="row">
          <a className="btn" href={exportUrl("csv")}>Export CSV</a>
          <a className="btn" href={exportUrl("json")}>Export JSON</a>
        </div>
      </div>
      <div className="panel" style={{ marginBottom: 12 }}>
        <div className="row" style={{ gap: 10 }}>
          <input placeholder="Search pair, ID, reference, notes…" value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} style={{ minWidth: 260 }} />
          <select value={status} onChange={(e) => { setStatus(e.target.value); setPage(0); }}>
            <option value="">All statuses</option>
            {Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select value={category} onChange={(e) => { setCategory(e.target.value); setPage(0); }}>
            <option value="">All categories</option>
            {Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <select value={kind} onChange={(e) => { setKind(e.target.value); setPage(0); }}>
            <option value="">Survey + validation + manual</option>
            <option value="survey">Survey runs</option>
            <option value="validation">Validation runs</option>
            <option value="manual">Manual runs</option>
          </select>
          <label className="row small muted">min score
            <input type="range" min={0} max={1} step={0.05} value={minScore} onChange={(e) => { setMinScore(+e.target.value); setPage(0); }} />
            <span className="mono">{minScore.toFixed(2)}</span>
          </label>
          <span className="spacer" />
          <span className="faint small">{data?.total ?? 0} candidates</span>
        </div>
      </div>
      {!data ? <Loading err={err} /> : (
        <>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  {COLS.map((c) => (
                    <th key={c.key} className={c.sortable ? "sortable" : ""} onClick={() => c.sortable && toggleSort(c.key)}>
                      {c.label}{sort === c.key ? (order === "desc" ? " ↓" : " ↑") : ""}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.items.map((c) => (
                  <tr key={c.id} className="clickable" onClick={() => nav(`/candidates/${c.id}`)}>
                    <td>{c.chips?.chip && <img className="thumb" loading="lazy" src={asset(`/runs/${encodeURIComponent(c.run_id)}/${c.chips.chip}`)} alt="" />}</td>
                    <td className="num mono">{c.id}</td>
                    <td><ScoreBar v={c.score} /></td>
                    <td><StatusBadge s={c.classification} />{c.known_match && <span className="tag" style={{ marginLeft: 4 }}>{c.known_match}</span>}</td>
                    <td><CategoryTag c={c.category} /></td>
                    <td className="num">{fmt(c.eq_diameter_m, 1)}</td>
                    <td className="num">{Math.round(c.area_m2).toLocaleString()}</td>
                    <td className="num mono">{fmt(c.lat, 4)}</td>
                    <td className="num mono">{fmt(c.lon, 4)}</td>
                    <td className="num">{fmt(c.registration_quality)}</td>
                    <td className="mono small">{c.pair_id}</td>
                    <td className="small faint">{Object.entries(c.methods || {}).filter(([, v]) => v).map(([k]) => k.split("_")[0]).join(" ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <button disabled={page === 0} onClick={() => setPage(page - 1)}>← Prev</button>
            <span className="small muted">page {page + 1} of {Math.max(1, Math.ceil(data.total / per))}</span>
            <button disabled={(page + 1) * per >= data.total} onClick={() => setPage(page + 1)}>Next →</button>
          </div>
        </>
      )}
    </div>
  );
}
