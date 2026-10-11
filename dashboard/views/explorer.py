"""Forecast explorer: history + forecast, backtest overlay, SHAP 'why', and what-if scenarios."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import (
    BAND,
    BLUE,
    FEATURE_LABELS,
    SERIES,
    backtest,
    euro,
    forecaster,
    history,
    pct,
    select_series,
    style,
)

fc = forecaster()
st.title("🔎 Forecast explorer")
county, location, beds, ptype = select_series()

base_row = fc.row(location, beds, ptype)
base = fc.predict_frame(base_row).iloc[0]
cur_q, tgt_q = base["quarter"], base["target_quarter"]

# ------------------------------------------------------------------ what-if controls (sidebar)
SCENARIO = {
    "growth_4q": "This area's last-12m growth",
    "county_growth_4q": "County rent momentum (12m)",
    "national_growth_4q": "National rent momentum (12m)",
    "price_growth_4q": "County house-price growth (12m)",
}
with st.sidebar:
    st.header("🎛️ What-if scenario")
    st.caption(
        "Change the market conditions the model sees and watch the forecast respond. "
        "Defaults are the latest observed values."
    )
    if st.button("Reset to observed", width="stretch"):
        for k in SCENARIO:
            st.session_state.pop(f"wi_{k}_{location}_{beds}_{ptype}", None)
    scenario = base_row.copy()
    changed = False
    for feat, label in SCENARIO.items():
        observed = base_row[feat].iloc[0]
        if pd.isna(observed):
            continue
        obs_pct = float((np.exp(observed) - 1) * 100)
        val = st.slider(
            label,
            -15.0,
            25.0,
            round(obs_pct, 1),
            0.5,
            format="%+.1f%%",
            key=f"wi_{feat}_{location}_{beds}_{ptype}",
            help=f"Observed: {obs_pct:+.1f}%",
        )
        if abs(val - round(obs_pct, 1)) > 1e-9:
            scenario[feat] = np.log1p(val / 100)
            changed = True
            if feat == "growth_4q":
                scenario["growth_8q"] = base_row["growth_8q"] - observed + scenario[feat]

what_if = fc.predict_frame(scenario).iloc[0] if changed else None

# ------------------------------------------------------------------ headline numbers
k1, k2, k3, k4 = st.columns(4)
k1.metric(f"Latest rent ({cur_q})", euro(base["rent"]))
k2.metric(f"Forecast ({tgt_q})", euro(base["forecast_rent"]), pct(base["growth_pct"]), delta_color="inverse")
k3.metric("~80% range", f"{euro(base['lower_rent'])} – {euro(base['upper_rent'])}")
if what_if is not None:
    k4.metric(
        "Your scenario",
        euro(what_if["forecast_rent"]),
        f"{what_if['forecast_rent'] - base['forecast_rent']:+,.0f} € vs model",
        delta_color="inverse",
    )
else:
    k4.metric(
        "Extra cost over 12 months",
        euro(12 * (base["forecast_rent"] - base["rent"])),
        help="If rent moves from today's level to the forecast level",
    )

# ------------------------------------------------------------------ chart
h = history()
hist = h[(h["location"] == location) & (h["beds"] == beds) & (h["property_type"] == ptype)]
bt = backtest()
bt = bt[(bt["location"] == location) & (bt["beds"] == beds) & (bt["property_type"] == ptype)] if len(bt) else bt

t1, t2, t3 = st.columns([2, 2, 3])
show_bt = t1.toggle(
    "Show past forecasts vs actual",
    value=len(bt) > 0,
    disabled=len(bt) == 0,
    help="Backtest: forecasts the model made 12 months earlier, never trained on these outcomes",
)
years = t2.select_slider("History from", options=list(range(2008, 2026)), value=2015)
log_y = t3.toggle("Log scale", value=False)

hist = hist[hist["date"].dt.year >= years]
last_date = pd.Period(cur_q, "Q").to_timestamp(how="end").normalize()
fdate = pd.Period(tgt_q, "Q").to_timestamp(how="end").normalize()
fig = go.Figure(
    [
        go.Scatter(
            x=[last_date, fdate, fdate, last_date],
            y=[base["rent"], base["upper_rent"], base["lower_rent"], base["rent"]],
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
            line=dict(color=BLUE, width=2),
            hovertemplate="€%{y:,.0f}",
        ),
        go.Scatter(
            x=[last_date, fdate],
            y=[base["rent"], base["forecast_rent"]],
            name="Model forecast",
            line=dict(color=BLUE, width=2, dash="dot"),
            marker=dict(size=9),
            mode="lines+markers",
            hovertemplate="€%{y:,.0f}",
        ),
    ]
)
if what_if is not None:
    fig.add_scatter(
        x=[last_date, fdate],
        y=[base["rent"], what_if["forecast_rent"]],
        name="Your scenario",
        line=dict(color=SERIES[1], width=2, dash="dash"),
        marker=dict(size=9),
        mode="lines+markers",
        hovertemplate="€%{y:,.0f}",
    )
if show_bt and len(bt):
    bdates = pd.PeriodIndex(bt["target_quarter"], freq="Q").to_timestamp(how="end").normalize()
    fig.add_scatter(
        x=bdates,
        y=bt["pred_rent"],
        mode="markers",
        name="Past forecast (made 12m earlier)",
        marker=dict(color=SERIES[2], size=8, symbol="diamond", line=dict(color="white", width=1)),
        error_y=dict(
            type="data",
            symmetric=False,
            array=bt["upper_rent"] - bt["pred_rent"],
            arrayminus=bt["pred_rent"] - bt["lower_rent"],
            color="rgba(27,175,122,0.5)",
            thickness=1,
        ),
        customdata=np.c_[bt["actual_rent"], (bt["pred_rent"] / bt["actual_rent"] - 1) * 100],
        hovertemplate="Forecast €%{y:,.0f} · actual €%{customdata[0]:,.0f} (%{customdata[1]:+.1f}% off)",
    )
fig = style(fig, 460, "€ per month")
if log_y:
    fig.update_yaxes(type="log")
st.plotly_chart(fig)
if show_bt and len(bt):
    err = (bt["pred_rent"] / bt["actual_rent"] - 1).abs().mean() * 100
    st.caption(
        f"Backtest for this series: average error **{err:.1f}%** over {len(bt)} forecasts "
        f"({bt['target_quarter'].min()}–{bt['target_quarter'].max()})."
    )

# ------------------------------------------------------------------ why
st.subheader("🧠 Why this forecast?")
st.caption(
    "SHAP breaks the forecast into contributions from each factor, starting from the average "
    "12-month growth the model has seen. Hover a bar for detail."
)
row_for_explain = scenario if what_if is not None else base_row
contrib = fc.explain(row_for_explain).iloc[0]
base_value = contrib.pop("base_value")
contrib = contrib.rename(FEATURE_LABELS) * 100  # log points ≈ % points
top = contrib.reindex(contrib.abs().sort_values(ascending=False).index)
shown, other = top.iloc[:7], top.iloc[7:].sum()
labels = ["Typical 12m growth", *shown.index, "All other factors", "Forecast growth"]
values = [base_value * 100, *shown.to_numpy(), other, 0]
wf = go.Figure(
    go.Waterfall(
        orientation="h",
        y=labels,
        x=values,
        measure=["absolute"] + ["relative"] * (len(shown) + 1) + ["total"],
        increasing=dict(marker_color="#e34948"),
        decreasing=dict(marker_color=BLUE),
        totals=dict(marker_color="#52514e"),
        connector=dict(line=dict(color="rgba(128,128,128,0.4)", width=1)),
        hovertemplate="%{y}: %{x:+.2f} pts<extra></extra>",
    )
)
wf = style(wf, 420, hover="closest").update_layout(
    xaxis_title="Contribution to forecast growth (≈ % points)", showlegend=False
)
wf.update_yaxes(autorange="reversed")  # read top-down: baseline → factors → forecast
w1, w2 = st.columns([3, 2], gap="large")
w1.plotly_chart(wf)
with w2:
    up = shown[shown > 0]
    down = shown[shown < 0]
    st.markdown(f"**Forecast: {pct(np.expm1(base_value + contrib.sum() / 100) * 100)}** over 12 months")
    if len(up):
        st.markdown("🔺 **Pushing rent up:** " + ", ".join(f"{k} ({v:+.1f})" for k, v in up.items()))
    if len(down):
        st.markdown("🔻 **Holding rent down:** " + ", ".join(f"{k} ({v:+.1f})" for k, v in down.items()))
    st.caption(
        "Red increases the forecast, blue reduces it. "
        + ("Explaining **your scenario**." if what_if is not None else "Adjust the sidebar sliders to test a scenario.")
    )
