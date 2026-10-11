"""Clean raw RTB rents and PPR sales into tidy, model-ready tables."""

import logging

import numpy as np
import pandas as pd

from rentcast.config import settings

log = logging.getLogger(__name__)

COUNTIES = [
    "Carlow",
    "Cavan",
    "Clare",
    "Cork",
    "Donegal",
    "Dublin",
    "Galway",
    "Kerry",
    "Kildare",
    "Kilkenny",
    "Laois",
    "Leitrim",
    "Limerick",
    "Longford",
    "Louth",
    "Mayo",
    "Meath",
    "Monaghan",
    "Offaly",
    "Roscommon",
    "Sligo",
    "Tipperary",
    "Waterford",
    "Westmeath",
    "Wexford",
    "Wicklow",
]


def location_county(location: str) -> tuple[str, str]:
    """Map an RTB location label to (county, level).

    Labels look like "Cork" (county), "Cork City" / "Dublin 6W" (district), or
    "Bandon, Cork" / "Clondalkin, Dublin 22" (town).
    """
    if location in COUNTIES:
        return location, "county"
    if "," in location:
        # Suffix is a county or a Dublin postal district ("Clondalkin, Dublin 22")
        return location.rsplit(",", 1)[1].strip().split(" ", 1)[0], "town"
    head = location.split(" ", 1)[0]
    if head in COUNTIES:
        return head, "district"
    raise ValueError(f"Cannot map RTB location to a county: {location!r}")


def clean_rents(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.rename(
        columns={
            "Quarter": "quarter",
            "Number of Bedrooms": "beds",
            "Property Type": "property_type",
            "Location": "location",
            "value": "rent",
        }
    )[["quarter", "beds", "property_type", "location", "rent"]]
    df = df[df["rent"] > 0].copy()
    df["quarter"] = pd.PeriodIndex(df["quarter"], freq="Q")
    mapping = {loc: location_county(loc) for loc in df["location"].unique()}
    df["county"] = df["location"].map(lambda loc: mapping[loc][0])
    df["level"] = df["location"].map(lambda loc: mapping[loc][1])
    unknown = set(df["county"]) - set(COUNTIES)
    if unknown:
        raise ValueError(f"Unknown counties in RTB data: {unknown}")
    return df.sort_values(["location", "beds", "property_type", "quarter"]).reset_index(drop=True)


def clean_sales(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["date"] = pd.to_datetime(df["date_of_sale"], format="%d/%m/%Y", errors="coerce")
    df["price"] = pd.to_numeric(df["price"].str.replace(r"[^0-9.]", "", regex=True), errors="coerce")
    df["new_build"] = df["description"].str.contains("New|Nua", na=False)
    df = df[
        df["date"].notna()
        & df["county"].isin(COUNTIES)
        & (df["not_full_market_price"] == "No")
        & df["price"].between(10_000, 20_000_000)
    ]
    df["quarter"] = df["date"].dt.to_period("Q")
    return df[["quarter", "county", "price", "new_build"]].reset_index(drop=True)


def county_market(sales: pd.DataFrame) -> pd.DataFrame:
    """Quarterly county-level housing-market signals from the Property Price Register."""
    agg = (
        sales.groupby(["county", "quarter"])
        .agg(median_price=("price", "median"), n_sales=("price", "size"), new_build_share=("new_build", "mean"))
        .reset_index()
        .sort_values(["county", "quarter"])
    )
    g = agg.groupby("county")
    agg["price_growth_4q"] = np.log(agg["median_price"]) - np.log(g["median_price"].shift(4))
    agg["sales_growth_4q"] = np.log(agg["n_sales"]) - np.log(g["n_sales"].shift(4))
    return agg


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    out = settings.processed_dir
    out.mkdir(parents=True, exist_ok=True)

    rents = clean_rents(pd.read_parquet(settings.raw_dir / "rtb_rents.parquet"))
    sales = clean_sales(pd.read_parquet(settings.raw_dir / "ppr.parquet"))
    market = county_market(sales)

    rents.assign(quarter=rents["quarter"].astype(str)).to_parquet(out / "rents.parquet", index=False)
    market.assign(quarter=market["quarter"].astype(str)).to_parquet(out / "county_market.parquet", index=False)
    log.info(
        "rents: %d rows, %d series, %s..%s",
        len(rents),
        rents.groupby(["location", "beds", "property_type"]).ngroups,
        rents["quarter"].min(),
        rents["quarter"].max(),
    )
    log.info("sales: %d valid sales -> %d county-quarters", len(sales), len(market))


if __name__ == "__main__":
    main()
