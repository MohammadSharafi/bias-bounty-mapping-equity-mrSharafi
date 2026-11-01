"""Download the fire-station reference for the Best Bias Discovery entry from the public USGS National Map Structures
service (public domain), so judges can reproduce the analysis without the challenge-bucket copy that was removed on
2026-09-25. Layer 16 "Fire Stations/EMS Stations" (FCode 74026), queried by each region's tract bounding box and kept only
inside the region's tracts. Writes data_public/external/usgs_fire_stations.csv and prints the retrieval date.
The same service supplies the control facilities: --layer 23 --out usgs_schools.csv (Schools), --layer 14 --out
usgs_hospitals.csv (Hospitals/Medical Centers).
usage: .venv/bin/python research/fetch_usgs_stations.py [--layer N --out NAME.csv]"""
import datetime
import sys
import json
import urllib.parse
import urllib.request
import duckdb
import pandas as pd

LAYER = sys.argv[sys.argv.index("--layer") + 1] if "--layer" in sys.argv else "16"
OUT = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "usgs_fire_stations.csv"
URL = f"https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer/{LAYER}/query"
REGIONS = ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx"]
FIELDS = "PERMANENT_IDENTIFIER,NAME,ADDRESS,CITY,STATE,FCODE,LOADDATE"


def fetch(bbox):
    rows, offset = [], 0
    while True:
        q = {"where": "1=1", "geometry": json.dumps({"xmin": bbox[0], "ymin": bbox[1], "xmax": bbox[2], "ymax": bbox[3],
                                                     "spatialReference": {"wkid": 4326}}),
             "geometryType": "esriGeometryEnvelope", "spatialRel": "esriSpatialRelIntersects", "outFields": FIELDS,
             "returnGeometry": "true", "outSR": "4326", "resultOffset": offset, "resultRecordCount": 1000, "f": "json"}
        d = json.load(urllib.request.urlopen(URL + "?" + urllib.parse.urlencode(q), timeout=120))
        assert "error" not in d, d
        feats = d.get("features", [])
        rows += [{**{k.lower(): v for k, v in f["attributes"].items()}, "lon": f["geometry"]["x"], "lat": f["geometry"]["y"]} for f in feats]
        if not d.get("exceededTransferLimit") and len(feats) < 1000:
            return rows
        offset += len(feats)


con = duckdb.connect(); con.sql("LOAD spatial")
out = []
for R in REGIONS:
    tr = f"data_public/strata/{R}/{R}-census-tracts.parquet"
    bbox = con.sql(f"SELECT min(ST_XMin(geometry)), min(ST_YMin(geometry)), max(ST_XMax(geometry)), max(ST_YMax(geometry)) FROM '{tr}'").fetchone()
    df = pd.DataFrame(fetch(bbox))
    con.register("s", df)
    inside = con.sql(f"""SELECT s.*, t.GEOID FROM s JOIN '{tr}' t ON ST_Contains(t.geometry, ST_Point(s.lon, s.lat))""").df()
    inside["region"] = R
    print(R, "bbox", len(df), "inside tracts", len(inside))
    out.append(inside)
res = pd.concat(out, ignore_index=True)
res["retrieved"] = datetime.date.today().isoformat()
res.to_csv(f"data_public/external/{OUT}", index=False)
print("total", len(res), "retrieved", res.retrieved.iloc[0])
