"""ECPP (Atkin-Goldwasser-Kilian) reference: affine curve arithmetic over Z/n, the verifier rule that the
Noir circuit implements, and a certificate generator (baby-step giant-step point counting, n up to ~2^64).

Theorem (AGK): n coprime to 6, E: y^2 = x^3 + a x + b over Z/n with 4a^3 + 27b^2 a unit, P a point,
k an integer, q a prime with q > (n^(1/4) + 1)^2.  If R = [k]P is an AFFINE point (every inverse met while
computing it exists mod n) and [q]R = O, then n is prime.  (Mod any prime p | n, R has order exactly q, so
q <= #E(F_p) <= (sqrt(p)+1)^2 <= (n^(1/4)+1)^2, a contradiction.)

The verifier rule below is the circuit's: [q]R = O is checked as [q-1]R == -R.
"""
import math
import random

import sympy


def inv(a, n):
    a %= n
    return pow(a, -1, n) if math.gcd(a, n) == 1 else None


def add(P, Q, a, n):
    """Affine addition/doubling mod n; None if an inverse does not exist (or the result is O)."""
    (x1, y1), (x2, y2) = P, Q
    if (x1 - x2) % n == 0:
        if (y1 + y2) % n == 0:
            return None                      # P + (-P) = O: not an affine point
        d = inv(2 * y1, n)
        if d is None or (y1 - y2) % n != 0:  # doubling needs P == Q
            return None
        lam = (3 * x1 * x1 + a) * d % n
    else:
        d = inv(x2 - x1, n)
        if d is None:
            return None
        lam = (y2 - y1) * d % n
    x3 = (lam * lam - x1 - x2) % n
    y3 = (lam * (x1 - x3) - y1) % n
    return (x3, y3)


def ladder(P, k, a, n):
    """[k]P by left-to-right double-and-add (k >= 1); None if any step is not an affine point."""
    R = P
    for bit in bin(k)[3:]:
        R = add(R, R, a, n)
        if R is None:
            return None
        if bit == "1":
            R = add(R, P, a, n)
            if R is None:
                return None
    return R


def fourth_root_witness(n):
    """Smallest r with (r+1)^4 > n."""
    r = max(0, int(round(n ** 0.25)) - 3)
    while (r + 1) ** 4 <= n:
        r += 1
    return r


def verify_level(n, a, b, P, k, q, r=None, check=None):
    """The circuit's rule for one ECPP level.  `check` may disable named assertions (for the model check)."""
    check = check or {}
    def on(name): return check.get(name, True)
    if on("coprime6") and (n % 2 == 0 or n % 3 == 0):
        return False
    x, y = P
    if on("range") and not all(0 <= v < n for v in (a, b, x, y)):
        return False
    if on("disc") and math.gcd((4 * a ** 3 + 27 * b * b) % n, n) != 1:
        return False
    if on("oncurve") and (y * y - (x ** 3 + a * x + b)) % n != 0:
        return False
    if r is None:
        r = fourth_root_witness(n)
    if on("bound") and not ((r + 1) ** 4 > n and q >= (r + 2) ** 2):
        return False
    if k < 2 or q < 3:
        return False
    R = ladder(P, k, a, n)
    if R is None:
        return False
    Q = ladder(R, q - 1, a, n)
    if Q is None:
        return False
    return Q[0] == R[0] and (Q[1] + R[1]) % n == 0


# ---------------------------------------------------------------------------- certificate generation
def bsgs_order(P, a, n, lo, hi):
    """The unique m in [lo, hi] with [m]P = O, if it is unique (baby-step giant-step). None otherwise."""
    w = hi - lo + 1
    s = int(math.isqrt(w)) + 1
    baby = {}
    cur = None                               # j*P for j = 1..s (affine); j = 0 is O
    for j in range(1, s + 1):
        cur = P if j == 1 else add(cur, P, a, n)
        if cur is None:
            return None
        baby.setdefault(cur, j)
    # lo*P, then steps of s*P: m = lo + i*s + j'  with  [m]P = O  <=>  [lo + i*s]P = -[j]P  for some j in 0..s
    A = ladder(P, lo, a, n)
    if A is None:
        return None
    sP = ladder(P, s, a, n)
    found = []
    cur = A
    i = 0
    while lo + i * s <= hi:
        # [lo + i s]P + [j]P = O  <=>  [lo + i s]P == -[j]P
        if cur is not None:
            neg = (cur[0], (-cur[1]) % n)
            if neg in baby:
                found.append(lo + i * s + baby[neg])
        # also j = 0: [lo + i s]P = O cannot be represented (we only hold affine points) -> skip
        if cur is None:
            return None
        nxt = add(cur, sP, a, n)
        if nxt is None:
            # cur == +-sP: the multiple is O (or doubling): treat as a hit/stop
            return None
        cur = nxt
        i += 1
    found = sorted(set(m for m in found if lo <= m <= hi))
    return found[0] if len(found) == 1 else None


def random_curve_point(n, rng):
    while True:
        a, x, y = rng.randrange(n), rng.randrange(n), rng.randrange(n)
        b = (y * y - x ** 3 - a * x) % n
        if math.gcd((4 * a ** 3 + 27 * b * b) % n, n) == 1:
            return a, b, (x, y)


def next_level(n, rng, qbits, kbits, tries=100000):
    """Find (a, b, P, k, q) with q prime of exactly `qbits` bits, k of exactly `kbits` bits, q >= (r+2)^2."""
    r = fourth_root_witness(n)
    lo, hi = n + 1 - 2 * math.isqrt(n) - 2, n + 1 + 2 * math.isqrt(n) + 2
    for _ in range(tries):
        a, b, P = random_curve_point(n, rng)
        m = bsgs_order(P, a, n, lo, hi)
        if m is None:
            continue
        for q in sympy.primefactors(m):
            k = m // q
            if q.bit_length() == qbits and k.bit_length() == kbits and q >= (r + 2) ** 2:
                if verify_level(n, a, b, P, k, q, r):
                    return a, b, P, k, q, r
    return None


def build_chain(n, plan, rng):
    """plan = [(qbits, kbits), ...]: levels from n downwards; returns [(n, a, b, P, k, q, r), ...]."""
    levels = []
    cur = n
    for qbits, kbits in plan:
        res = next_level(cur, rng, qbits, kbits)
        if res is None:
            return None
        a, b, P, k, q, r = res
        levels.append((cur, a, b, P, k, q, r))
        cur = q
    return levels, cur
