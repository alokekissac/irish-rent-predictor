import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def toy_rents() -> pd.DataFrame:
    """Two series over 12 quarters with known 1%/quarter growth, plus the county headline series."""
    quarters = pd.period_range("2020Q1", periods=12, freq="Q").astype(str)
    rows = []
    for loc, beds, ptype, base in [
        ("Cork", "All bedrooms", "All property types", 1000.0),
        ("Bandon, Cork", "Two bed", "Apartment", 800.0),
    ]:
        for i, q in enumerate(quarters):
            rows.append(
                {
                    "quarter": q,
                    "beds": beds,
                    "property_type": ptype,
                    "location": loc,
                    "county": "Cork",
                    "level": "county" if loc == "Cork" else "town",
                    "rent": base * 1.01**i,
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def toy_market() -> pd.DataFrame:
    quarters = pd.period_range("2020Q1", periods=12, freq="Q").astype(str)
    return pd.DataFrame(
        {
            "county": "Cork",
            "quarter": quarters,
            "median_price": np.linspace(250_000, 300_000, 12),
            "n_sales": 500,
            "new_build_share": 0.2,
            "price_growth_4q": 0.05,
            "sales_growth_4q": 0.0,
        }
    )
