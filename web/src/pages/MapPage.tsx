// Clickable county choropleth with drill-down, plus an animated 2008→today timeline.
import { useEffect, useMemo, useState } from "react";
import Plot, { useIsNarrow } from "../components/Plot";
import { Card, Kpi, PageHead, Segmented, Select } from "../components/ui";
import { ALL_BEDS, ALL_TYPES, BEDS_ORDER, TYPES_ORDER, euro, ordered, pct, shortArea } from "../data";
import { useApp } from "../state";
import { scale, useChartTheme } from "../theme";

type Metric = "f" | "g" | "rent" | "g12";
const METRICS: { value: Metric; label: string }[] = [
  { value: "f", label: "Forecast rent" },
  { value: "g", label: "Forecast growth" },
  { value: "rent", label: "Rent now" },
  { value: "g12", label: "Past 12m growth" },
];

export default function MapPage() {
  const { core, county, setCounty, openSeries } = useApp();
  const t = useChartTheme();
  const mapHeight = useIsNarrow() ? 440 : 620;
  const [metric, setMetric] = useState<Metric>("f");
  const [beds, setBeds] = useState(ALL_BEDS);
  const [type, setType] = useState(ALL_TYPES);
  const isEuro = metric === "f" || metric === "rent";

  const subset = useMemo(
    () => core.series.map((s, i) => ({ ...s, i })).filter((s) => s.beds === beds && s.type === type),
    [core, beds, type],
  );
  const counties = subset.filter((s) => s.level === "county");
  const sel = counties.find((s) => s.county === county);
  const areas = subset.filter((s) => s.county === county && s.level !== "county").sort((a, b) => a.f - b.f);
  const rank = sel ? counties.filter((c) => c.f > sel.f).length + 1 : null;

  const mapData = useMemo(() => {
    const z = counties.map((c) => (c[metric] as number | null) ?? null);
    const base: any = {
      type: "choropleth",
      geojson: core.geo,
      featureidkey: "id",
      locations: counties.map((c) => c.county),
      z,
      colorscale: scale(isEuro ? t.seqBlue : t.seqOrange),
      marker: { line: { color: t.outline, width: 0.8 } },
      colorbar: { thickness: 10, len: 0.55, tickprefix: isEuro ? "€" : "", ticksuffix: isEuro ? "" : "%", tickfont: { color: t.muted }, outlinewidth: 0 },
      hovertemplate: `<b>%{location}</b><br>${METRICS.find((m) => m.value === metric)!.label}: ${isEuro ? "€%{z:,.0f}" : "%{z:+.1f}%"}<extra></extra>`,
    };
    const traces: any[] = [base];
    if (sel)
      traces.push({
        type: "choropleth", geojson: core.geo, featureidkey: "id", locations: [sel.county], z: [0],
        colorscale: [[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale: false, hoverinfo: "skip",
        marker: { line: { color: t.selected, width: 2 } },
      });
    return traces;
  }, [counties, metric, sel, core.geo, t, isEuro]);

  const geoLayout = useMemo(() => ({
    geo: {
      visible: false, bgcolor: "rgba(0,0,0,0)", projection: { type: "mercator" },
      lonaxis: { range: [-10.7, -5.9] }, lataxis: { range: [51.35, 55.45] },
    },
    margin: { l: 0, r: 0, t: 0, b: 0 },
    dragmode: false,
  }), []);

  const areaBars = useMemo(() => [{
    type: "bar", orientation: "h",
    x: areas.map((a) => a.f), y: areas.map((a) => shortArea(a.location, county)),
    customdata: areas.map((a) => [a.location, a.rent, a.g, a.i]),
    marker: { color: t.series[0] },
    error_x: { type: "data", symmetric: false, array: areas.map((a) => a.hi - a.f), arrayminus: areas.map((a) => a.f - a.lo), color: t.muted, thickness: 1, width: 0 },
    hovertemplate: "<b>%{customdata[0]}</b><br>Now €%{customdata[1]:,.0f} → €%{x:,.0f} (%{customdata[2]:+.1f}%)<extra>click to open</extra>",
  }], [areas, county, t]);

  return (
    <>
      <PageHead title="Irish rents, forecast 12 months ahead">
        Forecasts for {core.meta.n_series.toLocaleString()} RTB rent series from a LightGBM model with calibrated ranges.{" "}
        <b>Click any county</b> to drill into its towns and neighbourhoods.
      </PageHead>
      <div className="controls">
        <Segmented label="Colour map by" value={metric} options={METRICS} onChange={setMetric} />
        <Select label="Bedrooms" value={beds} options={ordered(new Set(core.series.map((s) => s.beds)), BEDS_ORDER)} onChange={setBeds} />
        <Select label="Property type" value={type} options={ordered(new Set(core.series.map((s) => s.type)), TYPES_ORDER)} onChange={setType} />
      </div>

      {counties.length === 0 ? (
        <Card><p>No county-level RTB data for this combination. Try “All property types”.</p></Card>
      ) : (
        <div className="grid cols-2">
          <Card>
            <Plot data={mapData} layout={geoLayout} height={mapHeight} ariaLabel="Map of Irish counties coloured by rent" onClick={(p) => p?.location && setCounty(p.location)} />
            <p className="note">
              Median county forecast growth <b>{pct(median(counties.map((c) => c.g)))}</b> · highest rent{" "}
              <b>{maxBy(counties, (c) => c.f).county}</b> · fastest rising <b>{maxBy(counties, (c) => c.g).county}</b>
            </p>
          </Card>
          <Card title={`📍 ${county}`} actions={sel && <button className="btn primary" onClick={() => openSeries(sel.i)}>Open in explorer →</button>}>
            {sel ? (
              <div className="kpis">
                <Kpi label={`Rent (${sel.q})`} value={euro(sel.rent)} sub={`${pct(sel.g12)} in 12m`} />
                <Kpi label={`Forecast (${sel.fq})`} value={euro(sel.f)} sub={pct(sel.g)} tone="up" />
                <Kpi label={`Price rank (of ${counties.length})`} value={`#${rank}`} sub={`${euro(sel.lo)} – ${euro(sel.hi)}`} />
              </div>
            ) : (
              <p className="note">No county figure for this filter.</p>
            )}
            {areas.length ? (
              <>
                <p className="note" style={{ marginTop: 0 }}><b>{areas.length} areas</b> · click a bar to open it · whiskers show the ~80% range</p>
                <div className="scroll">
                  <Plot data={areaBars} height={Math.max(260, areas.length * 22 + 50)} ariaLabel={`Forecast rent by area in ${county}`}
                    layout={{ bargap: 0.3, margin: { l: 10, r: 20, t: 4, b: 30 }, xaxis: { tickprefix: "€", showgrid: true } }}
                    onClick={(p) => p && openSeries(p.customdata[3])} />
                </div>
              </>
            ) : (
              <p className="note">No town-level data for this filter.</p>
            )}
          </Card>
        </div>
      )}
      <div className="spacer" />
      <Timeline />
    </>
  );
}

function Timeline() {
  const { core } = useApp();
  const t = useChartTheme();
  const mapHeight = useIsNarrow() ? 420 : 520;
  const quarters = core.meta.quarters;
  const rows = useMemo(() => {
    const heads = core.series.map((s, i) => ({ s, i })).filter(({ s }) => s.level === "county" && s.beds === ALL_BEDS && s.type === ALL_TYPES);
    const years = [...new Set(quarters.map((q) => Number(q.slice(0, 4))))].filter((y) => y >= 2008);
    const byYear = years.map((y) =>
      heads.map(({ i }) => {
        const vals = core.history[i].filter((_, k) => Number(quarters[k].slice(0, 4)) === y).filter((v): v is number => v != null);
        return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
      }),
    );
    return { heads: heads.map(({ s }) => s.county), years, byYear };
  }, [core, quarters]);

  const [k, setK] = useState(rows.years.length - 1);
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!playing) return;
    if (k >= rows.years.length - 1) {
      setPlaying(false);
      return;
    }
    const id = setTimeout(() => setK(k + 1), 700);
    return () => clearTimeout(id);
  }, [playing, k, rows.years.length]);

  const all = rows.byYear.flat().filter((v): v is number => v != null);
  const [zmin, zmax] = [Math.min(...all), Math.max(...all)];
  const first = rows.byYear[0];
  const last = rows.byYear[rows.byYear.length - 1];
  const change = rows.heads.map((c, j) => ({ c, v: first[j] && last[j] ? (last[j]! / first[j]! - 1) * 100 : null }))
    .filter((d) => d.v != null).sort((a, b) => a.v! - b.v!);

  return (
    <div className="grid cols-2">
      <Card title={`▶ Rents through time: ${rows.years[k]}`} actions={
        <div style={{ display: "flex", gap: 10, alignItems: "center", flex: 1, minWidth: 220 }}>
          <button className="btn" onClick={() => { if (k === rows.years.length - 1) setK(0); setPlaying((p) => !p); }} aria-label={playing ? "Pause" : "Play"}>
            {playing ? "⏸ Pause" : "▶ Play"}
          </button>
          <input type="range" min={0} max={rows.years.length - 1} value={k} onChange={(e) => { setPlaying(false); setK(Number(e.target.value)); }} aria-label="Year" style={{ flex: 1, accentColor: "var(--accent)" }} />
        </div>
      }>
        <Plot height={mapHeight} ariaLabel={`Average county rents in ${rows.years[k]}`}
          data={[{
            type: "choropleth", geojson: core.geo, featureidkey: "id", locations: rows.heads, z: rows.byYear[k], zmin, zmax,
            colorscale: scale(t.seqBlue), marker: { line: { color: t.outline, width: 0.8 } },
            colorbar: { thickness: 10, len: 0.55, tickprefix: "€", tickfont: { color: t.muted }, outlinewidth: 0 },
            hovertemplate: `<b>%{location}</b> ${rows.years[k]}<br>€%{z:,.0f}/month<extra></extra>`,
          }]}
          layout={{ geo: { visible: false, bgcolor: "rgba(0,0,0,0)", projection: { type: "mercator" }, lonaxis: { range: [-10.7, -5.9] }, lataxis: { range: [51.35, 55.45] } }, margin: { l: 0, r: 0, t: 0, b: 0 } }} />
        <p className="note">Annual average rent of new tenancies, all bedrooms and property types. Colour scale fixed across years.</p>
      </Card>
      <Card title={`Rent change ${rows.years[0]} → ${rows.years[rows.years.length - 1]}`}>
        <Plot height={560} ariaLabel="Percentage rent change by county"
          data={[{ type: "bar", orientation: "h", x: change.map((d) => d.v), y: change.map((d) => d.c), marker: { color: t.series[0] }, hovertemplate: "%{y}: %{x:+.0f}%<extra></extra>" }]}
          layout={{ bargap: 0.25, margin: { l: 10, r: 10, t: 4, b: 30 }, xaxis: { ticksuffix: "%", showgrid: true } }} />
      </Card>
    </div>
  );
}

export function median(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

export function maxBy<T>(xs: T[], f: (x: T) => number): T {
  return xs.reduce((best, x) => (f(x) > f(best) ? x : best));
}
