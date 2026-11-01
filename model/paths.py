"""Paths to the permitted challenge data only.

Only files that exist in the challenge bucket after the 2026-09-25 change are
referenced anywhere in this package: Overture extracts, ACS housing units,
strata tables, tract polygons and the per-region sample submission.
"""
import os

REMOTE = ("s3://us-west-2.opendata.source.coop/humane-intelligence"
          "/bias-bounty-mapping-equity-challenge")
BASE = os.environ.get("BB_DATA", REMOTE)

REGIONS = ["eastern-ok", "maricopa-az", "northern-ca", "south-central-tx", "eastern-wa"]
SCORED = {"eastern-ok": 1192, "maricopa-az": 1593, "northern-ca": 591, "south-central-tx": 6003, "eastern-wa": 415}
TOTAL_SCORED = 9794

PERMITTED_LAYERS = ("overture-buildings", "overture-roads", "overture-roads-unfiltered",
                    "overture-pois", "overture-rail", "overture-infrastructure",
                    "census-acs-housing", "sample-submission")


def ref(region, layer, ext="parquet"):
    assert layer in PERMITTED_LAYERS, layer
    return f"{BASE}/reference/{region}/{region}-{layer}.{ext}"


def strata(region, layer):
    return f"{BASE}/strata/{region}/{region}-{layer}.parquet"


def connect(memory_limit="8GB"):
    import duckdb
    con = duckdb.connect()
    con.sql("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    con.sql("SET s3_region='us-west-2'; SET s3_url_style='path';")
    con.sql(f"SET memory_limit='{memory_limit}';")
    return con
