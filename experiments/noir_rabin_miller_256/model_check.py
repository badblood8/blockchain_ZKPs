"""Exhaustive small-size check of the rabin_miller_256 *algorithm* (not the circuit).

The circuit decides "base a passes for n" by existential hints (idx, use_one) with these
constraints, over e = n-1 and s_i = a^(e >> i):
    n odd;  z[i] = (lowest i bits of e are zero) = (i <= r);  r = trailing zeros of e
    use_one:  s_r == 1                      (r is the unique i with z[i] and e bit i set)
    else   :  some idx with  1 <= idx <= r  and  s_idx == n-1
This script mirrors exactly that decision rule in Python and compares it with the textbook
strong-probable-prime test for ALL odd n below LIMIT and ALL bases 2 <= a <= n-2.
Each assertion is then dropped in turn to show that it is necessary (false accepts appear).

    python3 model_check.py [limit_bits]
"""
import sys


def textbook(n, a):
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    x = pow(a, d, n)
    if x in (1, n - 1):
        return True
    for _ in range(r - 1):
        x = x * x % n
        if x == n - 1:
            return True
    return False


def circuit_rule(n, a, require_odd=True, require_z=True, require_idx_ge1=True):
    """Existential acceptance of the circuit's hint rule."""
    if require_odd and n % 2 == 0:
        return False
    e = n - 1 if n % 2 else n          # without the odd check the circuit uses e = n (bit 0 cleared is a no-op)
    if e == 0:
        return False
    bits = e.bit_length()
    r = (e & -e).bit_length() - 1      # trailing zeros of e
    s = lambda i: pow(a, e >> i, n)
    # branch use_one: s_r == 1
    if s(r) == 1:
        return True
    lo = 1 if require_idx_ge1 else 0
    hi = r if require_z else bits
    return any(s(i) == n - 1 for i in range(lo, hi + 1))


def main():
    limit = 1 << (int(sys.argv[1]) if len(sys.argv) > 1 else 11)
    variants = {
        "full (all assertions)": {},
        "without i <= r (z[i])": {"require_z": False},
        "without i >= 1": {"require_idx_ge1": False},
        "without n odd": {"require_odd": False},
    }
    results = {k: [0, 0, 0] for k in variants}      # checked, false accepts, false rejects
    first = {}
    for n in range(5, limit):
        for a in range(2, n - 1):
            want = textbook(n, a) if n % 2 else False
            for k, kw in variants.items():
                got = circuit_rule(n, a, **kw)
                results[k][0] += 1
                if got and not want:
                    results[k][1] += 1
                    first.setdefault(k, (n, a))
                elif want and not got:
                    results[k][2] += 1
    ok = True
    for k, (c, fa, fr) in results.items():
        ex = f"  e.g. n={first[k][0]}, a={first[k][1]}" if k in first else ""
        print(f"{k:28} checked={c:>9}  false accepts={fa:>6}  false rejects={fr:>4}{ex}")
    full = results["full (all assertions)"]
    assert full[1] == 0 and full[2] == 0, "the full rule must equal textbook Rabin-Miller exactly"
    # i <= r and n odd are NECESSARY: dropping either creates false accepts.
    for k in ("without i <= r (z[i])", "without n odd"):
        assert results[k][1] > 0, f"dropping '{k}' should create false accepts but did not"
    # i >= 1 is provably REDUNDANT: s_0 = a^(n-1) == -1 (mod n) is impossible for odd n.
    # (It would force every prime p | n to satisfy p = 1 mod 2^(r+1), hence n = 1 mod 2^(r+1),
    #  contradicting v2(n-1) = r.)  Kept in the circuit as a one-line defense-in-depth check.
    assert results["without i >= 1"][1] == 0, "i >= 1 was supposed to be redundant"
    print("OK: the full rule equals textbook Rabin-Miller on every (n, a).")
    print("    necessary: i <= r, n odd.   provably redundant (kept as defense in depth): i >= 1, hits == 1.")


if __name__ == "__main__":
    main()
