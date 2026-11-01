"""One-way routed road length per tract, from the permitted Overture roads.

Overture (OpenStreetMap) draws a divided highway as two one-way carriageways, and both carry the
route, so routed length counts a divided road twice. If the reference draws one centreline, the
reference estimate built from routed length is too long exactly where routes are divided. Per
tract: clipped length of routed segments that deny travel backwards (`len_rt_oneway`), for the
route groups the estimate uses (Interstate / US / state and state sub-networks).
"""
import sys
import pandas as pd
from . import paths as P
from .features import PRJ, RT_CASE


def build(con, region):
    con.sql(f"CREATE OR REPLACE TABLE tp AS SELECT GEOID, {PRJ.format(g='geometry')} g FROM '{P.strata(region, 'census-tracts')}'")
    con.sql(f"""CREATE OR REPLACE TABLE ow AS SELECT g FROM (
        SELECT {RT_CASE} AS rt, {PRJ.format(g='geometry')} g,
               len(list_filter(coalesce(access_restrictions, []),
                   x -> x.access_type = 'denied' AND x.when.heading = 'backward')) > 0 AS oneway
        FROM '{P.ref(region, 'overture-roads-unfiltered')}'
        WHERE class NOT IN ('footway','path','steps','cycleway','pedestrian','bridleway','living_street'))
        WHERE oneway AND rt IN ('interstate','us','state','statesub')""")
    df = con.sql("""SELECT t.GEOID, sum(ST_Length(ST_Intersection(r.g, t.g))) len_rt_oneway
                    FROM tp t JOIN ow r ON ST_Intersects(t.g, r.g) GROUP BY 1""").df()
    scored = con.sql(f"SELECT GEOID FROM read_csv('{P.ref(region, 'sample-submission', 'csv')}', types={{'GEOID':'VARCHAR'}})").df()
    df = scored.merge(df, on="GEOID", how="left").fillna(0.0)
    print(f"[{region}] {len(df)} rows; tracts with one-way routed length: {(df.len_rt_oneway > 0).sum()}", flush=True)
    return df


def main(out="out2/features_oneway.parquet"):
    con = P.connect()
    df = pd.concat([build(con, r) for r in P.REGIONS], ignore_index=True)
    df.to_parquet(out, index=False); print("wrote", out, df.shape)


if __name__ == "__main__":
    main(*sys.argv[1:])
