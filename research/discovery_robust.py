"""Robustness of Finding 1 (2026-11-01): is the tribal / wildfire-hazard gap just a regional difference? Missing shares
within each region, and Mantel-Haenszel odds ratios stratified by region (Robins-Breslow-Greenland 95% CI).
Writes report_discovery/robust.json. usage: python3 research/discovery_robust.py"""
import json
import numpy as np
import pandas as pd

s = pd.read_csv("report_discovery/stations.csv")
s["top"] = s.usfs_WHP_mean >= s.usfs_WHP_mean.quantile(0.75)   # same cut as discovery_stations.py (top quartile of stations)


def mh(df, x, strata):
    """Mantel-Haenszel odds ratio of missing for x=True vs False, over strata with both groups present."""
    R = S = PR = PS_QR = QS = 0.0
    for _, g in df.groupby(strata):
        a = int((g[x] & g.missing).sum()); b = int((g[x] & ~g.missing).sum())
        c = int((~g[x] & g.missing).sum()); d = int((~g[x] & ~g.missing).sum()); n = a + b + c + d
        if min(a + b, c + d) == 0:
            continue
        r, q = a * d / n, b * c / n; p_, qq = (a + d) / n, (b + c) / n
        R += r; S += q; PR += p_ * r; PS_QR += p_ * q + qq * r; QS += qq * q
    orr = R / S; se = np.sqrt(PR / (2 * R ** 2) + PS_QR / (2 * R * S) + QS / (2 * S ** 2))
    return {"or": round(orr, 2), "lo": round(orr * np.exp(-1.96 * se), 2), "hi": round(orr * np.exp(1.96 * se), 2)}


rates = {f"{r}|{k}|{v}": {"n": int(len(g)), "rate": round(float(g.missing.mean()), 3)}
         for k in ("tribal", "top") for (r, v), g in s.groupby(["region", k])}
out = {"within_region": rates,
       "hazard_or_by_region_tribal": mh(s, "top", ["region", "tribal"]),
       "tribal_or_by_region_hazard": mh(s, "tribal", ["region", "top"]),
       "tribal_or_eastern_ok": mh(s[s.region == "eastern-ok"], "tribal", ["top"])}
json.dump(out, open("report_discovery/robust.json", "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "within_region"}))
