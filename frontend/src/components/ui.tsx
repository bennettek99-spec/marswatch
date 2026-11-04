import { useEffect, useRef, useState } from "react";
import Plotly from "plotly.js-dist-min";
import { CATEGORY_LABEL, STATUS_LABEL, fmt } from "../api";

export function Stat({ label, value, sub }: { label: string; value: React.ReactNode; sub?: React.ReactNode }) {
  return (
    <div className="panel stat">
      <span className="label">{label}</span>
      <span className="value">{value}</span>
      {sub && <span className="sub">{sub}</span>}
    </div>
  );
}

export function StatusBadge({ s }: { s: string }) {
  return <span className={`badge b-${s}`}>{STATUS_LABEL[s] ?? s}</span>;
}

export function JobBadge({ s }: { s: string }) {
  return <span className={`badge b-${s}`}>{s}</span>;
}

export function CategoryTag({ c }: { c: string }) {
  return <span className="tag">{CATEGORY_LABEL[c] ?? c}</span>;
}

export function ScoreBar({ v }: { v: number }) {
  return (
    <span className="scorebar" title="Heuristic ranking score (not a probability)">
      <span className="bar">
        <i style={{ width: `${Math.max(2, Math.min(100, v * 100))}%` }} />
      </span>
      <span className="mono">{fmt(v)}</span>
    </span>
  );
}

const plotTheme = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { color: "#a8b0bb", family: "Inter, system-ui, sans-serif", size: 12 },
  margin: { l: 48, r: 16, t: 10, b: 40 },
  xaxis: { gridcolor: "#262c35", zerolinecolor: "#363f4b", linecolor: "#363f4b" },
  yaxis: { gridcolor: "#262c35", zerolinecolor: "#363f4b", linecolor: "#363f4b" },
  legend: { orientation: "h", y: -0.32 },
  hoverlabel: { bgcolor: "#1d222a", bordercolor: "#363f4b", font: { color: "#e7e9ec" } },
};

export function Plot({ data, layout, height = 260 }: { data: any[]; layout?: any; height?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!ref.current) return;
    const l = { ...plotTheme, ...layout, height,
      xaxis: { ...plotTheme.xaxis, ...(layout?.xaxis || {}) },
      yaxis: { ...plotTheme.yaxis, ...(layout?.yaxis || {}) } };
    Plotly.react(ref.current, data, l, { displayModeBar: false, responsive: true });
  }, [data, layout, height]);
  useEffect(() => {
    const el = ref.current;
    return () => {
      if (el) Plotly.purge(el);
    };
  }, []);
  return <div ref={ref} style={{ width: "100%", height }} />;
}

export function usePoll<T>(fn: () => Promise<T>, ms: number, deps: any[] = []): [T | undefined, string | undefined, () => void] {
  const [data, setData] = useState<T>();
  const [err, setErr] = useState<string>();
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    const run = () =>
      fn()
        .then((d) => alive && (setData(d), setErr(undefined)))
        .catch((e) => alive && setErr(String(e.message || e)));
    run();
    const t = ms > 0 ? setInterval(run, ms) : undefined;
    return () => {
      alive = false;
      if (t) clearInterval(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return [data, err, () => setTick((x) => x + 1)];
}

export function Loading({ err }: { err?: string }) {
  return err ? <div className="notice warn">Error: {err}</div> : <div className="faint">Loading…</div>;
}

export function Markdown({ text }: { text: string }) {
  // Small, safe markdown renderer (headings, lists, tables, code, links, bold) — no HTML passthrough.
  const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const inline = (s: string) =>
    esc(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
      .replace(/_([^_]+)_/g, "<i>$1</i>")
      .replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');
  const lines = text.split("\n");
  const out: string[] = [];
  let i = 0;
  while (i < lines.length) {
    const l = lines[i];
    if (l.startsWith("```")) {
      const buf: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) buf.push(esc(lines[i++]));
      out.push(`<pre class="log" style="height:auto;max-height:320px">${buf.join("\n")}</pre>`);
      i++;
      continue;
    }
    if (l.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        const cells = lines[i].split("|").slice(1, -1).map((c) => c.trim());
        if (!cells.every((c) => /^-+$/.test(c))) rows.push(cells);
        i++;
      }
      const [h, ...b] = rows;
      out.push(`<div class="table-wrap"><table><thead><tr>${h.map((c) => `<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${b
        .map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join("")}</tr>`)
        .join("")}</tbody></table></div>`);
      continue;
    }
    const h = /^(#{1,4})\s+(.*)/.exec(l);
    if (h) out.push(`<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`);
    else if (/^\s*[*-]\s+/.test(l)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[*-]\s+/.test(lines[i])) items.push(`<li>${inline(lines[i++].replace(/^\s*[*-]\s+/, ""))}</li>`);
      out.push(`<ul>${items.join("")}</ul>`);
      continue;
    } else if (l.startsWith("![")) {
      /* images in reports are run-relative; skipped in this renderer */
    } else if (l.trim()) out.push(`<p>${inline(l)}</p>`);
    i++;
  }
  return <div className="md" dangerouslySetInnerHTML={{ __html: out.join("\n") }} />;
}

export function download(name: string, text: string, type = "text/markdown") {
  const blob = new Blob([text], { type });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}
