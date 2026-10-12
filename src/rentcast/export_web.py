"""Export forecasts, history, SHAP breakdowns, what-if grids and backtests as JSON for the static web app.

The web app (web/) has no server: everything it shows is precomputed here after training.
What-if sliders use per-series ICE curves: the model is re-run on a grid of values for each scenario
feature, so moving one slider is exact; combined moves are summed (an additive approximation).
"""

import json
import logging
import shutil
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from rentcast.config import ROOT, settings
from rentcast.features import FEATURES, SERIES_KEY
from rentcast.predict import Forecaster

log = logging.getLogger(__name__)

OUT = ROOT / "web" / "public" / "data"
GEOJSON = ROOT / "dashboard" / "assets" / "ireland_counties.geojson"
SCENARIO_FEATURES = ["growth_4q", "county_growth_4q", "national_growth_4q", "price_growth_4q"]
WHATIF_GRID_PCT = np.arange(-10.0, 25.01, 2.5)  # slider positions, % growth over 12 months


def _r(x: float | None, nd: int = 0) -> float | int | None:
    if x is None or not np.isfinite(x):
        return None
    return round(float(x), nd) if nd else round(float(x))


def _pct(log_growth: float) -> float | None:
    return _r(np.expm1(log_growth) * 100, 2) if pd.notna(log_growth) else None


def _dump(name: str, obj) -> None:
    path = OUT / name
    path.write_text(json.dumps(obj, separators=(",", ":"), allow_nan=False))
    log.info("%-18s %6.0f KB", name, path.stat().st_size / 1024)


def build(fc: Forecaster) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    latest = fc.latest.reset_index(drop=True)
    preds = fc.predict_frame(latest)
    shap = fc.explain(latest)
    base_value = float(shap.pop("base_value").iloc[0])

    rents = pd.read_parquet(settings.processed_dir / "rents.parquet")
    quarters = [str(q) for q in pd.period_range(rents["quarter"].min(), rents["quarter"].max(), freq="Q")]
    qidx = {q: i for i, q in enumerate(quarters)}
    sid = {tuple(k): i for i, k in enumerate(latest[SERIES_KEY].itertuples(index=False, name=None))}

    # ---- series: latest forecast + SHAP + observed scenario values
    series = []
    for i, row in preds.iterrows():
        series.append(
            {
                "location": row["location"],
                "county": row["county"],
                "level": row["level"],
                "beds": row["beds"],
                "type": row["property_type"],
                "q": row["quarter"],
                "fq": row["target_quarter"],
                "rent": _r(row["rent"], 2),
                "f": _r(row["forecast_rent"], 2),
                "lo": _r(row["lower_rent"], 2),
                "hi": _r(row["upper_rent"], 2),
                "g": _r(row["growth_pct"], 2),
                "g12": _pct(row["growth_4q"]),
                "shap": [_r(v * 100, 3) for v in shap.iloc[i].to_numpy()],
                "obs": {f: _pct(row[f]) for f in SCENARIO_FEATURES},
            }
        )

    # ---- history: one aligned array per series (null where RTB suppressed the quarter)
    hist = np.full((len(latest), len(quarters)), np.nan)
    keyed = rents.assign(i=[sid.get(k) for k in rents[SERIES_KEY].itertuples(index=False, name=None)])
    keyed = keyed[keyed["i"].notna()]
    hist[keyed["i"].astype(int).to_numpy(), keyed["quarter"].map(qidx).to_numpy()] = keyed["rent"].to_numpy()
    history = [[_r(v) for v in row] for row in hist]

    # ---- what-if ICE grids: forecast growth % for each scenario feature at each grid value
    grid_log = np.log1p(WHATIF_GRID_PCT / 100)
    whatif = {}
    for feat in SCENARIO_FEATURES:
        block = pd.concat([latest.assign(**{feat: v}) for v in grid_log], ignore_index=True)
        if feat == "growth_4q":  # keep the 2-year growth consistent with the edited 1-year growth
            block["growth_8q"] = np.tile(latest["growth_8q"] - latest["growth_4q"], len(grid_log)) + block[feat]
        g = fc.predict_frame(block)["growth_pct"].to_numpy().reshape(len(grid_log), len(latest)).T
        whatif[feat] = np.round(g, 2).tolist()

    # ---- backtest, columnar
    bt = pd.read_parquet(settings.reports_dir / "backtest.parquet")
    counties = sorted(rents["county"].unique())
    levels = ["county", "district", "town"]
    beds = sorted(rents["beds"].unique())
    backtest = {
        "county_names": counties,
        "level_names": levels,
        "beds_names": beds,
        "sid": [sid.get(k, -1) for k in bt[SERIES_KEY].itertuples(index=False, name=None)],
        "county": bt["county"].map({c: i for i, c in enumerate(counties)}).tolist(),
        "level": bt["level"].map({c: i for i, c in enumerate(levels)}).tolist(),
        "beds": bt["beds"].map({c: i for i, c in enumerate(beds)}).tolist(),
        "tq": bt["target_quarter"].map(qidx).tolist(),
        "actual": [_r(v) for v in bt["actual_rent"]],
        "pred": [_r(v) for v in bt["pred_rent"]],
        "lo": [_r(v) for v in bt["lower_rent"]],
        "hi": [_r(v) for v in bt["upper_rent"]],
    }

    info = fc.info
    meta = {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "data_through": info["data_through"],
        "horizon_quarters": info["horizon_quarters"],
        "n_series": len(series),
        "quarters": quarters,
        "features": FEATURES,
        "base_value": base_value * 100,
        "scenario_features": SCENARIO_FEATURES,
        "whatif_grid": WHATIF_GRID_PCT.tolist(),
        "metrics": {k: round(v, 4) for k, v in info["metrics"].items()},
        "split": {"valid_start": settings.valid_start, "test_start": settings.test_start},
    }

    _dump("meta.json", meta)
    _dump("series.json", series)
    _dump("history.json", history)
    _dump("whatif.json", whatif)
    _dump("backtest.json", backtest)
    shutil.copy(GEOJSON, OUT / "counties.geojson")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    build(Forecaster())


if __name__ == "__main__":
    main()
