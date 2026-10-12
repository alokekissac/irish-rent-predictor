// County → area → bedrooms → property type pickers bound to the app-wide selected series.
import { useMemo } from "react";
import { BEDS_ORDER, TYPES_ORDER, ordered, seriesKey } from "../data";
import { useApp } from "../state";
import { Select } from "./ui";

export default function SeriesPicker() {
  const { core, sid, openSeries } = useApp();
  const s = core.series[sid];
  const counties = useMemo(() => [...new Set(core.series.map((x) => x.county))].sort(), [core]);

  const inCounty = core.series.filter((x) => x.county === s.county);
  const areas = [s.county, ...[...new Set(inCounty.map((x) => x.location))].filter((a) => a !== s.county).sort()];
  const inArea = core.series.filter((x) => x.location === s.location);
  const beds = ordered(new Set(inArea.map((x) => x.beds)), BEDS_ORDER);
  const types = ordered(new Set(inArea.filter((x) => x.beds === s.beds).map((x) => x.type)), TYPES_ORDER);

  // Keep the nearest valid series when a parent choice changes
  const pick = (location: string, bed: string, type: string) => {
    const exact = core.byKey.get(seriesKey({ location, beds: bed, type }));
    if (exact != null) return openSeries(exact);
    const sameBeds = core.series.findIndex((x) => x.location === location && x.beds === bed);
    if (sameBeds >= 0) return openSeries(sameBeds);
    const headline = core.series.findIndex((x) => x.location === location && x.beds === BEDS_ORDER[0] && x.type === TYPES_ORDER[0]);
    openSeries(headline >= 0 ? headline : core.series.findIndex((x) => x.location === location));
  };

  return (
    <div className="controls">
      <Select label="County" value={s.county} options={counties} onChange={(c) => pick(core.series.some((x) => x.location === c) ? c : core.series.find((x) => x.county === c)!.location, s.beds, s.type)} />
      <Select label="Area" value={s.location} options={areas.filter((a) => core.series.some((x) => x.location === a))} onChange={(a) => pick(a, s.beds, s.type)} />
      <Select label="Bedrooms" value={s.beds} options={beds} onChange={(b) => pick(s.location, b, s.type)} />
      <Select label="Property type" value={s.type} options={types} onChange={(t) => pick(s.location, s.beds, t)} />
    </div>
  );
}
