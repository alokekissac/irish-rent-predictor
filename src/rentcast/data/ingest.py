"""Download raw data from the CSO PxStat API (RTB rents) and the Property Price Register."""

import io
import json
import logging
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from rentcast.config import settings

log = logging.getLogger(__name__)


def jsonstat_to_frame(payload: dict) -> pd.DataFrame:
    """Flatten a JSON-stat 2.0 dataset into a long DataFrame (one column per dimension + value)."""
    dims = payload["id"]
    sizes = payload["size"]
    labels = {}
    for dim in dims:
        cat = payload["dimension"][dim]["category"]
        labels[payload["dimension"][dim]["label"]] = [cat["label"][code] for code in cat["index"]]

    grids = np.meshgrid(*[np.arange(n) for n in sizes], indexing="ij")
    df = pd.DataFrame(
        {name: np.asarray(vals, dtype=object)[g.ravel()] for (name, vals), g in zip(labels.items(), grids, strict=True)}
    )
    df["value"] = pd.to_numeric(pd.Series(payload["value"], dtype="object"), errors="coerce")
    return df.dropna(subset=["value"]).reset_index(drop=True)


def fetch_rtb_rents(out_dir: Path | None = None) -> Path:
    out_dir = out_dir or settings.raw_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    url = settings.cso_api.format(table=settings.cso_rent_table)
    log.info("Fetching %s", url)
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    df = jsonstat_to_frame(resp.json())
    path = out_dir / "rtb_rents.parquet"
    df.to_parquet(path, index=False)
    log.info("Saved %d rent observations -> %s", len(df), path)
    return path


def fetch_ppr(out_dir: Path | None = None) -> Path:
    out_dir = out_dir or settings.raw_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    log.info("Fetching Property Price Register")
    resp = requests.get(settings.ppr_url, timeout=300)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        raw = zf.read(name)
    df = pd.read_csv(io.BytesIO(raw), encoding="latin-1", dtype=str)
    df.columns = [
        "date_of_sale",
        "address",
        "county",
        "eircode",
        "price",
        "not_full_market_price",
        "vat_exclusive",
        "description",
        "size_description",
    ]
    path = out_dir / "ppr.parquet"
    df.to_parquet(path, index=False)
    log.info("Saved %d property sales -> %s", len(df), path)
    return path


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    fetch_rtb_rents()
    fetch_ppr()
    (settings.raw_dir / "manifest.json").write_text(
        json.dumps({"rtb_table": settings.cso_rent_table, "ppr_url": settings.ppr_url}, indent=2)
    )


if __name__ == "__main__":
    main()
