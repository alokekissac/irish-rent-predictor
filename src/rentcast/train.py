"""Train and evaluate 12-month-ahead rent forecasters, tracked with MLflow.

Split is by *target* quarter so no future information leaks into training:
  train: target < valid_start | valid: valid_start <= target < test_start | test: target >= test_start
"""

import json
import logging
import os

os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import joblib
import lightgbm as lgb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
import shap

from rentcast.config import settings
from rentcast.features import CATEGORICAL, FEATURES, SERIES_KEY, TARGET, build_features, to_model_frame

log = logging.getLogger(__name__)

PARAMS = {
    "objective": "huber",
    "alpha": 0.1,
    "learning_rate": 0.03,
    "num_leaves": 63,
    "min_child_samples": 100,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "lambda_l2": 1.0,
    "cat_smooth": 50,
    "verbose": -1,
    "seed": 42,
}
QUANTILES = (0.1, 0.9)
PPR_FEATURES = ["log_median_price", "price_growth_4q", "sales_growth_4q", "new_build_share", "gross_yield"]


def metrics(rent_now: pd.Series, y_true: pd.Series, y_pred: np.ndarray, prefix: str) -> dict[str, float]:
    """Errors in euro on the forecast rent, not just on log growth."""
    actual = rent_now * np.exp(y_true)
    pred = rent_now * np.exp(y_pred)
    err = (pred - actual).abs()
    return {
        f"{prefix}_mae_eur": float(err.mean()),
        f"{prefix}_mape_pct": float((err / actual).mean() * 100),
        f"{prefix}_medape_pct": float((err / actual).median() * 100),
    }


def coverage(y: pd.Series, lo: np.ndarray, hi: np.ndarray) -> float:
    return float(((y >= lo) & (y <= hi)).mean() * 100)


def conformal_margin(y: pd.Series, lo: np.ndarray, hi: np.ndarray) -> float:
    """CQR (Romano et al., 2019): widen [lo, hi] by the finite-sample quantile of nonconformity scores."""
    target = QUANTILES[1] - QUANTILES[0]
    scores = np.maximum(lo - y, y - hi)
    level = min(1.0, np.ceil((len(scores) + 1) * target) / len(scores))
    return float(np.quantile(scores, level))


def split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    labelled = df[df[TARGET].notna()]
    tq = labelled["target_quarter"]
    valid_start, test_start = pd.Period(settings.valid_start, "Q"), pd.Period(settings.test_start, "Q")
    return labelled[tq < valid_start], labelled[(tq >= valid_start) & (tq < test_start)], labelled[tq >= test_start]


def fit(X, y, params, n_rounds, X_val=None, y_val=None):
    train_set = lgb.Dataset(X, y, categorical_feature=CATEGORICAL)
    if X_val is None:
        return lgb.train(params, train_set, num_boost_round=n_rounds)
    val_set = lgb.Dataset(X_val, y_val, reference=train_set)
    return lgb.train(
        params,
        train_set,
        num_boost_round=n_rounds,
        valid_sets=[val_set],
        callbacks=[lgb.early_stopping(100, verbose=False)],
    )


def evaluate(df: pd.DataFrame, pred: np.ndarray, name: str) -> dict[str, float]:
    out = metrics(df["rent"], df[TARGET], pred, name)
    headline = ((df["beds"] == "All bedrooms") & (df["property_type"] == "All property types")).to_numpy()
    out |= metrics(df.loc[headline, "rent"], df.loc[headline, TARGET], pred[headline], f"{name}_headline")
    return out


def plot_importance(model: lgb.Booster, path) -> None:
    imp = pd.Series(model.feature_importance("gain"), index=model.feature_name()).sort_values()
    fig, ax = plt.subplots(figsize=(7, 6))
    imp.plot.barh(ax=ax, color="#2a78d6")
    ax.set_title("LightGBM feature importance (gain)")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def plot_shap(model: lgb.Booster, X: pd.DataFrame, path) -> None:
    sample = X.sample(min(3000, len(X)), random_state=42)
    values = shap.TreeExplainer(model).shap_values(sample)
    shap.summary_plot(values, sample, show=False, max_display=15)
    plt.title("SHAP: drivers of 12-month rent growth")
    plt.tight_layout()
    plt.savefig(path, dpi=130)
    plt.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    rents = pd.read_parquet(settings.processed_dir / "rents.parquet")
    market = pd.read_parquet(settings.processed_dir / "county_market.parquet")
    df = build_features(rents, market)
    categories = {c: sorted(df[c].unique()) for c in CATEGORICAL}

    train, valid, test = split(df)
    log.info("train %d | valid %d | test %d", len(train), len(valid), len(test))
    Xtr, Xva, Xte = (to_model_frame(d, categories) for d in (train, valid, test))

    figs = settings.reports_dir / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment)

    with mlflow.start_run(run_name="lgbm-huber-h4"):
        mlflow.log_params(
            PARAMS
            | {
                "horizon_quarters": settings.horizon_quarters,
                "valid_start": settings.valid_start,
                "test_start": settings.test_start,
            }
        )
        results: dict[str, float] = {}

        # Baselines
        results |= evaluate(test, np.zeros(len(test)), "test_naive")
        results |= evaluate(
            test, test["growth_4q"].fillna(test["county_growth_4q"]).fillna(0).to_numpy(), "test_momentum"
        )

        # Tune rounds on validation, then refit on train+valid and score the untouched test set
        probe = fit(Xtr, train[TARGET], PARAMS, 5000, Xva, valid[TARGET])
        best_rounds = probe.best_iteration
        results |= evaluate(valid, probe.predict(Xva, num_iteration=best_rounds), "valid_lgbm")
        trval = pd.concat([train, valid])
        Xtrval = to_model_frame(trval, categories)
        model = fit(Xtrval, trval[TARGET], PARAMS, best_rounds)
        results |= evaluate(test, model.predict(Xte), "test_lgbm")

        # Ablation: how much do Property Price Register features add?
        no_ppr = [c for c in FEATURES if c not in PPR_FEATURES]
        ablation = fit(Xtrval[no_ppr], trval[TARGET], PARAMS, best_rounds)
        results |= evaluate(test, ablation.predict(Xte[no_ppr]), "test_lgbm_no_ppr")

        # Conformalized quantile regression: fit quantiles on train, calibrate width on valid,
        # then check coverage on the untouched test set
        qparams = {q: PARAMS | {"objective": "quantile", "alpha": q} for q in QUANTILES}
        lo_m, hi_m = (fit(Xtr, train[TARGET], qparams[q], best_rounds) for q in QUANTILES)
        conformal_pad = conformal_margin(valid[TARGET], lo_m.predict(Xva), hi_m.predict(Xva))
        lo, hi = lo_m.predict(Xte), hi_m.predict(Xte)
        results["test_raw_interval_coverage_pct"] = coverage(test[TARGET], lo, hi)
        results["test_interval_coverage_pct"] = coverage(test[TARGET], lo - conformal_pad, hi + conformal_pad)
        results["conformal_pad"] = conformal_pad

        mlflow.log_metric("best_rounds", best_rounds)
        mlflow.log_metrics(results)
        plot_importance(model, figs / "feature_importance.png")
        plot_shap(model, Xte, figs / "shap_summary.png")
        mlflow.log_artifacts(str(figs), artifact_path="figures")

        # Production model: refit on every labelled row so forecasts use the latest market regime
        labelled = df[df[TARGET].notna()]
        Xall = to_model_frame(labelled, categories)
        bundle = {
            "point": fit(Xall, labelled[TARGET], PARAMS, best_rounds),
            "quantiles": {q: fit(Xall, labelled[TARGET], qparams[q], best_rounds) for q in QUANTILES},
            "conformal_pad": conformal_pad,
            "categories": categories,
            "features": FEATURES,
            "horizon_quarters": settings.horizon_quarters,
            "data_through": str(df["quarter"].max()),
            "metrics": results,
        }
        settings.model_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(bundle, settings.model_dir / "rent_model.joblib")
        # Serve each series from its most recent observation in the last year (RTB suppresses
        # thin quarters and retired Dublin postal districts after 2021Q4)
        latest = (
            df[df["quarter"] > df["quarter"].max() - 4]
            .sort_values("quarter")
            .groupby(SERIES_KEY, observed=True)
            .tail(1)
            .drop(columns=[TARGET])
        )
        latest.assign(
            quarter=latest["quarter"].astype(str), target_quarter=latest["target_quarter"].astype(str)
        ).to_parquet(settings.model_dir / "latest_features.parquet", index=False)
        mlflow.log_artifact(str(settings.model_dir / "rent_model.joblib"), artifact_path="model")

        (settings.reports_dir / "metrics.json").write_text(json.dumps(results, indent=2))
        for k, v in sorted(results.items()):
            log.info("%-40s %.3f", k, v)


if __name__ == "__main__":
    main()
