"""Frontage roads among un-routed highway-class roads, from the permitted Overture roads.

The transport reference estimate adds a fraction (t_beta) of un-routed highway-class length,
standing in for arterials that the reference's secondary-road class contains. In Texas a large
share of that length is interstate frontage roads, digitised as secondary or tertiary and named
after the interstate ("North Interstate 35", "I-35 Frontage Road"). Frontage roads are service
drives, not primary or secondary roads, so they belong in Overture's count but not in the
reference estimate. Per tract: clipped length of un-routed highway-class roads whose name marks
them as frontage/service/access roads or names an interstate (`len_hwy_frontage`).
"""
import sys
import pandas as pd
from . import paths as P
from .features import PRJ, RT_CASE, HWY

FRONTAGE = r"frontage|service r(oa)?d|\baccess\b|interstate|\bi-? ?\d+"


def build(con, region):
    hwy = "','".join(HWY)
    con.sql(f"CREATE OR REPLACE TABLE tp AS SELECT GEOID, {PRJ.format(g='geometry')} g FROM '{P.strata(region, 'census-tracts')}'")
    con.sql(f"""CREATE OR REPLACE TABLE fr AS SELECT g FROM (
        SELECT {RT_CASE} AS rt, lower(coalesce(names.primary, '')) nm, {PRJ.format(g='geometry')} g
        FROM '{P.ref(region, 'overture-roads-unfiltered')}' WHERE class IN ('{hwy}'))
        WHERE rt = 'none' AND regexp_matches(nm, '{FRONTAGE}')""")
    df = con.sql("""SELECT t.GEOID, sum(ST_Length(ST_Intersection(r.g, t.g))) len_hwy_frontage
                    FROM tp t JOIN fr r ON ST_Intersects(t.g, r.g) GROUP BY 1""").df()
    scored = con.sql(f"SELECT GEOID FROM read_csv('{P.ref(region, 'sample-submission', 'csv')}', types={{'GEOID':'VARCHAR'}})").df()
    df = scored.merge(df, on="GEOID", how="left").fillna(0.0)
    df["region"] = region
    print(f"[{region}] {len(df)} rows; tracts with frontage length: {(df.len_hwy_frontage > 0).sum()}", flush=True)
    return df


def main(out="out2/features_names.parquet"):
    con = P.connect()
    df = pd.concat([build(con, r) for r in P.REGIONS], ignore_index=True)
    df.to_parquet(out, index=False); print("wrote", out, df.shape)


if __name__ == "__main__":
    main(*sys.argv[1:])
