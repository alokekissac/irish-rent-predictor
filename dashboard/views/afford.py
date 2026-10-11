"""Affordability: where can I rent on my income, now and in 12 months?"""

import plotly.graph_objects as go
import streamlit as st
from common import (
    BEDS_ORDER,
    BLUE,
    DIVERGING,
    SERIES,
    TYPES_ORDER,
    choropleth,
    clicked_county,
    euro,
    forecasts,
    open_page,
    ordered,
    short_area,
    style,
)

st.title("💶 Where can I afford?")
st.caption(
    "Enter your take-home pay. Areas are compared using RTB average rents for new tenancies "
    "today and the model's 12-month forecast."
)

all_fc = forecasts()
with st.container(border=True):
    c1, c2, c3, c4, c5 = st.columns([1.3, 1.3, 1, 1, 1.2])
    income = c1.number_input("Household take-home pay (€/month)", 500, 30_000, 4_000, 100)
    share = c2.slider(
        "Max share of pay on rent", 15, 60, 30, 1, format="%d%%", help="30% is the common affordability benchmark"
    )
    sharers = c3.number_input(
        "People splitting rent", 1, 6, 1, help="Rent is divided between this many people; pay is yours alone"
    )
    beds = c4.selectbox("Bedrooms", ordered(all_fc["beds"].unique(), BEDS_ORDER), index=2)
    ptype = c5.selectbox("Property type", ordered(all_fc["property_type"].unique(), TYPES_ORDER))
    when = (
        st.segmented_control(
            "Compare against", ["Rent today", "Forecast in 12 months"], default="Forecast in 12 months"
        )
        or "Forecast in 12 months"
    )

budget = income * share / 100
rent_col = "forecast_rent" if when.startswith("Forecast") else "rent"
df = all_fc[(all_fc["beds"] == beds) & (all_fc["property_type"] == ptype)].copy()
if df.empty:
    st.warning("No RTB data for this bedroom/type combination.")
    st.stop()
df["your_share"] = df[rent_col] / sharers
df["share_of_pay"] = df["your_share"] / income * 100
df["affordable"] = df["your_share"] <= budget
df["was_affordable"] = df["rent"] / sharers <= budget
df["will_be_affordable"] = df["forecast_rent"] / sharers <= budget
df["income_needed"] = df[rent_col] / sharers / (share / 100)

areas = df[df["level"] != "county"]
lost = areas[areas["was_affordable"] & ~areas["will_be_affordable"]]
k1, k2, k3, k4 = st.columns(4)
k1.metric("Your rent budget", euro(budget) + "/month")
k2.metric(
    f"Affordable areas ({'in 12m' if rent_col == 'forecast_rent' else 'today'})",
    f"{int(areas['affordable'].sum())} of {len(areas)}",
)
k3.metric("Areas priced out within 12 months", len(lost), delta=f"-{len(lost)}" if len(lost) else None)
cheapest = areas.sort_values(rent_col).iloc[0] if len(areas) else None
if cheapest is not None:
    k4.metric("Cheapest area", euro(cheapest[rent_col]), cheapest["location"], delta_color="off")

counties = df[df["level"] == "county"]
left, right = st.columns([5, 4], gap="large")
with left:
    st.markdown(f"**Share of your pay going on rent** · grey = exactly {share}%, blue = under budget, red = over")
    fig = choropleth(
        counties,
        "share_of_pay",
        DIVERGING,
        "% of pay",
        "<b>%{location}</b><br>%{z:.0f}% of your pay",
        ".0f",
        zmid=share,
        selected=st.session_state.get("sel_county"),
    )
    event = st.plotly_chart(
        fig, on_select="rerun", selection_mode="points", key="afford_map", config={"displayModeBar": False}
    )
    clicked = clicked_county(event)
    if clicked and clicked != st.session_state.get("sel_county"):
        st.session_state["sel_county"] = clicked
        st.rerun()
with right:
    county = st.session_state.get("sel_county", "Dublin")
    sub = areas[areas["county"] == county].sort_values(rent_col)
    st.markdown(f"**{county}: areas vs your budget** (click a county on the map)")
    if sub.empty:
        st.info("No town-level data for this filter.")
    else:
        bar = go.Figure(
            go.Bar(
                x=sub["your_share"],
                y=short_area(sub["location"], county),
                orientation="h",
                marker_color=[BLUE if a else "#e34948" for a in sub["affordable"]],
                customdata=sub[["share_of_pay", "income_needed"]],
                hovertemplate="<b>%{y}</b><br>Your share €%{x:,.0f} (%{customdata[0]:.0f}% of pay)"
                "<br>Pay needed: €%{customdata[1]:,.0f}/month<extra></extra>",
            )
        )
        bar.add_vline(
            x=budget,
            line=dict(color=SERIES[1], width=2, dash="dash"),
            annotation_text=f"Budget {euro(budget)}",
            annotation_position="top",
        )
        st.container(height=620, border=False).plotly_chart(
            style(bar, max(320, 22 * len(sub) + 80), hover="closest").update_layout(
                xaxis_title="Your monthly rent share (€)", bargap=0.3, yaxis_autorange="reversed"
            ),
            config={"displayModeBar": False},
        )

st.subheader("✅ Areas within your budget")
ok = areas[areas["affordable"]].sort_values(rent_col)
if ok.empty:
    st.info(
        f"No areas fit a {euro(budget)} budget for {beds.lower()} / {ptype.lower()}. "
        "Try more sharers, fewer bedrooms or a higher share."
    )
else:
    table = ok.assign(left_over=income - ok["your_share"])[
        ["location", "county", "rent", "forecast_rent", "growth_pct", "your_share", "share_of_pay", "left_over"]
    ]
    picked = st.dataframe(
        table,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        height=380,
        column_config={
            "location": "Area",
            "county": "County",
            "rent": st.column_config.NumberColumn("Rent today", format="€%.0f"),
            "forecast_rent": st.column_config.NumberColumn("Forecast +12m", format="€%.0f"),
            "growth_pct": st.column_config.NumberColumn("Growth", format="%+.1f%%"),
            "your_share": st.column_config.NumberColumn("Your share", format="€%.0f"),
            "share_of_pay": st.column_config.ProgressColumn(
                "Share of pay", format="%.0f%%", min_value=0, max_value=share
            ),
            "left_over": st.column_config.NumberColumn("Left after rent", format="€%.0f"),
        },
    )
    rows = picked.selection.rows
    if rows:
        r = table.iloc[rows[0]]
        st.session_state.update(sel_county=r["county"], sel_location=r["location"], sel_beds=beds, sel_ptype=ptype)
        open_page("explorer")
    st.caption("Select a row to open that area in the forecast explorer.")
if len(lost):
    with st.expander(f"⚠️ {len(lost)} areas affordable today but forecast to exceed your budget in 12 months"):
        st.dataframe(
            lost[["location", "county", "rent", "forecast_rent", "growth_pct"]].sort_values("rent"),
            hide_index=True,
            column_config={
                "rent": st.column_config.NumberColumn("Rent today", format="€%.0f"),
                "forecast_rent": st.column_config.NumberColumn("Forecast +12m", format="€%.0f"),
                "growth_pct": st.column_config.NumberColumn("Growth", format="%+.1f%%"),
            },
        )
