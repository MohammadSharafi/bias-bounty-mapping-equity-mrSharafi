"""Fire-station and school building footprints per tract, from the permitted Overture buildings.

Overture building footprints carry OpenStreetMap's building `class`. A footprint of class
`fire_station` marks a real station independently of the places layer, so a tract with such a
building but no `fire_department` place almost surely has a reference fire station that the
category match misses. Per tract (centroid in tract): `n_fire_bld`, `n_school_bld`.
"""
import sys
import pandas as pd
from . import paths as P


def build(con, region):
    df = con.sql(f"""
        SELECT t.GEOID,
               sum((b.class = 'fire_station')::INT) n_fire_bld,
               sum((b.class = 'school')::INT) n_school_bld
        FROM (SELECT class, ST_Centroid(geometry) c FROM '{P.ref(region, 'overture-buildings')}'
              WHERE class IN ('fire_station', 'school')) b
        JOIN '{P.strata(region, 'census-tracts')}' t ON ST_Intersects(t.geometry, b.c)
        GROUP BY 1""").df()
    scored = con.sql(f"SELECT GEOID FROM read_csv('{P.ref(region, 'sample-submission', 'csv')}', types={{'GEOID':'VARCHAR'}})").df()
    df = scored.merge(df, on="GEOID", how="left").fillna(0)
    df["region"] = region
    print(f"[{region}] {len(df)} rows; tracts with a fire-station building: {(df.n_fire_bld > 0).sum()}", flush=True)
    return df


def main(out="out2/features_fire.parquet"):
    con = P.connect()
    df = pd.concat([build(con, r) for r in P.REGIONS], ignore_index=True)
    df.to_parquet(out, index=False); print("wrote", out, df.shape)




# Places whose name says fire station but whose category is neither fire_department nor
# fire_protection_service: the reference facility layer lists the station, the category match does not.
FIRE_NAME = (r"(fire (dept|department|station|rescue|district|protection|company|hall)|volunteer fire|\bvfd\b|"
             r"\bv\.f\.d\b|emergency services district|\besd ?#?\d|fire & rescue|fire and rescue|fire[- ]rescue)")
NOT_STATION = ("restaurant", "bar", "american_restaurant", "fast_food_restaurant", "pizza_restaurant", "cafe",
               "coffee_shop", "sandwich_shop", "barbecue_restaurant", "grocery_store", "printing_services",
               "real_estate_service", "home_security", "building_supply_store", "contractor")


def names(out="out2/features_firename.parquet"):
    con = P.connect()
    excl = "','".join(("fire_department", "fire_protection_service") + NOT_STATION)
    dfs = []
    for region in P.REGIONS:
        df = con.sql(f"""
            WITH p AS (SELECT geometry g FROM '{P.ref(region, 'overture-pois')}'
                       WHERE regexp_matches(lower(names.primary), '{FIRE_NAME}')
                         AND coalesce(categories.primary, '') NOT IN ('{excl}'))
            SELECT t.GEOID, count(*) n_fire_name FROM p JOIN '{P.strata(region, 'census-tracts')}' t
            ON ST_Intersects(t.geometry, p.g) GROUP BY 1""").df()
        dfs.append(df)
        print(f"[{region}] tracts with a fire-named place in another category: {len(df)}", flush=True)
    pd.concat(dfs).to_parquet(out, index=False); print("wrote", out)


if __name__ == "__main__":
    names() if sys.argv[1:2] == ["names"] else main(*sys.argv[1:])
