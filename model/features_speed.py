"""Fast un-routed arterials among highway-class roads, from the permitted Overture roads.

The reference's secondary-road class is defined by function ("main arteries ... one or more lanes
each direction"), not by route number alone, so part of the un-routed highway-class length belongs
in the reference estimate (t_beta = 0.17 today, applied uniformly). Overture carries a posted
speed limit on 25-40% of highway-class length; an un-routed arterial posted at 45 mph or more is
a better candidate for the reference class than a 30 mph street. Per tract: clipped length of
un-routed highway-class roads whose first speed-limit rule is at least 45 mph
(`len_hwy_fast_unrouted`) and the clipped length of un-routed highway-class roads carrying any
speed limit (`len_hwy_speed_unrouted`, the denominator that separates "untagged" from "slow").
"""
import sys
import pandas as pd
from . import paths as P
from .features import PRJ, RT_CASE, HWY


def build(con, region):
    hwy = "','".join(HWY)
    con.sql(f"CREATE OR REPLACE TABLE tp AS SELECT GEOID, {PRJ.format(g='geometry')} g FROM '{P.strata(region, 'census-tracts')}'")
    con.sql(f"""CREATE OR REPLACE TABLE sp AS SELECT g, maxv FROM (
        SELECT {RT_CASE} AS rt, coalesce(speed_limits[1].max_speed.value, 0) maxv, {PRJ.format(g='geometry')} g
        FROM '{P.ref(region, 'overture-roads-unfiltered')}' WHERE class IN ('{hwy}'))
        WHERE rt = 'none' AND maxv > 0""")
    df = con.sql("""SELECT t.GEOID,
                           sum(ST_Length(ST_Intersection(r.g, t.g))) len_hwy_speed_unrouted,
                           sum(CASE WHEN r.maxv >= 45 THEN ST_Length(ST_Intersection(r.g, t.g)) ELSE 0 END) len_hwy_fast_unrouted
                    FROM tp t JOIN sp r ON ST_Intersects(t.g, r.g) GROUP BY 1""").df()
    scored = con.sql(f"SELECT GEOID FROM read_csv('{P.ref(region, 'sample-submission', 'csv')}', types={{'GEOID':'VARCHAR'}})").df()
    df = scored.merge(df, on="GEOID", how="left").fillna(0.0)
    df["region"] = region
    print(f"[{region}] {len(df)} rows; tracts with fast un-routed length: {(df.len_hwy_fast_unrouted > 0).sum()}", flush=True)
    return df


def main(out="out2/features_speed.parquet"):
    con = P.connect()
    df = pd.concat([build(con, r) for r in P.REGIONS], ignore_index=True)
    assert len(df) == P.TOTAL_SCORED, df.shape
    df.to_parquet(out, index=False); print("wrote", out, df.shape)


if __name__ == "__main__":
    main(*sys.argv[1:])
