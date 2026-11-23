"""Exhaustive small-size check of the simplified Pocklington criterion used by the circuits.

    n is accepted given prime f  iff   f^2 > n  and there is y with  y^f = 1 (mod n)  and  gcd(y-1, n) = 1.

Claim: every accepted n is prime.  (Proof: for a prime p | n, y mod p has order exactly f, so f | p-1, so
p > f > sqrt(n); this holds for every prime factor, hence n is prime.)  This script verifies the claim on
every n in [3, LIMIT) and every prime f, and shows that dropping f^2 > n lets composites through.

    python3 model_check.py [limit]
"""
import sys
from math import gcd

import sympy


def accepted(n, f, need_f_squared):
    if need_f_squared and f * f <= n:
        return False
    return any(pow(y, f, n) == 1 and gcd(y - 1, n) == 1 for y in range(n))


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    primes = list(sympy.primerange(2, 200))
    bad_with, bad_without, good, missed = 0, 0, 0, 0
    first_without = None
    for n in range(3, limit):
        prime = sympy.isprime(n)
        for f in primes:
            a_with = accepted(n, f, True)
            if a_with and not prime:
                bad_with += 1
            if a_with and prime:
                good += 1
            if prime and f * f > n and (n - 1) % f == 0 and not a_with:
                missed += 1          # honest prime with a prime f | n-1, f^2 > n must be accepted
            if f * f <= n and not prime and accepted(n, f, False):
                bad_without += 1
                first_without = first_without or (n, f)
    print(f"n < {limit}: composites accepted WITH f^2 > n   : {bad_with}")
    print(f"           primes accepted (honest)              : {good}   (honest primes wrongly rejected: {missed})")
    print(f"           composites accepted WITHOUT f^2 > n   : {bad_without}   e.g. n, f = {first_without}")
    assert bad_with == 0, "criterion is unsound"
    assert missed == 0, "criterion rejects an honest prime"
    assert bad_without > 0, "f^2 > n should be necessary"
    print("OK: the criterion is sound and complete on this range; f^2 > n is necessary.")


if __name__ == "__main__":
    main()
