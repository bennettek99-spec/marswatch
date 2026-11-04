import { Fragment } from "react";
import { Link } from "react-router-dom";
import { api, CATEGORY_LABEL, fmt, STATUS_LABEL } from "../api";
import { JobBadge, Loading, Plot, Stat, usePoll } from "../components/ui";

const STATUS_COLORS: Record<string, string> = {
  known_documented: "#8f7cf0",
  plausible_unverified: "#3fb68b",
  insufficient_evidence: "#e8b44c",
  likely_artifact: "#6f7986",
};

export default function MissionControl() {
  const [ov, err] = usePoll(api.overview, 8000);
  const [runs] = usePoll(() => api.runs(), 15000);
  if (!ov) return <div className="page"><Loading err={err} /></div>;
  const v = ov.validation;
  const op = (v?.operating_points || []) as any[];
  const statuses = ["known_documented", "plausible_unverified", "insufficient_evidence", "likely_artifact"];
  const cats = Object.entries(ov.candidates_by_category as Record<string, number>).sort((a, b) => b[1] - a[1]);
  const tl = (ov.timeline as any[]).filter((t) => t.finished_at);
  let cum = 0;
  const cumArea = tl.map((t) => (cum += t.area_km2 || 0));

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Mission Control</h1>
          <p>
            Autonomous search of public HiRISE imagery for surface changes. All counts come from the local MARSWATCH
            database; scores are heuristic rankings and every candidate requires expert review.
          </p>
        </div>
        <div className="row">
          <span className="muted small">Worker</span>
          <JobBadge s={ov.worker.paused ? "cancelled" : (ov.jobs.running ? "running" : "done")} />
          <span className="faint small">{ov.worker.paused ? "paused" : ov.jobs.running ? "processing" : "idle"}</span>
        </div>
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Stat label="Image pairs analysed" value={ov.pairs_analysed} sub={`${ov.runs_done} runs · ${ov.pairs_discovered} pairs discovered`} />
        <Stat label="Surface inspected" value={<>{fmt(ov.area_km2, 1)} <span className="faint" style={{ fontSize: 16 }}>km²</span></>}
          sub={`${ov.observations_indexed.toLocaleString()} HiRISE RED products indexed`} />
        <Stat label="Candidate detections" value={ov.candidates}
          sub={`${ov.candidates_by_status.plausible_unverified || 0} plausible · ${ov.candidates_by_status.known_documented || 0} known`} />
        <Stat label="Validation recall"
          value={v ? `${fmt((op.find((o) => o.threshold === 0.3)?.recall_any_category ?? 0) * 100, 0)}%` : "—"}
          sub={v ? `${v.n_cases} documented craters · score ≥ 0.3` : "run `marswatch validate`"} />
      </div>

      <div className="grid g3" style={{ marginBottom: 14 }}>
        <div className="panel">
          <div className="panel-head"><h3>Candidates by status</h3><Link to="/candidates" className="small">open catalog →</Link></div>
          <Plot height={230} data={[{
            type: "bar", orientation: "h",
            y: statuses.map((s) => STATUS_LABEL[s]), x: statuses.map((s) => ov.candidates_by_status[s] || 0),
            marker: { color: statuses.map((s) => STATUS_COLORS[s]) }, hovertemplate: "%{y}: %{x}<extra></extra>",
          }]} layout={{ margin: { l: 150, r: 10, t: 4, b: 30 }, yaxis: { autorange: "reversed" } }} />
        </div>
        <div className="panel">
          <div className="panel-head"><h3>Candidates by category</h3><span className="faint small">heuristic</span></div>
          <Plot height={230} data={[{
            type: "bar", orientation: "h", y: cats.map(([c]) => CATEGORY_LABEL[c] || c), x: cats.map(([, n]) => n),
            marker: { color: "#e0662f" }, hovertemplate: "%{y}: %{x}<extra></extra>",
          }]} layout={{ margin: { l: 190, r: 10, t: 4, b: 30 }, yaxis: { autorange: "reversed" } }} />
        </div>
        <div className="panel">
          <div className="panel-head"><h3>Validation operating points</h3><Link to="/validation" className="small">details →</Link></div>
          {op.length ? (
            <Plot height={230} data={[
              { x: op.map((o) => o.threshold), y: op.map((o) => o.recall_any_category), name: "recall", mode: "lines+markers", line: { color: "#3fb68b" } },
              { x: op.map((o) => o.threshold), y: op.map((o) => o.precision_window_assumption), name: "precision*", mode: "lines+markers", line: { color: "#8f7cf0" } },
              { x: op.map((o) => o.threshold), y: op.map((o) => o.fp_per_km2_positive_windows), name: "FP / km²", yaxis: "y2", mode: "lines+markers", line: { color: "#e5534b", dash: "dot" } },
            ]} layout={{ xaxis: { title: { text: "score threshold" } }, yaxis: { range: [0, 1.05] },
              yaxis2: { overlaying: "y", side: "right", gridcolor: "rgba(0,0,0,0)", color: "#e5534b" }, margin: { l: 40, r: 40, t: 4, b: 60 } }} />
          ) : <div className="faint">No validation run yet.</div>}
        </div>
      </div>

      <div className="grid g-side">
        <div className="panel">
          <div className="panel-head"><h3>Recent analyses</h3><span className="faint small">{runs?.length ?? 0} runs</span></div>
          <div className="table-wrap" style={{ maxHeight: 420 }}>
            <table>
              <thead><tr><th>Pair</th><th>Kind</th><th>Area km²</th><th>Registration</th><th>RMS px</th><th>Cand.</th><th>Plausible</th><th /></tr></thead>
              <tbody>
                {(runs || []).slice(0, 60).map((r: any) => (
                  <tr key={r.run_id}>
                    <td className="mono">{r.pair_id}</td>
                    <td><span className="tag">{r.kind}</span></td>
                    <td className="num">{fmt(r.analysed_km2)}</td>
                    <td><JobBadge s={r.registration?.status || r.status} /></td>
                    <td className="num">{fmt(r.registration?.check_rms_px)}</td>
                    <td className="num">{r.n_candidates ?? "—"}</td>
                    <td className="num">{r.by_status?.plausible_unverified ?? "—"}</td>
                    <td>{r.status === "done" && <Link to={`/viewer/${encodeURIComponent(r.run_id)}`}>view</Link>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="grid" style={{ alignContent: "start" }}>
          <div className="panel">
            <div className="panel-head"><h3>Processing status</h3><Link to="/console" className="small">console →</Link></div>
            <dl className="kv">
              {["running", "queued", "done", "failed", "cancelled"].map((s) => (
                <Fragment key={s}><dt>{s}</dt><dd>{ov.jobs[s] || 0}</dd></Fragment>
              ))}
            </dl>
          </div>
          <div className="panel">
            <div className="panel-head"><h3>Cumulative area analysed</h3></div>
            <Plot height={170} data={[{ x: tl.map((t) => new Date(t.finished_at * 1000)), y: cumArea, mode: "lines", fill: "tozeroy",
              line: { color: "#e0662f" }, fillcolor: "rgba(224,102,47,0.15)" }]}
              layout={{ margin: { l: 40, r: 10, t: 4, b: 30 }, yaxis: { title: { text: "km²" } } }} />
          </div>
          <div className="notice">
            Registration on real pairs: median checkpoint RMS{" "}
            <b>{fmt(v?.registration?.checkpoint_rms_px_median)} px</b> across {v?.registration?.runs ?? 0} validation runs.
            Pointing offsets of {fmt(v?.registration?.coarse_offset_m_median, 0)} m (median) are corrected by image matching.
          </div>
        </div>
      </div>
    </div>
  );
}
