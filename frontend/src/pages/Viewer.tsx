import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import OpenSeadragon from "openseadragon";
import { api, asset, CATEGORY_LABEL, fmt, fmtDate } from "../api";
import { JobBadge, Loading, StatusBadge, usePoll } from "../components/ui";

type Mode = "slider" | "side" | "blink";

const STATUS_COLOR: Record<string, string> = {
  known_documented: "#8f7cf0", plausible_unverified: "#3fb68b", insufficient_evidence: "#e8b44c", likely_artifact: "#9aa3ad",
};

function source(run: any, key: "before" | "after" | "heat" | "mask"): any {
  if (run.dzi?.[key]) return run.dzi[key];
  const ext = key === "heat" || key === "mask" ? "png" : "jpg";
  return { type: "image", url: asset(`/runs/${encodeURIComponent(run.run_id)}/${key}.${ext}`) };
}

function makeViewer(el: HTMLElement) {
  return OpenSeadragon({
    element: el,
    showNavigationControl: false,
    maxZoomPixelRatio: 6,
    minZoomImageRatio: 0.6,
    visibilityRatio: 0.3,
    gestureSettingsMouse: { clickToZoom: false, dblClickToZoom: true },
    showNavigator: true,
    navigatorPosition: "BOTTOM_RIGHT",
    navigatorBackground: "#000",
    navigatorBorderColor: "#555",
    navigatorDisplayRegionColor: "#e0662f",
    crossOriginPolicy: false,
    animationTime: 0.6,
  } as any);
}

function RunPicker() {
  const [runs, err] = usePoll(() => api.runs(), 0);
  const nav = useNavigate();
  if (!runs) return <Loading err={err} />;
  return (
    <div className="panel">
      <div className="panel-head"><h3>Choose an analysed pair</h3></div>
      <div className="table-wrap" style={{ maxHeight: "70vh" }}>
        <table>
          <thead><tr><th>Pair</th><th>Kind</th><th>Registration</th><th>Candidates</th><th>Plausible</th><th>Known</th></tr></thead>
          <tbody>
            {runs.filter((r) => r.status === "done").map((r) => (
              <tr key={r.run_id} className="clickable" onClick={() => nav(`/viewer/${encodeURIComponent(r.run_id)}`)}>
                <td className="mono">{r.pair_id}</td><td><span className="tag">{r.kind}</span></td>
                <td><JobBadge s={r.registration?.status} /></td><td className="num">{r.n_candidates}</td>
                <td className="num">{r.by_status?.plausible_unverified ?? 0}</td><td className="num">{r.by_status?.known_documented ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function Viewer() {
  const { runId } = useParams();
  const [sp] = useSearchParams();
  const candParam = sp.get("cand");
  const [run, setRun] = useState<any>();
  const [err, setErr] = useState<string>();
  const [mode, setMode] = useState<Mode>("slider");
  const [heat, setHeat] = useState(0.0);
  const [outlines, setOutlines] = useState(true);
  const [boxes, setBoxes] = useState(true);
  const [split, setSplit] = useState(0.5);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sel, setSel] = useState<number | null>(null);
  const shell = useRef<HTMLDivElement>(null);
  const elA = useRef<HTMLDivElement>(null);
  const elB = useRef<HTMLDivElement>(null);
  const vA = useRef<any>();
  const vB = useRef<any>();
  const dragging = useRef(false);

  useEffect(() => {
    if (!runId) return;
    setRun(undefined);
    api.run(runId).then(setRun).catch((e) => setErr(e.message));
  }, [runId]);

  const cands = useMemo(() => (run?.candidates || []).filter((c: any) => statusFilter === "all" || c.classification === statusFilter), [run, statusFilter]);

  // (re)build viewers when run or mode changes
  useEffect(() => {
    if (!run || !elA.current) return;
    vA.current?.destroy();
    vB.current?.destroy();
    vB.current = undefined;
    const a = makeViewer(elA.current);
    vA.current = a;
    const addLayers = (v: any, keys: ("before" | "after" | "heat" | "mask")[]) => {
      keys.forEach((k, i) => v.addTiledImage({ tileSource: source(run, k), index: i, opacity: k === "heat" ? heat : 1,
        success: (ev: any) => { ev.item.__mw = k; } }));
    };
    if (mode === "side" && elB.current) {
      addLayers(a, ["before"]);
      const b = makeViewer(elB.current);
      vB.current = b;
      addLayers(b, ["after", "heat", "mask"]);
      let lock = false;
      const sync = (src: any, dst: any) => () => {
        if (lock) return;
        lock = true;
        dst.viewport.zoomTo(src.viewport.getZoom(), undefined, true);
        dst.viewport.panTo(src.viewport.getCenter(), true);
        lock = false;
      };
      a.addHandler("viewport-change", sync(a, b));
      b.addHandler("viewport-change", sync(b, a));
    } else {
      addLayers(a, ["before", "after", "heat", "mask"]);
    }
    return () => {
      a.destroy();
      vB.current?.destroy();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, mode]);

  const layer = (v: any, key: string) => {
    if (!v) return undefined;
    for (let i = 0; i < v.world.getItemCount(); i++) {
      const it = v.world.getItemAt(i);
      if (it.__mw === key) return it;
    }
    return undefined;
  };

  // heat / outline opacity
  useEffect(() => {
    const t = setInterval(() => {
      [vA.current, vB.current].forEach((v) => {
        layer(v, "heat")?.setOpacity(heat);
        layer(v, "mask")?.setOpacity(outlines ? 1 : 0);
      });
    }, 250);
    return () => clearInterval(t);
  }, [heat, outlines]);

  // slider clipping
  useEffect(() => {
    if (mode !== "slider") return;
    const apply = () => {
      const v = vA.current;
      const after = layer(v, "after");
      if (!v || !after || !elA.current) return;
      const px = elA.current.clientWidth * split;
      const vp = v.viewport.pointFromPixel(new OpenSeadragon.Point(px, 0));
      const ip = after.viewportToImageCoordinates(vp);
      const size = after.getContentSize();
      const x = Math.max(0, Math.min(size.x, ip.x));
      after.setClip(new OpenSeadragon.Rect(x, 0, size.x - x, size.y));
      ["heat", "mask"].forEach((k) => layer(v, k)?.setClip(new OpenSeadragon.Rect(x, 0, size.x - x, size.y)));
    };
    const v = vA.current;
    v?.addHandler("animation", apply);
    v?.addHandler("open", apply);
    v?.world.addHandler("add-item", apply);
    const t = setInterval(apply, 400);
    apply();
    return () => {
      clearInterval(t);
      v?.removeHandler("animation", apply);
    };
  }, [mode, split, run]);

  // blink
  useEffect(() => {
    if (mode !== "blink") return;
    let on = true;
    const t = setInterval(() => {
      on = !on;
      layer(vA.current, "after")?.setOpacity(on ? 1 : 0);
    }, 700);
    return () => clearInterval(t);
  }, [mode, run]);

  // candidate boxes as overlays
  useEffect(() => {
    if (!run) return;
    const t = setTimeout(() => {
      [vA.current, vB.current].forEach((v) => {
        if (!v) return;
        v.clearOverlays();
        if (!boxes) return;
        const ref = layer(v, "before") || layer(v, "after");
        if (!ref) return;
        cands.slice(0, 150).forEach((c: any, i: number) => {
          const k = run.display_scale ?? 1;
          const [r0, c0, r1, c1] = c.bbox.map((x: number) => x * k);
          const pad = 6 * k;
          const rect = ref.imageToViewportRectangle(c0 - pad, r0 - pad, c1 - c0 + 2 * pad, r1 - r0 + 2 * pad);
          const d = document.createElement("div");
          d.style.border = `${c.id === sel ? 3 : 1.5}px solid ${STATUS_COLOR[c.classification] || "#fff"}`;
          d.style.borderRadius = "3px";
          d.title = `${CATEGORY_LABEL[c.category]} · ${c.classification} · score ${c.score}`;
          v.addOverlay({ element: d, location: rect });
        });
      });
    }, 900);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, mode, boxes, cands, sel]);

  const zoomTo = (c: any) => {
    setSel(c.id ?? null);
    [vA.current, vB.current].forEach((v) => {
      const ref = layer(v, "before") || layer(v, "after");
      if (!v || !ref) return;
      const k = run?.display_scale ?? 1;
      const [r0, c0, r1, c1] = c.bbox.map((x: number) => x * k);
      const m = Math.max(60 * k, (c1 - c0) * 1.5, (r1 - r0) * 1.5);
      v.viewport.fitBounds(ref.imageToViewportRectangle(c0 - m, r0 - m, c1 - c0 + 2 * m, r1 - r0 + 2 * m));
    });
  };

  useEffect(() => {
    if (!run || !candParam) return;
    const c = run.candidates.find((x: any) => String(x.id) === candParam);
    if (c) setTimeout(() => zoomTo(c), 1500);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, candParam]);

  const onDrag = (e: React.PointerEvent) => {
    if (!dragging.current || !shell.current) return;
    const r = shell.current.getBoundingClientRect();
    setSplit(Math.max(0.01, Math.min(0.99, (e.clientX - r.left) / r.width)));
  };

  if (!runId) return <div className="page"><div className="page-head"><div><h1>Before / After Viewer</h1><p>Select a run to inspect co-registered imagery.</p></div></div><RunPicker /></div>;
  if (!run) return <div className="page"><Loading err={err} /></div>;
  const s = run.sources, reg = run.registration;

  return (
    <div className="page" style={{ maxWidth: "none" }}>
      <div className="page-head">
        <div>
          <h1 className="mono" style={{ fontSize: 18 }}>{run.pair_id}</h1>
          <p className="small">
            {fmtDate(s.before.start_time)} → {fmtDate(s.after.start_time)} · {fmt(run.pair.dt_days / 687, 1)} Mars years ·
            Δinc {fmt(run.pair.d_incidence, 1)}° · grid {run.params.grid.width}×{run.params.grid.height} @ {run.params.res_m} m/px
          </p>
        </div>
        <div className="row">
          <div className="seg">
            {(["slider", "side", "blink"] as Mode[]).map((m) => (
              <button key={m} className={mode === m ? "on" : ""} onClick={() => setMode(m)}>{m === "side" ? "side-by-side" : m}</button>
            ))}
          </div>
          <label className="row small muted">Heatmap
            <input type="range" min={0} max={1} step={0.05} value={heat} onChange={(e) => setHeat(+e.target.value)} style={{ width: 90 }} />
          </label>
          <label className="row small muted"><input type="checkbox" checked={outlines} onChange={(e) => setOutlines(e.target.checked)} />outlines</label>
          <label className="row small muted"><input type="checkbox" checked={boxes} onChange={(e) => setBoxes(e.target.checked)} />boxes</label>
          <a className="btn" href={asset(`/runs/${encodeURIComponent(run.run_id)}/report.md`)} target="_blank" rel="noreferrer">report</a>
        </div>
      </div>
      <div className="grid g-side">
        <div ref={shell} className="viewer-shell" onPointerMove={onDrag} onPointerUp={() => (dragging.current = false)} onPointerLeave={() => (dragging.current = false)}>
          {mode === "side" ? (
            <div className="viewer-split">
              <div style={{ position: "relative" }}><div ref={elA} className="osd" /><span className="viewer-label" style={{ left: 10 }}>BEFORE · {fmtDate(s.before.start_time)}</span></div>
              <div style={{ position: "relative" }}><div ref={elB} className="osd" /><span className="viewer-label" style={{ left: 10 }}>AFTER · {fmtDate(s.after.start_time)}</span></div>
            </div>
          ) : (
            <>
              <div ref={elA} className="osd" />
              {mode === "slider" && (
                <>
                  <div className="slider-handle" style={{ left: `${split * 100}%` }} onPointerDown={(e) => { dragging.current = true; (e.target as HTMLElement).setPointerCapture?.(e.pointerId); }} />
                  <span className="viewer-label" style={{ left: 10 }}>BEFORE · {fmtDate(s.before.start_time)}</span>
                  <span className="viewer-label" style={{ right: 10 }}>AFTER · {fmtDate(s.after.start_time)}</span>
                </>
              )}
              {mode === "blink" && <span className="viewer-label" style={{ left: 10 }}>blinking before ⇄ after (700 ms)</span>}
            </>
          )}
        </div>
        <div className="grid" style={{ alignContent: "start", maxHeight: "calc(100vh - 190px)", overflow: "auto" }}>
          <div className="panel">
            <div className="panel-head"><h3>Observations</h3></div>
            {(["before", "after"] as const).map((k) => (
              <div key={k} style={{ marginBottom: 10 }}>
                <div className="row"><b style={{ textTransform: "capitalize" }}>{k}</b>
                  <a className="mono small" href={s[k].uahirise_url} target="_blank" rel="noreferrer">{s[k].product_id}</a></div>
                <div className="small muted">{s[k].start_time} · i={fmt(s[k].incidence, 1)}° · e={fmt(s[k].emission, 1)}° · Ls={fmt(s[k].solar_longitude, 1)}° · {s[k].map_scale} m/px</div>
                <div className="small faint">{s[k].rationale} · <a href={s[k].pds_jp2_url} target="_blank" rel="noreferrer">PDS</a> · <a href={s[k].cog_url} target="_blank" rel="noreferrer">COG</a></div>
              </div>
            ))}
          </div>
          <div className="panel">
            <div className="panel-head"><h3>Registration</h3><JobBadge s={reg.status} /></div>
            <dl className="kv small">
              <dt>Pointing offset corrected</dt><dd>{fmt(reg.coarse_dx_m, 1)} m E, {fmt(reg.coarse_dy_m, 1)} m N</dd>
              <dt>Patch matches</dt><dd>{reg.n_matched}/{reg.n_patches} ({reg.n_inliers} inliers)</dd>
              <dt>Checkpoint RMS</dt><dd>{fmt(reg.check_rms_px)} px ({fmt(reg.check_rms_m)} m), P90 {fmt(reg.check_p90_px)} px</dd>
              <dt>High-pass NCC</dt><dd>{fmt(reg.ncc_before)} → {fmt(reg.ncc_after)}</dd>
              <dt>Quality</dt><dd>{fmt(reg.quality)}</dd>
            </dl>
            {reg.warnings?.map((w: string) => <div key={w} className="notice warn small" style={{ marginTop: 6 }}>{w}</div>)}
          </div>
          {run.stats?.scene_test && (
            <div className="panel">
              <div className="panel-head"><h3>Scene-level test</h3><span className={`badge ${run.stats.scene_test.flagged ? "b-marginal" : "b-good"}`}>{run.stats.scene_test.flagged ? "flagged" : "pass"}</span></div>
              <dl className="kv small">
                <dt>Candidates on steep relief</dt><dd>{fmt(run.stats.scene_test.frac_on_relief * 100, 0)}% of {run.stats.scene_test.n_candidates}</dd>
                <dt>Change pixels on relief</dt><dd>{fmt(run.stats.scene_test.relief_coupling_px, 1)}× chance</dd>
                <dt>Difference explained by shading</dt><dd>{fmt(run.stats.scene_test.shading_r2 * 100, 0)}%</dd>
                <dt>Demoted / kept as outliers</dt><dd>{run.stats.scene_test.demoted} / {run.stats.scene_test.survived_as_outliers}</dd>
              </dl>
            </div>
          )}
          <div className="panel">
            <div className="panel-head">
              <h3>Candidates ({cands.length})</h3>
              <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="small">
                <option value="all">all</option><option value="known_documented">known</option><option value="plausible_unverified">plausible</option>
                <option value="insufficient_evidence">insufficient</option><option value="likely_artifact">artifact</option>
              </select>
            </div>
            <div className="table-wrap" style={{ maxHeight: 340 }}>
              <table>
                <tbody>
                  {cands.slice(0, 150).map((c: any, i: number) => (
                    <tr key={i} className="clickable" onClick={() => zoomTo(c)} style={c.id === sel ? { background: "var(--mars-dim)" } : {}}>
                      <td className="num mono">{fmt(c.score)}</td>
                      <td><div className="small">{CATEGORY_LABEL[c.category]}</div><StatusBadge s={c.classification} /></td>
                      <td className="num small">{fmt(c.eq_diameter_m, 0)} m</td>
                      <td>{c.id && <Link to={`/candidates/${c.id}`} onClick={(e) => e.stopPropagation()}>›</Link>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <div className="notice small">
            Before image is radiometrically matched to the after image. Heatmap: <span style={{ color: "#ff7a3a" }}>orange = darkening</span>,{" "}
            <span style={{ color: "#5ab8ff" }}>blue = brightening</span>, intensity ∝ registration-aware z-score.
          </div>
        </div>
      </div>
    </div>
  );
}
