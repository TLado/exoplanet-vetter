"""Validate the vetter on TOIs with known TFOPWG dispositions (NASA Exoplanet Archive).

Usage: python validate.py [-n 15] [--max-sectors 3]
Expected label: CP/KP (known planets) -> PC, FP -> FP, FA -> FA.
"""
import argparse
import pandas as pd
from vetter import load_qlp, vet

TAP = ("https://exoplanetarchive.ipac.caltech.edu/TAP/sync?format=csv&query="
       "select+toi,tid,tfopwg_disp,pl_orbper,pl_tranmid,pl_trandurh,st_rad+from+toi"
       "+where+tfopwg_disp+in+('CP','KP','FP','FA')+and+pl_orbper>0")
EXPECTED = {"CP": "PC", "KP": "PC", "FP": "FP", "FA": "FA"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=15, help="TOIs per class")
    ap.add_argument("--max-sectors", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("-o", "--output", default="validation.csv")
    a = ap.parse_args()

    toi = pd.read_csv(TAP)
    toi["truth"] = toi.tfopwg_disp.map(EXPECTED)
    sample = toi.groupby("truth").sample(a.n, random_state=a.seed)
    rows = []
    for r in sample.to_dict("records"):
        try:
            lc = load_qlp(r["tid"], a.max_sectors)
            res = vet(lc, r["pl_orbper"], r["pl_tranmid"], r["pl_trandurh"], r["st_rad"])
        except Exception as e:
            res = {"disposition": "ERROR", "flags": str(e)[:80]}
        rows.append({**r, **res})
        print(f"TOI {r['toi']:>8} {r['tfopwg_disp']} -> {res['disposition']} {res['flags']}")
    df = pd.DataFrame(rows)
    df.to_csv(a.output, index=False)

    ok = df[df.disposition != "ERROR"]
    print("\nConfusion matrix (rows: truth, columns: vetter):")
    print(pd.crosstab(ok.truth, ok.disposition, margins=True))
    print(f"Accuracy: {(ok.truth == ok.disposition).mean():.2f}  (errors: {len(df) - len(ok)})")


if __name__ == "__main__":
    main()
