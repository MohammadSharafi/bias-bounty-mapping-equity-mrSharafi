"""Extra checks for the Best Bias Discovery entry (2026-11-01), all from public inputs: Overture places (challenge package)
and the USGS National Map Structures layers fetched by research/fetch_usgs_stations.py.
  1. control facilities: share of USGS schools and hospitals with no matching Overture place within 500 m (same rule as
     the fire stations: the facility's category, or its kind of name in any category);
  2. distance from every reference fire station to the nearest Overture fire place (no 1 km cap);
  3. Finding 1 with rural/urban also held fixed: rural-only cells and Mantel-Haenszel odds ratios stratified by
     region x rural x the other factor.
Writes report_discovery/checks.json. usage: PYTHONPATH=. .venv/bin/python research/discovery_checks.py"""
import json
import duckdb
import numpy as np
import pandas as pd
from model.features import PRJ
from model.features_fire import FIRE_NAME
import importlib.util

spec = importlib.util.spec_from_file_location("robust", "research/discovery_robust.py")
REGIONS = ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx"]
EXT = "data_public/external"
SCHOOL = "categories.primary IN ('elementary_school','middle_school','high_school','school','private_school','public_school') OR regexp_matches(lower(coalesce(names.primary,'')), 'school|academy')"
HOSP = "categories.primary IN ('hospital','medical_center','emergency_room') OR regexp_matches(lower(coalesce(names.primary,'')), 'hospital|medical center|health center')"
FIRE = f"categories.primary IN ('fire_department','fire_protection_service') OR regexp_matches(lower(coalesce(names.primary,'')), '{FIRE_NAME}')"
con = duckdb.connect(); con.sql("LOAD spatial")
pois = ", ".join(f"'data_public/reference/{r}/{r}-overture-pois.parquet'" for r in REGIONS)


def nearest(ref_csv, where, cap_m):
    """Distance (m) from each reference point to the nearest Overture place matching `where`, searched up to cap_m."""
    con.sql(f"CREATE OR REPLACE TABLE ov AS SELECT {PRJ.format(g='geometry')} g FROM read_parquet([{pois}]) WHERE {where}")
    con.sql(f"CREATE OR REPLACE TABLE rf AS SELECT permanent_identifier id, region, {PRJ.format(g='ST_Point(lon, lat)')} g FROM read_csv_auto('{ref_csv}')")
    return con.sql(f"""SELECT rf.id, rf.region, min(ST_Distance(rf.g, ov.g)) d FROM rf LEFT JOIN ov ON ST_DWithin(rf.g, ov.g, {cap_m})
                       GROUP BY 1, 2""").df()


out = {"control": {}}
for name, csv, where in (("schools", "usgs_schools.csv", SCHOOL), ("hospitals", "usgs_hospitals.csv", HOSP),
                         ("fire_stations", "usgs_fire_stations.csv", FIRE)):
    d = nearest(f"{EXT}/{csv}", where, 500)
    out["control"][name] = {"n": int(len(d)), "missing_500m": round(float(d.d.isna().mean()), 3)}

st = pd.read_csv("report_discovery/stations.csv")
far = nearest(f"{EXT}/usgs_fire_stations.csv", FIRE, 50000).rename(columns={"id": "id_", "d": "d_any"})
st = st.merge(far[["id_", "d_any"]], left_on="id", right_on="id_", how="left")
miss = st[st.missing]
out["distance_missing"] = {"n": int(len(miss)), "median_km": round(float(miss.d_any.median() / 1000), 1),
                           "share_over_5km": round(float((miss.d_any.isna() | (miss.d_any > 5000)).mean()), 3)}
for (ru, tr), g in miss.groupby(["rural", "tribal"]):
    out["distance_missing"][f"{'rural' if ru else 'urban'}_{'tribal' if tr else 'nontribal'}"] = {
        "n": int(len(g)), "median_km": round(float(g.d_any.median() / 1000), 1)}

q = float(st.usfs_WHP_mean.quantile(0.75)); st["top"] = st.usfs_WHP_mean >= q
out["whp_q75"] = round(q, 1)
cell = st[st.tribal & st.top]
out["tribal_top_by_region"] = {k: int(v) for k, v in cell.region.value_counts().items()}
out["rural_cells"] = {f"{'tribal' if t else 'nontribal'}|{'top' if h else 'lower'}": {"n": int(len(g)), "rate": round(float(g.missing.mean()), 3)}
                      for (t, h), g in st[st.rural].groupby(["tribal", "top"])}
rb = importlib.util.module_from_spec(spec)
src = open("research/discovery_robust.py").read().split("rates = {")[0]   # reuse mh() without re-running the script body
exec(compile(src, "discovery_robust.py", "exec"), rb.__dict__)
out["hazard_or_by_region_rural_tribal"] = rb.mh(st, "top", ["region", "rural", "tribal"])
out["tribal_or_by_region_rural_hazard"] = rb.mh(st, "tribal", ["region", "rural", "top"])
json.dump(out, open("report_discovery/checks.json", "w"), indent=1)
print(json.dumps(out, indent=1))
