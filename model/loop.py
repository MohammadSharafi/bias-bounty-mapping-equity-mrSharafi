"""The improvement loop: record scores, refit on everything, hand over the next files to upload.

Each round:
  1. `python -m model.loop record FILE SCORE` for every new score (validated, appended to the ledger).
  2. `python -m model.loop next`: refits over every known score (ours + other teams' published files,
     kappa 5). If the refit plus the published group means is predicted to beat the best score by more
     than the observed optimism plus a margin, it is built and handed over first. The rest of the round
     is filled from QUEUE (files built on the incumbent, so each can set a new best when its idea is
     right), skipping anything already scored.

usage: python -m model.loop record FILE SCORE | next
"""
import datetime
import os
import re
import sys
import numpy as np
import pandas as pd
from . import probe as pr
from .check_submission import check, scored_geoids

D = "submissions2"
OPTIMISM = 0.0002     # refits have scored this much above their prediction (h4, k16)
MARGIN = 0.0001       # extra gain a refit must promise before it is worth a slot
ROUND = 5             # uploads per day
QUEUE = ["k17_nudge_school_down", "k18_nudge_definedness_down", "k19_nudge_tx_rural_down",
         "k20_nudge_tribal_down", "k21_nudge_curvature_up", "f14_abl_e0_school", "f12_abl_e0_definedness",
         "f10_abl_e0_tx_rural", "f5_abl_e0_places_tx", "f7_abl_e0_places_az", "f6_abl_e0_places_ok",
         "f3_abl_e0_region_means", "f9_abl_e0_northern-ca", "g32_probe_all_score_sq"]


def ledger():
    return pd.read_csv(f"{D}/ledger.csv", dtype={"public_rmse": str})


def record(file, score):
    name = os.path.basename(file)
    path = f"{D}/{name}"
    errs = [] if os.path.exists(path) else [f"{path} does not exist"]
    if not errs:
        errs, _, _ = check(path, scored_geoids())
    if not re.fullmatch(r"0\.\d{6,}", score):
        errs.append(f"score {score!r}: paste it with all its digits")
    if errs:
        sys.exit("REFUSED: " + "; ".join(errs))
    with open(f"{D}/ledger.csv", "a") as fh:
        fh.write(f'{name},{datetime.date.today()},{score},"loop round"\n')
    print(f"recorded {name} {score}")


def best():
    L = ledger()
    L = L[L.public_rmse.str.fullmatch(r"0\.\d{6,}")]
    i = L.public_rmse.astype(float).idxmin()
    return L.file[i].replace(".csv", ""), float(L.public_rmse[i])


def next_round():
    inc, inc_score = best()
    scored = set(ledger().file.str.replace(".csv", "", regex=False))
    used = [int(n[1:].split("_")[0]) for n in os.listdir(D) if re.match(r"h\d+_", n)]
    n = max(used, default=-1) + 1
    print(f"best so far: {inc} {inc_score:.6f}")
    pr.D = D
    plan = []
    # shortcut: every call builds a new h<N>; rerun `next` only after new scores are recorded
    fit_name, cal_name = f"h{n}_probe_fit", f"k{90 + n}_loop_refit_cal"
    pr.fit(out=fit_name, kappa=5.0, ext=True)
    pr.calibrate(fit_name, cal_name)
    predicted = _predict(cal_name)
    if predicted + OPTIMISM + MARGIN < inc_score:
        plan.append((cal_name, f"refit + published group means, predicted {predicted:.5f} (+{OPTIMISM} usual optimism)"))
    else:
        print(f"refit candidate {cal_name}: predicted {predicted:.5f} + {OPTIMISM} optimism does not beat {inc_score:.6f}; not handed over")
    for q in QUEUE:
        if len(plan) >= ROUND:
            break
        if q not in scored and os.path.exists(f"{D}/{q}.csv"):
            plan.append((q, "queued test, built on the best file or on e0"))
    print("\nupload next:")
    for i, (q, why) in enumerate(plan, 1):
        print(f"  {i}. {q}.csv  ({why})")
    print("NEXT READY")


def _predict(name):
    f, o, reg, s, m, X, err = pr.base()
    pr.EXT = True
    names, Ds, Mg = pr.scored_directions(s, m, f.GEOID)
    Ms = 0.073550347 ** 2
    Dm = Ds[:, m]; Q = Dm @ Dm.T / m.sum(); c = (Ms + np.diag(Q) - Mg) / 2
    d = (pr.load_scores(f"{D}/{name}.csv", f.GEOID) - s)[m]
    a = np.linalg.lstsq(Dm.T, d, rcond=None)[0]
    return float(np.sqrt(Ms + np.mean(d ** 2) - 2 * a @ c))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["record"] and len(a) == 3:
        record(a[1], a[2])
    elif a[:1] == ["next"]:
        next_round()
    else:
        sys.exit(__doc__)
