"""Scale diagnostic for scored submissions (no new uploads).

For a file s and the scored constant c (20_const_058, RMSE0), the identity
    MSE(c + a (s - c)) = MSE0 + a^2 Q - 2 a C,   Q = mean((s - c)^2),  C = mean((s - c)(y - c))
gives C from the file's own public score, Q from the file itself (full-set mean, used as an
estimate of the public-subset mean), and so the best scale a* = C / Q and the ceiling
RMSE sqrt(MSE0 - C^2 / Q) that rescaling this model could reach. Only complete-model scores
already in the ledger are used; nothing here is a probe.

usage: python -m model.calib
"""
import numpy as np
import pandas as pd

CONST, CONST_FILE = 0.058, "20_const_058.csv"


def table(ledger="submissions2/ledger.csv", d="submissions2"):
    L = pd.read_csv(ledger)
    mse0 = float(L.loc[L.file == CONST_FILE, "public_rmse"].iloc[0]) ** 2
    rows = []
    for _, r in L.iterrows():
        if r.file == CONST_FILE:
            continue
        sub = pd.read_csv(f"{d}/{r.file}", dtype={"GEOID": str})
        s = sub.coverage_gap_score.to_numpy()[~sub.GEOID.str.startswith("53").to_numpy()]   # eastern-wa is never public
        q = float(np.mean((s - CONST) ** 2))
        c = (mse0 + q - r.public_rmse ** 2) / 2
        rows.append({"file": r.file, "public": r.public_rmse, "a_star": c / q,
                     "ceiling": np.sqrt(max(mse0 - c * c / q, 0)), "implied_corr": c / np.sqrt(q * mse0)})
    return pd.DataFrame(rows).sort_values("ceiling")


if __name__ == "__main__":
    print(table().round(5).to_string(index=False))
