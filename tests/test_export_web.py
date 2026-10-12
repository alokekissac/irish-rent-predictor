"""The static web app indexes several JSON files by series position; they must stay aligned."""

import json

import pytest

from rentcast.config import ROOT

DATA = ROOT / "web" / "public" / "data"
pytestmark = pytest.mark.skipif(not (DATA / "meta.json").exists(), reason="web data not exported")


def load(name):
    return json.loads((DATA / name).read_text())


def test_exported_files_are_aligned():
    meta, series, history, whatif, bt = (
        load(n) for n in ["meta.json", "series.json", "history.json", "whatif.json", "backtest.json"]
    )
    n = len(series)
    assert meta["n_series"] == n == len(history)
    assert all(len(row) == len(meta["quarters"]) for row in history)
    assert set(whatif) == set(meta["scenario_features"])
    for curves in whatif.values():
        assert len(curves) == n and all(len(c) == len(meta["whatif_grid"]) for c in curves)
    assert all(len(s["shap"]) == len(meta["features"]) for s in series)
    assert len({len(bt[k]) for k in ["sid", "county", "level", "beds", "tq", "actual", "pred", "lo", "hi"]}) == 1
    assert max(bt["sid"]) < n


def test_series_values_are_consistent():
    for s in load("series.json"):
        assert s["lo"] <= s["f"] <= s["hi"]
        # growth is rounded to 2 dp, so allow for that rounding on large rents
        assert abs(s["rent"] * (1 + s["g"] / 100) - s["f"]) <= s["rent"] * 0.00005 + 0.01
