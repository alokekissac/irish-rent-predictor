"""Compare up to three rent series side by side, in euro or indexed to a common base."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import BEDS_ORDER, SERIES, TYPES_ORDER, forecaster, history, ordered, style

st.title("⚖️ Compare areas")
fc = forecaster()
latest = fc.latest
h = history()

c1, c2, c3 = st.columns([3, 1, 1])
all_locs = fc.locations()["location"].tolist()
chosen = c1.multiselect("Areas (up to 3)", all_locs, default=["Dublin", "Cork", "Galway"], max_selections=3)
beds = c2.selectbox("Bedrooms", ordered(latest["beds"].unique(), BEDS_ORDER))
ptype = c3.selectbox("Property type", ordered(latest["property_type"].unique(), TYPES_ORDER))

o1, o2, o3 = st.columns([2, 2, 3])
mode = o1.segmented_control("Show", ["€ per month", "Indexed (start = 100)"], default="€ per month") or "€ per month"
start = o2.select_slider("From", options=list(range(2008, 2026)), value=2012)
show_fc = o3.toggle("Include 12-month forecasts", value=True)

fig = go.Figure()
rows = []
for colour, loc in zip(SERIES, chosen, strict=False):
    s = h[
        (h["location"] == loc) & (h["beds"] == beds) & (h["property_type"] == ptype) & (h["date"].dt.year >= start)
    ].sort_values("date")
    if s.empty:
        st.warning(f"No data for {loc} with {beds.lower()} / {ptype.lower()}.")
        continue
    base = s["rent"].iloc[0] if mode.startswith("Indexed") else 1.0
    scale = 100 / base if mode.startswith("Indexed") else 1.0
    fig.add_scatter(
        x=s["date"],
        y=s["rent"] * scale,
        name=loc,
        line=dict(color=colour, width=2),
        hovertemplate=("%{y:.0f}" if scale != 1 else "€%{y:,.0f}"),
    )
    try:
        f = fc.predict_frame(fc.row(loc, beds, ptype)).iloc[0]
    except LookupError:
        continue
    rows.append(
        {
            "Area": loc,
            f"Rent {s['quarter'].iloc[0]}": s["rent"].iloc[0],
            "Latest": f["rent"],
            "Forecast +12m": f["forecast_rent"],
            "Forecast growth": f["growth_pct"],
            f"Change since {start}": (f["rent"] / s["rent"].iloc[0] - 1) * 100,
        }
    )
    if show_fc:
        x0 = pd.Period(f["quarter"], "Q").to_timestamp(how="end").normalize()
        x1 = pd.Period(f["target_quarter"], "Q").to_timestamp(how="end").normalize()
        fig.add_scatter(
            x=[x0, x1],
            y=[f["rent"] * scale, f["forecast_rent"] * scale],
            mode="lines+markers",
            line=dict(color=colour, width=2, dash="dot"),
            marker=dict(size=8),
            showlegend=False,
            name=f"{loc} forecast",
            hovertemplate=("%{y:.0f}" if scale != 1 else "€%{y:,.0f}"),
            error_y=dict(
                type="data",
                symmetric=False,
                array=[0, (f["upper_rent"] - f["forecast_rent"]) * scale],
                arrayminus=[0, (f["forecast_rent"] - f["lower_rent"]) * scale],
                color=colour,
                thickness=1,
            ),
        )
st.plotly_chart(style(fig, 480, "Index (start = 100)" if mode.startswith("Indexed") else "€ per month"))
if rows:
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        column_config={
            c: st.column_config.NumberColumn(format="€%.0f")
            for c in pd.DataFrame(rows).columns
            if c.startswith(("Rent", "Latest", "Forecast +"))
        }
        | {
            "Forecast growth": st.column_config.NumberColumn(format="%+.1f%%"),
            f"Change since {start}": st.column_config.NumberColumn(format="%+.0f%%"),
        },
    )
