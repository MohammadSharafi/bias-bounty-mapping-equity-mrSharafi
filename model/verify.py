"""Compare a regenerated submission with the uploaded file.

Features are float sums whose last bits depend on DuckDB's parallel summation order, so a
rebuilt file can differ from the uploaded one in the 6th decimal of a few rows. The check
passes when every GEOID matches and the largest absolute difference is at most 1e-6.

usage: python -m model.verify regenerated.csv uploaded.csv
"""
import sys
import numpy as np
import pandas as pd

a = pd.read_csv(sys.argv[1], dtype={"GEOID": str}).set_index("GEOID").sort_index()
b = pd.read_csv(sys.argv[2], dtype={"GEOID": str}).set_index("GEOID").sort_index()
assert a.index.equals(b.index), "GEOID sets differ"
d = (a.coverage_gap_score - b.coverage_gap_score).abs()
rmse = float(np.sqrt((d ** 2).mean()))
print(f"{sys.argv[2]}: rows={len(a)} max_abs_diff={d.max():.1e} rows_differing={(d > 0).sum()} rmse={rmse:.1e}")
print("REPRODUCED" if d.max() <= 1e-6 else "NOT REPRODUCED")
sys.exit(0 if d.max() <= 1e-6 else 1)
