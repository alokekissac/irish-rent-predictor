// Up to three areas side by side, in euro or indexed to a common start.
import { useMemo, useState } from "react";
import Plot from "../components/Plot";
import { Card, PageHead, Segmented, Select } from "../components/ui";
import { ALL_BEDS, ALL_TYPES, BEDS_ORDER, TYPES_ORDER, euro, ordered, pct, quarterToDate, seriesKey } from "../data";
import { useApp } from "../state";
import { useChartTheme } from "../theme";

const NONE = "—";

export default function Compare() {
  const { core } = useApp();
  const t = useChartTheme();
  const [areas, setAreas] = useState(["Dublin", "Cork", "Galway"]);
  const [beds, setBeds] = useState(ALL_BEDS);
  const [type, setType] = useState(ALL_TYPES);
  const [mode, setMode] = useState<"eur" | "idx">("eur");
  const [from, setFrom] = useState(2012);
  const locations = useMemo(() => [...new Set(core.series.map((s) => s.location))].sort(), [core]);

  const picked = areas.map((a, slot) => ({ a, slot, i: a === NONE ? undefined : core.byKey.get(seriesKey({ location: a, beds, type })) }));
  const traces: any[] = [];
  const summary: { area: string; color: string; start: number; s: (typeof core.series)[number] }[] = [];
  for (const { a, slot, i } of picked) {
    if (i == null) continue;
    const s = core.series[i];
    const color = t.series[slot];
    const xs: string[] = [];
    const ys: number[] = [];
    core.meta.quarters.forEach((q, k) => {
      const v = core.history[i][k];
      if (v != null && Number(q.slice(0, 4)) >= from) {
        xs.push(quarterToDate(q));
        ys.push(v);
      }
    });
    if (!ys.length) continue;
    const k = mode === "idx" ? 100 / ys[0] : 1;
    traces.push({ x: xs, y: ys.map((v) => v * k), type: "scatter", mode: "lines", name: a, line: { color, width: 2 }, hovertemplate: mode === "idx" ? "%{y:.0f}" : "€%{y:,.0f}" });
    traces.push({
      x: [quarterToDate(s.q), quarterToDate(s.fq)], y: [s.rent * k, s.f * k], type: "scatter", mode: "lines+markers", showlegend: false, name: `${a} forecast`,
      line: { color, width: 2, dash: "dot" }, marker: { size: 8 }, hovertemplate: mode === "idx" ? "%{y:.0f}" : "€%{y:,.0f}",
      error_y: { type: "data", symmetric: false, array: [0, (s.hi - s.f) * k], arrayminus: [0, (s.f - s.lo) * k], color, thickness: 1, width: 4 },
    });
    summary.push({ area: a, color, start: ys[0], s });
  }

  return (
    <>
      <PageHead title="Compare areas">Pick up to three areas. Dotted segments are 12-month forecasts with their ~80% range.</PageHead>
      <div className="controls">
        {areas.map((a, slot) => (
          <Select key={slot} label={`Area ${slot + 1}`} value={a} options={[NONE, ...locations]} onChange={(v) => setAreas(areas.map((x, j) => (j === slot ? v : x)))} />
        ))}
        <Select label="Bedrooms" value={beds} options={ordered(new Set(core.series.map((s) => s.beds)), BEDS_ORDER)} onChange={setBeds} />
        <Select label="Property type" value={type} options={ordered(new Set(core.series.map((s) => s.type)), TYPES_ORDER)} onChange={setType} />
        <Segmented label="Show" value={mode} onChange={setMode} options={[{ value: "eur", label: "€ per month" }, { value: "idx", label: "Indexed (start = 100)" }]} />
        <Select label="From" value={String(from)} options={["2008", "2012", "2015", "2018", "2020"]} onChange={(v) => setFrom(Number(v))} />
      </div>
      <Card>
        {traces.length ? (
          <Plot data={traces} height={460} ariaLabel="Rent comparison chart"
            layout={{ hovermode: "x unified", margin: { l: 10, r: 10, t: 30, b: 30 }, yaxis: { tickprefix: mode === "eur" ? "€" : "", showgrid: true } }} />
        ) : <p className="note">None of the chosen areas has data for {beds.toLowerCase()} / {type.toLowerCase()}.</p>}
        {picked.some((p) => p.a !== NONE && p.i == null) && (
          <p className="note">No data for: {picked.filter((p) => p.a !== NONE && p.i == null).map((p) => p.a).join(", ")} with this bedroom / type filter.</p>
        )}
      </Card>
      {summary.length > 0 && (
        <>
          <div className="spacer" />
          <Card>
            <div className="table-wrap">
              <table>
                <thead><tr><th>Area</th><th className="num">Rent {from}</th><th className="num">Latest</th><th className="num">Change</th><th className="num">Forecast +12m</th><th className="num">Growth</th></tr></thead>
                <tbody>
                  {summary.map(({ area, color, start, s }) => (
                    <tr key={area}>
                      <td><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 5, background: color, marginRight: 8 }} />{area}</td>
                      <td className="num">{euro(start)}</td><td className="num">{euro(s.rent)}</td><td className="num">{pct((s.rent / start - 1) * 100, 0)}</td>
                      <td className="num">{euro(s.f)}</td><td className="num">{pct(s.g)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </>
  );
}
