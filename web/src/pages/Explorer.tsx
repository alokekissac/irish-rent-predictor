// One series in depth: history + forecast, past forecasts vs actuals, what-if scenario and SHAP "why".
import { useMemo, useState } from "react";
import Plot from "../components/Plot";
import SeriesPicker from "../components/SeriesPicker";
import { Card, Kpi, PageHead, Toggle } from "../components/ui";
import { FEATURE_LABELS, euro, interp, pct, quarterToDate, useLazy, type Backtest } from "../data";
import { useApp } from "../state";
import { useChartTheme } from "../theme";

const SCENARIO_LABELS: Record<string, string> = {
  growth_4q: "This area's last-12m growth",
  county_growth_4q: "County rent momentum (12m)",
  national_growth_4q: "National rent momentum (12m)",
  price_growth_4q: "County house-price growth (12m)",
};

export default function Explorer() {
  const { core, sid } = useApp();
  const t = useChartTheme();
  const s = core.series[sid];
  const { meta } = core;
  const whatif = useLazy<Record<string, number[][]>>("whatif.json");
  const backtest = useLazy<Backtest>("backtest.json");

  const [fromYear, setFromYear] = useState(2015);
  const [showBt, setShowBt] = useState(true);
  const [logY, setLogY] = useState(false);
  const [scenario, setScenario] = useState<Record<string, Record<string, number>>>({});

  const grid = meta.whatif_grid;
  const clamp = (v: number) => Math.min(grid[grid.length - 1], Math.max(grid[0], v));
  const observed = (f: string) => clamp(s.obs[f] ?? 0);
  const values = scenario[sid] ?? {};
  const changed = Object.entries(values).some(([f, v]) => Math.abs(v - observed(f)) > 1e-9);

  // ICE curves: exact for one slider; multiple sliders are combined additively
  const scenarioGrowth = useMemo(() => {
    if (!whatif || !changed) return null;
    let g = s.g;
    for (const [f, v] of Object.entries(values)) {
      const curve = whatif[f]?.[sid];
      if (curve) g += interp(grid, curve, v) - interp(grid, curve, observed(f));
    }
    return g;
  }, [whatif, changed, values, sid, s, grid]);
  const scenarioRent = scenarioGrowth == null ? null : s.rent * (1 + scenarioGrowth / 100);

  const bt = useMemo(() => {
    if (!backtest) return [];
    const out: { tq: string; actual: number; pred: number; lo: number; hi: number }[] = [];
    backtest.sid.forEach((x, k) => {
      if (x === sid) out.push({ tq: meta.quarters[backtest.tq[k]], actual: backtest.actual[k], pred: backtest.pred[k], lo: backtest.lo[k], hi: backtest.hi[k] });
    });
    return out;
  }, [backtest, sid, meta.quarters]);
  const btErr = bt.length ? bt.reduce((a, b) => a + Math.abs(b.pred / b.actual - 1), 0) / bt.length * 100 : null;

  const chart = useMemo(() => {
    const hist = core.history[sid];
    const xs: string[] = [];
    const ys: (number | null)[] = [];
    meta.quarters.forEach((q, k) => {
      if (Number(q.slice(0, 4)) >= fromYear) {
        xs.push(quarterToDate(q));
        ys.push(hist[k]);
      }
    });
    const x0 = quarterToDate(s.q);
    const x1 = quarterToDate(s.fq);
    const traces: any[] = [
      { x: [x0, x1, x1, x0], y: [s.rent, s.hi, s.lo, s.rent], fill: "toself", fillcolor: t.band, line: { width: 0 }, name: "~80% range", hoverinfo: "skip", type: "scatter" },
      { x: xs, y: ys, type: "scatter", mode: "lines", name: "RTB average rent", line: { color: t.series[0], width: 2 }, hovertemplate: "€%{y:,.0f}<extra></extra>", connectgaps: false },
      { x: [x0, x1], y: [s.rent, s.f], type: "scatter", mode: "lines+markers", name: "Model forecast", line: { color: t.series[0], width: 2, dash: "dot" }, marker: { size: 9 }, hovertemplate: "€%{y:,.0f}<extra>forecast</extra>" },
    ];
    if (scenarioRent != null)
      traces.push({ x: [x0, x1], y: [s.rent, scenarioRent], type: "scatter", mode: "lines+markers", name: "Your scenario", line: { color: t.series[1], width: 2, dash: "dash" }, marker: { size: 9 }, hovertemplate: "€%{y:,.0f}<extra>scenario</extra>" });
    if (showBt && bt.length)
      traces.push({
        x: bt.map((b) => quarterToDate(b.tq)), y: bt.map((b) => b.pred), type: "scatter", mode: "markers", name: "Past forecast (made 12m earlier)",
        marker: { color: t.series[2], size: 9, symbol: "diamond", line: { color: t.surface, width: 1.5 } },
        error_y: { type: "data", symmetric: false, array: bt.map((b) => b.hi - b.pred), arrayminus: bt.map((b) => b.pred - b.lo), color: t.series[2], thickness: 1, width: 3 },
        customdata: bt.map((b) => [b.actual, (b.pred / b.actual - 1) * 100]),
        hovertemplate: "Forecast €%{y:,.0f} · actual €%{customdata[0]:,.0f} (%{customdata[1]:+.1f}%)<extra></extra>",
      });
    return traces;
  }, [core, sid, s, meta.quarters, fromYear, t, scenarioRent, showBt, bt]);

  // SHAP waterfall
  const why = useMemo(() => {
    const contrib = meta.features.map((f, k) => ({ f: FEATURE_LABELS[f] ?? f, v: s.shap[k] }))
      .sort((a, b) => Math.abs(b.v) - Math.abs(a.v));
    const top = contrib.slice(0, 7);
    const other = contrib.slice(7).reduce((a, b) => a + b.v, 0);
    const labels = ["Typical 12m growth", ...top.map((c) => c.f), "All other factors", "Forecast growth"];
    const vals = [meta.base_value, ...top.map((c) => c.v), other, 0];
    return { top, labels, vals };
  }, [meta, s]);

  return (
    <>
      <PageHead title="Forecast explorer">Pick any area, bedroom count and property type. Shareable: the URL updates with your selection.</PageHead>
      <SeriesPicker />
      <div className="kpis">
        <Kpi label={`Latest rent (${s.q})`} value={euro(s.rent)} sub={`${pct(s.g12)} over the past 12 months`} />
        <Kpi label={`Forecast (${s.fq})`} value={euro(s.f)} sub={pct(s.g)} tone="up" />
        <Kpi label="~80% range" value={`${euro(s.lo)} – ${euro(s.hi)}`} />
        {scenarioRent != null ? (
          <Kpi label="Your scenario" value={euro(scenarioRent)} sub={`${scenarioRent - s.f >= 0 ? "+" : "−"}${euro(Math.abs(scenarioRent - s.f))} vs model`} tone={scenarioRent > s.f ? "up" : "down"} />
        ) : (
          <Kpi label="Extra cost over 12 months" value={euro(12 * (s.f - s.rent))} sub="at forecast vs today's rent" />
        )}
      </div>

      <div className="grid cols-main-side">
        <Card title={`${s.location} · ${s.beds} · ${s.type}`} actions={
          <div className="controls" style={{ margin: 0 }}>
            <Toggle label="Past forecasts vs actual" checked={showBt && bt.length > 0} disabled={!bt.length} onChange={setShowBt} />
            <Toggle label="Log scale" checked={logY} onChange={setLogY} />
            <label className="field" style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
              From
              <select value={fromYear} onChange={(e) => setFromYear(Number(e.target.value))}>
                {[2008, 2012, 2015, 2018, 2020, 2022].map((y) => <option key={y}>{y}</option>)}
              </select>
            </label>
          </div>
        }>
          <Plot data={chart} height={440} ariaLabel={`Rent history and forecast for ${s.location}`}
            layout={{ hovermode: "x unified", margin: { l: 10, r: 10, t: 30, b: 30 }, yaxis: { tickprefix: "€", type: logY ? "log" : "linear", showgrid: true } }} />
          <p className="note">
            {btErr != null && <>Backtest for this series: average error <b>{btErr.toFixed(1)}%</b> over {bt.length} forecasts the model never trained on. </>}
            Gaps mean the RTB suppressed that quarter (too few tenancies).
          </p>
        </Card>

        <Card title="🎛️ What-if scenario" actions={changed && <button className="btn" onClick={() => setScenario({ ...scenario, [sid]: {} })}>Reset</button>}>
          <p className="note" style={{ marginTop: 0 }}>Change the market conditions the model sees. Each slider re-uses the model's own response curve for this series.</p>
          {!whatif && <p className="note">Loading scenario curves…</p>}
          {whatif && meta.scenario_features.map((f) => {
            const obs = s.obs[f];
            const v = values[f] ?? observed(f);
            return (
              <div className="slider-row" key={f}>
                <div className="head"><span>{SCENARIO_LABELS[f]}</span><b>{pct(v)}</b></div>
                <input type="range" min={grid[0]} max={grid[grid.length - 1]} step={0.5} value={v} aria-label={SCENARIO_LABELS[f]}
                  onChange={(e) => setScenario({ ...scenario, [sid]: { ...values, [f]: Number(e.target.value) } })} />
                <div className="obs">Observed {pct(obs)}{obs != null && (obs < grid[0] || obs > grid[grid.length - 1]) ? " (outside slider range)" : ""}</div>
              </div>
            );
          })}
          {Object.keys(values).filter((f) => Math.abs(values[f] - observed(f)) > 1e-9).length > 1 && (
            <p className="note">Several sliders moved: their effects are added together, an approximation.</p>
          )}
        </Card>
      </div>

      <div className="spacer" />
      <Card title="🧠 Why this forecast?">
        <div className="grid cols-2">
          <Plot height={400} ariaLabel="SHAP waterfall of forecast drivers"
            data={[{
              type: "waterfall", orientation: "h", y: why.labels, x: why.vals,
              measure: ["absolute", ...why.top.map(() => "relative"), "relative", "total"],
              increasing: { marker: { color: t.up } }, decreasing: { marker: { color: t.down } }, totals: { marker: { color: t.total } },
              connector: { line: { color: t.grid, width: 1 } },
              hovertemplate: "%{y}: %{x:+.2f} pts<extra></extra>",
            }]}
            layout={{ yaxis: { autorange: "reversed" }, xaxis: { title: { text: "Contribution to 12-month growth (≈ % points)" }, showgrid: true, zeroline: true, zerolinecolor: t.grid }, margin: { l: 10, r: 10, t: 4, b: 40 } }} />
          <div>
            <p><b>Model forecast: {pct(s.g)}</b> over 12 months.</p>
            <p>🔺 <b>Pushing rent up:</b> {why.top.filter((c) => c.v > 0).map((c) => `${c.f} (${pct(c.v)})`).join(", ") || "nothing major"}</p>
            <p>🔻 <b>Holding rent down:</b> {why.top.filter((c) => c.v < 0).map((c) => `${c.f} (${pct(c.v)})`).join(", ") || "nothing major"}</p>
            <p className="note">
              SHAP splits the forecast into each factor's contribution, starting from the average growth the model has
              seen. Red raises the forecast, blue lowers it. This explains the model forecast, not your scenario.
            </p>
          </div>
        </div>
      </Card>
    </>
  );
}
