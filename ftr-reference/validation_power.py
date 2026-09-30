"""How many real-kit captures does Phase-0 validation need? Exact (Clopper-Pearson) bounds."""
from scipy.stats import beta

def upper(k, n, conf=0.95):          # one-sided upper bound on an error rate
    return 1.0 if k == n else beta.ppf(conf, k + 1, n - k)

def lower(k, n, conf=0.95):          # one-sided lower bound on an accuracy
    return 0.0 if k == 0 else beta.ppf(1 - conf, k, n - k + 1)

print("False-positive rate claim: negative-control captures needed (95% one-sided)")
for target in (0.05, 0.02, 0.01):
    for errs in (0, 1, 2):
        n = next(n for n in range(10, 5000) if upper(errs, n) <= target)
        print(f"  prove FP <= {target:.0%} with {errs} false positives observed: n >= {n}")
print("\nAccuracy lower bound for a given run size, if 98% observed")
for n in (100, 200, 400, 800):
    k = round(0.98 * n)
    print(f"  n={n}: observed {k}/{n} -> accuracy >= {lower(k, n):.1%} (95% one-sided)")
print("\nProposed design: 12 substances x 3 replicates x 3 phones x 4 lights x 3 read times =",
      12 * 3 * 3 * 4 * 3, "captures")
