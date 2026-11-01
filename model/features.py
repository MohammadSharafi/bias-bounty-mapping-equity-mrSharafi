"""Per-tract features from the permitted layers only (see paths.PERMITTED_LAYERS).

One row per scored tract. Lengths are planar metres after projecting tract polygons
and road segments to EPSG:5070 and clipping in projected space. Points (building
centroids, places) are assigned with ST_Intersects against the lon/lat polygon.
"""
import sys
import pandas as pd
from . import paths as P

PRJ = "ST_Transform({g},'EPSG:4326','EPSG:5070',always_xy:=true)"

HWY = ("motorway", "trunk", "primary", "secondary")
ROAD_CLASSES = HWY + ("tertiary", "unclassified", "residential", "service", "track")
RT_CASE = """CASE WHEN routes IS NULL OR len(routes)=0 THEN 'none'
                    WHEN len(list_filter(routes, r -> r.network = 'US:I' OR r.network LIKE 'US:I:%')) > 0 THEN 'interstate'
                    WHEN len(list_filter(routes, r -> r.network = 'US:US' OR r.network LIKE 'US:US:%')) > 0 THEN 'us'
                    WHEN len(list_filter(routes, r -> regexp_matches(r.network, '^US:[A-Z]{2}$'))) > 0 THEN 'state'
                    WHEN len(list_filter(routes, r -> regexp_matches(r.network, '^US:[A-Z]{2}:(FM|RM|Loop|Spur|Business|Beltway|Toll|Park|Scenic|Alt|Alternate|Historic|Old|Truck|Bypass)'))) > 0 THEN 'statesub'
                    WHEN len(list_filter(routes, r -> regexp_matches(r.network, '^US:[A-Z]{2}:'))) > 0 THEN 'county'
                    WHEN len(list_filter(routes, r -> r.network = 'US:BIA' OR r.network LIKE 'US:BIA:%')) > 0 THEN 'bia'
                    ELSE 'other' END"""

SCHOOL_CATS = ("elementary_school", "middle_school", "high_school", "school",
               "private_school", "public_school")


def build(con, region, verbose=True):
    say = (lambda *a: print(f"[{region}]", *a, flush=True)) if verbose else (lambda *a: None)
    con.sql(f"""CREATE OR REPLACE TABLE tracts AS
        SELECT GEOID, ALAND, pop_total, pct_urban, ur_class, frac_inside_aoi, geometry,
               ST_Area({PRJ.format(g='geometry')}) area_m2
        FROM '{P.strata(region, 'census-tracts')}'""")
    con.sql(f"""CREATE OR REPLACE TABLE scored AS SELECT GEOID FROM
        read_csv('{P.ref(region, "sample-submission", "csv")}', types={{'GEOID': 'VARCHAR'}})""")
    con.sql(f"CREATE OR REPLACE TABLE tp AS SELECT GEOID, {PRJ.format(g='geometry')} g FROM tracts")

    # ---- roads: per-class and per-route-network clipped lengths ------------
    say("roads")
    cls_case = " ".join(f"WHEN class='{c}' THEN '{c}'" for c in ROAD_CLASSES)
    con.sql(f"""CREATE OR REPLACE TABLE roads AS
        SELECT CASE {cls_case} ELSE 'other' END AS cls,
               {RT_CASE} AS rt,
               names.primary IS NOT NULL AS named,
               {PRJ.format(g='geometry')} g
        FROM '{P.ref(region, 'overture-roads-unfiltered')}'
        WHERE class NOT IN ('footway','path','steps','cycleway','pedestrian','bridleway','living_street')""")
    con.sql("""CREATE OR REPLACE TABLE road_len AS
        SELECT t.GEOID, r.cls, r.rt, r.named, sum(ST_Length(ST_Intersection(r.g, t.g))) m
        FROM tp t JOIN roads r ON ST_Intersects(t.g, r.g) GROUP BY 1,2,3,4""")
    cls_cols = ", ".join(f"COALESCE(sum(CASE WHEN cls='{c}' THEN m END),0) len_{c}" for c in ROAD_CLASSES + ("other",))
    hwy_in = "','".join(HWY)
    RT = ("interstate", "us", "state", "statesub", "county", "bia")
    rt_cols = ", ".join(f"COALESCE(sum(CASE WHEN rt='{r}' THEN m END),0) len_rt_{r}" for r in RT)
    rt_cols += ", " + ", ".join(f"COALESCE(sum(CASE WHEN rt='{r}' AND cls IN ('{hwy_in}') THEN m END),0) len_rt_{r}_hwy" for r in RT)
    con.sql(f"""CREATE OR REPLACE TABLE road_feat AS SELECT GEOID, {cls_cols}, {rt_cols},
        COALESCE(sum(CASE WHEN cls IN ('{hwy_in}') THEN m END),0) len_hwy,
        COALESCE(sum(CASE WHEN cls IN ('{hwy_in}') AND rt<>'none' THEN m END),0) len_hwy_routed,
        COALESCE(sum(CASE WHEN cls NOT IN ('{hwy_in}') AND rt IN ('interstate','us','state','statesub','county') THEN m END),0) len_nonhwy_routed,
        COALESCE(sum(CASE WHEN cls='tertiary' AND named THEN m END),0) len_tertiary_named,
        COALESCE(sum(m),0) len_all
        FROM road_len GROUP BY 1""")

    # ---- buildings: centroid-in-tract counts by primary source -------------
    say("buildings")
    con.sql(f"""CREATE OR REPLACE TABLE bld AS
        SELECT t.GEOID,
               count(*) n_bld,
               sum(CASE WHEN src='Microsoft ML Buildings' THEN 1 ELSE 0 END) n_bld_ms,
               sum(CASE WHEN src='OpenStreetMap' THEN 1 ELSE 0 END) n_bld_osm,
               sum(CASE WHEN src='Esri Community Maps' THEN 1 ELSE 0 END) n_bld_esri,
               sum(CASE WHEN src LIKE 'Google%' THEN 1 ELSE 0 END) n_bld_google,
               sum(CASE WHEN src NOT IN ('Microsoft ML Buildings','OpenStreetMap','Esri Community Maps') AND src NOT LIKE 'Google%' THEN 1 ELSE 0 END) n_bld_other,
               sum(CASE WHEN b.subtype IS NOT NULL THEN 1 ELSE 0 END) n_bld_typed,
               sum(ST_Area({PRJ.format(g='b.geometry')})) bld_area_m2
        FROM (SELECT sources[1].dataset src, subtype, ST_Centroid(geometry) c, geometry
              FROM '{P.ref(region, 'overture-buildings')}') b
        JOIN tracts t ON ST_Intersects(t.geometry, b.c)
        GROUP BY 1""")

    # ---- places -------------------------------------------------------------
    say("pois")
    sch = "','".join(SCHOOL_CATS)
    con.sql(f"""CREATE OR REPLACE TABLE poi AS
        SELECT t.GEOID,
               count(*) n_poi,
               sum((p.operating_status IS DISTINCT FROM 'permanently_closed')::INT) n_poi_open,
               sum((p.cat='fire_department')::INT) n_fire,
               sum((p.cat='fire_protection_service')::INT) n_fire_alt,
               sum((p.cat='ambulance_and_ems_services')::INT) n_ems,
               sum((p.cat IN ('{sch}'))::INT) n_schools,
               sum((p.cat='preschool')::INT) n_preschool,
               sum((p.cat='hospital')::INT) n_hospital,
               sum((p.cat IS NULL)::INT) n_poi_nocat,
               sum((p.src='meta')::INT) n_poi_meta,
               sum((p.src='Microsoft')::INT) n_poi_ms,
               sum((p.src='BrightQuery')::INT) n_poi_bq,
               sum((p.src='Foursquare')::INT) n_poi_fsq,
               sum((p.src='AllThePlaces')::INT) n_poi_atp,
               sum((p.confidence >= 0.5)::INT) n_poi_conf50,
               sum((p.n_src >= 2)::INT) n_poi_multisrc
        FROM (SELECT categories.primary cat, operating_status, confidence, geometry,
                     len(sources) n_src,
                     list_filter(list_transform(sources, s -> s.dataset), d -> d NOT IN ('Overture','Overture-signals'))[1] src
              FROM '{P.ref(region, 'overture-pois')}') p
        JOIN tracts t ON ST_Intersects(t.geometry, p.geometry)
        GROUP BY 1""")

    # ---- infrastructure + rail ---------------------------------------------
    say("infra")
    con.sql(f"""CREATE OR REPLACE TABLE infra AS
        SELECT t.GEOID, sum((i.class='bus_stop')::INT) n_bus_stop,
               sum((i.subtype='airport')::INT) n_airport, count(*) n_infra
        FROM '{P.ref(region, 'overture-infrastructure')}' i JOIN tracts t ON ST_Intersects(t.geometry, i.geometry)
        GROUP BY 1""")
    con.sql(f"""CREATE OR REPLACE TABLE rail AS
        SELECT t.GEOID, sum(ST_Length(ST_Intersection({PRJ.format(g='r.geometry')}, t.g))) len_rail
        FROM '{P.ref(region, 'overture-rail')}' r JOIN tp t ON ST_Intersects(t.g, {PRJ.format(g='r.geometry')})
        GROUP BY 1""")

    # ---- ACS + strata --------------------------------------------------------
    say("strata")
    con.sql(f"CREATE OR REPLACE TABLE acs AS SELECT GEOID, housing_units FROM '{P.ref(region, 'census-acs-housing')}'")
    con.sql(f"""CREATE OR REPLACE TABLE st AS SELECT GEOID, ruca_primary, rucc_2023, rucc_metro, nchs_2013,
            tribal_any, tribal_pct, svi_overall, cvi_overall,
            usfs_BuildingCount_sum, usfs_BuildingDensity_mean, usfs_HUCount_sum, usfs_HUDen_mean, carbonplan_buildings,
            usfs_WHP_mean
        FROM '{P.strata(region, 'strata-tract-table')}'""")

    df = con.sql("""
        SELECT s.GEOID, t.ALAND, t.area_m2, t.pop_total, t.pct_urban, t.ur_class, t.frac_inside_aoi,
               r.* EXCLUDE (GEOID), b.* EXCLUDE (GEOID), p.* EXCLUDE (GEOID), i.* EXCLUDE (GEOID),
               rl.len_rail, a.housing_units, st.* EXCLUDE (GEOID)
        FROM scored s
        JOIN tracts t USING (GEOID)
        LEFT JOIN road_feat r USING (GEOID) LEFT JOIN bld b USING (GEOID) LEFT JOIN poi p USING (GEOID)
        LEFT JOIN infra i USING (GEOID) LEFT JOIN rail rl USING (GEOID) LEFT JOIN acs a USING (GEOID)
        LEFT JOIN st USING (GEOID)""").df()
    count_like = [c for c in df.columns if c.startswith(("len_", "n_", "bld_area"))]
    df[count_like] = df[count_like].fillna(0)
    df["region"] = region
    assert len(df) == P.SCORED[region], (len(df), P.SCORED[region])
    return df


def main(regions=None, out="out2/features.parquet", merge_into=None):
    import time
    regions = regions or P.REGIONS
    con = P.connect()
    parts = []
    for r in regions:
        t0 = time.time()
        parts.append(build(con, r))
        print(f"[{r}] {len(parts[-1])} rows in {time.time()-t0:.0f}s", flush=True)
    df = pd.concat(parts, ignore_index=True)
    if merge_into:
        old = pd.read_parquet(merge_into)
        df = pd.concat([old[~old.region.isin(regions)], df], ignore_index=True)
    df.to_parquet(out, index=False)
    print("wrote", out, df.shape)
    return df


if __name__ == "__main__":
    main(sys.argv[1:] or None)
