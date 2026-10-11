"""Shared data loaders, palette and helpers for the RentCast dashboard."""

import json
import os
from pathlib import Path

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from rentcast.config import settings
from rentcast.predict import Forecaster, get_forecaster

ASSETS = Path(__file__).parent / "assets"
ALL_BEDS, ALL_TYPES = "All bedrooms", "All property types"
BEDS_ORDER = [ALL_BEDS, "One bed", "Two bed", "Three bed", "Four plus bed", "1 to 2 bed", "1 to 3 bed"]
TYPES_ORDER = [ALL_TYPES, "Apartment", "Terrace house", "Semi detached house", "Detached house", "Other flats"]

# Palette: categorical slots 1-3 (validated all-pairs), one-hue sequential ramps, blue<->red diverging
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
BLUE = "#2a78d6"
BAND = "rgba(42,120,214,0.18)"
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SEQ_ORANGE = ["#fde3d6", "#f9c1a6", "#f49a74", "#eb6834", "#c94f1f", "#9c3b15", "#6e290e"]
DIVERGING = ["#184f95", "#6da7ec", "#f0efec", "#f08a89", "#b8302f"]

FEATURE_LABELS = {
    "county_growth_4q": "County rent momentum (12m)",
    "national_growth_4q": "National rent momentum (12m)",
    "price_growth_4q": "House-price growth in county",
    "growth_8q": "This area's 2-year growth",
    "growth_4q": "This area's 12-month growth",
    "growth_1q": "This area's last-quarter change",
    "log_median_price": "County house-price level",
    "log_rent": "Current rent level",
    "location": "Area-specific effect",
    "county": "County effect",
    "rel_to_county": "Premium vs county average",
    "sales_growth_4q": "Property sales volume growth",
    "gross_yield": "Rental yield",
    "new_build_share": "New-build share of sales",
    "volatility_8q": "Rent volatility",
    "n_obs_8q": "Data coverage",
    "level": "Area type",
    "beds": "Bedrooms",
    "property_type": "Property type",
    "quarter_of_year": "Season",
}


@st.cache_resource
def forecaster() -> Forecaster:
    return get_forecaster()


@st.cache_data
def history() -> pd.DataFrame:
    df = pd.read_parquet(settings.processed_dir / "rents.parquet")
    df["date"] = pd.PeriodIndex(df["quarter"], freq="Q").to_timestamp(how="end").normalize()
    return df


@st.cache_data
def forecasts() -> pd.DataFrame:
    df = forecaster().forecast_all()
    df["forecast_quarter"] = df["target_quarter"]
    df["growth_12m_pct"] = (np.exp(df["growth_4q"]) - 1) * 100
    return df


@st.cache_data
def backtest() -> pd.DataFrame:
    path = settings.reports_dir / "backtest.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


@st.cache_data
def counties_geojson() -> dict:
    return json.loads((ASSETS / "ireland_counties.geojson").read_text())


def ordered(values, order: list[str]) -> list[str]:
    values = set(values)
    return [v for v in order if v in values] + sorted(values - set(order))


def synced_select(label: str, options: list, state_key: str, **kwargs):
    """Selectbox whose value lives in session_state[state_key], so pages and map clicks share it."""
    current = st.session_state.get(state_key)
    index = options.index(current) if current in options else 0
    value = st.selectbox(label, options, index=index, **kwargs)
    st.session_state[state_key] = value
    return value


def select_series(prefix: str = "") -> tuple[str, str, str, str]:
    """County → area → bedrooms → type pickers, shared across pages via session state."""
    fc = forecaster()
    locs = fc.locations()
    c1, c2, c3, c4 = st.columns(4)
    counties = sorted(locs["county"].unique())
    st.session_state.setdefault("sel_county", "Dublin")
    with c1:
        county = synced_select(f"{prefix}County", counties, "sel_county")
    area_options = locs[locs["county"] == county]["location"].tolist()
    area_options = [county] + [a for a in area_options if a != county] if county in area_options else area_options
    with c2:
        location = synced_select(f"{prefix}Area", area_options, "sel_location")
    opts = fc.options(location)
    with c3:
        beds = synced_select(f"{prefix}Bedrooms", ordered(opts["beds"].unique(), BEDS_ORDER), "sel_beds")
    with c4:
        types = ordered(opts[opts["beds"] == beds]["property_type"].unique(), TYPES_ORDER)
        ptype = synced_select(f"{prefix}Property type", types, "sel_ptype")
    return county, location, beds, ptype


def style(fig: go.Figure, height: int = 420, y_title: str = "", hover: str = "x unified") -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode=hover,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        yaxis_title=y_title,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)", zeroline=False)
    return fig


def choropleth(
    df: pd.DataFrame,
    value: str,
    colorscale,
    title: str,
    hover: str,
    fmt: str,
    zmid: float | None = None,
    height: int = 620,
    selected: str | None = None,
) -> go.Figure:
    """County choropleth; `selected` gets a heavier outline so the clicked county stays visible."""
    fig = go.Figure(
        go.Choropleth(
            geojson=counties_geojson(),
            locations=df["county"],
            featureidkey="id",
            z=df[value],
            colorscale=colorscale,
            zmid=zmid,
            customdata=df[["county"]],
            marker_line_color="rgba(255,255,255,0.9)",
            marker_line_width=0.8,
            colorbar=dict(title=title, tickformat=fmt, thickness=12, len=0.6),
            hovertemplate=hover + "<extra></extra>",
        )
    )
    if selected and selected in set(df["county"]):
        sel = df[df["county"] == selected]
        fig.add_trace(
            go.Choropleth(
                geojson=counties_geojson(),
                locations=sel["county"],
                featureidkey="id",
                z=[0],
                colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
                showscale=False,
                marker_line_color="#0b0b0b",
                marker_line_width=1.8,
                hoverinfo="skip",
            )
        )
    fit_ireland(fig)
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        clickmode="event+select",
        dragmode=False,
    )
    return fig


def fit_ireland(fig: go.Figure) -> go.Figure:
    """Mercator view framed tightly on Ireland (plotly's default world projection leaves it tiny)."""
    fig.update_geos(
        visible=False,
        bgcolor="rgba(0,0,0,0)",
        projection_type="mercator",
        lonaxis_range=[-10.7, -5.9],
        lataxis_range=[51.35, 55.45],
    )
    return fig


def clicked_county(event) -> str | None:
    try:
        points = event.selection.points
    except AttributeError:
        return None
    for p in points or []:
        loc = p.get("location") or (p.get("customdata") or [None])[0]
        if loc:
            return loc
    return None


def euro(x: float) -> str:
    return f"€{x:,.0f}"


def pct(x: float, sign: bool = True) -> str:
    return f"{x:+.1f}%" if sign else f"{x:.1f}%"


def open_page(name: str) -> None:
    st.switch_page(st.session_state["pages"][name])


def short_area(locations: pd.Series, county: str) -> pd.Series:
    """'Bandon, Cork' -> 'Bandon'; 'Clonliffe, Dublin 3' -> 'Clonliffe (D3)'."""
    return (
        locations.str.replace(rf",\s*{county}$", "", regex=True)
        .str.replace(r"\s*,\s*Dublin (\w+)$", r" (D\1)", regex=True)
        .str.strip()
    )
