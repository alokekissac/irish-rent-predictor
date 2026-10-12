// Where can I afford? Rent-to-income by county and area, today and in 12 months.
import { useMemo, useState } from "react";
import Plot, { useIsNarrow } from "../components/Plot";
import { Card, Kpi, PageHead, Segmented, Select } from "../components/ui";
import { BEDS_ORDER, TYPES_ORDER, euro, ordered, pct, shortArea } from "../data";
import { useApp } from "../state";
import { scale, useChartTheme } from "../theme";

export default function Afford() {
  const { core, county, setCounty, openSeries } = useApp();
  const t = useChartTheme();
  const mapHeight = useIsNarrow() ? 440 : 600;
  const [income, setIncome] = useState(4000);
  const [share, setShare] = useState(30);
  const [sharers, setSharers] = useState(1);
  const [beds, setBeds] = useState("Two bed");
  const [type, setType] = useState("All property types");
  const [when, setWhen] = useState<"now" | "f">("f");

  const budget = (income * share) / 100;
  const rows = useMemo(() => core.series.map((s, i) => {
    const rent = when === "f" ? s.f : s.rent;
    return { ...s, i, yours: rent / sharers, sharePay: (rent / sharers / income) * 100, ok: rent / sharers <= budget, wasOk: s.rent / sharers <= budget, willOk: s.f / sharers <= budget };
  }).filter((s) => s.beds === beds && s.type === type), [core, when, sharers, income, budget, beds, type]);

  const counties = rows.filter((r) => r.level === "county");
  const areas = rows.filter((r) => r.level !== "county");
  const lost = areas.filter((a) => a.wasOk && !a.willOk).sort((a, b) => a.rent - b.rent);
  const ok = areas.filter((a) => a.ok).sort((a, b) => a.yours - b.yours);
  const inCounty = areas.filter((a) => a.county === county).sort((a, b) => a.yours - b.yours);
  const cheapest = [...areas].sort((a, b) => a.yours - b.yours)[0];

  return (
    <>
      <PageHead title="Where can I afford?">
        Enter your household's take-home pay. Areas are compared using RTB average rents for new tenancies, today or as
        forecast in 12 months.
      </PageHead>
      <Card>
        <div className="controls" style={{ marginBottom: 0 }}>
          <label className="field">
            <span>Take-home pay (€/month)</span>
            <input type="number" min={500} max={30000} step={100} value={income} onChange={(e) => setIncome(Math.max(500, Number(e.target.value) || 0))} />
          </label>
          <label className="field" style={{ minWidth: 200 }}>
            <span>Max share on rent: <b>{share}%</b></span>
            <input type="range" min={15} max={60} value={share} onChange={(e) => setShare(Number(e.target.value))} />
          </label>
          <label className="field">
            <span>People splitting rent</span>
            <input type="number" min={1} max={6} value={sharers} onChange={(e) => setSharers(Math.min(6, Math.max(1, Number(e.target.value) || 1)))} />
          </label>
          <Select label="Bedrooms" value={beds} options={ordered(new Set(core.series.map((s) => s.beds)), BEDS_ORDER)} onChange={setBeds} />
          <Select label="Property type" value={type} options={ordered(new Set(core.series.map((s) => s.type)), TYPES_ORDER)} onChange={setType} />
          <Segmented label="Compare against" value={when} onChange={setWhen} options={[{ value: "now", label: "Rent today" }, { value: "f", label: "In 12 months" }]} />
        </div>
      </Card>
      <div className="spacer" />
      <div className="kpis">
        <Kpi label="Your rent budget" value={`${euro(budget)}/mo`} sub={`${share}% of ${euro(income)}`} />
        <Kpi label={`Affordable areas (${when === "f" ? "in 12m" : "today"})`} value={`${ok.length} of ${areas.length}`} />
        <Kpi label="Priced out within 12 months" value={lost.length} sub={lost.length ? "affordable today, not at forecast" : "none"} tone={lost.length ? "up" : "muted"} />
        {cheapest && <Kpi label="Cheapest area" value={euro(cheapest.yours)} sub={cheapest.location} />}
      </div>

      {areas.length === 0 ? (
        <Card><p>No RTB data for this bedroom / property type combination.</p></Card>
      ) : (
        <div className="grid cols-2">
          <Card title="Share of your pay going on rent" actions={<span className="note" style={{ margin: 0 }}>grey = {share}% · blue under · red over · click a county</span>}>
            <Plot height={mapHeight} ariaLabel="Map of rent as a share of income by county" onClick={(p) => p?.location && setCounty(p.location)}
              data={[
                {
                  type: "choropleth", geojson: core.geo, featureidkey: "id", locations: counties.map((c) => c.county), z: counties.map((c) => c.sharePay),
                  zmid: share, colorscale: scale(t.diverging), marker: { line: { color: t.outline, width: 0.8 } },
                  colorbar: { thickness: 10, len: 0.55, ticksuffix: "%", tickfont: { color: t.muted }, outlinewidth: 0 },
                  customdata: counties.map((c) => c.yours), hovertemplate: "<b>%{location}</b><br>%{z:.0f}% of pay (€%{customdata:,.0f})<extra></extra>",
                },
                ...(counties.some((c) => c.county === county) ? [{
                  type: "choropleth", geojson: core.geo, featureidkey: "id", locations: [county], z: [0], showscale: false, hoverinfo: "skip",
                  colorscale: [[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], marker: { line: { color: t.selected, width: 2 } },
                }] : []),
              ]}
              layout={{ geo: { visible: false, bgcolor: "rgba(0,0,0,0)", projection: { type: "mercator" }, lonaxis: { range: [-10.7, -5.9] }, lataxis: { range: [51.35, 55.45] } }, margin: { l: 0, r: 0, t: 0, b: 0 }, dragmode: false }} />
          </Card>
          <Card title={`${county}: areas vs your budget`}>
            {inCounty.length ? (
              <div className="scroll">
                <Plot height={Math.max(260, inCounty.length * 22 + 60)} ariaLabel={`Rent share by area in ${county}`} onClick={(p) => p && openSeries(p.customdata[2])}
                  data={[{
                    type: "bar", orientation: "h", x: inCounty.map((a) => a.yours), y: inCounty.map((a) => shortArea(a.location, county)),
                    marker: { color: inCounty.map((a) => (a.ok ? t.down : t.up)) }, customdata: inCounty.map((a) => [a.sharePay, a.location, a.i]),
                    hovertemplate: "<b>%{customdata[1]}</b><br>Your share €%{x:,.0f} (%{customdata[0]:.0f}% of pay)<extra>click to open</extra>",
                  }]}
                  layout={{
                    bargap: 0.3, margin: { l: 10, r: 20, t: 24, b: 30 }, yaxis: { autorange: "reversed" }, xaxis: { tickprefix: "€", showgrid: true },
                    shapes: [{ type: "line", x0: budget, x1: budget, yref: "paper", y0: 0, y1: 1, line: { color: t.series[1], width: 2, dash: "dash" } }],
                    annotations: [{ x: budget, yref: "paper", y: 1, yanchor: "bottom", text: `Budget ${euro(budget)}`, showarrow: false, font: { color: t.text } }],
                  }} />
              </div>
            ) : <p className="note">No town-level data for {county} with this filter.</p>}
          </Card>
        </div>
      )}

      <div className="spacer" />
      <Card title={`✅ ${ok.length} areas within your budget`}>
        {ok.length === 0 ? (
          <p className="note">Nothing fits {euro(budget)}. Try more people sharing, fewer bedrooms or a higher share.</p>
        ) : (
          <div className="table-wrap scroll">
            <table>
              <thead><tr><th>Area</th><th>County</th><th className="num">Rent today</th><th className="num">Forecast</th><th className="num">Growth</th><th className="num">Your share</th><th className="num">% of pay</th><th className="num">Left after rent</th></tr></thead>
              <tbody>
                {ok.slice(0, 200).map((a) => (
                  <tr key={a.i} className="clickable" onClick={() => openSeries(a.i)} tabIndex={0} onKeyDown={(e) => e.key === "Enter" && openSeries(a.i)}>
                    <td>{a.location}</td><td>{a.county}</td><td className="num">{euro(a.rent)}</td><td className="num">{euro(a.f)}</td>
                    <td className="num">{pct(a.g)}</td><td className="num">{euro(a.yours)}</td><td className="num">{a.sharePay.toFixed(0)}%</td><td className="num">{euro(income - a.yours)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {lost.length > 0 && (
          <details style={{ marginTop: 12 }}>
            <summary>⚠️ {lost.length} areas affordable today but forecast to exceed your budget</summary>
            <p className="note">{lost.map((a) => `${a.location} (${euro(a.rent)} → ${euro(a.f)})`).join(" · ")}</p>
          </details>
        )}
      </Card>
    </>
  );
}
