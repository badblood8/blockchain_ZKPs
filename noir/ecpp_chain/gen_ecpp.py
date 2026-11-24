"""Generate an ECPP certificate chain for a 64-bit prime and the Prover.toml for ecpp_chain.

    n (64 bits) <- q1 (33 bits, k1 31 bits) <- q2 (17 bits, k2 16 bits) <- q3 (9 bits, k3 8 bits); q3 by trial division.
    (q must exceed (n^(1/4)+1)^2 > sqrt(n), so every level can at best halve the bit length.)

    python3 gen_ecpp.py [seed] > Prover.toml          # also caches the chain in fixtures.json
"""
import json
import os
import random
import sys

import sympy

import ecpp_py as E

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures.json")
PLAN = [(33, 31), (17, 16), (9, 8)]   # (qbits, kbits) per level


def make_chain(seed):
    rng = random.Random(seed)
    while True:
        n = sympy.randprime(1 << 63, 1 << 64)
        res = E.build_chain(n, PLAN, rng)
        if res:
            levels, last = res
            return {"n": n, "levels": [{"n": L[0], "a": L[1], "b": L[2], "x": L[3][0], "y": L[3][1],
                                         "k": L[4], "q": L[5], "r": L[6]} for L in levels], "last": last}


def load_or_make(seed):
    cache = {}
    if os.path.exists(FIXTURES):
        cache = json.load(open(FIXTURES))
    key = str(seed)
    if key not in cache:
        cache[key] = make_chain(seed)
        json.dump(cache, open(FIXTURES, "w"), indent=1)
    return cache[key]


def dinv(n, a, b):
    return pow((4 * a ** 3 + 27 * b * b) % n, -1, n)


def prover_toml(ch):
    out = [f'n = "{ch["n"]}"']
    for i, L in enumerate(ch["levels"], start=1):
        out += [f'a{i} = "{L["a"]}"', f'b{i} = "{L["b"]}"', f'x{i} = "{L["x"]}"', f'y{i} = "{L["y"]}"',
                f'k{i} = "{L["k"]}"', f'q{i} = "{L["q"]}"', f'r{i} = "{L["r"]}"',
                f'dinv{i} = "{dinv(L["n"], L["a"], L["b"])}"']
    return "\n".join(out) + "\n"


def verify_python(ch):
    """Reference check of the whole chain with the circuit's rule."""
    cur = ch["n"]
    for L in ch["levels"]:
        assert L["n"] == cur
        if not E.verify_level(L["n"], L["a"], L["b"], (L["x"], L["y"]), L["k"], L["q"], L["r"]):
            return False
        cur = L["q"]
    return 256 <= cur < 65536 and sympy.isprime(cur)


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    ch = load_or_make(seed)
    assert verify_python(ch), "generated chain does not verify"
    sys.stderr.write(f"n = {ch['n']}  chain: {[L['q'] for L in ch['levels']]}\n")
    print(prover_toml(ch), end="")
