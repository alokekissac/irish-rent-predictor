"""API tests run against the trained model artefacts; skipped if `make train` hasn't been run."""

import pytest
from fastapi.testclient import TestClient

from rentcast.config import settings

pytestmark = pytest.mark.skipif(not (settings.model_dir / "rent_model.joblib").exists(), reason="model not trained")


@pytest.fixture(scope="module")
def client():
    from rentcast.api.main import app

    return TestClient(app)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_forecast_county_headline(client):
    r = client.post("/forecast", json={"location": "Galway"})
    assert r.status_code == 200
    body = r.json()
    assert body["county"] == "Galway"
    assert body["lower_rent"] <= body["forecast_rent"] <= body["upper_rent"]


def test_forecast_unknown_location_404(client):
    assert client.post("/forecast", json={"location": "Atlantis"}).status_code == 404


def test_locations_filter_by_county(client):
    locs = client.get("/locations", params={"county": "sligo"}).json()
    assert locs and all(loc["county"] == "Sligo" for loc in locs)
