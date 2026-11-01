"""Simplified tract outlines with tribal status and wildfire hazard, for the Bias Discovery maps (permitted strata
files only). Writes report_discovery/tracts_simple.json. usage: .venv/bin/python research/discovery_tracts.py"""
import json
import duckdb

REGIONS = ["eastern-ok", "northern-ca", "south-central-tx", "maricopa-az"]
con = duckdb.connect(); con.sql("LOAD spatial")
out = {}
for r in REGIONS:
    rows = con.sql(f"""
        SELECT t.GEOID, s.tribal_any, s.usfs_WHP_mean,
               ST_AsGeoJSON(ST_SimplifyPreserveTopology(t.geometry, 0.003)) AS g
        FROM 'data_public/strata/{r}/{r}-census-tracts.parquet' t
        JOIN 'data_public/strata/{r}/{r}-strata-tract-table.parquet' s USING (GEOID)""").fetchall()
    out[r] = [{"GEOID": g, "tribal": bool(tr), "whp": w, "geom": json.loads(js)} for g, tr, w, js in rows]
    print(r, len(rows), "tracts,", sum(x["tribal"] for x in out[r]), "tribal")
json.dump(out, open("report_discovery/tracts_simple.json", "w"))
