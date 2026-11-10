"""Rates, smoothing, and rankings."""

import numpy as np
import pandas as pd

from . import config as C


def empirical_bayes(events, base) -> np.ndarray:
    """Global Empirical Bayes rate smoothing (Marshall 1991).

    Small populations produce extreme raw rates. Each raw rate is pulled toward
    the overall rate in proportion to how little population backs it:

        m   = sum(e) / sum(b)                             overall rate
        s2  = sum(b * (r - m)^2) / sum(b) - m / mean(b)   between-place variance
        w_i = s2 / (s2 + m / b_i)                         weight on the place's own rate
        EB  = w_i * r_i + (1 - w_i) * m

    Places with missing or zero population get NaN.
    """
    e = np.asarray(events, dtype=float)
    b = np.asarray(base, dtype=float)
    ok = np.isfinite(e) & np.isfinite(b) & (b > 0)
    out = np.full(e.shape, np.nan)
    if not ok.any():
        return out
    e_ok, b_ok = e[ok], b[ok]
    r = e_ok / b_ok
    m = e_ok.sum() / b_ok.sum()
    s2 = max((b_ok * (r - m) ** 2).sum() / b_ok.sum() - m / b_ok.mean(), 0.0)
    w = s2 / (s2 + m / b_ok) if s2 > 0 else np.zeros_like(b_ok)
    out[ok] = w * r + (1 - w) * m
    return out


def add_rates(df: pd.DataFrame, cols) -> pd.DataFrame:
    """Raw and Empirical Bayes-smoothed rates per RATE_PER residents for each count column."""
    df = df.copy()
    pop = df["TotalPopulation"]
    for col in cols:
        df[f"{col}_per_10k"] = df[col] / pop * C.RATE_PER
        df[f"{col}_per_10k_eb"] = empirical_bayes(df[col], pop) * C.RATE_PER
    return df


def add_percentiles(df: pd.DataFrame, cols, eligible: pd.Series) -> pd.DataFrame:
    """National percentile (0-100) among eligible places; NaN for the rest."""
    df = df.copy()
    for col in cols:
        df[f"{col}_pctile"] = (df.loc[eligible, col].rank(pct=True) * 100).reindex(df.index)
    return df
