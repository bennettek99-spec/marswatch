import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, CandidateDetail as CD, CATEGORY_LABEL, fmt, fmtDate, Status, STATUS_LABEL } from "../api";
import { CategoryTag, download, Loading, ScoreBar, StatusBadge } from "../components/ui";

const FEATURE_LABELS: Record<string, string> = {
  max_abs_z: "Peak |z| (registration-aware)",
  mean_ssim: "Mean SSIM in region",
  elongation: "Elongation (major/minor)",
  crater_resp_after: "Crater template NCC — after",
  crater_resp_before: "Crater template NCC — before",
  crater_sun_misfit_deg: "Crater shading vs solar azimuth (°)",
  angular_coverage: "Radial darkening coverage",
  ray_contrast: "Ray contrast",
  taper: "Taper (fan-likeness)",
  new_edge_frac: "New-edge fraction",
  relief_index: "Relief index (× median gradient)",
  dipole: "Opposite-polarity dipole",
  local_reg_quality: "Local registration quality",
  deep_z: "CNN feature-change z (Method C)",
  disp_median_px: "Residual displacement (px)",
  artifact_index: "Artifact index",
};

export default function CandidateDetail() {
  const { id } = useParams();
  const [c, setC] = useState<CD>();
  const [err, setErr] = useState<string>();
  const [notes, setNotes] = useState("");
  const [saved, setSaved] = useState<string>();

  const load = () => api.candidate(id!).then((d) => { setC(d); setNotes(d.notes || ""); }).catch((e) => setErr(e.message));
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);
  if (!c) return <div className="page"><Loading err={err} /></div>;

  const s = c.sources;
  const reg = c.registration;
  const f = { ...c.features };
  const checks: { name: string; pass: boolean | null; detail: string }[] = [
    { name: "Registration verified by held-out checkpoints", pass: reg.status === "good" ? true : reg.status === "poor" ? false : null,
      detail: `RMS ${fmt(reg.check_rms_px)} px over ${reg.checkpoints} checkpoints; quality ${fmt(reg.quality)}` },
    { name: "Local registration adequate at candidate", pass: (c.registration_quality ?? 0) >= 0.3, detail: `local quality ${fmt(c.registration_quality)}` },
    { name: "Not a shadow/parallax dipole", pass: (f.dipole ?? 0) <= 0.5, detail: `dipole ${fmt(f.dipole)}, relief ${fmt(f.relief_index, 1)}×` },
    { name: "Signal well above noise", pass: (f.max_abs_z ?? 0) >= 5, detail: `peak |z| = ${fmt(f.max_abs_z, 1)}` },
    { name: "Illumination comparable", pass: (c.pair?.d_incidence ?? 99) <= 10 && (c.pair?.d_sun_azimuth ?? 99) <= 30,
      detail: `Δinc ${fmt(c.pair?.d_incidence, 1)}°, Δsun az ${fmt(c.pair?.d_sun_azimuth, 0)}°` },
    { name: "Independent CNN evidence (unvalidated)", pass: f.deep_z === undefined ? null : f.deep_z > 3, detail: `deep z ${fmt(f.deep_z, 1)}` },
    { name: "Matches catalogued change", pass: c.known_match ? true : null, detail: c.known_match || "no catalogued change within tolerance" },
  ];
  const review = async (cls?: Status) => {
    await api.review(c.id, { notes, classification: cls });
    setSaved(cls ? `Status set to ${STATUS_LABEL[cls]}` : "Notes saved");
    load();
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="row" style={{ marginBottom: 6 }}><Link to="/candidates" className="small">← Candidates</Link></div>
          <h1>Candidate {c.id} <span className="faint" style={{ fontWeight: 400 }}>· {CATEGORY_LABEL[c.category]}</span></h1>
          <div className="row" style={{ marginTop: 8 }}>
            <StatusBadge s={c.classification} /><CategoryTag c={c.category} /><ScoreBar v={c.score} />
            <span className="faint small">heuristic score, not a probability</span>
          </div>
        </div>
        <div className="row">
          <Link className="btn" to={`/viewer/${encodeURIComponent(c.run_id)}?cand=${c.id}`}>Open in viewer</Link>
          <button onClick={async () => download(`marswatch_candidate_${c.id}.md`, await api.candidateReport(c.id))}>Export report (.md)</button>
        </div>
      </div>

      {c.chips?.chip && (
        <div className="panel" style={{ marginBottom: 14 }}>
          <div className="panel-head"><h3>Evidence chips</h3><span className="small faint">before (radiometrically matched) · after · signed z (red = darker, blue = brighter)</span></div>
          <img className="chip-img" src={`/runs/${encodeURIComponent(c.run_id)}/${c.chips.chip}`} alt="before, after, difference" />
        </div>
      )}

      <div className="grid g2" style={{ marginBottom: 14 }}>
        <div className="panel">
          <div className="panel-head"><h3>Measurements</h3></div>
          <dl className="kv">
            <dt>Location (before frame)</dt><dd className="mono">{fmt(c.lat, 5)}°N, {fmt(c.lon, 5)}°E</dd>
            <dt>Location (after frame)</dt><dd className="mono">{fmt(f.lat_after_frame, 5)}°N, {fmt(f.lon_after_frame, 5)}°E</dd>
            <dt>Area</dt><dd>{Math.round(c.area_m2).toLocaleString()} m² (equivalent diameter {fmt(c.eq_diameter_m, 1)} m)</dd>
            <dt>Polarity</dt><dd>{c.polarity}</dd>
            <dt>Observation dates</dt><dd>{fmtDate(s.before.start_time)} → {fmtDate(s.after.start_time)}</dd>
            <dt>Known match</dt><dd>{c.known_match || "—"}</dd>
          </dl>
          <div style={{ marginTop: 12 }} className="table-wrap">
            <table><tbody>
              {Object.entries(FEATURE_LABELS).filter(([k]) => f[k] !== undefined).map(([k, label]) => (
                <tr key={k}><td className="muted">{label}</td><td className="num mono">{typeof f[k] === "number" ? fmt(f[k], 3) : String(f[k])}</td></tr>
              ))}
            </tbody></table>
          </div>
        </div>
        <div className="grid" style={{ alignContent: "start" }}>
          <div className="panel">
            <div className="panel-head"><h3>Evidence supporting</h3></div>
            <ul className="evidence ev-for">{c.evidence_for.map((e, i) => <li key={i}>{e}</li>)}</ul>
          </div>
          <div className="panel">
            <div className="panel-head"><h3>Evidence against</h3></div>
            {c.evidence_against.length ? <ul className="evidence ev-against">{c.evidence_against.map((e, i) => <li key={i}>{e}</li>)}</ul> : <div className="faint small">None recorded by the automated tests.</div>}
          </div>
          <div className="panel">
            <div className="panel-head"><h3>Validation checks</h3></div>
            <table><tbody>
              {checks.map((k) => (
                <tr key={k.name}>
                  <td style={{ width: 24, color: k.pass === null ? "var(--text-3)" : k.pass ? "var(--ok)" : "var(--bad)" }}>{k.pass === null ? "○" : k.pass ? "✓" : "✗"}</td>
                  <td>{k.name}<div className="small faint">{k.detail}</div></td>
                </tr>
              ))}
            </tbody></table>
          </div>
        </div>
      </div>

      <div className="grid g2" style={{ marginBottom: 14 }}>
        <div className="panel">
          <div className="panel-head"><h3>Original observations</h3></div>
          {(["before", "after"] as const).map((k) => (
            <div key={k} style={{ marginBottom: 12 }}>
              <div className="row"><b style={{ textTransform: "capitalize", width: 50 }}>{k}</b>
                <a className="mono" href={s[k].uahirise_url} target="_blank" rel="noreferrer">{s[k].product_id}</a></div>
              <div className="small muted">{s[k].start_time} · incidence {fmt(s[k].incidence, 1)}° · emission {fmt(s[k].emission, 1)}° · Ls {fmt(s[k].solar_longitude, 1)}° · {s[k].map_scale} m/px</div>
              <div className="small faint">“{s[k].rationale}” · <a href={s[k].pds_jp2_url} target="_blank" rel="noreferrer">PDS RDR (JP2)</a> · <a href={s[k].cog_url} target="_blank" rel="noreferrer">USGS COG</a></div>
            </div>
          ))}
          <div className="panel-head" style={{ marginTop: 10 }}><h3>Other HiRISE coverage of this point</h3><span className="small faint">{c.other_observations.length}</span></div>
          <div className="table-wrap" style={{ maxHeight: 220 }}>
            <table><tbody>
              {c.other_observations.map((o) => (
                <tr key={o.product_id}><td className="mono small"><a href={o.uahirise_url} target="_blank" rel="noreferrer">{o.product_id}</a></td>
                  <td className="small">{fmtDate(o.start_time)}</td><td className="small num">i {fmt(o.incidence, 0)}°</td><td className="small num">Ls {fmt(o.solar_longitude, 0)}°</td></tr>
              ))}
            </tbody></table>
          </div>
        </div>
        <div className="panel">
          <div className="panel-head"><h3>Processing history</h3><span className="mono small faint">{c.code_version}</span></div>
          <ol style={{ margin: 0, paddingLeft: 18 }}>
            {c.processing_history.map((h) => <li key={h.stage} style={{ marginBottom: 6 }}><b>{h.stage}</b> — <span className="muted small">{h.detail}</span></li>)}
          </ol>
          <div className="panel-head" style={{ marginTop: 14 }}><h3>Registration diagnostics</h3></div>
          <dl className="kv small">
            <dt>Pointing offset</dt><dd>{fmt(reg.coarse_dx_m, 1)} m E, {fmt(reg.coarse_dy_m, 1)} m N</dd>
            <dt>Checkpoint RMS / P90</dt><dd>{fmt(reg.check_rms_px)} / {fmt(reg.check_p90_px)} px</dd>
            <dt>NCC before → after</dt><dd>{fmt(reg.ncc_before)} → {fmt(reg.ncc_after)}</dd>
          </dl>
          <div className="panel-head" style={{ marginTop: 14 }}><h3>Catalogued changes within 2 km</h3></div>
          {c.references_nearby.length ? (
            <ul className="evidence">{c.references_nearby.map((r) => <li key={r.ref_id}>{r.ref_id}: {r.category}, D={r.diameter_m} m, {fmt(r.distance_m, 0)} m away, formed {r.before_date}…{r.after_date}</li>)}</ul>
          ) : <div className="small faint">None in the reference catalog (Daubar et al. 2022). Literature search still required before any claim.</div>}
        </div>
      </div>

      <div className="panel">
        <div className="panel-head"><h3>Reviewer assessment</h3>{saved && <span className="small" style={{ color: "var(--ok)" }}>{saved}</span>}</div>
        <textarea rows={4} style={{ width: "100%" }} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Notes: literature checks, additional observations inspected, interpretation…" />
        <div className="row" style={{ marginTop: 8 }}>
          <button onClick={() => review()}>Save notes</button>
          <span className="spacer" />
          <span className="small muted">Set status:</span>
          {(Object.keys(STATUS_LABEL) as Status[]).map((s) => <button key={s} className="ghost" onClick={() => review(s)}>{STATUS_LABEL[s]}</button>)}
        </div>
      </div>
    </div>
  );
}
