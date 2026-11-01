"""Check that the Bias Discovery writeup quotes the analysis outputs exactly: every generated table line and every
headline number must appear verbatim in docs/BEST_BIAS_DISCOVERY.md (catches hand edits and stale numbers after a re-run).
usage: python research/check_entry_numbers.py"""
import json

doc = open("docs/BEST_BIAS_DISCOVERY.md").read()
R = "report_discovery"
o = json.load(open(f"{R}/stations.json")); ck = json.load(open(f"{R}/checks.json")); mb = json.load(open(f"{R}/meta_baseline.json"))
rb = json.load(open(f"{R}/robust.json"))
haz = {(x["tribal"], x["wildfire_top_quartile"]): x for x in o["hazard"]}
pct = lambda r: f"{100 * r:.1f}%"
want = [l for l in open(f"{R}/stations_tables.md").read().splitlines() if l.startswith("| ") and "---" not in l]
want += [f"{o['stations']:,}", f"{o['all']['missing']:,} of {o['stations']:,}", pct(o["all"]["rate"]), pct(haz[(True, True)]["rate"]),
         pct(haz[(False, False)]["rate"]), f"{o['missing_top_quartile_wildfire']['stations']} missing stations",
         f"{o['missing_top_quartile_wildfire']['residents']:,} residents", pct(o["meta_only_share_of_visible"]),
         f"**{o['missing_held_as_building']}** of\nthe {o['all']['missing']:,} missing stations",
         f"{o['missing_volunteer_top_quartile_wildfire']['whp_q75']:.1f}",
         pct(mb["meta_only_fire"]), pct(mb["meta_only_civic"]), pct(mb["meta_only_all"]),
         pct(ck["control"]["schools"]["missing_500m"]), pct(ck["control"]["hospitals"]["missing_500m"]),
         f"{ck['control']['schools']['n']:,}", f"{ck['distance_missing']['median_km']} km", pct(ck["distance_missing"]["share_over_5km"])]
for k in ("hazard_or_by_region_rural_tribal", "tribal_or_by_region_rural_hazard"):
    want += [f"{ck[k]['or']:.2f}", f"{ck[k]['lo']:.2f}–{ck[k]['hi']:.2f}"]
for k in ("hazard_or_by_region_tribal", "tribal_or_by_region_hazard"):
    want.append(f"{rb[k]['or']:.2f}")
missing = [w for w in want if w not in doc]
for w in missing:
    print("NOT IN WRITEUP:", w)
print(f"checked {len(want)} numbers/lines")
print("NUMBERS OK" if not missing else f"NUMBERS FAIL ({len(missing)})")
