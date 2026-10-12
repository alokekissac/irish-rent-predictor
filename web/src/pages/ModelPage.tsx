// Model accuracy, baselines, and a backtest you can slice by county, area type and bedrooms.
import { useMemo, useState } from "react";
import Plot from "../components/Plot";
import { Card, Kpi, PageHead, Select } from "../components/ui";
import { LEVEL_LABEL, ordered, BEDS_ORDER, useLazy, type Backtest } from "../data";
import { useApp } from "../state";
import { useChartTheme } from "../theme";

const ALL = "All";

export default function ModelPage() {
  const { core } = useApp();
  const t = useChartTheme();
  const m = core.meta.metrics;
  const bt = useLazy<Backtest>("backtest.json");
  const [county, setCounty] = useState(ALL);
  const [level, setLevel] = useState(ALL);
  const [beds, setBeds] = useState(ALL);

  const models = [
    ["Naive (no change)", "test_naive"],
    ["Momentum (last year repeats)", "test_momentum"],
    ["LightGBM without house-price data", "test_lgbm_no_ppr"],
    ["LightGBM (full model)", "test_lgbm"],
  ].filter(([, k]) => m[`${k}_mape_pct`] != null);

  const slice = useMemo(() => {
    if (!bt) return null;
    const ci = bt.county_names.indexOf(county), li = bt.level_names.indexOf(level), bi = bt.beds_names.indexOf(beds);
    const idx: number[] = [];
    for (let k = 0; k < bt.pred.length; k++) {
      if ((county === ALL || bt.county[k] === ci) && (level === ALL || bt.level[k] === li) && (beds === ALL || bt.beds[k] === bi)) idx.push(k);
    }
    const err = idx.map((k) => (bt.pred[k] / bt.actual[k] - 1) * 100);
    const covered = idx.filter((k) => bt.actual[k] >= bt.lo[k] && bt.actual[k] <= bt.hi[k]).length;
    const byCounty = bt.county_names.map((c, ci2) => {
      const e = idx.filter((k) => bt.county[k] === ci2).map((k) => Math.abs(bt.pred[k] / bt.actual[k] - 1) * 100);
      return { c, mape: e.length ? e.reduce((a, b) => a + b, 0) / e.length : null, n: e.length };
    }).filter((d) => d.mape != null).sort((a, b) => a.mape! - b.mape!);
    const step = Math.max(1, Math.floor(idx.length / 4000));
    const sample = idx.filter((_, j) => j % step === 0);
    return {
      n: idx.length,
      mape: err.reduce((a, b) => a + Math.abs(b), 0) / (err.length || 1),
      bias: err.reduce((a, b) => a + b, 0) / (err.length || 1),
      coverage: (covered / (idx.length || 1)) * 100,
      err, byCounty, sample,
    };
  }, [bt, county, level, beds]);

  const maxAxis = slice ? Math.max(...slice.sample.map((k) => Math.max(bt!.actual[k], bt!.pred[k]))) * 1.05 : 1;

  return (
    <>
      <PageHead title="Model performance">
        Each series' rent is forecast 12 months ahead. The model trained on outcomes before {core.meta.split.valid_start}, was
        tuned on {core.meta.split.valid_start.slice(0, 4)}, and is scored here on <b>unseen</b> outcomes from{" "}
        {core.meta.split.test_start} on.
      </PageHead>
      <div className="kpis">
        <Kpi label="Average error (MAPE)" value={`${m.test_lgbm_mape_pct.toFixed(2)}%`} sub={`${((1 - m.test_lgbm_mape_pct / m.test_naive_mape_pct) * 100).toFixed(0)}% less than naive`} tone="down" />
        <Kpi label="Average miss" value={`€${m.test_lgbm_mae_eur.toFixed(0)}/mo`} />
        <Kpi label="~80% range coverage" value={`${m.test_interval_coverage_pct.toFixed(1)}%`} sub={`${(m.test_interval_coverage_pct - m.test_raw_interval_coverage_pct).toFixed(1)} pts from conformal calibration`} />
        <Kpi label="Forecasts scored" value={(slice?.n ?? 0).toLocaleString()} sub="in current slice" />
      </div>
      <div className="grid cols-2">
        <Card title="Test error vs baselines">
          <Plot height={260} ariaLabel="Model comparison bar chart"
            data={[{ type: "bar", orientation: "h", y: models.map(([n]) => n), x: models.map(([, k]) => m[`${k}_mape_pct`]), marker: { color: t.series[0] },
              text: models.map(([, k]) => `${m[`${k}_mape_pct`].toFixed(2)}%`), textposition: "outside", textfont: { color: t.text },
              hovertemplate: "%{y}: %{x:.2f}%<extra></extra>" }]}
            layout={{ margin: { l: 10, r: 10, t: 4, b: 30 }, xaxis: { ticksuffix: "%", showgrid: true, range: [0, Math.max(...models.map(([, k]) => m[`${k}_mape_pct`])) * 1.2] }, bargap: 0.35 }} />
        </Card>
        <Card title="What the backtest taught me">
          <div className="callout">
            <p style={{ marginTop: 0 }}><b>Importance ≠ predictive value.</b> House-price features rank high by importance, yet removing them doesn't change test error.</p>
            <p><b>Conformal needs stable data.</b> Calibrated ranges cover {m.test_interval_coverage_pct.toFixed(0)}% rather than 80% because 2024–25 behaved differently from the 2023 calibration year.</p>
            <p style={{ marginBottom: 0 }}><b>Slight under-forecasting.</b> The model's bias is shown below; slice it to see where it runs low.</p>
          </div>
        </Card>
      </div>

      <div className="spacer" />
      <Card title="🔬 Slice the backtest">
        {!bt || !slice ? <p className="note">Loading backtest…</p> : (
          <>
            <div className="controls">
              <Select label="County" value={county} options={[ALL, ...bt.county_names]} onChange={setCounty} />
              <Select label="Area type" value={level} options={[ALL, ...bt.level_names]} onChange={setLevel} format={(v) => LEVEL_LABEL[v] ?? v} />
              <Select label="Bedrooms" value={beds} options={[ALL, ...ordered(bt.beds_names, BEDS_ORDER)]} onChange={setBeds} />
            </div>
            {slice.n === 0 ? <p className="note">No forecasts in this slice.</p> : (
              <>
                <div className="kpis">
                  <Kpi label="MAPE" value={`${slice.mape.toFixed(2)}%`} />
                  <Kpi label="Bias" value={`${slice.bias > 0 ? "+" : ""}${slice.bias.toFixed(2)}%`} sub={slice.bias < 0 ? "under-forecasts on average" : "over-forecasts on average"} />
                  <Kpi label="Range coverage" value={`${slice.coverage.toFixed(1)}%`} sub="target 80%" />
                  <Kpi label="Forecasts" value={slice.n.toLocaleString()} />
                </div>
                <div className="grid cols-2-even">
                  <div>
                    <h3 style={{ fontSize: 15 }}>Forecast vs actual rent</h3>
                    <Plot height={400} ariaLabel="Scatter of forecast versus actual rent"
                      data={[
                        { x: [0, maxAxis], y: [0, maxAxis], type: "scatter", mode: "lines", line: { color: t.muted, dash: "dash", width: 1 }, hoverinfo: "skip", showlegend: false },
                        { x: slice.sample.map((k) => bt.actual[k]), y: slice.sample.map((k) => bt.pred[k]), type: "scattergl", mode: "markers",
                          marker: { color: t.series[0], size: 6, opacity: 0.45 }, showlegend: false,
                          customdata: slice.sample.map((k) => [core.meta.quarters[bt.tq[k]], bt.county_names[bt.county[k]]]),
                          hovertemplate: "%{customdata[1]} · %{customdata[0]}<br>Actual €%{x:,.0f} · forecast €%{y:,.0f}<extra></extra>" },
                      ]}
                      layout={{ margin: { l: 10, r: 10, t: 4, b: 40 }, xaxis: { title: { text: "Actual (€)" }, showgrid: true }, yaxis: { title: { text: "Forecast (€)" }, showgrid: true } }} />
                  </div>
                  <div>
                    <h3 style={{ fontSize: 15 }}>Distribution of errors</h3>
                    <Plot height={400} ariaLabel="Histogram of forecast errors"
                      data={[{ x: slice.err.map((e) => Math.max(-30, Math.min(30, e))), type: "histogram", nbinsx: 60, marker: { color: t.series[0], line: { color: t.surface, width: 1 } }, hovertemplate: "%{x}%: %{y}<extra></extra>" }]}
                      layout={{ margin: { l: 10, r: 10, t: 4, b: 40 }, bargap: 0.02, xaxis: { title: { text: "Forecast error % (clipped ±30)" } }, yaxis: { showgrid: true },
                        shapes: [{ type: "line", x0: 0, x1: 0, yref: "paper", y0: 0, y1: 1, line: { color: t.series[1], dash: "dash", width: 2 } }] }} />
                  </div>
                </div>
                <h3 style={{ fontSize: 15, marginTop: 12 }}>Error by county</h3>
                <Plot height={320} ariaLabel="Forecast error by county"
                  data={[{ type: "bar", x: slice.byCounty.map((d) => d.c), y: slice.byCounty.map((d) => d.mape), customdata: slice.byCounty.map((d) => d.n), marker: { color: t.series[0] }, hovertemplate: "<b>%{x}</b><br>MAPE %{y:.2f}% · %{customdata} forecasts<extra></extra>" }]}
                  layout={{ margin: { l: 10, r: 10, t: 4, b: 60 }, yaxis: { ticksuffix: "%", showgrid: true }, bargap: 0.25 }} />
              </>
            )}
          </>
        )}
      </Card>
    </>
  );
}
