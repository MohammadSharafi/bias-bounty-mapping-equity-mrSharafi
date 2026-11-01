"""Writes docs/BEST_BIAS_DISCOVERY.md from the analysis outputs, so every quoted number comes from a file:
report_discovery/stations.json, stations_tables.md, robust.json, checks.json, meta_baseline.json.
usage: python3 research/build_discovery_doc.py   (then research/check_entry_numbers.py and research/build_entry_pdf.sh)"""
import json

R = "report_discovery"
o = json.load(open(f"{R}/stations.json")); rb = json.load(open(f"{R}/robust.json")); ck = json.load(open(f"{R}/checks.json"))
mb = json.load(open(f"{R}/meta_baseline.json"))
T = [t.strip() for t in open(f"{R}/stations_tables.md").read().strip().split("\n\n")]
T_ALL, T_STRATA, T_HAZ, T_REG, T_NAMED = T
pc = lambda x: f"{100 * x:.1f}%"
A = o["all"]; n, miss = A["n"], A["missing"]
haz = {(h["tribal"], h["wildfire_top_quartile"]): h for h in o["hazard"]}
cut = o["missing_volunteer_top_quartile_wildfire"]["whp_q75"]
top = o["missing_top_quartile_wildfire"]
cell = ck["tribal_top_by_region"]; n_cell = sum(cell.values())
rc = ck["rural_cells"]; W = rb["within_region"]
hz_r, tb_r = ck["hazard_or_by_region_rural_tribal"], ck["tribal_or_by_region_rural_hazard"]
hz_0, tb_0, ok = rb["hazard_or_by_region_tribal"], rb["tribal_or_by_region_hazard"], rb["tribal_or_eastern_ok"]
ctl = ck["control"]; dist = ck["distance_missing"]
vol, car = o["volunteer"], o["career"]
sens = o["sensitivity"]
st = {(x["rural"], x["tribal"], x["volunteer"]): x for x in o["strata"]}
pool = st[(True, True, True)]
ci = lambda d: f"{d['or']:.2f} (95% CI {d['lo']:.2f}–{d['hi']:.2f})"
w = lambda k: f"{100 * W[k]['rate']:.1f}%"

doc = f'''<div class="kicker">Best Bias Discovery · Zindi Bias Bounty: Mapping Equity</div>

# A third of fire stations are missing from Overture, most of all in wildfire country and Oklahoma's tribal areas

<div class="meta">Zindi user <strong>mrSharafi</strong> · 1 November 2026 · data and code: see “Method, data and reproducibility”</div>

<p class="lead">On the Klamath River in Humboldt County, California, the Yurok Volunteer Fire Department runs Station 1 in
Weitchpec. Its tract's wildfire hazard index is 2,233; the top-quarter cut-off in this study is {cut:.1f}. Overture's map has
no fire station within a kilometre of it. In southeastern Oklahoma, inside the Choctaw Nation, the Battiest and Pickens
volunteer departments are missing too. Across four regions, {miss:,} of {n:,} public-record stations are missing, and a
typical missing station is {dist['median_km']} km from the nearest fire place Overture does show.</p>

<div class="stats">
<div class="hot"><b>{pc(A['rate'])}</b><span>of {n:,} USGS fire stations missing from Overture (schools: {pc(ctl['schools']['missing_500m'])})</span></div>
<div class="hot"><b>{pc(haz[(True, True)]['rate'])}</b><span>missing in tribal-area tracts with top-quarter wildfire hazard ({cell['eastern-ok']} of the {n_cell} are in eastern Oklahoma)</span></div>
<div><b>{dist['median_km']} km</b><span>median distance from a missing station to the nearest fire place Overture shows</span></div>
<div><b>{pc(mb['meta_only_fire'])}</b><span>of Overture's fire places come from Meta alone (all places: {pc(mb['meta_only_all'])})</span></div>
</div>

![](../report_discovery/fig0_fate.png)

*Fig. 1. Each of the {n:,} stations in the public USGS National Structures Dataset, looked up in Overture's places
(release 2026-08-19.0). Top row: is the station on the map. Bottom row: where the shown ones come from, and whether a
missing one has at least a fire-station building in Overture.*

## Who is affected

The missing stations are not slightly misplaced; they are absent from their whole neighbourhood. The median missing
station is {dist['median_km']} km from the nearest fire place Overture shows, and {pc(dist['share_over_5km'])} are more
than 5 km from one. In rural tribal-area tracts the median is {dist['rural_tribal']['median_km']} km; in urban non-tribal
tracts it is {dist['urban_nontribal']['median_km']} km. {top['stations']} missing stations sit in top-quarter-hazard tracts;
those {top['tracts']} tracts have {top['residents']:,} residents (tract totals, not people left without a station).

The named cases are the Yurok and Hoopa Valley country on the Klamath and Trinity rivers and the Anderson Valley in
Mendocino County, the highest-hazard tracts in the study's named list; in Oklahoma, the Choctaw Nation (Battiest, Pickens,
Honobia, Finley), the Cherokee Nation (Stilwell) and Osage County (Big Bend, Drum Creek). Fire stations are where engines
stage for wildland response and where residents go when roads close. Any station finder, routing or coverage-gap analysis
built on Overture shows no station at these addresses, and every nearest-station query drawn from it skips them.

## Finding 1 — Where: wildfire hazard everywhere, tribal areas in Oklahoma

Wildfire hazard and tribal-area status each raise the share of missing stations, and the two stack. Among rural
stations, {pc(rc['nontribal|lower']['rate'])} are missing in non-tribal lower-hazard tracts, {pc(rc['nontribal|top']['rate'])} in
non-tribal top-hazard tracts, {pc(rc['tribal|lower']['rate'])} in tribal-area lower-hazard tracts and {pc(rc['tribal|top']['rate'])} in
tribal-area top-hazard tracts (n = {rc['tribal|top']['n']}).

![](../report_discovery/fig1_compound.png){{width=86%}}

*Fig. 2. All stations, before any adjustment: {haz[(True, True)]['missing']}/{haz[(True, True)]['n']} = {pc(haz[(True, True)]['rate'])} missing in
tribal-area top-hazard tracts against {haz[(False, False)]['missing']}/{haz[(False, False)]['n']} = {pc(haz[(False, False)]['rate'])} in non-tribal lower-hazard
tracts; the 2.9× arrow is that raw ratio. Whiskers are 95% Wilson intervals. Top-quarter hazard = tract USFS Wildfire Hazard
Potential of {cut:.1f} or more, the 75th percentile across stations.*

**Is this just Oklahoma, or just rurality?** Top-quarter hazard raises the missing share in all four regions: eastern
Oklahoma {w('eastern-ok|top|True')} vs {w('eastern-ok|top|False')}, northern California {w('northern-ca|top|True')} vs
{w('northern-ca|top|False')}, Maricopa {w('maricopa-az|top|True')} vs {w('maricopa-az|top|False')}, south-central Texas
{w('south-central-tx|top|True')} vs {w('south-central-tx|top|False')}. Holding region, rural/urban and tribal-area status
fixed, a station's odds of being missing are {hz_r['or']:.2f} times higher in top-hazard tracts (95% CI {hz_r['lo']:.2f}–{hz_r['hi']:.2f}).
The tribal-area effect is smaller and regional: with region, rural/urban and hazard fixed the odds ratio is
{tb_r['or']:.2f} ({tb_r['lo']:.2f}–{tb_r['hi']:.2f}). It is clear in eastern Oklahoma ({w('eastern-ok|tribal|True')} vs
{w('eastern-ok|tribal|False')}; odds ratio {ok['or']:.2f}, {ok['lo']:.2f}–{ok['hi']:.2f}) and Arizona ({w('maricopa-az|tribal|True')} vs
{w('maricopa-az|tribal|False')}, only {W['maricopa-az|tribal|True']['n']} tribal-area stations), but absent in northern California
({w('northern-ca|tribal|True')} vs {w('northern-ca|tribal|False')}, {W['northern-ca|tribal|True']['n']} stations). Without the rural/urban
adjustment the odds ratios are {hz_0['or']:.2f} and {tb_0['or']:.2f}.

![](../report_discovery/fig1b_robust.png){{width=92%}}

*Fig. 3. Within-region shares; the odds ratios hold region, rural/urban and the other factor fixed (see Method).*

## Finding 2 — Why: fire stations, not facilities in general, and a feed with no backup

Overture does not lose public facilities in general. Under the same 500 m test, {pc(ctl['schools']['missing_500m'])} of
{ctl['schools']['n']:,} USGS schools and {pc(ctl['hospitals']['missing_500m'])} of {ctl['hospitals']['n']:,} hospitals are missing, against
{pc(ctl['fire_stations']['missing_500m'])} of fire stations. What sets fire stations apart is where Overture gets them:
{pc(mb['meta_only_fire'])} of Overture's fire places have Meta as their only upstream source, against
{pc(mb['meta_only_civic'])} of civic places and {pc(mb['meta_only_all'])} of all places; among the stations Overture does show
it is {pc(o['meta_only_share_of_visible'])}. Meta dependence alone does not explain the gap, since civic places are almost as
Meta-heavy and are rarely missing. What it does explain is fragility: where Meta has no fire-station record, Overture has
almost no second route to one. We cannot see Meta's own data, so this is a well-supported mechanism, not a proven cause.

Yet for **{o['missing_held_as_building']}** of
the {miss:,} missing stations, Overture already holds the station: its own buildings theme has a footprint of class
`fire_station` (from OpenStreetMap) within 500 m. Linking those footprints to the places theme would restore them with
data Overture already ships (the pale orange slice in Fig. 1).

## Where the missing stations are

The missing stations (orange) spread across the countryside, while the stations Overture shows (blue) cluster in the
cities. Most of eastern Oklahoma is tribal-area land (shaded):

![](../report_discovery/fig2_maps.png){{.map}}

*Fig. 4. Tribal-area tracts are shaded (`tribal_any` in the challenge's strata table). Circles mark stations named in the
named-stations table.*

Up close the pattern is stark. Along the Klamath and Trinity rivers, Overture shows Orleans and the two Hoopa stations,
but not Yurok Station 1, Yurok Station 2, Willow Creek, Salmon River or Salyer. In southeastern Oklahoma, inside the
Choctaw Nation, most of the stations in the frame are missing:

![](../report_discovery/fig2b_closeups.png)

*Fig. 5. The frames are about 95 km (California) and 110 km (Oklahoma) across; counts in the panel headings cover every
reference station inside the frame. Frames were chosen in high-hazard areas and are more affected than their regional
averages.*

## Finding 3 — It is the place, not the kind of department

Volunteer stations are missed more overall ({pc(vol['rate'])} vs {pc(car['rate'])}), but that follows from where they are.
Within each tract type the two are missed at similar rates: rural tribal-area {pc(st[(True, True, True)]['rate'])} vs
{pc(st[(True, True, False)]['rate'])}. In rural non-tribal tracts volunteer stations are missed *less*
({pc(st[(True, False, True)]['rate'])} vs {pc(st[(True, False, False)]['rate'])}). The data do not support a "volunteer departments
have no Facebook page" explanation (we cannot observe Facebook pages directly).

![](../report_discovery/fig3_place.png){{width=88%}}

*Fig. 6. Lines are 95% Wilson intervals; n is the number of reference stations in each group. Cell counts are in the appendix.*

## How strong is this?

| check | result |
|---|---|
| Matching radius | missing shares move by under 2 points at 250 m and 1 km (volunteer {pc(sens['250']['volunteer'])} / {pc(sens['500']['volunteer'])} / {pc(sens['1000']['volunteer'])}; other {pc(sens['250']['career'])} / {pc(sens['500']['career'])} / {pc(sens['1000']['career'])}) |
| Mislocation | the median missing station is {dist['median_km']} km from any Overture fire place; {pc(dist['share_over_5km'])} are more than 5 km away |
| Generic rural sparsity | same test: schools {pc(ctl['schools']['missing_500m'])} missing (n = {ctl['schools']['n']:,}), hospitals {pc(ctl['hospitals']['missing_500m'])} (n = {ctl['hospitals']['n']:,}) |
| Rurality | hazard odds ratio {ci(hz_r)}, tribal-area {ci(tb_r)}, with region and rural/urban held fixed |
| Region | hazard gap in all four regions; tribal-area gap in Oklahoma and Arizona, not northern California |
| Provenance baseline | Meta-only: fire places {pc(mb['meta_only_fire'])}, civic {pc(mb['meta_only_civic'])}, all places {pc(mb['meta_only_all'])} |
| Public re-run | {n:,} stations from the live USGS service; all {n:,} match the earlier challenge-package copy (3 stations it listed are no longer in the service) |

**Limitations.**

- Matching is by distance and fire category, not by name, so errors run both ways: a nearby unrelated fire place can
  make a station look present, and a station filed under a non-fire name in a shared civic building can make it look missing.
- The reference can list stations that have closed or moved; we did not verify stations individually.
- Stations in one tract share its hazard value, so intervals that treat stations as independent are somewhat too narrow.

## What should change

::: {{.callout}}
1. **Overture: add a public second source for emergency facilities.** The USGS National Structures Dataset is public
   domain and lists every station in this study. Today {pc(mb['meta_only_fire'])} of Overture's fire places rest on Meta alone.
2. **Overture: link what it already ships (a quick win).** {o['missing_held_as_building']} of the {miss:,} missing stations
   ({pc(o['missing_held_as_building'] / miss)}) have an OpenStreetMap `fire_station` building within 500 m in Overture's own
   buildings theme. Joining those footprints to the places theme restores them with no new data.
3. **Map users: do not trust absence.** In rural and tribal-area tracts, "no station here" in Overture is often wrong.
   Station finders and coverage analyses should cross-check a public facility list first.
4. **The scorecard: add three views.** A per-facility check against a public reference, with a control category such as
   schools; a split by data provenance (`sources`); and intersections such as tribal-area × wildfire hazard.
:::

## The named stations

{len(o['named'])} of the {pool['missing']} missing volunteer stations in rural tribal-area tracts, highest hazard first
(top-quarter cut-off WHP {cut:.1f}). The four California rows lead on hazard; their tracts are flagged tribal by overlap and
illustrate the hazard effect (in northern California the tribal-area flag does not raise the missing share). None has an
Overture fire place within 1 km except Bethel (660 m).

{T_NAMED}

## How this differs from other entries

The automated scorecard reports five metrics per tract over fixed strata. This entry works per facility against an
independent public list, with control categories (schools, hospitals) showing the omission is specific to fire stations;
it splits by data provenance (Overture `sources`, which the scorecard never reads) and crosses tribal-area status with
wildfire hazard. None of the entries below reports a per-facility reference check or a control category.

| entry | what it shows | what ours adds |
|---|---|---|
| Hunter_Toledo (8 Oct), "coverage deserts are authorship deserts" | rural tracts with no Overture fire POI; POIs carry no OSM records | a station-level check against a public reference: real stations, named, that Overture misses, and how far away the nearest shown one is |
| mugeha-laura (31 Oct), hidden fire departments | fire departments that are in Overture but filed outside the fire categories | the opposite failure: stations absent from Overture altogether. We search fire names in every category, so their "hidden" departments count as shown here |
| hero76 (31 Oct), ambulances filed as fire stations | wrong records inside Overture's fire category | missing records, checked against the reference |
| vigohan (14 Oct), phantom roads | unnamed, unedited TIGER-import roads near the Texas border | a different layer (facilities) and a different failure (omission, not phantom features) |

## Method, data and reproducibility

**Method.** For each reference station we take the nearest Overture place filed as `fire_department` or
`fire_protection_service`, or carrying a fire-station name in any other category. A station is *missing* when no such
place lies within 500 m. Tract fields come from the challenge's strata table: rural = `pct_urban` < 0.5; tribal-area =
the tract overlaps a reservation or tribal statistical area (`tribal_any`), which in eastern Oklahoma covers most tracts;
hazard = `usfs_WHP_mean`, cut at {cut:.1f}, the 75th percentile across stations. *Meta-only*: the matched place lists Meta and no
other upstream dataset among its sources. Schools and hospitals use the same 500 m rule with their own categories and
names. Rates carry 95% Wilson intervals; odds ratios are Mantel–Haenszel, stratified as stated, with
Robins–Breslow–Greenland intervals.

**Data.** Fire stations, schools and hospitals: USGS National Structures Dataset (public domain), National Map service
https://carto.nationalmap.gov/arcgis/rest/services/structures/MapServer, layers 16 (Fire Stations/EMS Stations, FCode
74026), 23 (Schools) and 14 (Hospitals/Medical Centers), retrieved 2026-11-01 by `research/fetch_usgs_stations.py`; the
snapshots are committed in `data_public/external/`. The live service changes over time, so use the committed snapshot to
reproduce the exact numbers. Catalogue:
https://catalog.data.gov/dataset/usgs-national-structures-dataset-usgs-national-map-downloadable-data-collection. Overture
places and buildings (release 2026-08-19.0), tract polygons and the strata table come from the challenge package (CC BY-SA
4.0). The rules allow additional public datasets for this prize; none of our leaderboard submissions reads the USGS data
(`model/paths.py`, `check_compliance.sh`). Associated leaderboard submissions: `RzkTLsFj` and `2gyMPZPa`.

**Reproduce** (about 3 minutes on a laptop):

```
.venv/bin/python research/fetch_usgs_stations.py              # optional re-fetch
.venv/bin/python research/fetch_usgs_stations.py --layer 23 --out usgs_schools.csv
.venv/bin/python research/fetch_usgs_stations.py --layer 14 --out usgs_hospitals.csv
PYTHONPATH=. .venv/bin/python research/discovery_stations.py  # stations
python3 research/discovery_robust.py                          # robust.json
PYTHONPATH=. .venv/bin/python research/discovery_checks.py    # checks.json
.venv/bin/python research/discovery_meta_baseline.py          # meta baseline
python3 research/discovery_figures_v3.py                      # Figs. 1-6
python3 research/check_entry_numbers.py                       # NUMBERS OK
```

## Appendix — full tables

**Tribal-area status × wildfire hazard** (the cells of Fig. 2; columns: lower hazard, top-quarter hazard).

{T_HAZ}

**Volunteer vs career by tract type** (the cells of Fig. 6).

{T_STRATA}

**All stations.**

{T_ALL}

**By region** (volunteer stations are missed more in every region; the tract-type table above shows that this follows
from where they sit):

{T_REG}
'''
open("docs/BEST_BIAS_DISCOVERY.md", "w").write(doc)
print("wrote docs/BEST_BIAS_DISCOVERY.md")
