// App-wide selection (county + series) and hash routing, shared by every page.
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ALL_BEDS, ALL_TYPES, seriesKey, type Core } from "./data";

export type Route = "map" | "explorer" | "afford" | "compare" | "table" | "model";
export const ROUTES: { id: Route; label: string; icon: string }[] = [
  { id: "map", label: "Map", icon: "🗺️" },
  { id: "explorer", label: "Forecast explorer", icon: "🔎" },
  { id: "afford", label: "Where can I afford?", icon: "💶" },
  { id: "compare", label: "Compare", icon: "⚖️" },
  { id: "table", label: "League table", icon: "🏆" },
  { id: "model", label: "Model", icon: "📊" },
];

interface AppState {
  core: Core;
  route: Route;
  go: (r: Route) => void;
  county: string;
  setCounty: (c: string) => void;
  sid: number;
  openSeries: (sid: number) => void;
}

const Ctx = createContext<AppState | null>(null);
export const useApp = () => {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp outside provider");
  return v;
};

function parseHash(core: Core): { route: Route; sid: number | null } {
  const [path, query] = window.location.hash.replace(/^#\/?/, "").split("?");
  const route = (ROUTES.find((r) => r.id === path)?.id ?? "map") as Route;
  const s = new URLSearchParams(query ?? "").get("s");
  return { route, sid: s != null ? core.byKey.get(s) ?? null : null };
}

export function AppProvider({ core, children }: { core: Core; children: ReactNode }) {
  const dublin = core.byKey.get(`Dublin|${ALL_BEDS}|${ALL_TYPES}`) ?? 0;
  const initial = parseHash(core);
  const [route, setRoute] = useState<Route>(initial.route);
  const [sid, setSid] = useState<number>(initial.sid ?? dublin);
  const [county, setCounty] = useState<string>(core.series[initial.sid ?? dublin].county);

  useEffect(() => {
    const onHash = () => {
      const h = parseHash(core);
      setRoute(h.route);
      if (h.sid != null) {
        setSid(h.sid);
        setCounty(core.series[h.sid].county);
      }
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [core]);

  const go = useCallback(
    (r: Route) => {
      const q = r === "explorer" ? `?s=${encodeURIComponent(seriesKey(core.series[sid]))}` : "";
      window.location.hash = `/${r}${q}`;
      window.scrollTo({ top: 0 });
    },
    [core, sid],
  );

  const openSeries = useCallback(
    (i: number) => {
      setSid(i);
      setCounty(core.series[i].county);
      window.location.hash = `/explorer?s=${encodeURIComponent(seriesKey(core.series[i]))}`;
      window.scrollTo({ top: 0 });
    },
    [core],
  );

  const selectSeries = useCallback(
    (i: number) => {
      setSid(i);
      setCounty(core.series[i].county);
      if (route === "explorer") {
        history.replaceState(null, "", `#/explorer?s=${encodeURIComponent(seriesKey(core.series[i]))}`);
      }
    },
    [core, route],
  );

  return (
    <Ctx.Provider value={{ core, route, go, county, setCounty, sid, openSeries: route === "explorer" ? selectSeries : openSeries }}>
      {children}
    </Ctx.Provider>
  );
}
