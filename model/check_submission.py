"""Validate submission files against the official layout before upload.

usage: python -m model.check_submission submissions2/60_*.csv [...]

Checks per file: header is GEOID,coverage_gap_score; GEOIDs read as text are exactly the
union of the per-region sample submissions (9,794, no duplicates, no extras); no blank
cells; every score is a finite number in [0, 1].
"""
import sys
import numpy as np
import pandas as pd
from . import paths as P


def scored_geoids():
    base = P.BASE if P.BASE != P.REMOTE else "data_public"
    ids = [pd.read_csv(f"{base}/reference/{r}/{r}-sample-submission.csv", dtype={"GEOID": str}).GEOID
           for r in P.REGIONS]
    ids = pd.concat(ids)
    assert len(ids) == P.TOTAL_SCORED and ids.is_unique, (len(ids), ids.is_unique)
    return set(ids)


def check(path, expected):
    errs = []
    try:
        d = pd.read_csv(path, dtype={"GEOID": str})
    except (pd.errors.ParserError, ValueError) as e:
        return [f"unreadable as CSV: {e}"], 0, float("nan")
    if list(d.columns) != ["GEOID", "coverage_gap_score"]:
        errs.append(f"columns {list(d.columns)}")
    if d.isna().any().any():
        errs.append(f"{int(d.isna().sum().sum())} blank cells")
    if not d.GEOID.is_unique:
        errs.append(f"{int(d.GEOID.duplicated().sum())} duplicate GEOIDs")
    got = set(d.GEOID)
    if got != expected:
        errs.append(f"{len(expected - got)} missing, {len(got - expected)} extra GEOIDs")
    s = pd.to_numeric(d.coverage_gap_score, errors="coerce").to_numpy()
    if not np.isfinite(s).all() or (s < 0).any() or (s > 1).any():
        errs.append("score not a finite number in [0, 1]")
    return errs, len(d), float(np.nanmean(s))


def main(paths):
    expected = scored_geoids()
    bad = 0
    for p in paths:
        errs, n, mean = check(p, expected)
        bad += bool(errs)
        print(f"{'OK  ' if not errs else 'FAIL'} {p}: rows={n} mean={mean:.5f}" + ("" if not errs else "  " + "; ".join(errs)))
    print("ALL OK" if bad == 0 and paths else f"{bad} file(s) failed")
    sys.exit(1 if bad or not paths else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
