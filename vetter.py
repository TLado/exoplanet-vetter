"""Minimal LEO-vetter-like vetting of QLP TCEs: PC / FP / FA.

Usage:  python vetter.py tces.csv -o results.csv
CSV columns: tic, period [d], epoch [BTJD or BJD], duration [h], optional rstar [Rsun]
"""
import argparse
import numpy as np
import pandas as pd

# Decision thresholds (see DEVELOPER.md)
TH = dict(
    snr=7.1,           # FA: total transit SNR (MES-like) below this
    min_transits=2,    # FA: fewer transits with data
    snr_wo_max=5.0,    # FA: SNR after removing the strongest single event
    odd_even=4.0,      # FP: odd/even depth difference [sigma]
    sec_sigma=4.0,     # FP: secondary eclipse significance [sigma] ...
    sec_ratio=0.1,     # ... and secondary/primary depth ratio
    max_rp=2.5,        # FP: implied radius [R_Jup] (needs rstar)
    max_depth=0.05,    # FP: depth [rel. flux] when rstar unknown
    ap_sigma=4.0,      # FP: large vs small aperture depth difference [sigma] ...
    ap_ratio=1.3,      # ... and depth ratio (neighbour contamination)
)
RJ_PER_RSUN = 9.731


def load_qlp(tic, max_sectors=None):
    """Download and stitch detrended QLP light curves (quality == 0); each sector normalised to 1.
    Detrended columns are kspsap_* in sectors 1-55 and det_* in 56+; missing ones become NaN."""
    import lightkurve as lk
    res = lk.search_lightcurve(f"TIC {tic}", author="QLP")
    if len(res) == 0:
        raise ValueError(f"No QLP light curve for TIC {tic}")
    parts = []
    for lc in res[:max_sectors].download_all():
        lc = lc[lc.quality.value == 0]
        d = {"time": lc.time.value}
        for out, suffix in [("flux", ""), ("flux_sml", "_sml"), ("flux_lag", "_lag")]:
            c = next((p + suffix for p in ("kspsap_flux", "det_flux") if p + suffix in lc.colnames), None)
            v = np.asarray(lc[c].value, float) if c else np.full(len(lc), np.nan)
            d[out] = v / np.nanmedian(v) if np.isfinite(v).any() else v
        parts.append(pd.DataFrame(d))
    return pd.concat(parts).dropna(subset=["time", "flux"]).sort_values("time")


def box(t, f, P, t0, dur, sigma, phase=0.0, sel=None):
    """Box depth and its error at a given orbital phase (local baseline)."""
    x = (((t - t0) / P - phase + 0.5) % 1 - 0.5) * P
    ok = np.isfinite(f) & (True if sel is None else sel)
    inn = (np.abs(x) < dur / 2) & ok
    out = (np.abs(x) > dur) & (np.abs(x) < 3 * dur) & ok
    if inn.sum() < 3 or out.sum() < 3:
        return np.nan, np.inf
    depth = np.median(f[out]) - np.mean(f[inn])
    return depth, sigma * np.sqrt(1 / inn.sum() + 1 / out.sum())


def vet(lc, period, epoch, duration, rstar=None):
    """Vet one TCE. duration in hours. Returns dict with disposition, flags, metrics."""
    t, f = lc["time"].to_numpy(), lc["flux"].to_numpy()
    P, dur = period, duration / 24
    t0 = epoch - 2457000 if epoch > 2400000 else epoch
    n = np.round((t - t0) / P)
    oot = np.abs(t - t0 - n * P) > dur
    sigma = 1.4826 * np.median(np.abs(f[oot] - np.median(f[oot])))
    # Red noise: beta = scatter of transit-length bins / white-noise expectation.
    # White sigma is used for detection (FA) tests, beta-inflated sigma_r for FP tests.
    b = pd.Series(f[oot]).groupby(np.floor(t[oot] / dur)).agg(["mean", "size"])
    b = b[b["size"] >= 3]
    beta = 1.4826 * np.median(np.abs(b["mean"] - b["mean"].median()) * np.sqrt(b["size"])) / sigma
    m = {"beta": beta}
    sigma_r = sigma * max(np.nan_to_num(beta), 1.0)

    depth, err = box(t, f, P, t0, dur, sigma)
    m["depth_ppm"], m["snr"] = depth * 1e6, depth / err

    # Individual events: count and SNR without the strongest one
    ses = {}
    for k in np.unique(n[~oot]):
        d, e = box(t, f, P, t0, dur, sigma, sel=n == k)
        if np.isfinite(d):
            ses[k] = d / e
    m["n_transits"] = len(ses)
    if ses:
        kmax = max(ses, key=ses.get)
        d, e = box(t, f, P, t0, dur, sigma, sel=n != kmax)
        m["snr_wo_max"] = d / e
    else:
        m["snr_wo_max"] = np.nan

    # Odd/even depth difference
    do, eo = box(t, f, P, t0, dur, sigma_r, sel=n % 2 == 1)
    de, ee = box(t, f, P, t0, dur, sigma_r, sel=n % 2 == 0)
    m["odd_even_sigma"] = abs(do - de) / np.hypot(eo, ee)

    # Strongest secondary eclipse in phase 0.15-0.85
    step = max(dur / P / 3, 1e-3)
    sec = [box(t, f, P, t0, dur, sigma_r, phase=p) for p in np.arange(0.15, 0.85, step)]
    sd, se = max(sec, key=lambda x: x[0] / x[1] if np.isfinite(x[0]) else -np.inf)
    m["sec_sigma"], m["sec_ratio"] = sd / se, sd / depth

    # Small vs large aperture depth (contamination by a neighbour)
    sm = [box(t, lc[c].to_numpy(), P, t0, dur, sigma_r) for c in ("flux_sml", "flux_lag")]
    m["ap_ratio"] = sm[1][0] / sm[0][0]
    m["ap_sigma"] = (sm[1][0] - sm[0][0]) / np.hypot(sm[0][1], sm[1][1])

    m["rp_rjup"] = np.sqrt(max(depth, 0)) * rstar * RJ_PER_RSUN if rstar else np.nan

    fa = {
        "LOW_SNR": not m["snr"] >= TH["snr"],
        "FEW_TRANSITS": m["n_transits"] < TH["min_transits"],
        "SINGLE_EVENT": not m["snr_wo_max"] >= TH["snr_wo_max"],
    }
    fp = {
        "ODD_EVEN": m["odd_even_sigma"] > TH["odd_even"],
        "SECONDARY": m["sec_sigma"] > TH["sec_sigma"] and m["sec_ratio"] > TH["sec_ratio"],
        "TOO_LARGE": m["rp_rjup"] > TH["max_rp"] if rstar else depth > TH["max_depth"],
        "APERTURE": m["ap_sigma"] > TH["ap_sigma"] and m["ap_ratio"] > TH["ap_ratio"],
    }
    flags = [k for k, v in {**fa, **fp}.items() if v]
    disp = "FA" if any(fa.values()) else "FP" if any(fp.values()) else "PC"
    return {"disposition": disp, "flags": ";".join(flags), **m}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tces")
    ap.add_argument("-o", "--output", default="results.csv")
    ap.add_argument("--max-sectors", type=int, default=None)
    a = ap.parse_args()
    rows = []
    for r in pd.read_csv(a.tces).to_dict("records"):
        try:
            lc = load_qlp(int(r["tic"]), a.max_sectors)
            rstar = r.get("rstar") if pd.notna(r.get("rstar")) else None
            res = vet(lc, r["period"], r["epoch"], r["duration"], rstar)
        except Exception as e:
            res = {"disposition": "ERROR", "flags": str(e)}
        rows.append({**r, **res})
        print(r["tic"], res["disposition"], res["flags"])
    pd.DataFrame(rows).to_csv(a.output, index=False)


if __name__ == "__main__":
    main()
