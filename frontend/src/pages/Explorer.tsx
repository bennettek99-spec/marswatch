import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import L from "leaflet";
import { api, fmt, fmtDate, STATUS_LABEL } from "../api";

const TREK = "https://trek.nasa.gov/tiles/Mars/EQ";
const BASEMAPS: Record<string, string> = {
  "Viking MDIM2.1 color mosaic (NASA Trek)": `${TREK}/Mars_Viking_MDIM21_ClrMosaic_global_232m/1.0.0/default/default028mm/{z}/{y}/{x}.jpg`,
  "MOLA colour shaded relief (NASA Trek)": `${TREK}/Mars_MGS_MOLA_ClrShade_merge_global_463m/1.0.0/default/default028mm/{z}/{y}/{x}.jpg`,
};
const COLORS: Record<string, string> = {
  known_documented: "#8f7cf0",
  plausible_unverified: "#3fb68b",
  insufficient_evidence: "#e8b44c",
  likely_artifact: "#6f7986",
};
const lon180 = (lon: number) => (lon > 180 ? lon - 360 : lon);
const lon360 = (lon: number) => ((lon % 360) + 360) % 360;

export default function Explorer() {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map>();
  const nav = useNavigate();
  const [selecting, setSelecting] = useState(false);
  const selRef = useRef<{ pts: L.LatLng[]; rect?: L.Rectangle }>({ pts: [] });
  const [region, setRegion] = useState<{ min_lat: number; max_lat: number; min_lon: number; max_lon: number } | null>(null);
  const [click, setClick] = useState<{ lat: number; lon: number } | null>(null);
  const [coverage, setCoverage] = useState<any[] | null>(null);
  const [msg, setMsg] = useState<string>();
  const [form, setForm] = useState({ name: "custom-region", enqueue_top: 5, res_m: 1.0, max_area_km2: 20 });
  const [counts, setCounts] = useState({ areas: 0, cands: 0, refs: 0 });

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { crs: L.CRS.EPSG4326, center: [10, -60], zoom: 2, minZoom: 1, maxZoom: 16, worldCopyJump: false });
    map.current = m;
    const bases: Record<string, L.TileLayer> = {};
    Object.entries(BASEMAPS).forEach(([k, url], i) => {
      bases[k] = L.tileLayer(url, { maxNativeZoom: 7, maxZoom: 16, noWrap: true, attribution: "NASA/JPL/USGS · Mars Trek" });
      if (i === 0) bases[k].addTo(m);
    });
    const areas = L.layerGroup().addTo(m);
    const cands = L.layerGroup().addTo(m);
    const refs = L.layerGroup();
    L.control.layers(bases, { "Analysed areas": areas, Candidates: cands, "Daubar et al. 2022 new craters": refs }, { collapsed: false }).addTo(m);
    const legend = new L.Control({ position: "bottomleft" });
    legend.onAdd = () => {
      const d = L.DomUtil.create("div", "legend");
      d.innerHTML = Object.entries(COLORS).map(([k, c]) => `<div><span class="dot" style="background:${c}"></span>${STATUS_LABEL[k]}</div>`).join("") +
        `<div><span class="dot" style="background:transparent;border:2px solid #e0662f;border-radius:2px"></span>Analysed area</div>` +
        `<div><span class="dot" style="background:#cfd5dc;width:6px;height:6px"></span>Catalogued new crater</div>`;
      return d;
    };
    legend.addTo(m);
    L.control.scale({ imperial: false }).addTo(m);

    api.map().then((d) => {
      d.areas.forEach((a: any) => {
        const b = a.bounds.map((p: number[]) => [p[0], lon180(p[1])]) as L.LatLngBoundsLiteral;
        L.rectangle(b, { color: a.kind === "validation" ? "#8f7cf0" : "#e0662f", weight: 1.5, fillOpacity: 0.08 })
          .bindPopup(`<b>${a.pair_id}</b><br/>${a.kind} · ${a.n_candidates ?? 0} candidates<br/><a href="/viewer/${encodeURIComponent(a.run_id)}">open viewer</a>`)
          .addTo(areas);
      });
      d.candidates.forEach((c: any) => {
        L.circleMarker([c.lat, lon180(c.lon)], { radius: 4 + 5 * c.score, color: COLORS[c.classification] || "#fff", weight: 1.5, fillOpacity: 0.6 })
          .bindPopup(`<b>Candidate ${c.id}</b><br/>${c.category.replace(/_/g, " ")}<br/>${STATUS_LABEL[c.classification]}<br/>score ${c.score.toFixed(2)} · D≈${c.eq_diameter_m.toFixed(1)} m<br/><a href="/candidates/${c.id}">details</a>`)
          .addTo(cands);
      });
      d.references.forEach((r: any) => {
        L.circleMarker([r.lat, lon180(r.lon)], { radius: 2.5, color: "#cfd5dc", weight: 0, fillOpacity: 0.8 })
          .bindPopup(`<b>${r.ref_id}</b><br/>new impact crater, D=${r.diameter_m} m<br/>Daubar et al. (2022)`)
          .addTo(refs);
      });
      setCounts({ areas: d.areas.length, cands: d.candidates.length, refs: d.references.length });
    });

    m.on("click", (e: L.LeafletMouseEvent) => {
      const s = selRef.current;
      if ((m as any)._mwSelecting) {
        s.pts.push(e.latlng);
        if (s.pts.length === 2) {
          const b = L.latLngBounds(s.pts[0], s.pts[1]);
          s.rect?.remove();
          s.rect = L.rectangle(b, { color: "#ff8a50", weight: 2, dashArray: "4 4", fillOpacity: 0.05 }).addTo(m);
          setRegion({ min_lat: b.getSouth(), max_lat: b.getNorth(), min_lon: lon360(b.getWest()), max_lon: lon360(b.getEast()) });
          (m as any)._mwSelecting = false;
          setSelecting(false);
          s.pts = [];
        }
        return;
      }
      setClick({ lat: e.latlng.lat, lon: lon360(e.latlng.lng) });
      setCoverage(null);
    });
  }, []);

  useEffect(() => {
    if (map.current) (map.current as any)._mwSelecting = selecting;
  }, [selecting]);

  const submit = async () => {
    if (!region) return;
    try {
      const r = await api.discover({ region: form.name, ...region, enqueue_top: form.enqueue_top, res_m: form.res_m, max_area_km2: form.max_area_km2 });
      setMsg(r.deduplicated ? "An identical discovery job already exists." : `Discovery job #${r.job_id} queued. Follow it in the Processing Console.`);
    } catch (e: any) {
      setMsg(`Error: ${e.message}`);
    }
  };

  return (
    <div className="page" style={{ maxWidth: "none" }}>
      <div className="page-head">
        <div>
          <h1>Mars Explorer</h1>
          <p>
            Analysed areas, candidate detections and the {counts.refs.toLocaleString()} catalogued new impacts of Daubar et al. (2022).
            Click anywhere to list HiRISE coverage, or select a region to discover and queue new image pairs.
          </p>
        </div>
        <div className="row">
          <span className="faint small">{counts.areas} areas · {counts.cands} candidates (score ≥ 0.2)</span>
          <button className={selecting ? "primary" : ""} onClick={() => { setSelecting(!selecting); setRegion(null); selRef.current.rect?.remove(); }}>
            {selecting ? "Click two corners…" : "Select survey region"}
          </button>
        </div>
      </div>
      <div className="grid g-side">
        <div ref={el} className="map" />
        <div className="grid" style={{ alignContent: "start" }}>
          {region && (
            <div className="panel">
              <div className="panel-head"><h3>Survey region</h3></div>
              <p className="small muted" style={{ marginTop: 0 }}>
                {fmt(region.min_lat, 3)}°…{fmt(region.max_lat, 3)}°N, {fmt(region.min_lon, 3)}°…{fmt(region.max_lon, 3)}°E
              </p>
              <div className="grid" style={{ gap: 8 }}>
                <label className="field">Region name<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
                <div className="grid g2" style={{ gap: 8 }}>
                  <label className="field">Queue top-N pairs<input type="number" min={0} max={200} value={form.enqueue_top} onChange={(e) => setForm({ ...form, enqueue_top: +e.target.value })} /></label>
                  <label className="field">Resolution (m/px)<select value={form.res_m} onChange={(e) => setForm({ ...form, res_m: +e.target.value })}><option value={0.5}>0.5</option><option value={1}>1.0</option><option value={2}>2.0</option></select></label>
                </div>
                <label className="field">Max area per pair (km²)<input type="number" value={form.max_area_km2} onChange={(e) => setForm({ ...form, max_area_km2: +e.target.value })} /></label>
                <button className="primary" onClick={submit}>Discover pairs &amp; queue analysis</button>
                {msg && <div className="notice">{msg}</div>}
              </div>
            </div>
          )}
          {click && (
            <div className="panel">
              <div className="panel-head">
                <h3>Location</h3>
                <span className="mono small">{fmt(click.lat, 4)}°N {fmt(click.lon, 4)}°E</span>
              </div>
              {coverage === null ? (
                <button onClick={() => api.covering(click.lat, click.lon).then(setCoverage)}>List HiRISE observations here</button>
              ) : coverage.length === 0 ? (
                <div className="faint small">No HiRISE RED observation covers this point.</div>
              ) : (
                <>
                  <div className="small muted" style={{ marginBottom: 6 }}>{coverage.length} observations (oldest first)</div>
                  <div className="table-wrap" style={{ maxHeight: 360 }}>
                    <table>
                      <thead><tr><th>Product</th><th>Date</th><th>Inc.</th><th>Ls</th></tr></thead>
                      <tbody>
                        {coverage.map((o) => (
                          <tr key={o.product_id} title={o.rationale}>
                            <td className="mono"><a href={o.uahirise_url} target="_blank" rel="noreferrer">{o.product_id.replace("_RED", "")}</a></td>
                            <td>{fmtDate(o.start_time)}</td><td className="num">{fmt(o.incidence, 0)}°</td><td className="num">{fmt(o.solar_longitude, 0)}°</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {coverage.length >= 2 && (
                    <button style={{ marginTop: 8 }} onClick={async () => {
                      const r = await api.analyze({ before_id: coverage[0].product_id, after_id: coverage[coverage.length - 1].product_id, lat: click.lat, lon: click.lon, half_size_m: 500, res_m: 0.5 });
                      setMsg(r.deduplicated ? "Already queued." : `Analysis job #${r.job_id} queued (oldest vs newest, 1 km² window).`);
                    }}>Analyse oldest vs newest (1 km² window)</button>
                  )}
                  {msg && !region && <div className="notice" style={{ marginTop: 8 }}>{msg} <Link to="/console">console →</Link></div>}
                </>
              )}
            </div>
          )}
          {!region && !click && (
            <div className="notice">
              Basemaps are global mosaics served by NASA's Mars Trek (Viking MDIM 2.1, MOLA). They are only
              context: all change detection uses full-resolution HiRISE data. Longitudes are planetocentric, east-positive.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
