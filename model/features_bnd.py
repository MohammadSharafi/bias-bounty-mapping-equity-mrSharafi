"""Numbered-route roads running along tract boundaries, from the permitted Overture roads.

Extends features_extra (highway-class roads along the boundary) to route networks, of any
class. Census tract boundaries follow many state and US highways, and the reference road
layer shares geometry with the tract boundaries, so such a road is counted in both adjacent
tracts there and makes both of them transport-defined. Overture digitises the road a few
metres to one side, so the tract on the other side has no routed length inside it and the
point model calls its transport component undefined.

Per tract, for route groups strong (Interstate, US, state), sub (state sub-networks such as
Texas FM/RM/Loop) and county: the routed length lying within BUF metres outside the boundary
(`rtb_out_<group>`) and inside it (`rtb_in_<group>`), counting only pieces longer than
MIN_PIECE so that roads which merely cross the boundary are excluded.
"""
import sys
import pandas as pd
from . import paths as P
from .features import PRJ, RT_CASE

BUF = 25.0
MIN_PIECE = 80.0
GROUPS = {"strong": ("interstate", "us", "state"), "sub": ("statesub",), "county": ("county",)}


def build(con, region):
    con.sql(f"CREATE OR REPLACE TABLE tp AS SELECT GEOID, {PRJ.format(g='geometry')} g FROM '{P.strata(region, 'census-tracts')}'")
    con.sql(f"""CREATE OR REPLACE TABLE rr AS SELECT rt, g FROM (
        SELECT {RT_CASE} AS rt, {PRJ.format(g='geometry')} g
        FROM '{P.ref(region, 'overture-roads-unfiltered')}'
        WHERE class NOT IN ('footway','path','steps','cycleway','pedestrian','bridleway','living_street'))
        WHERE rt IN ('interstate','us','state','statesub','county')""")
    con.sql(f"CREATE OR REPLACE TABLE ring AS SELECT GEOID, g, ST_Buffer(ST_Boundary(g), {BUF}) ring FROM tp")
    grp = " ".join("WHEN r.rt IN ('" + "','".join(v) + f"') THEN '{k}'" for k, v in GROUPS.items())
    cols = ", ".join(f"sum(CASE WHEN grp='{k}' AND l_{s} > {MIN_PIECE} THEN l_{s} ELSE 0 END) rtb_{s}_{k}"
                     for k in GROUPS for s in ("out", "in"))
    df = con.sql(f"""
        WITH pieces AS (
            SELECT t.GEOID, CASE {grp} END grp,
                   ST_Length(ST_Intersection(r.g, ST_Difference(t.ring, t.g))) l_out,
                   ST_Length(ST_Intersection(r.g, ST_Intersection(t.ring, t.g))) l_in
            FROM ring t JOIN rr r ON ST_Intersects(t.ring, r.g))
        SELECT GEOID, {cols} FROM pieces GROUP BY 1""").df()
    scored = con.sql(f"SELECT GEOID FROM read_csv('{P.ref(region, 'sample-submission', 'csv')}', types={{'GEOID':'VARCHAR'}})").df()
    df = scored.merge(df, on="GEOID", how="left").fillna(0.0)
    df["region"] = region
    print(f"[{region}] {len(df)} rows; tracts with strong road along the outside: {(df.rtb_out_strong > 0).sum()}", flush=True)
    return df


def main(out="out2/features_bnd.parquet", buf=None):
    global BUF
    if buf: BUF = float(buf)
    con = P.connect()
    df = pd.concat([build(con, r) for r in P.REGIONS], ignore_index=True)
    df.to_parquet(out, index=False); print("wrote", out, df.shape)


if __name__ == "__main__":
    main(*sys.argv[1:])
