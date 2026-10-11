"""Model performance: backtest accuracy you can slice by county, area type and bedrooms."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from common import BEDS_ORDER, BLUE, SERIES, backtest, forecaster, ordered, style

from rentcast.config import settings

st.title("📊 Model performance")
metrics = forecaster().info["metrics"]
st.markdown(
    "**Task:** forecast each series' average rent 12 months ahead. **Backtest:** trained on targets up to "
    f"{pd.Period(settings.valid_start, 'Q') - 1}, early-stopped on {settings.valid_start[:4]}, then scored on "
    f"**unseen** outcomes from {settings.test_start} onward."
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("LightGBM error (MAPE)", f"{metrics['test_lgbm_mape_pct']:.2f}%")
k2.metric(
    "vs naive baseline",
    f"{metrics['test_naive_mape_pct']:.2f}%",
    f"{(1 - metrics['test_lgbm_mape_pct'] / metrics['test_naive_mape_pct']) * 100:.0f}% less error",
    delta_color="off",
)
k3.metric("Average miss", f"€{metrics['test_lgbm_mae_eur']:.0f}/month")
k4.metric(
    "80% interval coverage",
    f"{metrics['test_interval_coverage_pct']:.1f}%",
    f"{metrics['test_interval_coverage_pct'] - metrics['test_raw_interval_coverage_pct']:+.1f} pts from "
    "conformal calibration",
    delta_color="off",
)

rows = [
    ("Naive (no change)", "test_naive"),
    ("Momentum", "test_momentum"),
    ("LightGBM without house-price data", "test_lgbm_no_ppr"),
    ("LightGBM (full)", "test_lgbm"),
]
comp = pd.DataFrame(
    [
        {"Model": n, "MAPE": metrics[f"{k}_mape_pct"], "MAE": metrics[f"{k}_mae_eur"]}
        for n, k in rows
        if f"{k}_mape_pct" in metrics
    ]
)
fig = go.Figure(
    go.Bar(
        x=comp["MAPE"],
        y=comp["Model"],
        orientation="h",
        marker_color=BLUE,
        text=comp["MAPE"].map("{:.2f}%".format),
        textposition="outside",
        customdata=comp["MAE"],
        hovertemplate="%{y}: %{x:.2f}% (€%{customdata:.0f})<extra></extra>",
    )
)
a, b = st.columns([3, 2], gap="large")
a.plotly_chart(
    style(fig, 280, hover="closest").update_layout(
        xaxis_title="Test MAPE (%)", xaxis_range=[0, comp["MAPE"].max() * 1.18]
    ),
    config={"displayModeBar": False},
)
b.info(
    "**Ablation finding:** house-price features rank high in feature importance, yet removing them doesn't "
    "change test error. The rent series already carry that signal. Importance ≠ predictive value."
)

bt = backtest()
if bt.empty:
    st.stop()
bt = bt.assign(
    err_pct=(bt["pred_rent"] / bt["actual_rent"] - 1) * 100,
    covered=(bt["actual_rent"] >= bt["lower_rent"]) & (bt["actual_rent"] <= bt["upper_rent"]),
)

st.subheader("🔬 Slice the backtest")
f1, f2, f3 = st.columns(3)
counties = f1.multiselect("Counties", sorted(bt["county"].unique()), placeholder="All counties")
levels = f2.multiselect("Area type", sorted(bt["level"].unique()), placeholder="All types")
beds = f3.multiselect("Bedrooms", ordered(bt["beds"].unique(), BEDS_ORDER), placeholder="All")
s = bt
if counties:
    s = s[s["county"].isin(counties)]
if levels:
    s = s[s["level"].isin(levels)]
if beds:
    s = s[s["beds"].isin(beds)]
if s.empty:
    st.warning("No backtest rows for this slice.")
    st.stop()

m1, m2, m3, m4 = st.columns(4)
m1.metric("Forecasts in slice", f"{len(s):,}")
m2.metric("MAPE", f"{s['err_pct'].abs().mean():.2f}%")
m3.metric("Bias", f"{s['err_pct'].mean():+.2f}%", help="Positive = model over-forecasts on average")
m4.metric("Interval coverage", f"{s['covered'].mean() * 100:.1f}%")

c1, c2 = st.columns(2, gap="large")
with c1:
    st.markdown("**Forecast vs actual rent** (each dot is one 12-month-ahead forecast)")
    sample = s.sample(min(4000, len(s)), random_state=0)
    lim = [0, float(max(sample["actual_rent"].max(), sample["pred_rent"].max()) * 1.05)]
    sc = go.Figure(
        [
            go.Scatter(
                x=lim,
                y=lim,
                mode="lines",
                line=dict(color="rgba(128,128,128,0.6)", dash="dash"),
                name="Perfect forecast",
                hoverinfo="skip",
            ),
            go.Scatter(
                x=sample["actual_rent"],
                y=sample["pred_rent"],
                mode="markers",
                name="Forecast",
                marker=dict(color=BLUE, size=6, opacity=0.45),
                customdata=np.c_[sample["location"], sample["beds"], sample["target_quarter"], sample["err_pct"]],
                hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]} · %{customdata[2]}<br>"
                "Actual €%{x:,.0f} · forecast €%{y:,.0f} (%{customdata[3]:+.1f}%)<extra></extra>",
            ),
        ]
    )
    st.plotly_chart(
        style(sc, 440, "Forecast rent (€)", hover="closest").update_layout(
            xaxis_title="Actual rent (€)", showlegend=False
        )
    )
with c2:
    st.markdown("**Distribution of forecast errors**")
    hist = go.Figure(
        go.Histogram(
            x=s["err_pct"].clip(-30, 30),
            nbinsx=60,
            marker_color=BLUE,
            marker_line=dict(color="white", width=1),
            hovertemplate="%{x}%: %{y} forecasts<extra></extra>",
        )
    )
    hist.add_vline(x=0, line=dict(color=SERIES[1], width=2, dash="dash"))
    st.plotly_chart(
        style(hist, 440, "Forecasts", hover="closest").update_layout(
            xaxis_title="Forecast error (%; clipped at ±30)", bargap=0.02
        )
    )

st.markdown("**Error by county**")
by = (
    s.groupby("county")
    .agg(mape=("err_pct", lambda e: e.abs().mean()), n=("err_pct", "size"), coverage=("covered", "mean"))
    .reset_index()
    .sort_values("mape")
)
bc = go.Figure(
    go.Bar(
        x=by["county"],
        y=by["mape"],
        marker_color=BLUE,
        customdata=by[["n", "coverage"]],
        hovertemplate="<b>%{x}</b><br>MAPE %{y:.2f}%<br>%{customdata[0]} forecasts · "
        "coverage %{customdata[1]:.0%}<extra></extra>",
    )
)
st.plotly_chart(style(bc, 340, "MAPE (%)", hover="closest"), config={"displayModeBar": False})

figs = settings.reports_dir / "figures"
with st.expander("Global feature effects (SHAP)"):
    if (figs / "shap_summary.png").exists():
        st.image(str(figs / "shap_summary.png"))
