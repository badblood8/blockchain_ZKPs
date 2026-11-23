"""Pratt primality certificate generator and reference verifier.

A certificate for a prime p is a flat list of entries (see lib/pratt.circom):
    entry i = (p_i, g_i, [q_0 .. q_{F-1}])
where g_i is a primitive root mod p_i and the q's are the ODD prime factors of
p_i - 1 listed with multiplicity in ascending order, padded with 1.  Entry 0 is
the prime being certified; every odd prime factor appearing in an entry has an
entry of its own.  Unused entries are padded with the trivial valid entry
(3, 2, [1, ..., 1]).

Usage:
    python3 scripts/pratt_certificate_generator.py 8675309 --entries 9 --factors 4 \
        -o inputs/pratt.json
"""
import argparse
import json
import sys

import sympy

PAD_ENTRY = (3, 2)  # prime 3 with primitive root 2 (3 - 1 = 2^1, no odd factors)


def primitive_root(p):
    """Smallest primitive root of the odd prime p."""
    return sympy.primitive_root(p)


def odd_prime_factors(p):
    """Odd prime factors of p - 1 with multiplicity, ascending."""
    factors = []
    for q, e in sorted(sympy.factorint(p - 1).items()):
        if q != 2:
            factors += [q] * e
    return factors


def collect_primes(prime):
    """All primes needing an entry (odd, in discovery order), `prime` first."""
    if prime < 3 or not sympy.isprime(prime):
        raise ValueError(f"{prime} is not an odd prime")
    order, seen, stack = [], set(), [prime]
    while stack:
        p = stack.pop(0)
        if p in seen:
            continue
        seen.add(p)
        order.append(p)
        for q in odd_prime_factors(p):
            if q not in seen:
                stack.append(q)
    return order


def build_certificate(prime, max_entries, max_factors):
    """Return the circuit input dict for `prime`; raise if it does not fit."""
    primes = collect_primes(prime)
    if len(primes) > max_entries:
        raise ValueError(f"certificate needs {len(primes)} entries but only {max_entries} fit "
                         f"(primes: {primes})")
    cert_primes, cert_bases, cert_factors = [], [], []
    for p in primes:
        facs = odd_prime_factors(p)
        if len(facs) > max_factors:
            raise ValueError(f"{p} - 1 has {len(facs)} odd prime factors (with multiplicity), "
                             f"more than --factors {max_factors}")
        cert_primes.append(p)
        cert_bases.append(primitive_root(p))
        cert_factors.append(facs + [1] * (max_factors - len(facs)))
    while len(cert_primes) < max_entries:
        cert_primes.append(PAD_ENTRY[0])
        cert_bases.append(PAD_ENTRY[1])
        cert_factors.append([1] * max_factors)
    return {
        "mainPrime": prime,
        "certPrimes": cert_primes,
        "certBases": cert_bases,
        "certFactors": cert_factors,
    }


def verify_certificate(cert, nbits=32):
    """Pure-Python mirror of the circuit's rules.  Returns (ok, reason)."""
    P, G, Q = cert["certPrimes"], cert["certBases"], cert["certFactors"]
    if cert["mainPrime"] != P[0]:
        return False, "mainPrime != certPrimes[0]"
    for i, (p, g, qs) in enumerate(zip(P, G, Q)):
        if not (2 <= p < 2 ** nbits):
            return False, f"entry {i}: p out of range"
        if not (0 <= g < p):
            return False, f"entry {i}: g out of range"
        n = p - 1
        s = 0
        while n % 2 == 0 and n > 0:
            n //= 2
            s += 1
        if s < 1 or s > nbits - 1:
            return False, f"entry {i}: p - 1 not divisible by 2 (or too wide)"
        prod = 2 ** s
        for q in qs:
            prod *= q
            if prod >= 2 ** nbits:
                return False, f"entry {i}: partial product exceeds {nbits} bits"
        if prod != p - 1:
            return False, f"entry {i}: factors do not multiply to p - 1"
        h = pow(g, (p - 1) // 2, p)
        if h == 1 or h * h % p != 1:
            return False, f"entry {i}: Lucas condition fails for q = 2"
        prev = None
        for q in qs:
            if q != 1:
                if q not in P:
                    return False, f"entry {i}: factor {q} has no entry"
                if q != prev and pow(g, (p - 1) // q, p) == 1:
                    return False, f"entry {i}: g^((p-1)/{q}) == 1"
            prev = q
    return True, "ok"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prime", type=int)
    ap.add_argument("--entries", type=int, default=9, help="certificate capacity M (default 9)")
    ap.add_argument("--factors", type=int, default=4, help="odd prime factor slots F (default 4)")
    ap.add_argument("-o", "--output", help="write JSON here (default: stdout)")
    args = ap.parse_args()

    cert = build_certificate(args.prime, args.entries, args.factors)
    ok, why = verify_certificate(cert)
    if not ok:
        sys.exit(f"internal error: generated certificate fails verification: {why}")
    text = json.dumps(cert, indent=4)
    if args.output:
        with open(args.output, "w") as f:
            f.write(text + "\n")
        print(f"wrote {args.output}: {len(collect_primes(args.prime))} of {args.entries} entries used")
    else:
        print(text)


if __name__ == "__main__":
    main()
