"""Filterable league table of every area, with sparklines and CSV export."""

import streamlit as st
from common import BEDS_ORDER, TYPES_ORDER, forecasts, history, open_page, ordered

st.title("🏆 League table")
st.caption("Every RTB area, filterable and sortable. Select a row to open it in the forecast explorer.")

df = forecasts()
with st.container(border=True):
    c1, c2, c3, c4 = st.columns(4)
    counties = c1.multiselect("Counties", sorted(df["county"].unique()), placeholder="All counties")
    levels = c2.multiselect(
        "Area type",
        ["county", "district", "town"],
        default=["district", "town"],
        format_func=lambda x: {"county": "County", "district": "City / district", "town": "Town / neighbourhood"}[x],
    )
    beds = c3.selectbox("Bedrooms", ordered(df["beds"].unique(), BEDS_ORDER))
    ptype = c4.selectbox("Property type", ordered(df["property_type"].unique(), TYPES_ORDER))
    q = df[(df["beds"] == beds) & (df["property_type"] == ptype)]
    if counties:
        q = q[q["county"].isin(counties)]
    if levels:
        q = q[q["level"].isin(levels)]
    r1, r2, r3 = st.columns([2, 2, 1])
    lo, hi = int(df["rent"].min() // 100 * 100), int(df["rent"].max() // 100 * 100 + 100)
    rent_range = r1.slider("Current rent (€/month)", lo, hi, (lo, hi), 50)
    sort = (
        r2.segmented_control("Rank by (forecast)", ["Growth", "Rent", "Past 12m", "Cheapest"], default="Growth")
        or "Growth"
    )
    search = r3.text_input("Search area", placeholder="e.g. Rathmines")
q = q[q["rent"].between(*rent_range)]
if search:
    q = q[q["location"].str.contains(search, case=False)]
sort_col, asc = {
    "Growth": ("growth_pct", False),
    "Rent": ("forecast_rent", False),
    "Past 12m": ("growth_12m_pct", False),
    "Cheapest": ("rent", True),
}[sort]
q = q.sort_values(sort_col, ascending=asc)

h = history()
h = h[(h["beds"] == beds) & (h["property_type"] == ptype) & (h["quarter"] >= "2020Q1")]
spark = h.sort_values("quarter").groupby("location")["rent"].apply(lambda s: s.round().tolist())
table = q.assign(trend=q["location"].map(spark), rank=range(1, len(q) + 1))[
    [
        "rank",
        "location",
        "county",
        "trend",
        "rent",
        "growth_12m_pct",
        "forecast_rent",
        "growth_pct",
        "lower_rent",
        "upper_rent",
    ]
]
st.markdown(f"**{len(table)} areas**")
event = st.dataframe(
    table,
    hide_index=True,
    height=620,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "rank": st.column_config.NumberColumn("#", width="small"),
        "location": "Area",
        "county": "County",
        "trend": st.column_config.LineChartColumn("Rent since 2020"),
        "rent": st.column_config.NumberColumn("Latest rent", format="€%.0f"),
        "growth_12m_pct": st.column_config.NumberColumn("Last 12m", format="%+.1f%%"),
        "forecast_rent": st.column_config.NumberColumn("Forecast +12m", format="€%.0f"),
        "growth_pct": st.column_config.ProgressColumn(
            "Forecast growth",
            format="%+.1f%%",
            min_value=float(min(0, df["growth_pct"].min())),
            max_value=float(df["growth_pct"].quantile(0.99)),
        ),
        "lower_rent": st.column_config.NumberColumn("Low (~10%)", format="€%.0f"),
        "upper_rent": st.column_config.NumberColumn("High (~90%)", format="€%.0f"),
    },
)
if event.selection.rows:
    r = table.iloc[event.selection.rows[0]]
    st.session_state.update(sel_county=r["county"], sel_location=r["location"], sel_beds=beds, sel_ptype=ptype)
    open_page("explorer")
st.download_button(
    "⬇️ Download as CSV", table.drop(columns="trend").to_csv(index=False).encode(), "rentcast_forecasts.csv", "text/csv"
)
