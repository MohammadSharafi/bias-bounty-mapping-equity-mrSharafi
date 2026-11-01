"""Baseline for Finding 3 (2026-11-01): is fire special, or is every Overture place mostly Meta-only? Share of places whose
only upstream source is Meta (same rule as research/discovery_stations.py), for all places, fire places and other civic
places, pooled over the four scored regions. Permitted data only (Overture places). Writes report_discovery/meta_baseline.json.
usage: .venv/bin/python research/discovery_meta_baseline.py"""
import json
import duckdb

MO = ("len(list_filter(list_transform(sources, s -> s.dataset), x -> x NOT IN ('meta','Overture','Overture-signals'))) = 0 "
      "AND list_contains(list_transform(sources, s -> s.dataset), 'meta')")
FIRE = "categories.primary IN ('fire_department','fire_protection_service')"
CIVIC = "categories.primary IN ('police_department','hospital','school','elementary_school','post_office','library')"
files = ", ".join(f"'data_public/reference/{r}/{r}-overture-pois.parquet'"
                  for r in ("eastern-ok", "maricopa-az", "northern-ca", "south-central-tx"))
row = duckdb.sql(f"""SELECT count(*), avg(({MO})::int),
    count(*) FILTER (WHERE {FIRE}), avg(({MO})::int) FILTER (WHERE {FIRE}),
    count(*) FILTER (WHERE {CIVIC}), avg(({MO})::int) FILTER (WHERE {CIVIC})
    FROM read_parquet([{files}])""").fetchone()
out = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in
       zip(("n_all", "meta_only_all", "n_fire", "meta_only_fire", "n_civic", "meta_only_civic"), row)}
json.dump(out, open("report_discovery/meta_baseline.json", "w"), indent=1)
print(out)
