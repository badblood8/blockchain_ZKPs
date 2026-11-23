"""Generate a provable-prime chain (Maurer-style) and the Prover.toml hints for prime_chain.

    n16 (trial division) -> n32 -> n64 -> n128 -> n256,   n_{i+1} = f * e + 1,  f = n_i prime,
    f^2 > n_{i+1}  (Pocklington), base a with a^e != 1 and a^(n-1) = 1.

    python3 gen_chain.py [seed] > Prover.toml
"""
import random
import sys

import sympy

LIMB = 120
MASK = (1 << LIMB) - 1
LEVELS = [16, 32, 64, 128, 256]


def limbs(x, count):
    assert x < 1 << (LIMB * count)
    return [(x >> (LIMB * i)) & MASK for i in range(count)]


def step_witness(n, f):
    """(y, inv) for the Pocklington step: y has order exactly f modulo the prime n."""
    assert (n - 1) % f == 0
    e = (n - 1) // f
    for a in range(2, 1000):
        y = pow(a, e, n)
        if y != 1:
            return y, pow(y - 1, -1, n)
    raise RuntimeError("no element of order f found")


def next_prime(f, bits, rng):
    """Random prime n with exactly `bits` bits, n = f*e + 1 and f^2 > n."""
    lo, hi = 1 << (bits - 1), min(1 << bits, f * f)
    if lo >= hi:
        raise ValueError("f too small for this level")
    for _ in range(200000):
        e = rng.randrange(lo // f + 1, (hi - 1) // f + 1)
        n = f * e + 1
        if lo <= n < hi and sympy.isprime(n):
            return n
    raise RuntimeError("no prime found")


def build(rng, levels=LEVELS):
    # top-of-range 16-bit prime so that f^2 > n at every level above
    n16 = sympy.randprime(46341, 65536)
    chain = [n16]
    for bits in levels[1:]:
        for _ in range(200):
            try:
                chain.append(next_prime(chain[-1], bits, rng))
                break
            except ValueError:
                # previous prime too small to reach `bits`: restart the whole chain
                return None
        else:
            return None
    return chain


def chain_for(seed):
    rng = random.Random(seed)
    while True:
        c = build(rng)
        if c:
            return c


def redc(n, mb, count):
    return limbs((1 << (2 * mb + 6)) // n, count)


def fmt(v):
    return f'"0x{v:x}"'


def lst(vs, hexfmt=True):
    return "[" + ", ".join(fmt(v) if hexfmt else f'"{v}"' for v in vs) + "]"


def prover_toml(chain):
    n16, n32, n64, n128, n256 = chain
    y256, inv256 = step_witness(n256, n128)
    y128, inv128 = step_witness(n128, n64)
    y64, inv64 = step_witness(n64, n32)
    y32, inv32 = step_witness(n32, n16)
    out = [
        f"n = {lst(limbs(n256, 3))}",
        f"redc256 = {lst(redc(n256, 256, 3))}",
        f"y256 = {lst(limbs(y256, 3))}",
        f"inv256 = {lst(limbs(inv256, 3))}",
        f"n128 = {lst(limbs(n128, 2))}",
        f"redc128 = {lst(redc(n128, 128, 2))}",
        f"y128 = {lst(limbs(y128, 2))}",
        f"inv128 = {lst(limbs(inv128, 2))}",
        f'n64 = "{n64}"', f'y64 = "{y64}"', f'inv64 = "{inv64}"',
        f'n32 = "{n32}"', f'y32 = "{y32}"', f'inv32 = "{inv32}"',
        f'n16 = "{n16}"',
    ]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    chain = chain_for(seed)
    sys.stderr.write("chain bits: " + str([c.bit_length() for c in chain]) + "\n")
    sys.stderr.write(f"n256 = {chain[-1]}\n")
    print(prover_toml(chain), end="")
