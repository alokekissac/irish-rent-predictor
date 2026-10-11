import numpy as np

from rentcast.features import FEATURES, TARGET, build_features, to_model_frame


def test_target_is_future_log_growth(toy_rents, toy_market):
    df = build_features(toy_rents, toy_market, horizon=4)
    row = df[(df["location"] == "Bandon, Cork") & (df["quarter"].astype(str) == "2020Q1")].iloc[0]
    assert np.isclose(row[TARGET], 4 * np.log(1.01))
    assert str(row["target_quarter"]) == "2021Q1"


def test_features_only_use_past(toy_rents, toy_market):
    df = build_features(toy_rents, toy_market, horizon=4)
    first = df[df["quarter"].astype(str) == "2020Q1"]
    # Nothing exists before the first quarter, so every lagged feature must be missing
    assert first[["growth_1q", "growth_4q"]].isna().all().all()
    last = df[df["quarter"] == df["quarter"].max()]
    assert last[TARGET].isna().all()


def test_county_context_joined(toy_rents, toy_market):
    df = build_features(toy_rents, toy_market, horizon=4)
    town = df[(df["location"] == "Bandon, Cork") & (df["quarter"].astype(str) == "2021Q1")].iloc[0]
    assert np.isclose(town["county_growth_4q"], 4 * np.log(1.01))
    assert np.isclose(town["rel_to_county"], np.log(0.8))


def test_model_frame_uses_fixed_categories(toy_rents, toy_market):
    df = build_features(toy_rents, toy_market)
    cats = {
        c: ["Bandon, Cork", "Cork", "Unseen"] if c == "location" else sorted(df[c].unique())
        for c in ["county", "level", "beds", "property_type", "location"]
    }
    X = to_model_frame(df, cats)
    assert list(X.columns) == FEATURES
    assert list(X["location"].cat.categories) == ["Bandon, Cork", "Cork", "Unseen"]
