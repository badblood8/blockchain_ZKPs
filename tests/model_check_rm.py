"""Exhaustive model check of the constraint logic of circom/rabin_miller.circom (python3 only).

For one base, the circuit accepts (n, a) iff the prover can choose the hints  u in {0,1}  and a one-hot position
idx in [1, nBits-1]  such that every constraint holds.  This script enumerates ALL n < 2^nBits, ALL a and ALL hints
and compares with the textbook strong-probable-prime test:

  * the real constraint set must accept exactly the strong probable primes (soundness and completeness);
  * each mutant (one constraint deleted) must either accept something it should not, or be explained below as
    provably redundant (it never changes the verdict).

    python3 tests/model_check_rm.py [nBits]      (default 8)
"""
import itertools
import sys

NBITS = int(sys.argv[1]) if len(sys.argv) > 1 else 8


def strong_pass(n, a):
    """Textbook test for odd n >= 5 and 2 <= a <= n-2."""
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


def accepted(n, a, flags):
    """Does ANY hint make the (possibly mutated) constraint set hold?  Returns (accepted, hint)."""
    if "odd" not in flags.get("drop", ()) and n % 2 == 0:
        return False
    if "range" not in flags.get("drop", ()) and not (2 <= a <= n - 2):
        return False
    if n < 3:
        return False                       # ModMul needs a modulus > 1; not part of what is being tested
    e = n & ~1                              # the circuit clears bit 0 of n: e = n - 1 only for odd n
    z = [1]
    for i in range(NBITS):
        z.append(z[i] * (1 - (e >> i & 1)))
    at_r = [z[i] * (e >> i & 1) for i in range(NBITS)]
    x = [pow(a, e >> j, n) for j in range(NBITS)]          # s_j = a^(e >> j) mod n
    s_r = sum(at_r[j] * x[j] for j in range(1, NBITS))
    drop = flags.get("drop", ())
    lo = 0 if "no_exclude_0" in drop else 1
    if "onehot" in drop:
        position_sets = [c for k in (1, 2) for c in itertools.combinations(range(lo, NBITS), k)]
    else:
        position_sets = [(j,) for j in range(lo, NBITS)]
    for u in (0, 1):
        for pos in position_sets:
            if "gate" not in drop and any(not z[j] for j in pos):
                continue
            s_idx = sum(x[j] for j in pos)
            cand = s_idx + u * (s_r - s_idx)
            if cand == (n - 1) + u * (2 - n):
                return True
    return False


def run(name, flags, expect):
    false_accepts = missed = 0
    first = None
    for n in range(0, 2 ** NBITS):
        for a in range(0, 2 ** NBITS):
            want = n % 2 == 1 and n >= 5 and 2 <= a <= n - 2 and strong_pass(n, a)
            got = accepted(n, a, flags)
            if got and not want:
                false_accepts += 1
                first = first or (n, a)
            if want and not got:
                missed += 1
    ok = (false_accepts == 0 and missed == 0) if expect == "exact" else (false_accepts > 0)
    if expect == "redundant":
        ok = false_accepts == 0 and missed == 0
    print(f"  {'ok ' if ok else 'BAD'} {name:44} false accepts {false_accepts:6}, missed {missed}"
          + (f", e.g. n={first[0]} a={first[1]}" if first else ""))
    return ok


if __name__ == "__main__":
    print(f"Rabin-Miller constraint model, all n,a < 2^{NBITS}")
    results = [
        run("real constraints", {}, "exact"),
        run("drop: n odd            (necessary)", {"drop": ("odd",)}, "attack"),
        run("drop: idx <= r gate    (necessary)", {"drop": ("gate",)}, "attack"),
        run("drop: base range 2..n-2 (necessary)", {"drop": ("range",)}, "attack"),
        run("drop: idx one-hot      (necessary)", {"drop": ("onehot",)}, "attack"),
        run("allow idx = 0          (redundant)", {"drop": ("no_exclude_0",)}, "redundant"),
    ]
    sys.exit(0 if all(results) else 1)
