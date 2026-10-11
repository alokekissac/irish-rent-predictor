"""Load the trained bundle and produce 12-month rent forecasts for any RTB series."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from rentcast.config import settings
from rentcast.features import to_model_frame


class UnknownSeriesError(LookupError):
    pass


@dataclass(frozen=True)
class Forecast:
    location: str
    county: str
    beds: str
    property_type: str
    current_quarter: str
    current_rent: float
    forecast_quarter: str
    forecast_rent: float
    lower_rent: float
    upper_rent: float
    growth_pct: float


class Forecaster:
    def __init__(self, model_dir: Path | None = None):
        model_dir = model_dir or settings.model_dir
        self.bundle = joblib.load(model_dir / "rent_model.joblib")
        self.latest = pd.read_parquet(model_dir / "latest_features.parquet")
        self._index = self.latest.set_index(["location", "beds", "property_type"]).index

    @property
    def info(self) -> dict:
        b = self.bundle
        return {
            "data_through": b["data_through"],
            "horizon_quarters": b["horizon_quarters"],
            "metrics": b["metrics"],
            "n_series": len(self.latest),
        }

    def locations(self) -> pd.DataFrame:
        return self.latest[["location", "county", "level"]].drop_duplicates().sort_values(["county", "location"])

    def options(self, location: str) -> pd.DataFrame:
        rows = self.latest[self.latest["location"] == location]
        if rows.empty:
            raise UnknownSeriesError(f"Unknown location: {location}")
        return rows[["beds", "property_type", "rent"]]

    def predict_frame(self, rows: pd.DataFrame) -> pd.DataFrame:
        X = to_model_frame(rows, self.bundle["categories"])
        pad = self.bundle["conformal_pad"]
        lo_q, hi_q = sorted(self.bundle["quantiles"])
        point = self.bundle["point"].predict(X)
        lo = np.minimum(self.bundle["quantiles"][lo_q].predict(X) - pad, point)
        hi = np.maximum(self.bundle["quantiles"][hi_q].predict(X) + pad, point)
        rent = rows["rent"].to_numpy()
        return rows.assign(
            forecast_rent=rent * np.exp(point),
            lower_rent=rent * np.exp(lo),
            upper_rent=rent * np.exp(hi),
            growth_pct=(np.exp(point) - 1) * 100,
        )

    def forecast(
        self, location: str, beds: str = "All bedrooms", property_type: str = "All property types"
    ) -> Forecast:
        key = (location, beds, property_type)
        if key not in self._index:
            raise UnknownSeriesError(f"No RTB data for {property_type} / {beds} in {location}")
        row = self.predict_frame(self.latest.iloc[[self._index.get_loc(key)]]).iloc[0]
        return Forecast(
            location=location,
            county=row["county"],
            beds=beds,
            property_type=property_type,
            current_quarter=row["quarter"],
            current_rent=round(float(row["rent"]), 2),
            forecast_quarter=row["target_quarter"],
            forecast_rent=round(float(row["forecast_rent"]), 2),
            lower_rent=round(float(row["lower_rent"]), 2),
            upper_rent=round(float(row["upper_rent"]), 2),
            growth_pct=round(float(row["growth_pct"]), 2),
        )

    def forecast_all(self) -> pd.DataFrame:
        return self.predict_frame(self.latest)


@lru_cache(maxsize=1)
def get_forecaster() -> Forecaster:
    return Forecaster()
