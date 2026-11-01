"""Best Bias Discovery, station level: which reference fire stations are missing from Overture?

For every fire station in the USGS National Map Structures dataset (public domain; downloaded from the public USGS
service by research/fetch_usgs_stations.py into data_public/external/usgs_fire_stations.csv - the same layer the
challenge bucket carried until 2026-09-25; used only as comparison evidence for the Best Bias Discovery prize, never for
a scored submission), find the nearest Overture place filed as a
fire station (`fire_department`, `fire_protection_service`, or a fire-station name in any other
category). A station is *visible* when such a place lies within 500 m (sensitivity: 250 m, 1 km).

Outputs (report_discovery/): stations.csv (one row per reference station), stations.json (every
number the writeup quotes) and stations_tables.md (the writeup's tables, generated here).
usage: PYTHONPATH=. python research/discovery_stations.py
"""
import json
import math
import pandas as pd
from model import paths as P
from model.features import PRJ
from model.features_fire import FIRE_NAME

REGIONS = ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx"]
VOL = r"volunteer|\bvfd\b|v\.f\.d|\bvol\.? fire"
OUT = "report_discovery"
USGS = "data_public/external/usgs_fire_stations.csv"   # research/fetch_usgs_stations.py


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def build():
    con = P.connect()
    rows = []
    for R in REGIONS:
        con.sql(f"CREATE OR REPLACE TABLE tr AS SELECT GEOID, {PRJ.format(g='geometry')} g FROM 'data_public/strata/{R}/{R}-census-tracts.parquet'")
        con.sql(f"""CREATE OR REPLACE TABLE st AS SELECT permanent_identifier id, name, city, address, lon, lat,
                    {PRJ.format(g='ST_Point(lon, lat)')} g FROM read_csv_auto('{USGS}') WHERE region = '{R}'""")
        con.sql(f"""CREATE OR REPLACE TABLE ov AS SELECT categories.primary cat,
                    len(list_filter(list_transform(sources, s -> s.dataset), x -> x NOT IN ('meta','Overture','Overture-signals'))) = 0
                      AND list_contains(list_transform(sources, s -> s.dataset), 'meta') AS meta_only,
                    {PRJ.format(g='geometry')} g FROM 'data_public/reference/{R}/{R}-overture-pois.parquet'
                    WHERE categories.primary IN ('fire_department','fire_protection_service')
                       OR regexp_matches(lower(coalesce(names.primary,'')), '{FIRE_NAME}')""")
        con.sql(f"""CREATE OR REPLACE TABLE fb AS SELECT ST_Centroid({PRJ.format(g='geometry')}) g
                    FROM 'data_public/reference/{R}/{R}-overture-buildings.parquet' WHERE class = 'fire_station'""")
        bld = con.sql("""SELECT s.id, min(ST_Distance(s.g, b.g)) bld_m FROM st s JOIN fb b ON ST_DWithin(s.g, b.g, 1000) GROUP BY 1""").df()
        df = con.sql("""
            WITH near AS (SELECT s.id, min(ST_Distance(s.g, o.g)) d,
                                 arg_min(o.meta_only, ST_Distance(s.g, o.g)) meta_only
                          FROM st s JOIN ov o ON ST_DWithin(s.g, o.g, 1000) GROUP BY 1)
            SELECT s.id, s.name, s.city, s.address, s.lon, s.lat, t.GEOID, near.d nearest_m, near.meta_only
            FROM st s JOIN tr t ON ST_Intersects(t.g, s.g) LEFT JOIN near ON near.id = s.id""").df()
        df = df.merge(bld, on="id", how="left")
        df["region"] = R
        rows.append(df)
    st = pd.concat(rows, ignore_index=True)
    strata = pd.concat([pd.read_parquet(f"data_public/strata/{R}/{R}-strata-tract-table.parquet",
                                        columns=["GEOID", "pop_total", "pct_urban", "tribal_any", "usfs_WHP_mean", "svi_overall"])
                        for R in REGIONS])
    scored = pd.concat([pd.read_csv(f"data_public/reference/{R}/{R}-sample-submission.csv", dtype={"GEOID": str}).GEOID for R in REGIONS])
    st = st[st.GEOID.isin(set(scored))].merge(strata, on="GEOID", how="left")
    st["volunteer"] = st.name.fillna("").str.lower().str.contains(VOL, regex=True)
    st["rural"] = st.pct_urban.fillna(0) < 0.5
    st["tribal"] = st.tribal_any.fillna(0).astype(bool)
    for m in (250, 500, 1000):
        st[f"visible_{m}"] = st.nearest_m.fillna(1e9) <= m
    st["missing"] = ~st.visible_500
    st["held_as_building"] = st.missing & (st.bld_m.fillna(1e9) <= 500)   # in Overture's buildings, not its places
    return st.sort_values(["region", "GEOID", "name"]).reset_index(drop=True)


def rate(s):
    k, n = int(s.missing.sum()), len(s)
    lo, hi = wilson(k, n)
    return {"n": n, "missing": k, "rate": k / n if n else float("nan"), "ci_lo": lo, "ci_hi": hi}


def main():
    st = build()
    st.to_csv(f"{OUT}/stations.csv", index=False)
    out = {"stations": len(st), "tracts": int(st.GEOID.nunique()),
           "all": rate(st), "volunteer": rate(st[st.volunteer]), "career": rate(st[~st.volunteer]),
           "sensitivity": {m: {"volunteer": float((~st[st.volunteer][f"visible_{m}"]).mean()),
                               "career": float((~st[~st.volunteer][f"visible_{m}"]).mean())} for m in (250, 500, 1000)},
           "strata": [], "regions": [],
           "meta_only_share_of_visible": float(st[st.visible_500].meta_only.fillna(False).mean()),
           "missing_held_as_building": int(st.held_as_building.sum())}
    for rur in (False, True):
        for tri in (False, True):
            for vol in (False, True):
                s = st[(st.rural == rur) & (st.tribal == tri) & (st.volunteer == vol)]
                out["strata"].append({"rural": rur, "tribal": tri, "volunteer": vol, **rate(s)})
    for R in REGIONS:
        s = st[st.region == R]
        out["regions"].append({"region": R, "volunteer": rate(s[s.volunteer]), "career": rate(s[~s.volunteer])})
    whp_q75 = float(st.usfs_WHP_mean.quantile(0.75))
    st["wild_top"] = st.usfs_WHP_mean >= whp_q75
    out["hazard"] = [{"tribal": tri, "wildfire_top_quartile": w, **rate(st[(st.tribal == tri) & (st.wild_top == w)])}
                     for tri in (False, True) for w in (False, True)]
    hm = st[st.missing & st.wild_top]
    out["missing_top_quartile_wildfire"] = {"stations": len(hm), "tracts": int(hm.GEOID.nunique()),
                                           "residents": int(hm.drop_duplicates("GEOID").pop_total.sum())}
    hz = st[st.missing & st.volunteer & (st.usfs_WHP_mean >= whp_q75)]
    out["missing_volunteer_top_quartile_wildfire"] = {"stations": len(hz), "tracts": int(hz.GEOID.nunique()),
                                                     "residents": int(hz.drop_duplicates("GEOID").pop_total.sum()),
                                                     "whp_q75": whp_q75}
    named = st[st.missing & st.volunteer & st.rural & st.tribal].sort_values("usfs_WHP_mean", ascending=False)
    out["named"] = named[["name", "city", "region", "GEOID", "nearest_m", "usfs_WHP_mean", "pop_total"]].head(12).to_dict("records")
    with open(f"{OUT}/stations.json", "w") as fh:
        json.dump(out, fh, indent=1, default=float)

    pct = lambda r: f"{100 * r['rate']:.1f}% ({100 * r['ci_lo']:.1f}-{100 * r['ci_hi']:.1f})"
    md = ["| reference stations | n | missing from Overture (no fire place within 500 m) | 95% CI |", "|---|---|---|---|"]
    for lab, key in (("volunteer departments", "volunteer"), ("all other (career/combination)", "career"), ("all", "all")):
        r = out[key]; md.append(f"| {lab} | {r['n']} | {r['missing']} ({100 * r['rate']:.1f}%) | {100 * r['ci_lo']:.1f}-{100 * r['ci_hi']:.1f}% |")
    md += ["", "| tract type | volunteer: missing | other: missing |", "|---|---|---|"]
    for rur in (False, True):
        for tri in (False, True):
            v = next(x for x in out["strata"] if x["rural"] == rur and x["tribal"] == tri and x["volunteer"])
            c = next(x for x in out["strata"] if x["rural"] == rur and x["tribal"] == tri and not x["volunteer"])
            md.append(f"| {'rural' if rur else 'urban'}, {'tribal' if tri else 'non-tribal'} | {v['missing']}/{v['n']} = {pct(v)} | {c['missing']}/{c['n']} = {pct(c)} |")
    md += ["", "| tract type | not top-quartile wildfire hazard: missing | top-quartile wildfire hazard: missing |", "|---|---|---|"]
    for tri in (False, True):
        lo_, hi_ = (next(x for x in out["hazard"] if x["tribal"] == tri and x["wildfire_top_quartile"] == w) for w in (False, True))
        md.append(f"| {'tribal' if tri else 'non-tribal'} | {lo_['missing']}/{lo_['n']} = {pct(lo_)} | {hi_['missing']}/{hi_['n']} = {pct(hi_)} |")
    md += ["", "| region | volunteer: missing | other: missing |", "|---|---|---|"]
    for x in out["regions"]:
        md.append(f"| {x['region']} | {x['volunteer']['missing']}/{x['volunteer']['n']} = {pct(x['volunteer'])} | {x['career']['missing']}/{x['career']['n']} = {pct(x['career'])} |")
    md += ["", "| station (reference name) | city | region | tract GEOID | wildfire hazard (USFS WHP) | tract residents |", "|---|---|---|---|---|---|"]
    for r in out["named"]:   # nearest Overture fire place goes in the caption (none within 1 km except one)
        md.append(f"| {r['name']} | {r['city']} | {r['region']} | {r['GEOID']} | {r['usfs_WHP_mean']:,.0f} | {int(r['pop_total']):,} |")
    with open(f"{OUT}/stations_tables.md", "w") as fh:
        fh.write("\n".join(md) + "\n")
    print(json.dumps({k: out[k] for k in ("stations", "all", "volunteer", "career", "meta_only_share_of_visible",
                                          "missing_top_quartile_wildfire", "missing_held_as_building")}, indent=1, default=float))
    print("STATIONS DONE")


if __name__ == "__main__":
    main()
