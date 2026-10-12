// Every series, filterable and rankable, with sparklines and CSV export.
import { useMemo, useState } from "react";
import { Card, PageHead, Segmented, Select } from "../components/ui";
import { ALL_BEDS, ALL_TYPES, BEDS_ORDER, LEVEL_LABEL, TYPES_ORDER, euro, ordered, pct } from "../data";
import { useApp } from "../state";

type Rank = "g" | "f" | "g12" | "cheap";
const PAGE = 100;

function Spark({ values }: { values: (number | null)[] }) {
  const pts = values.map((v, i) => [i, v] as const).filter((p): p is readonly [number, number] => p[1] != null);
  if (pts.length < 2) return null;
  const ys = pts.map((p) => p[1]);
  const [lo, hi] = [Math.min(...ys), Math.max(...ys)];
  const w = 96, h = 24, n = values.length - 1;
  const d = pts.map(([i, v], k) => `${k ? "L" : "M"}${((i / n) * w).toFixed(1)},${(h - 2 - ((v - lo) / (hi - lo || 1)) * (h - 4)).toFixed(1)}`).join("");
  return <svg className="spark" width={w} height={h} aria-hidden><path d={d} /></svg>;
}

export default function League() {
  const { core, openSeries } = useApp();
  const [county, setCounty] = useState("All counties");
  const [level, setLevel] = useState("district+town");
  const [beds, setBeds] = useState(ALL_BEDS);
  const [type, setType] = useState(ALL_TYPES);
  const [rank, setRank] = useState<Rank>("g");
  const [search, setSearch] = useState("");
  const [maxRent, setMaxRent] = useState(5000);
  const [limit, setLimit] = useState(PAGE);
  const since = core.meta.quarters.indexOf("2020Q1");

  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    const out = core.series.map((s, i) => ({ ...s, i })).filter((s) =>
      s.beds === beds && s.type === type && s.rent <= maxRent &&
      (county === "All counties" || s.county === county) &&
      (level === "all" || (level === "district+town" ? s.level !== "county" : s.level === level)) &&
      (!q || s.location.toLowerCase().includes(q)));
    const key: Record<Rank, (s: (typeof out)[number]) => number> = { g: (s) => -s.g, f: (s) => -s.f, g12: (s) => -(s.g12 ?? -999), cheap: (s) => s.rent };
    return out.sort((a, b) => key[rank](a) - key[rank](b));
  }, [core, beds, type, maxRent, county, level, search, rank]);

  const gMax = Math.max(1, ...rows.map((r) => r.g));
  const download = () => {
    const head = ["rank", "location", "county", "level", "beds", "property_type", "latest_quarter", "rent", "past_12m_growth_pct", "forecast_quarter", "forecast_rent", "lower", "upper", "forecast_growth_pct"];
    const esc = (v: unknown) => (typeof v === "string" && /[",]/.test(v) ? `"${v.replace(/"/g, '""')}"` : String(v ?? ""));
    const lines = rows.map((r, k) => [k + 1, r.location, r.county, r.level, r.beds, r.type, r.q, r.rent, r.g12, r.fq, r.f, r.lo, r.hi, r.g].map(esc).join(","));
    const url = URL.createObjectURL(new Blob([[head.join(","), ...lines].join("\n")], { type: "text/csv" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "rentcast_forecasts.csv" });
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <PageHead title="League table">Every RTB area, ranked by forecast. Click a row to open it in the explorer.</PageHead>
      <Card>
        <div className="controls" style={{ marginBottom: 0 }}>
          <Select label="County" value={county} options={["All counties", ...[...new Set(core.series.map((s) => s.county))].sort()]} onChange={(v) => { setCounty(v); setLimit(PAGE); }} />
          <Select label="Area type" value={level} options={["district+town", "town", "district", "county", "all"]} onChange={(v) => { setLevel(v); setLimit(PAGE); }}
            format={(v) => ({ "district+town": "Towns & districts", all: "Everything" } as Record<string, string>)[v] ?? LEVEL_LABEL[v]} />
          <Select label="Bedrooms" value={beds} options={ordered(new Set(core.series.map((s) => s.beds)), BEDS_ORDER)} onChange={setBeds} />
          <Select label="Property type" value={type} options={ordered(new Set(core.series.map((s) => s.type)), TYPES_ORDER)} onChange={setType} />
          <label className="field" style={{ minWidth: 180 }}>
            <span>Max current rent: <b>{euro(maxRent)}</b></span>
            <input type="range" min={600} max={5000} step={50} value={maxRent} onChange={(e) => setMaxRent(Number(e.target.value))} />
          </label>
          <Segmented label="Rank by" value={rank} onChange={setRank} options={[{ value: "g", label: "Growth" }, { value: "f", label: "Rent" }, { value: "g12", label: "Past 12m" }, { value: "cheap", label: "Cheapest" }]} />
          <label className="field">
            <span>Search</span>
            <input type="search" placeholder="e.g. Rathmines" value={search} onChange={(e) => { setSearch(e.target.value); setLimit(PAGE); }} />
          </label>
        </div>
      </Card>
      <div className="spacer" />
      <Card title={`${rows.length.toLocaleString()} areas`} actions={<button className="btn" onClick={download}>⬇ Download CSV</button>}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th className="num">#</th><th>Area</th><th>County</th><th>Rent since 2020</th><th className="num">Latest</th><th className="num">Past 12m</th><th className="num">Forecast +12m</th><th className="num">Forecast growth</th><th className="num">~80% range</th></tr>
            </thead>
            <tbody>
              {rows.slice(0, limit).map((r, k) => (
                <tr key={r.i} className="clickable" tabIndex={0} onClick={() => openSeries(r.i)} onKeyDown={(e) => e.key === "Enter" && openSeries(r.i)}>
                  <td className="num">{k + 1}</td><td>{r.location}</td><td>{r.county}</td>
                  <td><Spark values={core.history[r.i].slice(since)} /></td>
                  <td className="num">{euro(r.rent)}</td><td className="num">{pct(r.g12)}</td><td className="num">{euro(r.f)}</td>
                  <td className="num"><div className="bar-cell"><span className="bar" style={{ width: `${Math.max(0, (r.g / gMax) * 60)}px` }} />{pct(r.g)}</div></td>
                  <td className="num">{euro(r.lo)} – {euro(r.hi)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {rows.length > limit && <div style={{ textAlign: "center", marginTop: 12 }}><button className="btn" onClick={() => setLimit(limit + PAGE)}>Show {Math.min(PAGE, rows.length - limit)} more</button></div>}
      </Card>
    </>
  );
}
