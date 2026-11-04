import { Fragment, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmt } from "../api";
import { Loading, Markdown, Plot, usePoll } from "../components/ui";

export default function Validation() {
  const [v, err] = usePoll(api.validation, 0);
  const [doc] = usePoll(() => api.doc("VALIDATION").catch(() => ""), 0);
  const [tab, setTab] = useState<"results" | "method">("results");
  const [set, setSet] = useState<"crater_validation" | "crater_validation_holdout">("crater_validation_holdout");
  if (!v) return <div className="page"><Loading err={err} /></div>;
  const cv = v[set] || v.crater_validation;
  const m = cv?.metrics;
  const injEasy = v.injection_sensitivity;
  const inj = v.injection_sensitivity_hard || injEasy;
  const rs = v.registration_synthetic;

  const injDs = inj ? Array.from(new Set(inj.table.map((r: any) => r.diameter_m))) as number[] : [];
  const injCs = inj ? Array.from(new Set(inj.table.map((r: any) => r.halo_contrast))) as number[] : [];

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Scientific Validation</h1>
          <p>
            Performance measured on documented new impact craters (Daubar et al. 2022, JGR Planets) with real HiRISE
            observations before and after formation, same-site negative controls, and clearly labelled synthetic tests.
          </p>
        </div>
        <div className="row">
        <div className="seg">
          <button className={set === "crater_validation_holdout" ? "on" : ""} onClick={() => setSet("crater_validation_holdout")} disabled={!v.crater_validation_holdout}>Held-out pairs</button>
          <button className={set === "crater_validation" ? "on" : ""} onClick={() => setSet("crater_validation")}>Tuning set</button>
        </div>
        <div className="seg">
          <button className={tab === "results" ? "on" : ""} onClick={() => setTab("results")}>Results</button>
          <button className={tab === "method" ? "on" : ""} onClick={() => setTab("method")}>Method &amp; caveats</button>
        </div>
        </div>
      </div>
      {tab === "method" ? <div className="panel"><Markdown text={doc || "docs/VALIDATION.md not found"} /></div> : !m ? (
        <div className="notice">No crater validation run yet. Run <code>marswatch validate</code>.</div>
      ) : (
        <>
          <div className="notice" style={{ marginBottom: 14 }}>
            {set === "crater_validation" ? "Tuning set — rules were revised after inspecting run 1 on these sites, so these numbers are optimistic. " : "Held-out image pairs — never inspected while developing the rules. "}
            Validation run #{cv.id} · code <span className="mono">{cv.code_version}</span> · {m.n_cases} entries ·{" "}
            {m.n_positive_runs} positive, {m.n_prepre_runs} pre-pre and {m.n_postpost_runs} post-post runs · {m.n_failed_runs} QC-rejected/failed · {m.n_skipped_runs ?? 0} skipped (listed below).
          </div>
          <div className="grid g2" style={{ marginBottom: 14 }}>
            <div className="panel">
              <div className="panel-head"><h3>Recall & false positives vs score threshold</h3></div>
              <Plot height={280} data={[
                { x: m.operating_points.map((o: any) => o.threshold), y: m.operating_points.map((o: any) => o.recall_any_category), name: "recall (any category)", mode: "lines+markers", line: { color: "#3fb68b" } },
                { x: m.operating_points.map((o: any) => o.threshold), y: m.operating_points.map((o: any) => o.recall_as_new_impact), name: "recall (as new impact)", mode: "lines+markers", line: { color: "#3fb68b", dash: "dot" } },
                { x: m.operating_points.map((o: any) => o.threshold), y: m.operating_points.map((o: any) => o.precision_window_assumption), name: "precision*", mode: "lines+markers", line: { color: "#8f7cf0" } },
                { x: m.operating_points.map((o: any) => o.threshold), y: m.operating_points.map((o: any) => o.fp_per_km2_positive_windows), name: "FP/km²", yaxis: "y2", mode: "lines+markers", line: { color: "#e5534b" } },
              ]} layout={{ xaxis: { title: { text: "heuristic score threshold" } }, yaxis: { range: [0, 1.05] },
                yaxis2: { overlaying: "y", side: "right", title: { text: "FP / km²" }, gridcolor: "rgba(0,0,0,0)" }, margin: { l: 40, r: 50, t: 4, b: 70 } }} />
              <div className="small faint">* precision assumes the catalogued crater is the only real change in each 1 km² window.</div>
            </div>
            <div className="panel">
              <div className="panel-head"><h3>Detection vs crater diameter (real cases)</h3></div>
              <Plot height={280} data={[
                { type: "bar", x: m.sensitivity_by_diameter_real.map((s: any) => `${s.diameter_m} m`), y: m.sensitivity_by_diameter_real.map((s: any) => s.rate ?? 0),
                  text: m.sensitivity_by_diameter_real.map((s: any) => `${s.detected}/${s.n}`), textposition: "outside", marker: { color: "#e0662f" } },
              ]} layout={{ yaxis: { range: [0, 1.15], title: { text: "detection rate" } }, xaxis: { title: { text: "catalogued effective diameter" } } }} />
            </div>
          </div>

          <div className="panel" style={{ marginBottom: 14 }}>
            <div className="panel-head"><h3>Operating points</h3></div>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Threshold</th><th>Recall (any)</th><th>Recall (as impact)</th><th>TP</th><th>FP pos. windows</th><th>FP pre-pre</th><th>FP/km² pos.</th><th>FP/km² pre-pre</th><th>Precision*</th></tr></thead>
                <tbody>{m.operating_points.map((o: any) => (
                  <tr key={o.threshold}><td className="num">{o.threshold.toFixed(1)}</td><td className="num">{fmt(o.recall_any_category)}</td><td className="num">{fmt(o.recall_as_new_impact)}</td>
                    <td className="num">{o.tp}</td><td className="num">{o.fp_in_positive_windows}</td><td className="num">{o.fp_in_prepre_controls}</td>
                    <td className="num">{fmt(o.fp_per_km2_positive_windows)}</td><td className="num">{fmt(o.fp_per_km2_prepre)}</td><td className="num">{fmt(o.precision_window_assumption)}</td></tr>
                ))}</tbody>
              </table>
            </div>
          </div>

          <div className="grid g3" style={{ marginBottom: 14 }}>
            <div className="panel">
              <div className="panel-head"><h3>Registration (real pairs)</h3></div>
              <dl className="kv small">
                <dt>Runs</dt><dd>{m.registration_real.runs}</dd>
                <dt>Checkpoint RMS median</dt><dd>{fmt(m.registration_real.checkpoint_rms_px_median)} px</dd>
                <dt>Checkpoint RMS P90</dt><dd>{fmt(m.registration_real.checkpoint_rms_px_p90)} px</dd>
                <dt>Status</dt><dd>{Object.entries(m.registration_real.status_counts).map(([k, n]) => `${k} ${n}`).join(" · ")}</dd>
                <dt>Median pointing offset</dt><dd>{fmt(m.registration_real.coarse_offset_m_median, 0)} m</dd>
              </dl>
            </div>
            <div className="panel">
              <div className="panel-head"><h3>Method C ablation</h3></div>
              <dl className="kv small">
                <dt>CNN z, documented</dt><dd>{fmt(m.ml_deep_z.documented_median, 1)}</dd>
                <dt>CNN z, other candidates</dt><dd>{fmt(m.ml_deep_z.other_candidates_median, 1)}</dd>
                <dt>AUC</dt><dd>{fmt(m.ml_deep_z.auc)}</dd>
              </dl>
              <div className="small faint" style={{ marginTop: 8 }}>Pretrained ImageNet ResNet-18 features; not trained on Mars data. Used as supporting evidence only.</div>
            </div>
            <div className="panel">
              <div className="panel-head"><h3>Illumination stress</h3></div>
              <dl className="kv small">
                {m.illumination_breakdown.map((g: any) => (<Fragment key={g.group}><dt>{g.group} ({g.runs} runs)</dt><dd>{fmt(g["fp_per_km2_at_0.4"])} FP/km²</dd></Fragment>))}
                <dt>Throughput</dt><dd>{fmt(m.performance.seconds_per_km2, 1)} s/km² @0.5 m</dd>
                <dt>Peak memory</dt><dd>{fmt(m.peak_rss_mb, 0)} MB</dd>
              </dl>
            </div>
          </div>

          {(inj || rs) && (
            <div className="grid g2" style={{ marginBottom: 14 }}>
              {inj && (
                <div className="panel">
                  <div className="panel-head"><h3>Sensitivity — synthetic injection{v.injection_sensitivity_hard ? " (hard variant)" : ""}</h3><span className="tag">SYNTHETIC</span></div>
                  <Plot height={260} data={[{
                    type: "heatmap", x: injDs.map((d) => `${d} m`), y: injCs.map((c) => `${c * 100}%`),
                    z: injCs.map((c) => injDs.map((d) => inj.table.find((r: any) => r.diameter_m === d && r.halo_contrast === c)?.detection_rate ?? null)),
                    colorscale: [[0, "#1d222a"], [1, "#e0662f"]], zmin: 0, zmax: 1, texttemplate: "%{z:.2f}", hovertemplate: "D=%{x}, contrast=%{y}: %{z:.2f}<extra></extra>",
                  }]} layout={{ xaxis: { title: { text: "crater diameter" } }, yaxis: { title: { text: "halo contrast" } }, margin: { l: 60, r: 10, t: 4, b: 50 } }} />
                  <div className="small faint">{v.injection_sensitivity_hard
                    ? "Bowl-only craters (0 %) or bowl + faint compact halo (radius 3×D) injected into real unchanged imagery. The easy variant (8×D halo, ≥5 %) saturates at 100 %."
                    : "Artificial blast zones injected into real unchanged imagery; measures detectability only."}</div>
                </div>
              )}
              {rs && (
                <div className="panel">
                  <div className="panel-head"><h3>Registration — known synthetic warps</h3><span className="tag">SYNTHETIC</span></div>
                  <Plot height={260} data={[
                    { type: "bar", x: rs.trials.map((_: any, i: number) => `#${i}`), y: rs.trials.map((t: any) => t.err_rms_px), name: "true RMS error", marker: { color: "#3fb68b" } },
                    { type: "bar", x: rs.trials.map((_: any, i: number) => `#${i}`), y: rs.trials.map((t: any) => t.checkpoint_rms_px), name: "checkpoint estimate", marker: { color: "#8f7cf0" } },
                  ]} layout={{ barmode: "group", yaxis: { title: { text: "px" } } }} />
                </div>
              )}
            </div>
          )}

          <div className="panel">
            <div className="panel-head"><h3>Per-site results</h3></div>
            <div className="table-wrap" style={{ maxHeight: 520 }}>
              <table>
                <thead><tr><th>Site</th><th>D (m)</th><th>Run</th><th>Pair</th><th>Δinc</th><th>Reg.</th><th>Cands</th><th>Matched</th><th>Score</th><th>Category / status</th><th>Rank</th><th /></tr></thead>
                <tbody>
                  {cv.cases.flatMap((e: any) => e.runs.map((r: any, i: number) => (
                    <tr key={e.ref_id + i}>
                      <td className="mono">{i === 0 ? e.ref_id : ""}</td><td className="num">{i === 0 ? e.diameter_m : ""}</td>
                      <td><span className="tag">{r.kind.replace("neg:", "")}</span></td>
                      <td className="mono small">{r.before_id?.replace("_RED", "")} → {r.after_id?.replace("_RED", "")}</td>
                      <td className="num">{r.error ? "" : `${fmt(r.d_incidence, 0)}°`}</td>
                      <td className="num">{r.error ? <span className="badge b-failed">{r.input_rejected ? "QC reject" : "error"}</span> : r.skipped ? <span className="badge b-cancelled">skipped</span> : fmt(r.registration?.check_rms_px)}</td>
                      <td className="num">{r.n_candidates ?? "—"}</td>
                      <td>{r.kind === "positive" ? (r.match ? "✓" : "✗") : ""}</td>
                      <td className="num">{fmt(r.match?.score)}</td>
                      <td className="small" style={{ whiteSpace: "normal", maxWidth: 320 }}>{r.match ? `${r.match.category} / ${r.match.status}` : (r.error || r.skipped || "").slice(0, 90)}</td>
                      <td className="num">{r.match?.rank ?? ""}</td>
                      <td>{r.run_id && <Link to={`/viewer/${encodeURIComponent(r.run_id)}`}>view</Link>}</td>
                    </tr>
                  )))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
