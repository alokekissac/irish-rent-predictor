"""Streamlit dashboard: explore Irish rents and 12-month forecasts."""

import json
import os

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from rentcast.config import settings
from rentcast.predict import get_forecaster

SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # categorical slots 1-3 (validated all-pairs)
BAND = "rgba(42,120,214,0.18)"
ALL_BEDS, ALL_TYPES = "All bedrooms", "All property types"

st.set_page_config(page_title="RentCast Ireland", page_icon="🏠", layout="wide")


@st.cache_data
def load_history() -> pd.DataFrame:
    df = pd.read_parquet(settings.processed_dir / "rents.parquet")
    df["date"] = pd.PeriodIndex(df["quarter"], freq="Q").to_timestamp(how="end").normalize()
    return df


@st.cache_data
def load_forecasts() -> pd.DataFrame:
    return get_forecaster().forecast_all()


def style(fig: go.Figure, height: int = 420, y_title: str = "") -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        yaxis_title=y_title,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,0.15)", zeroline=False)
    return fig


def euro(x: float) -> str:
    return f"€{x:,.0f}"


history, forecasts = load_history(), load_forecasts()
fc = get_forecaster()
info = fc.info
metrics = info["metrics"]

st.title("🏠 RentCast Ireland")
st.caption(
    f"12-month rent forecasts for {info['n_series']:,} RTB rent series · data through {info['data_through']} · "
    "Sources: RTB Rent Index via CSO PxStat (RIQ02), Property Price Register"
)

tab_overview, tab_explore, tab_compare, tab_model = st.tabs(
    ["National overview", "Forecast explorer", "Compare areas", "Model performance"]
)

# ---------------------------------------------------------------- overview
with tab_overview:
    headline = forecasts[(forecasts["beds"] == ALL_BEDS) & (forecasts["property_type"] == ALL_TYPES)]
    counties = headline[headline["level"] == "county"].sort_values("growth_pct")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Median county forecast growth", f"{counties['growth_pct'].median():+.1f}%")
    top = counties.sort_values("forecast_rent").iloc[-1]
    c2.metric("Highest forecast rent", euro(top["forecast_rent"]), top["county"], delta_color="off")
    c3.metric(
        "Fastest rising county",
        f"{counties.iloc[-1]['growth_pct']:+.1f}%",
        counties.iloc[-1]["county"],
        delta_color="off",
    )
    c4.metric(
        "Backtest error (MAPE)",
        f"{metrics['test_lgbm_mape_pct']:.1f}%",
        f"{metrics['test_lgbm_mape_pct'] - metrics['test_naive_mape_pct']:+.1f} pts vs naive",
        delta_color="inverse",
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Forecast 12-month rent growth by county")
        fig = go.Figure(
            go.Bar(
                x=counties["growth_pct"],
                y=counties["county"],
                orientation="h",
                marker_color=SERIES[0],
                customdata=counties[["rent", "forecast_rent"]],
                hovertemplate="<b>%{y}</b><br>Growth %{x:+.1f}%<br>Now €%{customdata[0]:,.0f} → "
                "€%{customdata[1]:,.0f}<extra></extra>",
            )
        )
        st.plotly_chart(
            style(fig, 700).update_layout(hovermode="closest", xaxis_title="Forecast growth (%)"),
            use_container_width=True,
        )
    with right:
        st.subheader("Average monthly rent, now vs forecast")
        by_rent = counties.sort_values("forecast_rent")
        fig = go.Figure(
            [
                go.Bar(
                    x=by_rent["rent"],
                    y=by_rent["county"],
                    orientation="h",
                    name="Latest (RTB)",
                    marker_color="#86b6ef",
                    hovertemplate="%{y}: €%{x:,.0f}<extra>Latest</extra>",
                ),
                go.Bar(
                    x=by_rent["forecast_rent"],
                    y=by_rent["county"],
                    orientation="h",
                    name="Forecast +12m",
                    marker_color=SERIES[0],
                    hovertemplate="%{y}: €%{x:,.0f}<extra>Forecast</extra>",
                ),
            ]
        )
        st.plotly_chart(
            style(fig, 700).update_layout(
                barmode="group", bargap=0.25, bargroupgap=0.1, hovermode="closest", xaxis_title="€ per month"
            ),
            use_container_width=True,
        )

    with st.expander("Table view"):
        st.dataframe(
            counties[
                [
                    "county",
                    "quarter",
                    "rent",
                    "target_quarter",
                    "forecast_rent",
                    "lower_rent",
                    "upper_rent",
                    "growth_pct",
                ]
            ]
            .rename(columns={"quarter": "latest_quarter", "target_quarter": "forecast_quarter"})
            .sort_values("growth_pct", ascending=False)
            .round(1),
            hide_index=True,
            use_container_width=True,
        )

# ---------------------------------------------------------------- explorer
with tab_explore:
    locs = fc.locations()
    f1, f2, f3, f4 = st.columns(4)
    county = f1.selectbox(
        "County", sorted(locs["county"].unique()), index=sorted(locs["county"].unique()).index("Dublin")
    )
    county_locs = locs[locs["county"] == county]["location"].tolist()
    location = f2.selectbox("Area", county_locs, index=county_locs.index(county) if county in county_locs else 0)
    opts = fc.options(location)
    beds_opts = sorted(opts["beds"].unique(), key=lambda b: (b != ALL_BEDS, b))
    beds = f3.selectbox("Bedrooms", beds_opts)
    type_opts = sorted(opts[opts["beds"] == beds]["property_type"].unique(), key=lambda t: (t != ALL_TYPES, t))
    ptype = f4.selectbox("Property type", type_opts)

    result = fc.forecast(location, beds, ptype)
    m1, m2, m3 = st.columns(3)
    m1.metric(f"Latest rent ({result.current_quarter})", euro(result.current_rent))
    m2.metric(
        f"Forecast ({result.forecast_quarter})",
        euro(result.forecast_rent),
        f"{result.growth_pct:+.1f}%",
        delta_color="inverse",
    )
    m3.metric("~80% range", f"{euro(result.lower_rent)} – {euro(result.upper_rent)}")

    hist = history[(history["location"] == location) & (history["beds"] == beds) & (history["property_type"] == ptype)]
    last_date = hist["date"].max()
    fdate = pd.Period(result.forecast_quarter, freq="Q").to_timestamp(how="end").normalize()
    fig = go.Figure(
        [
            go.Scatter(
                x=[last_date, fdate, fdate, last_date],
                y=[result.current_rent, result.upper_rent, result.lower_rent, result.current_rent],
                fill="toself",
                fillcolor=BAND,
                line=dict(width=0),
                name="~80% interval",
                hoverinfo="skip",
            ),
            go.Scatter(
                x=hist["date"],
                y=hist["rent"],
                name="RTB average rent",
                line=dict(color=SERIES[0], width=2),
                hovertemplate="€%{y:,.0f}",
            ),
            go.Scatter(
                x=[last_date, fdate],
                y=[result.current_rent, result.forecast_rent],
                name="Forecast",
                line=dict(color=SERIES[0], width=2, dash="dot"),
                marker=dict(size=9),
                mode="lines+markers",
                hovertemplate="€%{y:,.0f}",
            ),
        ]
    )
    st.plotly_chart(style(fig, y_title="€ per month"), use_container_width=True)
    st.caption(
        "RTB figures are averages of new tenancies registered in each quarter. "
        "Gaps mean the RTB suppressed the quarter (too few tenancies)."
    )

# ---------------------------------------------------------------- compare
with tab_compare:
    all_locs = locs["location"].tolist()
    defaults = [x for x in ["Dublin", "Cork", "Galway"] if x in all_locs]
    chosen = st.multiselect(
        "Choose up to 3 areas (all bedrooms, all property types)", all_locs, default=defaults, max_selections=3
    )
    fig = go.Figure()
    for colour, loc in zip(SERIES, chosen, strict=False):
        h = history[
            (history["location"] == loc) & (history["beds"] == ALL_BEDS) & (history["property_type"] == ALL_TYPES)
        ]
        fig.add_scatter(
            x=h["date"], y=h["rent"], name=loc, line=dict(color=colour, width=2), hovertemplate="€%{y:,.0f}"
        )
    st.plotly_chart(style(fig, 460, "€ per month"), use_container_width=True)

# ---------------------------------------------------------------- model
with tab_model:
    st.markdown(
        "**Task:** forecast each series' average rent 4 quarters ahead. **Backtest:** trained on targets up to "
        f"{pd.Period(settings.valid_start, 'Q') - 1}, early-stopped on {settings.valid_start[:4]}, "
        f"scored on unseen targets from {settings.test_start} onward."
    )
    rows = [
        ("Naive (no change)", "test_naive"),
        ("Momentum (last year's growth)", "test_momentum"),
        ("LightGBM", "test_lgbm"),
    ]
    table = pd.DataFrame(
        [
            {
                "Model": name,
                "MAPE %": metrics[f"{k}_mape_pct"],
                "MAE €": metrics[f"{k}_mae_eur"],
                "Headline-series MAPE %": metrics[f"{k}_headline_mape_pct"],
            }
            for name, k in rows
        ]
    ).round(2)
    a, b = st.columns([2, 3])
    with a:
        fig = go.Figure(
            go.Bar(
                x=table["Model"],
                y=table["MAPE %"],
                marker_color=SERIES[0],
                text=table["MAPE %"].map("{:.1f}%".format),
                textposition="outside",
                hovertemplate="%{x}: %{y:.2f}%<extra></extra>",
            )
        )
        st.plotly_chart(style(fig, 360, "Test MAPE (%)").update_layout(hovermode="closest"), use_container_width=True)
    with b:
        st.dataframe(table, hide_index=True, use_container_width=True)
        st.markdown(
            f"Prediction intervals use **conformalized quantile regression**: raw 80% quantile bands covered "
            f"{metrics['test_raw_interval_coverage_pct']:.1f}% of test outcomes; after conformal calibration "
            f"**{metrics['test_interval_coverage_pct']:.1f}%**. The remaining shortfall comes from the 2024–25 "
            "regime differing from the 2023 calibration year."
        )
    figs = settings.reports_dir / "figures"
    i1, i2 = st.columns(2)
    if (figs / "shap_summary.png").exists():
        i1.image(str(figs / "shap_summary.png"), caption="SHAP: what drives forecast rent growth")
    if (figs / "feature_importance.png").exists():
        i2.image(str(figs / "feature_importance.png"), caption="Feature importance (gain)")
    with st.expander("Raw metrics"):
        st.code(json.dumps(metrics, indent=2))
