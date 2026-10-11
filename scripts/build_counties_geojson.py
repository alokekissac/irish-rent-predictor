"""One-off: turn Tailte Éireann county boundaries (ITM, 20 m) into a light WGS84 GeoJSON for the dashboard.

Source: Counties - National Statutory Boundaries - 2019 - Generalised 20m (CC BY 4.0)
https://data.gov.ie/dataset/counties-national-statutory-boundaries-2019-generalised-20m1

Usage: uv run --with shapely --with pyproj python scripts/build_counties_geojson.py <downloaded.geojson>
"""

import json
import sys
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import MultiPolygon, mapping, shape
from shapely.ops import transform

OUT = Path(__file__).resolve().parents[1] / "dashboard" / "assets" / "ireland_counties.geojson"
TOLERANCE_M = 700
MIN_ISLAND_M2 = 3_000_000  # drop islets under 3 km² (invisible at county scale)


def round_coords(obj, ndigits=3):
    if isinstance(obj, (list, tuple)):
        if obj and isinstance(obj[0], float):
            return [round(v, ndigits) for v in obj]
        return [round_coords(o, ndigits) for o in obj]
    return obj


def main(src: str) -> None:
    to_wgs84 = Transformer.from_crs("EPSG:2157", "EPSG:4326", always_xy=True).transform
    features = []
    for feat in json.loads(Path(src).read_text())["features"]:
        geom = shape(feat["geometry"])
        if isinstance(geom, MultiPolygon):
            geom = MultiPolygon([p for p in geom.geoms if p.area >= MIN_ISLAND_M2])
        geom = geom.simplify(TOLERANCE_M, preserve_topology=True)
        geom = mapping(transform(to_wgs84, geom))
        geom["coordinates"] = round_coords(geom["coordinates"])
        county = feat["properties"]["COUNTY"].title()
        features.append(
            {
                "type": "Feature",
                "id": county,
                "properties": {"county": county, "province": feat["properties"]["PROVINCE"]},
                "geometry": geom,
            }
        )
    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")))
    print(f"{len(features)} counties -> {OUT} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main(sys.argv[1])
