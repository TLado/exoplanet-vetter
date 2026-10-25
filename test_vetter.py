"""Offline tests on synthetic light curves: python -m pytest"""
import numpy as np
import pandas as pd
from vetter import vet

P, T0, DUR = 3.0, 1.0, 3.0  # d, BTJD, h


def fake_lc(depth=0.005, odd_depth=None, sec=0.0, noise=1e-3, lag_scale=1.0, seed=0):
    t = np.arange(0, 27, 1 / 48)
    f = 1 + np.random.default_rng(seed).normal(0, noise, t.size)
    n = np.round((t - T0) / P)
    inn = np.abs(t - T0 - n * P) < DUR / 48
    d = np.where(n % 2 == 1, odd_depth if odd_depth is not None else depth, depth)
    f_true = 1 - np.where(inn, d, 0.0)
    f_true -= np.where(np.abs(t - T0 - (n + 0.5) * P) < DUR / 48, sec, 0.0)
    f = f + f_true - 1
    lag = f + (f_true - 1) * (lag_scale - 1)
    return pd.DataFrame({"time": t, "flux": f, "flux_sml": f, "flux_lag": lag})


def disp(lc, **kw):
    return vet(lc, P, T0, DUR, **kw)["disposition"]


def test_planet():
    assert disp(fake_lc()) == "PC"


def test_noise_only():
    assert disp(fake_lc(depth=0.0)) == "FA"


def test_odd_even():
    assert disp(fake_lc(depth=0.005, odd_depth=0.01)) == "FP"


def test_secondary():
    assert disp(fake_lc(sec=0.002)) == "FP"


def test_too_large():
    assert disp(fake_lc(depth=0.01), rstar=3.0) == "FP"


def test_aperture():
    assert disp(fake_lc(lag_scale=2.0)) == "FP"
