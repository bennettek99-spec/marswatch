import { Fragment, useEffect, useRef, useState } from "react";
import { api, fmt } from "../api";
import { JobBadge, Loading, Stat, usePoll } from "../components/ui";

export default function Console() {
  const [jobs, jerr, reloadJobs] = usePoll(api.jobs, 3000);
  const [sys] = usePoll(api.system, 4000);
  const [ov, , reloadOv] = usePoll(api.overview, 5000);
  const [logs, setLogs] = useState<any[]>([]);
  const [level, setLevel] = useState("");
  const [follow, setFollow] = useState(true);
  const since = useRef(0);
  const box = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState<number | null>(null);

  useEffect(() => {
    let alive = true;
    const pull = () => api.logs(since.current).then((rows) => {
      if (!alive || !rows.length) return;
      since.current = rows[rows.length - 1].id;
      setLogs((l) => [...l, ...rows].slice(-1500));
    }).catch(() => {});
    pull();
    const t = setInterval(pull, 2000);
    return () => { alive = false; clearInterval(t); };
  }, []);
  useEffect(() => {
    if (follow && box.current) box.current.scrollTop = box.current.scrollHeight;
  }, [logs, follow]);

  const act = async (fn: () => Promise<any>) => { await fn(); reloadJobs(); reloadOv(); };
  const paused = ov?.worker?.paused;
  const counts = ov?.jobs || {};
  const rr = sys?.remote_reads;

  return (
    <div className="page" style={{ maxWidth: "none" }}>
      <div className="page-head">
        <div>
          <h1>Processing Console</h1>
          <p>Job queue, downloads (remote windowed reads), failures, logs and local resource use. The queue is persistent:
            interrupted jobs resume, failures retry with exponential backoff, duplicates are rejected.</p>
        </div>
        <div className="row">
          <span className="small muted">Worker {paused ? "paused" : "active"}{ov && !ov.worker.embedded && " (run `marswatch worker` or MARSWATCH_EMBED_WORKER=1)"}</span>
          {paused ? <button className="primary" onClick={() => act(() => api.worker("resume"))}>Resume</button>
            : <button onClick={() => act(() => api.worker("pause"))}>Pause</button>}
        </div>
      </div>

      <div className="grid g4" style={{ marginBottom: 14 }}>
        <Stat label="Running / queued" value={`${counts.running || 0} / ${counts.queued || 0}`} sub={`${counts.done || 0} done · ${counts.failed || 0} failed`} />
        <Stat label="CPU / memory" value={sys ? `${fmt(sys.cpu_percent, 0)}%` : "—"} sub={sys ? `${fmt(sys.mem_used_percent, 0)}% RAM · process ${fmt(sys.process_rss_mb, 0)} MB (limit ${sys.settings.memory_limit_mb})` : ""} />
        <Stat label="Cache / disk" value={sys ? `${fmt(sys.cache_mb, 0)} MB` : "—"} sub={sys ? `budget ${sys.cache_budget_mb} MB · ${fmt(sys.disk_free_gb, 1)} GB free` : ""} />
        <Stat label="Remote reads (all processes)" value={rr ? rr.reads : "—"} sub={rr ? `${(rr.pixels / 1e6).toFixed(1)} Mpx · ${fmt(rr.seconds, 0)} s · ${rr.cache_hits} cache hits · ${rr.failures} failures` : ""} />
      </div>

      <div className="panel" style={{ marginBottom: 14 }}>
        <div className="panel-head"><h3>Jobs</h3><span className="small faint">{sys && `rate limit ${sys.settings.requests_per_second} req/s · ${sys.settings.max_workers} worker threads`}</span></div>
        {!jobs ? <Loading err={jerr} /> : (
          <div className="table-wrap" style={{ maxHeight: 420 }}>
            <table>
              <thead><tr><th>#</th><th>Kind</th><th>Status</th><th>Progress</th><th>Stage</th><th>Pair / params</th><th>Attempts</th><th>Duration</th><th /></tr></thead>
              <tbody>
                {jobs.map((j) => (
                  <Fragment key={j.id}>
                    <tr className="clickable" onClick={() => setExpanded(expanded === j.id ? null : j.id)}>
                      <td className="mono num">{j.id}</td>
                      <td>{j.kind}</td>
                      <td><JobBadge s={j.status} /></td>
                      <td><span className="bar" style={{ display: "inline-block", width: 90 }}><i style={{ width: `${(j.progress || 0) * 100}%` }} /></span></td>
                      <td className="small muted">{j.stage}</td>
                      <td className="mono small">{j.pair_id || j.params?.region || ""}</td>
                      <td className="num">{j.attempts}/{j.max_attempts}</td>
                      <td className="num small">{j.started_at ? fmt(((j.finished_at || Date.now() / 1000) - j.started_at), 0) + " s" : "—"}</td>
                      <td onClick={(e) => e.stopPropagation()}>
                        {(j.status === "failed" || j.status === "cancelled") && <button onClick={() => act(() => api.retry(j.id))}>Retry</button>}
                        {j.status === "queued" && <button className="ghost" onClick={() => act(() => api.cancel(j.id))}>Cancel</button>}
                      </td>
                    </tr>
                    {expanded === j.id && (
                      <tr><td colSpan={9}>
                        <pre className="log" style={{ height: "auto", maxHeight: 260 }}>{JSON.stringify({ params: j.params, result: j.result }, null, 1)}{j.error ? "\n\nERROR:\n" + j.error : ""}</pre>
                      </td></tr>
                    )}
                  </Fragment>
                ))}
                {!jobs.length && <tr><td colSpan={9} className="faint">No jobs yet. Queue some from Mars Explorer or `marswatch discover --enqueue N`.</td></tr>}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="panel">
        <div className="panel-head">
          <h3>Live log</h3>
          <div className="row">
            <select value={level} onChange={(e) => setLevel(e.target.value)}><option value="">all levels</option><option>INFO</option><option>WARNING</option><option>ERROR</option></select>
            <label className="row small muted"><input type="checkbox" checked={follow} onChange={(e) => setFollow(e.target.checked)} />follow</label>
          </div>
        </div>
        <div className="log" ref={box}>
          {logs.filter((l) => !level || l.level === level).map((l) => (
            <div key={l.id} className={`lv-${l.level}`}>
              <span className="faint">{new Date(l.ts * 1000).toISOString().slice(11, 19)}</span> {l.level.padEnd(7)} <span className="faint">{l.logger.replace("marswatch.", "")}</span> {l.message}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
