"""REST API serving 12-month Irish rent forecasts."""

from dataclasses import asdict
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from rentcast import __version__
from rentcast.predict import Forecaster, UnknownSeriesError, get_forecaster

app = FastAPI(
    title="RentCast Ireland API",
    description="12-month rent forecasts for every RTB location, built on CSO/RTB and Property Price Register data.",
    version=__version__,
)

ForecasterDep = Annotated[Forecaster, Depends(get_forecaster)]


class ForecastRequest(BaseModel):
    location: str = Field(examples=["Dublin 8"])
    beds: str = Field("All bedrooms", examples=["Two bed"])
    property_type: str = Field("All property types", examples=["Apartment"])


class ForecastResponse(BaseModel):
    location: str
    county: str
    beds: str
    property_type: str
    current_quarter: str
    current_rent: float
    forecast_quarter: str
    forecast_rent: float
    lower_rent: float = Field(description="Lower bound of the calibrated ~80% interval")
    upper_rent: float = Field(description="Upper bound of the calibrated ~80% interval")
    growth_pct: float


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/model")
def model_info(fc: ForecasterDep) -> dict:
    return fc.info


@app.get("/locations")
def locations(fc: ForecasterDep, county: str | None = Query(None, examples=["Galway"])) -> list[dict]:
    locs = fc.locations()
    if county:
        locs = locs[locs["county"].str.lower() == county.lower()]
    return locs.to_dict(orient="records")


@app.get("/locations/{location}/options")
def options(location: str, fc: ForecasterDep) -> list[dict]:
    try:
        return fc.options(location).round(2).to_dict(orient="records")
    except UnknownSeriesError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@app.post("/forecast", response_model=ForecastResponse)
def forecast(req: ForecastRequest, fc: ForecasterDep) -> ForecastResponse:
    try:
        return ForecastResponse(**asdict(fc.forecast(req.location, req.beds, req.property_type)))
    except UnknownSeriesError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
