"""Tests for the ECPP circuits (zkp_primality::ecpp, step_ecpp, ecpp_chain).

    NARGO=/path/to/nargo python3 test_ecpp.py            # behaviour: one step, then whole chains
    NARGO=... python3 test_ecpp.py mutants               # mutation check on the step
"""
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

import sympy

HERE = os.path.dirname(os.path.abspath(__file__))
NARGO = os.environ.get("NARGO", "nargo")
sys.path.insert(0, os.path.join(HERE, "ecpp_chain"))
import ecpp_py as E  # noqa: E402
import gen_ecpp as G  # noqa: E402

KEEP = ("zkp_primality", "step_ecpp", "ecpp_chain")


def step_toml(n, a, b, P, k, q, r, dinv=None):
    if dinv is None:
        d = (4 * a ** 3 + 27 * b * b) % n
        dinv = pow(d, -1, n) if math.gcd(d, n) == 1 else 0
    return (f'n = "{n}"\na = "{a}"\nb = "{b}"\nx = "{P[0]}"\ny = "{P[1]}"\n'
            f'k = "{k}"\nq = "{q}"\nr = "{r}"\ndinv = "{dinv}"\n')


class Env:
    def __init__(self, project, mutate=None):
        self.tmp = tempfile.mkdtemp(prefix="zkp_ecpp_")
        for d in KEEP:
            shutil.copytree(os.path.join(HERE, d), os.path.join(self.tmp, d),
                            ignore=shutil.ignore_patterns("target", "Prover.toml", "__pycache__", "fixtures.json"))
        if mutate:
            path, old, new = mutate
            f = os.path.join(self.tmp, path)
            s = open(f).read()
            assert old in s, mutate
            open(f, "w").write(s.replace(old, new))
        self.dir = os.path.join(self.tmp, project)
        r = subprocess.run([NARGO, "compile"], cwd=self.dir, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        self.count = 0

    def solvable(self, text):
        self.count += 1
        name = f"case{self.count}"
        with open(os.path.join(self.dir, name + ".toml"), "w") as f:
            f.write(text)
        r = subprocess.run([NARGO, "execute", "--prover-name", name], cwd=self.dir, capture_output=True, text=True)
        return r.returncode == 0

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def bound_forgery():
    """Composite n = 281 * 269 with q = 281 prime < (r+2)^2 = 324: passes everything except the size bound."""
    n, a, b, P, k, q, r = 75589, 37659, 14846, (6127, 25990), 128, 281, 16
    assert E.verify_level(n, a, b, P, k, q, r, {"bound": False}) and not E.verify_level(n, a, b, P, k, q, r)
    return n, a, b, P, k, q, r


def random_composite_attack(rng):
    """Composite n, random curve and point, k and q of the right sizes with the bound satisfied:
    every assertion holds except [q-1]R = -R."""
    while True:
        p1, p2 = sympy.randprime(250, 450), sympy.randprime(250, 450)
        n = p1 * p2
        if p1 == p2 or n % 6 == 0 or not (1 << 16) <= n < (1 << 17):
            continue
        r = E.fourth_root_witness(n)
        qs = [q for q in sympy.primerange(max(256, (r + 2) ** 2), 512)]
        if not qs:
            continue
        for _ in range(200):
            a, b, P = E.random_curve_point(n, rng)
            k = rng.randrange(128, 256)
            q = rng.choice(qs)
            R = E.ladder(P, k, a, n)
            if R is None:
                continue
            Q = E.ladder(R, q - 1, a, n)
            if Q is not None and not E.verify_level(n, a, b, P, k, q, r):
                return n, a, b, P, k, q, r


class StepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = Env("step_ecpp")
        cls.fix = [G.load_or_make(1)]

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def honest_level3(self, ch):
        L = ch["levels"][2]
        return L["n"], L["a"], L["b"], (L["x"], L["y"]), L["k"], L["q"], L["r"]

    def test_honest_level_accepted(self):
        n, a, b, P, k, q, r = self.honest_level3(self.fix[0])
        self.assertTrue(E.verify_level(n, a, b, P, k, q, r))
        self.assertTrue(self.env.solvable(step_toml(n, a, b, P, k, q, r)))

    def test_size_bound_is_enforced(self):
        n, a, b, P, k, q, r = bound_forgery()
        self.assertFalse(self.env.solvable(step_toml(n, a, b, P, k, q, r)), "composite below the ECPP size bound accepted")
        # r chosen too small so that the bound looks weaker
        for rr in (0, 1, 5, 15):
            self.assertFalse(self.env.solvable(step_toml(n, a, b, P, k, q, rr)), f"r={rr} accepted")

    def test_random_composites_rejected(self):
        rng = random.Random(4)
        for _ in range(5):
            n, a, b, P, k, q, r = random_composite_attack(rng)
            self.assertFalse(self.env.solvable(step_toml(n, a, b, P, k, q, r)), f"composite {n} accepted")

    def test_tampered_hints_rejected(self):
        n, a, b, P, k, q, r = self.honest_level3(self.fix[0])
        cases = {
            "n + 2": (n + 2, a, b, P, k, q, r),
            "a + 1": (n, a + 1, b, P, k, q, r),
            "b + 1": (n, a, b + 1, P, k, q, r),
            "P.x + 1": (n, a, b, (P[0] + 1, P[1]), k, q, r),
            "P.y + 1": (n, a, b, (P[0], P[1] + 1), k, q, r),
            "k + 1": (n, a, b, P, k + 1, q, r),
            "q + 2": (n, a, b, P, k, q + 2, r),
            "q composite": (n, a, b, P, k, 9 * 49, r),
            "r + 1 (q below the bound)": (n, a, b, P, k, q, r + 30),
        }
        for label, args in cases.items():
            self.assertFalse(self.env.solvable(step_toml(*args)), f"accepted: {label}")
        self.assertFalse(self.env.solvable(step_toml(n, a, b, P, k, q, r, dinv=1)), "wrong discriminant inverse accepted")

    def test_even_or_multiple_of_three_rejected(self):
        for n in (2 * 60001, 3 * 40009, 9 * 10007):
            self.assertFalse(self.env.solvable(step_toml(n, 1, 1, (1, 1), 130, 449, 20)), f"n={n} accepted")


class ChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = Env("ecpp_chain")
        cls.chains = [G.load_or_make(s) for s in (1, 2, 3) if str(s) in json.load(open(G.FIXTURES))]

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def test_honest_chains_accepted(self):
        self.assertTrue(self.chains)
        for ch in self.chains:
            self.assertTrue(G.verify_python(ch))
            self.assertTrue(self.env.solvable(G.prover_toml(ch)), f"honest chain for {ch['n']} rejected")

    def test_composite_public_n_rejected(self):
        ch = self.chains[0]
        rng = random.Random(1)
        for _ in range(3):
            while True:
                n = rng.randrange(1 << 63, 1 << 64) | 1
                if not sympy.isprime(n) and n % 3:
                    break
            t = G.prover_toml(ch).replace(f'n = "{ch["n"]}"', f'n = "{n}"', 1)
            self.assertFalse(self.env.solvable(t), f"composite {n} accepted")
        # n + 2 with the honest data
        t = G.prover_toml(ch).replace(f'n = "{ch["n"]}"', f'n = "{ch["n"] + 2}"', 1)
        self.assertFalse(self.env.solvable(t))

    def test_tampered_chain_rejected(self):
        """Perturb every hint of every level.  r is only a witness for the fourth root: any value with
        (r+1)^4 > n and q >= (r+2)^2 is valid, so for r the circuit must simply agree with the reference rule."""
        ch = self.chains[0]
        base = G.prover_toml(ch).splitlines()
        keys = [l.split(" = ")[0] for l in base]
        levels = ch["levels"]
        for key in keys[1:]:
            lines = list(base)
            i = keys.index(key)
            v = int(lines[i].split('"')[1])
            lines[i] = f'{key} = "{v + 1}"'
            got = self.env.solvable("\n".join(lines) + "\n")
            if key.startswith("r"):
                L = levels[int(key[1:]) - 1]
                want = E.verify_level(L["n"], L["a"], L["b"], (L["x"], L["y"]), L["k"], L["q"], L["r"] + 1)
                self.assertEqual(got, want, f"{key}+1: circuit={got}, reference rule={want}")
            else:
                self.assertFalse(got, f"tampered {key} accepted")

    def test_bad_base_case_rejected(self):
        ch = self.chains[0]
        t = G.prover_toml(ch)
        for bad in (255, 63001, 1):
            lines = [(f'q3 = "{bad}"' if l.startswith("q3 =") else l) for l in t.splitlines()]
            self.assertFalse(self.env.solvable("\n".join(lines) + "\n"), f"q3={bad} accepted")


def run_mutants():
    rng = random.Random(11)
    forg = bound_forgery()
    comp = random_composite_attack(rng)
    f = "zkp_primality/src/ecpp.nr"
    mutants = [
        ("size bound q >= (r+2)^2 dropped", f, "    assert(q >= (r + 2) * (r + 2));\n", "", forg),
        ("(r+1)^4 > n dropped (r unconstrained)", f, "    assert(r1 * r1 * r1 * r1 > n);\n", "", None),
        ("[q-1]R = -R check dropped", f, "    assert(big_q.x == big_r.x);\n    assert((big_q.y + big_r.y) % n == 0); // [q - 1]R = -R   i.e.   [q]R = O\n", "", comp),
    ]
    survivors = []
    for label, path, old, new, attack in mutants:
        env = Env("step_ecpp", mutate=(path, old, new))
        try:
            if attack is None:                       # the forgery with r = 0 (so the bound is vacuous)
                n, a, b, P, k, q, r = forg
                text = step_toml(n, a, b, P, k, q, 0)
            else:
                text = step_toml(*attack)
            accepted = env.solvable(text)
        finally:
            env.close()
        print(f"MUTANT {label!r}: " + ("caught (attack accepted by mutant)" if accepted else "SURVIVED  <-- attack rejected even without this assertion"))
        if not accepted:
            survivors.append(label)
    print("survivors:", survivors if survivors else "none")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "mutants":
        run_mutants()
    else:
        unittest.main(verbosity=2)
