// Thin React wrapper around Plotly.react with theme-aware defaults and click handling.
import { useEffect, useRef, useState } from "react";
import { useChartTheme } from "../theme";

interface Props {
  data: any[];
  layout?: Record<string, any>;
  height?: number;
  onClick?: (point: any) => void;
  className?: string;
  ariaLabel: string;
}

// Plotly is ~1.4 MB gzipped: load it once, in its own chunk, so the page shell renders first
let plotlyPromise: Promise<any> | null = null;
const loadPlotly = () => (plotlyPromise ??= import("plotly.js-dist-min").then((m) => m.default));

export function useIsNarrow(px = 720): boolean {
  const [narrow, setNarrow] = useState(() => window.matchMedia(`(max-width: ${px}px)`).matches);
  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${px}px)`);
    const on = () => setNarrow(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [px]);
  return narrow;
}

export default function Plot({ data, layout = {}, height = 420, onClick, className, ariaLabel }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const clickRef = useRef(onClick);
  clickRef.current = onClick;
  const t = useChartTheme();
  const [Plotly, setPlotly] = useState<any>(null);
  useEffect(() => {
    let live = true;
    loadPlotly().then((p) => live && setPlotly(() => p));
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    const el = ref.current as any;
    if (!el || !Plotly) return;
    const base = {
      height,
      margin: { l: 10, r: 10, t: 10, b: 10 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: "Inter, system-ui, sans-serif", color: t.muted, size: 12 },
      hoverlabel: { font: { family: "Inter, system-ui, sans-serif" } },
      legend: { orientation: "h", x: 0, y: 1.08, font: { color: t.text } },
      xaxis: { gridcolor: t.grid, zeroline: false, automargin: true, showgrid: false, ...layout.xaxis },
      yaxis: { gridcolor: t.grid, zeroline: false, automargin: true, ...layout.yaxis },
    };
    Plotly.react(el, data, { ...base, ...layout, xaxis: base.xaxis, yaxis: base.yaxis }, {
      displayModeBar: false,
      responsive: true,
      scrollZoom: false,
    });
    el.removeAllListeners?.("plotly_click");
    el.on?.("plotly_click", (ev: any) => clickRef.current?.(ev.points?.[0]));
  }, [Plotly, data, layout, height, t]);

  useEffect(() => {
    const el = ref.current;
    return () => {
      if (el && plotlyPromise) plotlyPromise.then((p) => p.purge(el));
    };
  }, []);

  return (
    <div
      ref={ref}
      className={`plot ${onClick ? "clickable" : ""} ${className ?? ""}`}
      role="img"
      aria-label={ariaLabel}
      style={{ minHeight: height }}
    >
      {!Plotly && <div className="plot-loading">Loading chart…</div>}
    </div>
  );
}
