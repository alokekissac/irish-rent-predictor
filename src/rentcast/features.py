"""Leakage-safe feature engineering for 12-month-ahead rent forecasting.

Every row is a (series, origin quarter t). Features use only data observed at or before t;
the target is log(rent[t + horizon]) - log(rent[t]).
"""

import numpy as np
import pandas as pd

from rentcast.config import settings

SERIES_KEY = ["location", "beds", "property_type"]
CATEGORICAL = ["county", "level", "beds", "property_type", "location"]
NUMERIC = [
    "log_rent",
    "growth_1q",
    "growth_4q",
    "growth_8q",
    "volatility_8q",
    "n_obs_8q",
    "county_growth_4q",
    "national_growth_4q",
    "rel_to_county",
    "log_median_price",
    "price_growth_4q",
    "sales_growth_4q",
    "new_build_share",
    "gross_yield",
    "quarter_of_year",
]
FEATURES = CATEGORICAL + NUMERIC
TARGET = "target_growth"


def _full_grid(rents: pd.DataFrame) -> pd.DataFrame:
    """Reindex every series onto a contiguous quarterly grid so shifts are true time lags."""
    quarters = pd.period_range(rents["quarter"].min(), rents["quarter"].max(), freq="Q")
    meta = rents.drop_duplicates(SERIES_KEY)[SERIES_KEY + ["county", "level"]]
    grid = meta.merge(pd.DataFrame({"quarter": quarters}), how="cross")
    return grid.merge(rents[SERIES_KEY + ["quarter", "rent"]], on=SERIES_KEY + ["quarter"], how="left")


def build_features(rents: pd.DataFrame, market: pd.DataFrame, horizon: int | None = None) -> pd.DataFrame:
    horizon = horizon or settings.horizon_quarters
    rents = rents.assign(quarter=pd.PeriodIndex(rents["quarter"], freq="Q"))
    market = market.assign(quarter=pd.PeriodIndex(market["quarter"], freq="Q"))

    df = _full_grid(rents).sort_values(SERIES_KEY + ["quarter"]).reset_index(drop=True)
    df["log_rent"] = np.log(df["rent"])
    g = df.groupby(SERIES_KEY, sort=False)["log_rent"]
    for k in (1, 4, 8):
        df[f"growth_{k}q"] = df["log_rent"] - g.shift(k)
    df["volatility_8q"] = df.groupby(SERIES_KEY, sort=False)["growth_1q"].transform(
        lambda s: s.rolling(8, min_periods=3).std()
    )
    df["n_obs_8q"] = g.transform(lambda s: s.notna().rolling(8, min_periods=1).sum())
    df[TARGET] = g.shift(-horizon) - df["log_rent"]
    df["target_quarter"] = df["quarter"] + horizon

    # County headline series (all beds, all types) as a regional context signal
    head = df[
        (df["level"] == "county") & (df["beds"] == "All bedrooms") & (df["property_type"] == "All property types")
    ][["county", "quarter", "log_rent", "growth_4q"]].rename(
        columns={"log_rent": "county_log_rent", "growth_4q": "county_growth_4q"}
    )
    national = head.groupby("quarter")["county_growth_4q"].median().rename("national_growth_4q")
    df = df.merge(head, on=["county", "quarter"], how="left").merge(national, on="quarter", how="left")
    df["rel_to_county"] = df["log_rent"] - df["county_log_rent"]

    # Property Price Register signals
    df = df.merge(market, on=["county", "quarter"], how="left")
    df["log_median_price"] = np.log(df["median_price"])
    df["gross_yield"] = 12 * np.exp(df["county_log_rent"]) / df["median_price"]
    df["quarter_of_year"] = df["quarter"].dt.quarter

    df = df[df["log_rent"].notna()].reset_index(drop=True)
    return df[["quarter", "target_quarter", "rent", *FEATURES, TARGET]]


def to_model_frame(df: pd.DataFrame, categories: dict[str, list[str]] | None = None) -> pd.DataFrame:
    """Select model inputs with stable categorical encodings (shared by training and serving)."""
    X = df[FEATURES].copy()
    for col in CATEGORICAL:
        cats = categories[col] if categories else sorted(df[col].dropna().unique())
        X[col] = pd.Categorical(X[col], categories=cats)
    return X
