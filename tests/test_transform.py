import pandas as pd
import pytest

from rentcast.data.transform import clean_sales, location_county


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("Cork", ("Cork", "county")),
        ("Cork City", ("Cork", "district")),
        ("Dublin 6W", ("Dublin", "district")),
        ("Bandon, Cork", ("Cork", "town")),
        ("Clondalkin, Dublin 22", ("Dublin", "town")),
        ("Kilmainham , Dublin 8", ("Dublin", "town")),
    ],
)
def test_location_county(label, expected):
    assert location_county(label) == expected


def test_location_county_rejects_unknown():
    with pytest.raises(ValueError):
        location_county("Atlantis")


def test_clean_sales_parses_euro_prices_and_filters():
    raw = pd.DataFrame(
        {
            "date_of_sale": ["01/02/2024", "01/02/2024", "31/12/2024"],
            "county": ["Galway", "Galway", "Galway"],
            "price": ["\x80350,000.00", "\x80120,000.00", "\x80500.00"],
            "not_full_market_price": ["No", "Yes", "No"],
            "description": ["New Dwelling house /Apartment"] * 3,
        }
    )
    out = clean_sales(raw)
    assert out["price"].tolist() == [350_000.0]
    assert out["new_build"].tolist() == [True]
    assert str(out["quarter"].iloc[0]) == "2024Q1"
