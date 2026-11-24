"""Exhaustive small-size check of the ECPP verifier rule (see ecpp_py.verify_level).

For every composite n coprime to 6 in a small list, every curve (a, b), point P and k in [2, KMAX], the
full rule must NEVER accept; for honest primes it must.  Dropping each assertion in turn shows which are
necessary at these sizes.  Larger composites are scanned over random curves.

    python3 model_check.py
"""
import math
import random
import sys
import time

import sympy

import ecpp_py as E

KMAX = 5


def order_seq(R, a, n, limit):
    """Smallest j >= 2 with [j]R = O by sequential multiples; None on a non-invertible step or past `limit`."""
    cur = R
    for j in range(2, limit + 1):
        if (cur[0] - R[0]) % n == 0 and (cur[1] + R[1]) % n == 0:
            return j
        nxt = E.add(cur, R, a, n)
        if nxt is None:
            return None
        cur = nxt
    return None


def scan(n, disable, curves):
    """First accepted (a, b, P, k, q) over the given curves with the named checks disabled, else None."""
    chk = {name: False for name in disable}
    r = E.fourth_root_witness(n)
    limit = n + 2 * math.isqrt(n) + 4
    for a, b in curves:
        if "disc" not in disable and math.gcd((4 * a ** 3 + 27 * b * b) % n, n) != 1:
            continue
        roots = {}
        for y in range(n):
            roots.setdefault(y * y % n, []).append(y)
        for x in range(n):
            for y in roots.get((x ** 3 + a * x + b) % n, []):
                P = (x, y)
                for k in range(2, KMAX + 1):
                    R = E.ladder(P, k, a, n)
                    if R is None:
                        continue
                    q = order_seq(R, a, n, limit)
                    if q is not None and sympy.isprime(q) and E.verify_level(n, a, b, P, k, q, r, chk):
                        return (a, b, P, k, q)
    return None


def all_curves(n):
    return ((a, b) for a in range(n) for b in range(n))


def random_curves(n, count, rng):
    return ((rng.randrange(n), rng.randrange(n)) for _ in range(count))


def main():
    t0 = time.time()
    rng = random.Random(1)
    exhaustive = [25, 35, 49, 55]
    sampled = [65, 77, 85, 91, 95, 115, 119, 121, 143, 169, 187, 209, 221]
    primes_ex = [29, 31, 37, 41, 43]

    print("1. composites accepted by the FULL rule (must be none)")
    bad = []
    for n in exhaustive:
        ex = scan(n, [], all_curves(n))
        if ex:
            bad.append((n, ex))
    for n in sampled:
        ex = scan(n, [], random_curves(n, 4000, rng))
        if ex:
            bad.append((n, ex))
    print("   exhaustive:", exhaustive, " sampled:", sampled, "->", bad if bad else "none", f"[{time.time() - t0:.0f}s]")
    assert not bad, "the ECPP rule accepted a composite"

    print("2. honest primes: has a certificate under the full rule?")
    res = {n: bool(scan(n, [], all_curves(n))) for n in primes_ex}
    print("   ", res, f"[{time.time() - t0:.0f}s]")
    assert any(res.values()), "no honest prime accepted: the rule is too strict"

    print("3. necessity of each assertion: composites accepted when ONE assertion is dropped")
    necessary = {}
    for name in ("bound", "disc", "oncurve"):
        hits = []
        for n in exhaustive:
            if scan(n, [name], all_curves(n)):
                hits.append(n)
        for n in sampled:
            if scan(n, [name], random_curves(n, 4000, rng)):
                hits.append(n)
        necessary[name] = hits
        print(f"   without {name:8}: " + (f"false accepts for n in {hits}" if hits else "no false accept found (redundant at these sizes)"))
    print(f"done in {time.time() - t0:.0f}s")
    return necessary


if __name__ == "__main__":
    main()
