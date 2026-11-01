"""Boundary-highway features from the permitted Overture roads layer.

Census tract boundaries are frequently drawn along highways, and the reference
road layer shares geometry with the tract boundaries it comes from, so a
boundary highway is counted in both adjacent tracts there. Overture segments
are independently digitised and fall a few metres to one side, so Overture
counts the road in one tract only. The tract on the other side then shows a
transport gap that has nothing to do with mapping effort. These features
measure, per tract, the highway-class length lying just outside the tract
within `BUF` metres of its boundary (`len_hwy_near_out`) and the part just
inside (`len_hwy_near_in`).
"""
import sys
import pandas as pd
from . import paths as P
from .features import PRJ, HWY

BUF = 25.0
MIN_PIECE = 80.0


def build(con, region):
    hwy = "','".join(HWY)
    con.sql(f"CREATE OR REPLACE TABLE tp AS SELECT GEOID, {PRJ.format(g='geometry')} g FROM '{P.strata(region, 'census-tracts')}'")
    con.sql(f"CREATE OR REPLACE TABLE hp AS SELECT {PRJ.format(g='geometry')} g FROM '{P.ref(region, 'overture-roads')}' WHERE class IN ('{hwy}')")
    con.sql(f"CREATE OR REPLACE TABLE ring AS SELECT GEOID, g, ST_Buffer(ST_Boundary(g), {BUF}) ring FROM tp")
    # a road that merely crosses the boundary leaves at most ~35 m inside the 25 m band;
    # only pieces longer than MIN_PIECE are counted, so the sums measure roads that run
    # along the boundary.
    df = con.sql(f"""
        WITH pieces AS (
            SELECT t.GEOID,
                   ST_Length(ST_Intersection(r.g, ST_Difference(t.ring, t.g))) l_out,
                   ST_Length(ST_Intersection(r.g, ST_Intersection(t.ring, t.g))) l_in
            FROM ring t JOIN hp r ON ST_Intersects(t.ring, r.g))
        SELECT GEOID,
               sum(CASE WHEN l_out > {MIN_PIECE} THEN l_out ELSE 0 END) len_hwy_near_out,
               sum(CASE WHEN l_in > {MIN_PIECE} THEN l_in ELSE 0 END) len_hwy_near_in
        FROM pieces GROUP BY 1""").df()
    scored = con.sql(f"SELECT GEOID FROM read_csv('{P.ref(region, 'sample-submission', 'csv')}', types={{'GEOID':'VARCHAR'}})").df()
    df = scored.merge(df, on="GEOID", how="left").fillna(0.0)
    df["region"] = region
    print(f"[{region}] {len(df)} rows; tracts with near_out>0: {(df.len_hwy_near_out>0).sum()}", flush=True)
    return df


def main(regions=None, out="out2/features_extra.parquet", buf=None, min_piece=None):
    global BUF, MIN_PIECE
    if buf: BUF = float(buf)
    if min_piece: MIN_PIECE = float(min_piece)
    con = P.connect()
    df = pd.concat([build(con, r) for r in (regions or P.REGIONS)], ignore_index=True)
    df.to_parquet(out, index=False); print("wrote", out, df.shape)


if __name__ == "__main__":
    # usage: python -m model.features_extra [out] [buf]
    main(None, *(sys.argv[1:] or []))
