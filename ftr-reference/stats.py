"""Exact (Clopper-Pearson) 95% intervals, reported in percent. Used for every rate claimed in the docs."""
from scipy.stats import beta


def ci(k, n, conf=0.95):
    """Two-sided CI for k events out of n, in percent."""
    if n == 0:
        return 0.0, 100.0
    a = (1 - conf) / 2
    lo = 0.0 if k == 0 else beta.ppf(a, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - a, k + 1, n - k)
    return 100 * lo, 100 * hi


def fmt(k, n):
    lo, hi = ci(k, n)
    return f"{100 * k / max(n, 1):.1f}% [{lo:.1f}-{hi:.1f}] (n={n})"
