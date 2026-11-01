"""Footprint area by source, from the permitted Overture buildings.

Overture keeps one footprint per building, preferring OpenStreetMap and Esri Community Maps over
Microsoft ML footprints where they overlap. Where an OSM or Esri footprint outlines several
structures (a block, a complex), the Microsoft footprints it replaced are no longer counted. The
size of each source's footprints relative to the Microsoft footprints in the same tract estimates
how many Microsoft footprints a replacing footprint hides. Per tract and source (ms, osm, esri):
count and total planar area (EPSG:5070), by centroid, like model.features.
"""
import sys
import pandas as pd
from . import paths as P
from .features import PRJ

SRC = {"ms": "Microsoft ML Buildings", "osm": "OpenStreetMap", "esri": "Esri Community Maps"}


def build(con, region):
    con.sql(f"CREATE OR REPLACE TABLE tp AS SELECT GEOID, geometry FROM '{P.strata(region, 'census-tracts')}'")
    cols = ",\n".join(f"sum(CASE WHEN src='{v}' THEN a ELSE 0 END) area_{k}" for k, v in SRC.items())
    df = con.sql(f"""SELECT t.GEOID, {cols}
        FROM (SELECT sources[1].dataset src, ST_Area({PRJ.format(g='geometry')}) a, ST_Centroid(geometry) c
              FROM '{P.ref(region, 'overture-buildings')}') b
        JOIN tp t ON ST_Intersects(t.geometry, b.c) GROUP BY 1""").df()
    scored = con.sql(f"SELECT GEOID FROM read_csv('{P.ref(region, 'sample-submission', 'csv')}', types={{'GEOID':'VARCHAR'}})").df()
    df = scored.merge(df, on="GEOID", how="left").fillna(0.0)
    df["region"] = region
    print(f"[{region}] {len(df)} rows", flush=True)
    return df


def main(out="out2/features_bldarea.parquet"):
    con = P.connect()
    df = pd.concat([build(con, r) for r in P.REGIONS], ignore_index=True)
    assert len(df) == P.TOTAL_SCORED, df.shape
    df.to_parquet(out, index=False); print("wrote", out, df.shape)


if __name__ == "__main__":
    main(*sys.argv[1:])
