import { useEffect, useState } from "react";
import { loadCore, type Core } from "./data";
import Afford from "./pages/Afford";
import Compare from "./pages/Compare";
import Explorer from "./pages/Explorer";
import League from "./pages/League";
import MapPage from "./pages/MapPage";
import ModelPage from "./pages/ModelPage";
import { AppProvider, ROUTES, useApp } from "./state";
import { THEMES, ThemeContext, type ThemeName } from "./theme";

const REPO = "https://github.com/alokekissac/irish-rent-predictor";

function systemTheme(): ThemeName {
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function storedTheme(): ThemeName | null {
  try {
    const v = localStorage.getItem("theme");
    return v === "light" || v === "dark" ? v : null;
  } catch {
    return null;
  }
}

function useTheme(): [ThemeName, () => void] {
  const [override, setOverride] = useState<ThemeName | null>(storedTheme);
  const [system, setSystem] = useState<ThemeName>(systemTheme);
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const on = () => setSystem(systemTheme());
    mq?.addEventListener("change", on);
    return () => mq?.removeEventListener("change", on);
  }, []);
  const theme = override ?? system;
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    setOverride(next);
    try {
      localStorage.setItem("theme", next);
    } catch {
      /* storage unavailable: theme still switches for this visit */
    }
  };
  return [theme, toggle];
}

function Shell({ theme, toggle }: { theme: ThemeName; toggle: () => void }) {
  const { route, go, core } = useApp();
  const Page = { map: MapPage, explorer: Explorer, afford: Afford, compare: Compare, table: League, model: ModelPage }[route];
  return (
    <>
      <header className="topbar">
        <a className="brand" href="#/map">
          <span aria-hidden>🏠</span> RentCast <span className="brand-sub">Ireland</span>
        </a>
        <nav aria-label="Pages">
          {ROUTES.map((r) => (
            <button key={r.id} className={route === r.id ? "active" : ""} aria-current={route === r.id ? "page" : undefined} onClick={() => go(r.id)}>
              <span aria-hidden>{r.icon}</span> <span className="nav-label">{r.label}</span>
            </button>
          ))}
        </nav>
        <button className="icon-btn" onClick={toggle} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`} title="Toggle theme">
          {theme === "dark" ? "☀️" : "🌙"}
        </button>
      </header>
      <main>
        <Page />
      </main>
      <footer>
        <p>
          Data through <b>{core.meta.data_through}</b>: RTB Rent Index via CSO (RIQ02), Residential Property Price Register,
          Tailte Éireann county boundaries (CC BY 4.0). Forecasts are model estimates, not financial advice.
        </p>
        <p>
          <a href={REPO}>Source code &amp; methodology on GitHub</a> · LightGBM + conformal intervals · SHAP explanations
        </p>
      </footer>
    </>
  );
}

export default function App() {
  const [theme, toggle] = useTheme();
  const [core, setCore] = useState<Core | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    loadCore().then(setCore).catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="splash">Couldn't load data: {error}</div>;
  if (!core)
    return (
      <div className="splash">
        <div className="spinner" aria-hidden /> Loading 3,000+ rent forecasts…
      </div>
    );
  return (
    <ThemeContext.Provider value={THEMES[theme]}>
      <AppProvider core={core}>
        <Shell theme={theme} toggle={toggle} />
      </AppProvider>
    </ThemeContext.Provider>
  );
}
