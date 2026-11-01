"""Fully clean line (2026-10-31): the h11 fit (our own scored files above k16, all-zero RMSE, kappa 5, EB groups)
without k13_ext_vigohan_signals (built from vigohan's GitHub correlations) and h4_probe_fit (fitted with k13).
Inputs: the challenge package, our own uploads and their public RMSE, numbers posted on the Zindi forum.
usage: PYTHONPATH=. python research/clean_fit.py [--keep-k13] [--out NAME]"""
import sys
from model import probe as pr

DROP = [] if "--keep-k13" in sys.argv else ["k13_ext_vigohan_signals.csv", "h4_probe_fit.csv"]
_ledger = pr.ledger
pr.ledger = lambda until=None: (lambda L: L[~L.file.isin(DROP)])(_ledger(until))
out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
pr.fit(dry=out is None, out=out, until="k16_grp_published_means_ext", kappa=5.0, eb=0.4, eb_grp=True, zero=True)
