// Types, loaders and formatting for the precomputed JSON exported by `rentcast.export_web`.
import { useEffect, useState } from "react";

export interface Series {
  location: string;
  county: string;
  level: "county" | "district" | "town";
  beds: string;
  type: string;
  q: string; // latest observed quarter
  fq: string; // forecast quarter
  rent: number;
  f: number;
  lo: number;
  hi: number;
  g: number; // forecast growth %
  g12: number | null; // past 12m growth %
  shap: number[]; // contribution to forecast growth, % points, aligned with meta.features
  obs: Record<string, number | null>;
}

export interface Meta {
  generated: string;
  data_through: string;
  horizon_quarters: number;
  n_series: number;
  quarters: string[];
  features: string[];
  base_value: number;
  scenario_features: string[];
  whatif_grid: number[];
  metrics: Record<string, number>;
  split: { valid_start: string; test_start: string };
}

/** Columnar backtest: one entry per 12-month-ahead forecast scored on the unseen test period. */
export interface Backtest {
  county_names: string[];
  level_names: string[];
  beds_names: string[];
  sid: number[]; // index into series.json, -1 if the series is no longer published
  county: number[];
  level: number[];
  beds: number[];
  tq: number[]; // index into meta.quarters
  actual: number[];
  pred: number[];
  lo: number[];
  hi: number[];
}

export interface Core {
  meta: Meta;
  series: Series[];
  history: (number | null)[][];
  geo: unknown;
  byKey: Map<string, number>;
}

const BASE = `${import.meta.env.BASE_URL}data/`;
const cache = new Map<string, Promise<unknown>>();
function load<T>(name: string): Promise<T> {
  if (!cache.has(name)) {
    cache.set(
      name,
      fetch(BASE + name).then((r) => {
        if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`);
        return r.json();
      }),
    );
  }
  return cache.get(name) as Promise<T>;
}

export const seriesKey = (s: { location: string; beds: string; type: string }) =>
  `${s.location}|${s.beds}|${s.type}`;

export async function loadCore(): Promise<Core> {
  const [meta, series, history, geo] = await Promise.all([
    load<Meta>("meta.json"),
    load<Series[]>("series.json"),
    load<(number | null)[][]>("history.json"),
    load<unknown>("counties.geojson"),
  ]);
  const byKey = new Map(series.map((s, i) => [seriesKey(s), i]));
  return { meta, series, history, geo, byKey };
}

export function useLazy<T>(name: string): T | null {
  const [value, setValue] = useState<T | null>(null);
  useEffect(() => {
    let live = true;
    load<T>(name).then((v) => live && setValue(v));
    return () => {
      live = false;
    };
  }, [name]);
  return value;
}

// ---------------------------------------------------------------- domain constants
export const ALL_BEDS = "All bedrooms";
export const ALL_TYPES = "All property types";
export const BEDS_ORDER = [ALL_BEDS, "One bed", "Two bed", "Three bed", "Four plus bed", "1 to 2 bed", "1 to 3 bed"];
export const TYPES_ORDER = [ALL_TYPES, "Apartment", "Terrace house", "Semi detached house", "Detached house", "Other flats"];
export const LEVEL_LABEL: Record<string, string> = {
  county: "County",
  district: "City / district",
  town: "Town / neighbourhood",
};

export const FEATURE_LABELS: Record<string, string> = {
  county_growth_4q: "County rent momentum (12m)",
  national_growth_4q: "National rent momentum (12m)",
  price_growth_4q: "House-price growth in county",
  growth_8q: "This area's 2-year growth",
  growth_4q: "This area's 12-month growth",
  growth_1q: "This area's last-quarter change",
  log_median_price: "County house-price level",
  log_rent: "Current rent level",
  location: "Area-specific effect",
  county: "County effect",
  rel_to_county: "Premium vs county average",
  sales_growth_4q: "Property sales volume growth",
  gross_yield: "Rental yield",
  new_build_share: "New-build share of sales",
  volatility_8q: "Rent volatility",
  n_obs_8q: "Data coverage",
  level: "Area type",
  beds: "Bedrooms",
  property_type: "Property type",
  quarter_of_year: "Season",
};

export function ordered(values: Iterable<string>, order: string[]): string[] {
  const set = new Set(values);
  return [...order.filter((v) => set.has(v)), ...[...set].filter((v) => !order.includes(v)).sort()];
}

// ---------------------------------------------------------------- formatting
export const euro = (x: number) => `€${Math.round(x).toLocaleString("en-IE")}`;
export const pct = (x: number | null | undefined, digits = 1) =>
  x == null || !Number.isFinite(x) ? "–" : `${x > 0 ? "+" : ""}${x.toFixed(digits)}%`;

export function shortArea(location: string, county: string): string {
  return location
    .replace(new RegExp(`,\\s*${county}$`), "")
    .replace(/\s*,\s*Dublin (\w+)$/, " (D$1)")
    .trim();
}

export const quarterToDate = (q: string) => {
  const year = Number(q.slice(0, 4));
  const quarter = Number(q.slice(5));
  return `${year}-${String(quarter * 3).padStart(2, "0")}-28`;
};

/** Linear interpolation on an increasing grid, clamped to its ends. */
export function interp(grid: number[], values: number[], x: number): number {
  if (x <= grid[0]) return values[0];
  if (x >= grid[grid.length - 1]) return values[values.length - 1];
  const i = grid.findIndex((g) => g >= x);
  const t = (x - grid[i - 1]) / (grid[i] - grid[i - 1]);
  return values[i - 1] + t * (values[i] - values[i - 1]);
}
