"""Central configuration. Override any value with an env var prefixed RENTCAST_."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RENTCAST_", env_file=".env", extra="ignore")

    data_dir: Path = ROOT / "data"
    model_dir: Path = ROOT / "models"
    reports_dir: Path = ROOT / "reports"
    mlflow_tracking_uri: str = f"sqlite:///{ROOT / 'mlflow.db'}"
    mlflow_experiment: str = "irish-rent-forecast"

    cso_rent_table: str = "RIQ02"  # RTB Average Monthly Rent Report, quarterly
    cso_api: str = "https://ws.cso.ie/public/api.restful/PxStat.Data.Cube_API.ReadDataset/{table}/JSON-stat/2.0/en"
    ppr_url: str = (
        "https://www.propertypriceregister.ie/website/npsra/ppr/npsra-ppr.nsf/Downloads/PPR-ALL.zip/$FILE/PPR-ALL.zip"
    )

    horizon_quarters: int = 4  # forecast rent 12 months ahead
    valid_start: str = "2023Q1"
    test_start: str = "2024Q1"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"


settings = Settings()
