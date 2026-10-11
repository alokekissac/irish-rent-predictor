"""Interactive county map: click a county to drill into its areas; play rents through time."""

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from common import (
    ALL_BEDS,
    ALL_TYPES,
    BEDS_ORDER,
    BLUE,
    SEQ_BLUE,
    SEQ_ORANGE,
    TYPES_ORDER,
    choropleth,
    clicked_county,
    counties_geojson,
    euro,
    fit_ireland,
    forecaster,
    forecasts,
    history,
    open_page,
    ordered,
    pct,
    short_area,
    style,
)

METRICS = {
    "Forecast rent": ("forecast_rent", SEQ_BLUE, "€/month", "€,.0f"),
    "Forecast growth": ("growth_pct", SEQ_ORANGE, "%", ".1f"),
    "Rent now": ("rent", SEQ_BLUE, "€/month", "€,.0f"),
    "Past 12m growth": ("growth_12m_pct", SEQ_ORANGE, "%", ".1f"),
}

fc = forecaster()
info = fc.info
all_fc = forecasts()

st.title("🏠 RentCast Ireland")
st.caption(
    f"12-month rent forecasts for {info['n_series']:,} RTB rent series · data through {info['data_through']} · "
    "**Click any county** to drill into its towns and neighbourhoods."
)

c1, c2, c3 = st.columns([2, 1, 1])
metric_label = (
    c1.segmented_control("Colour map by", list(METRICS), default="Forecast rent", key="map_metric") or "Forecast rent"
)
beds = c2.selectbox("Bedrooms", ordered(all_fc["beds"].unique(), BEDS_ORDER))
ptype = c3.selectbox("Property type", ordered(all_fc["property_type"].unique(), TYPES_ORDER))
col, scale, unit, fmt = METRICS[metric_label]

subset = all_fc[(all_fc["beds"] == beds) & (all_fc["property_type"] == ptype)]
counties = subset[subset["level"] == "county"].copy()
if counties.empty:
    st.warning("No county-level RTB data for this combination. Try 'All property types'.")
    st.stop()

st.session_state.setdefault("sel_county", "Dublin")
selected = st.session_state["sel_county"]

left, right = st.columns([5, 4], gap="large")
with left:
    value_fmt = "€%{z:,.0f}" if unit.startswith("€") else "%{z:+.1f}%"
    fig = choropleth(
        counties,
        col,
        scale,
        unit,
        f"<b>%{{location}}</b><br>{metric_label}: {value_fmt}",
        fmt.replace("€", ""),
        selected=selected,
    )
    event = st.plotly_chart(
        fig,
        on_select="rerun",
        selection_mode="points",
        key="county_map",
        config={"displayModeBar": False, "scrollZoom": False},
    )
    clicked = clicked_county(event)
    if clicked and clicked != selected:
        st.session_state["sel_county"] = clicked
        st.session_state["sel_location"] = clicked
        st.rerun()
    nat = counties.sort_values(col)
    st.caption(
        f"Lowest: **{nat.iloc[0]['county']}** · Highest: **{nat.iloc[-1]['county']}** · "
        f"Median county forecast growth **{pct(counties['growth_pct'].median())}**"
    )

with right:
    row = counties[counties["county"] == selected]
    st.subheader(f"📍 {selected}")
    if row.empty:
        st.info("No data for this county with the current filters.")
    else:
        r = row.iloc[0]
        rank = int((counties["forecast_rent"] > r["forecast_rent"]).sum()) + 1
        k1, k2, k3 = st.columns(3)
        k1.metric(
            f"Rent ({r['quarter']})", euro(r["rent"]), pct(r["growth_12m_pct"]) + " in 12m", delta_color="inverse"
        )
        k2.metric(
            f"Forecast ({r['forecast_quarter']})", euro(r["forecast_rent"]), pct(r["growth_pct"]), delta_color="inverse"
        )
        k3.metric(f"Price rank (of {len(counties)})", f"#{rank}")
        st.caption(f"~80% range for {r['forecast_quarter']}: {euro(r['lower_rent'])} – {euro(r['upper_rent'])}")

    areas = subset[(subset["county"] == selected) & (subset["level"] != "county")].sort_values("forecast_rent")
    if areas.empty:
        st.info("No town-level data for this filter.")
    else:
        st.markdown(f"**{len(areas)} areas in {selected}**: click a bar to open it in the explorer")
        bar = go.Figure(
            go.Bar(
                x=areas["forecast_rent"],
                y=short_area(areas["location"], selected),
                orientation="h",
                marker_color=BLUE,
                customdata=areas[["location", "rent", "growth_pct"]],
                error_x=dict(
                    type="data",
                    symmetric=False,
                    array=areas["upper_rent"] - areas["forecast_rent"],
                    arrayminus=areas["forecast_rent"] - areas["lower_rent"],
                    color="rgba(128,128,128,0.6)",
                    thickness=1,
                    width=0,
                ),
                hovertemplate="<b>%{customdata[0]}</b><br>Now €%{customdata[1]:,.0f} → €%{x:,.0f} "
                "(%{customdata[2]:+.1f}%)<extra></extra>",
            )
        )
        bar = style(bar, max(320, 22 * len(areas) + 60), hover="closest")
        bar.update_layout(
            xaxis_title="Forecast rent, €/month (whiskers: ~80% range)", bargap=0.3, clickmode="event+select"
        )
        area_event = st.container(height=620, border=False).plotly_chart(
            bar,
            on_select="rerun",
            selection_mode="points",
            key=f"area_bars_{selected}_{beds}_{ptype}",
            config={"displayModeBar": False},
        )
        pts = getattr(getattr(area_event, "selection", None), "points", None) or []
        if pts:
            st.session_state.update(sel_location=pts[0]["customdata"][0], sel_beds=beds, sel_ptype=ptype)
            open_page("explorer")
    if st.button(f"Open {selected} in the forecast explorer →", type="primary"):
        st.session_state.update(sel_location=selected, sel_beds=beds, sel_ptype=ptype)
        open_page("explorer")

# ------------------------------------------------------------------ timeline
st.divider()
st.subheader("▶️ Ireland's rents, 2008 to today")
st.caption("Press play: annual average rent of new tenancies per county (all bedrooms, all property types).")
h = history()
yearly = (
    h[(h["level"] == "county") & (h["beds"] == ALL_BEDS) & (h["property_type"] == ALL_TYPES)]
    .assign(year=lambda d: d["quarter"].str[:4].astype(int))
    .query("year >= 2008")
    .groupby(["year", "county"], as_index=False)["rent"]
    .mean()
)
anim = px.choropleth(
    yearly,
    geojson=counties_geojson(),
    locations="county",
    featureidkey="id",
    color="rent",
    animation_frame="year",
    color_continuous_scale=SEQ_BLUE,
    range_color=(yearly["rent"].min(), yearly["rent"].max()),
    labels={"rent": "€/month"},
    hover_name="county",
    hover_data={"rent": ":,.0f", "county": False, "year": False},
)
anim.update_traces(marker_line_color="rgba(255,255,255,0.9)", marker_line_width=0.8)
fit_ireland(anim)
anim.update_layout(
    height=600,
    margin=dict(l=0, r=0, t=0, b=0),
    paper_bgcolor="rgba(0,0,0,0)",
    coloraxis_colorbar=dict(thickness=12, len=0.6, tickprefix="€"),
)
anim.layout.updatemenus[0].buttons[0].args[1]["frame"]["duration"] = 600
a1, a2 = st.columns([3, 2], gap="large")
a1.plotly_chart(anim, config={"displayModeBar": False})
with a2:
    first, last = yearly["year"].min(), yearly["year"].max()
    change = yearly.pivot(index="county", columns="year", values="rent")
    change = ((change[last] / change[first] - 1) * 100).sort_values()
    st.markdown(f"**Rent change {first} → {last}**")
    chg = go.Figure(
        go.Bar(
            x=change.values,
            y=change.index,
            orientation="h",
            marker_color=BLUE,
            hovertemplate="%{y}: %{x:+.0f}%<extra></extra>",
        )
    )
    st.plotly_chart(
        style(chg, 560, hover="closest").update_layout(xaxis_title="% change"), config={"displayModeBar": False}
    )
