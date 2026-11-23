"""Adversarial tests for the Pocklington steps in zkp_primality (native and bignum).

Each case writes a Prover.toml and runs `nargo execute`; a rejected case means NO valid witness
exists.  The key forgery is a composite n = p1 * p2 with p_i = 1 + k_i * f: for y of order f modulo
both p_i it satisfies  y^f = 1  and  gcd(y - 1, n) = 1,  and ONLY  f^2 > n  stops it.

    NARGO=/path/to/nargo python3 test_steps.py            # tests against the real library
    NARGO=... python3 test_steps.py mutants               # mutation check of every assertion
"""
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from math import gcd

import sympy
from sympy.ntheory.modular import crt

HERE = os.path.dirname(os.path.abspath(__file__))
NARGO = os.environ.get("NARGO", "nargo")
LIMB = 120
MASK = (1 << LIMB) - 1
KEEP = ("zkp_primality", "step_native", "step_big", "step_trial")


def limbs(x, count):
    assert 0 <= x < 1 << (LIMB * count)
    return [(x >> (LIMB * i)) & MASK for i in range(count)]


def hexl(vs):
    return "[" + ", ".join(f'"0x{v:x}"' for v in vs) + "]"


def redc(n, mb, count):
    return limbs((1 << (2 * mb + 6)) // n, count)


def honest_y(n, f):
    """y of order f modulo the prime n (needs f | n-1)."""
    e = (n - 1) // f
    for a in range(2, 1000):
        y = pow(a, e, n)
        if y != 1:
            return y
    raise RuntimeError


def forge(f, ks, rng):
    """Composite n = prod(1 + k f) and y of order f modulo every factor (so y^f = 1, gcd(y-1, n) = 1)."""
    ps = [1 + k * f for k in ks]
    assert all(sympy.isprime(p) for p in ps)
    ys = []
    for p, k in zip(ps, ks):
        while True:
            y = pow(rng.randrange(2, p - 1), k, p)
            if y != 1:
                ys.append(y)
                break
    n = 1
    for p in ps:
        n *= p
    y = int(crt(ps, ys)[0])
    assert pow(y, f, n) == 1 and gcd(y - 1, n) == 1
    return n, y


def find_forgery(f_bits, ks, n_lo, n_hi, rng):
    """A prime f of ~f_bits bits such that 1+k f is prime for all k in ks and n is in [n_lo, n_hi)."""
    for _ in range(200000):
        f = sympy.randprime(1 << (f_bits - 1), 1 << f_bits)
        if all(sympy.isprime(1 + k * f) for k in ks):
            n, y = forge(f, ks, rng)
            if n_lo <= n < n_hi:
                return f, n, y
    raise RuntimeError("no forgery parameters found")


class Harness:
    def __init__(self, root, project):
        self.dir = os.path.join(root, project)
        r = subprocess.run([NARGO, "compile"], cwd=self.dir, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        self.count = 0

    def solvable(self, text):
        self.count += 1
        name = f"case{self.count}"
        with open(os.path.join(self.dir, name + ".toml"), "w") as f:
            f.write(text)
        r = subprocess.run([NARGO, "execute", "--prover-name", name], cwd=self.dir,
                           capture_output=True, text=True)
        self.last_output = (r.stdout + r.stderr)[-700:]
        return r.returncode == 0


def native_toml(n, f, y, inv=None):
    if inv is None:
        inv = pow(y - 1, -1, n) if gcd(y - 1, n) == 1 and n > 1 else 0
    return f'n = "{n}"\nf = "{f}"\ny = "{y}"\ninv = "{inv}"\n'


def big_toml(n, f, y, inv=None, f_limbs=None):
    if inv is None:
        inv = pow(y - 1, -1, n) if gcd(y - 1, n) == 1 else 0
    fl = f_limbs if f_limbs is not None else limbs(f, 1)
    return (f"n = {hexl(limbs(n, 2))}\nf = {hexl(fl)}\nredc = {hexl(redc(n, 128, 2))}\n"
            f"y = {hexl(limbs(y, 2))}\ninv = {hexl(limbs(inv, 2))}\n")


# ---------------------------------------------------------------- attacks, reusable by the mutation run
def native_attacks(rng):
    """name -> toml text.  Every one must be REJECTED by the real library."""
    out = {}
    f, n, y = find_forgery(30, (2, 6), 1 << 62, 1 << 64, rng)
    out["forged composite p1*p2 (f^2 <= n)"] = native_toml(n, f, y)
    # y = 1: y^f = 1 trivially, but y - 1 = 0 has no inverse
    p = sympy.randprime(1 << 30, 1 << 31)
    comp = p * sympy.randprime(1 << 30, 1 << 31)
    out["y = 1 (no inverse of y - 1)"] = native_toml(comp, 2147483647, 1, inv=0)
    # random composite n < f^2 with an arbitrary y: y^f != 1  (y - 1 invertible, so ONLY y^f = 1 stops it)
    while True:
        f2 = sympy.randprime(1 << 31, 1 << 32)
        cn = 15 * (f2 // 15) + 1
        while sympy.isprime(cn):
            cn += 2
        if cn < f2 * f2 and gcd(12344, cn) == 1 and pow(12345, f2, cn) != 1:
            break
    out["random composite, arbitrary y (y^f != 1)"] = native_toml(cn, f2, 12345, inv=pow(12344, -1, cn))
    out["n = 1"] = native_toml(1, 65521, 0, inv=0)
    out["n = 2"] = native_toml(2, 65521, 0, inv=1)
    out["even n"] = native_toml(2 * (1 << 40) + 2, 4294967291, 5, inv=0)
    return out


def big_attacks(rng):
    out = {}
    f, n, y = find_forgery(62, (2, 6), 1 << 127, 1 << 128, rng)
    out["forged composite p1*p2 (f^2 <= n)"] = big_toml(n, f, y)
    # high bits of f beyond FB are ignored by the exponent loop but counted by f^2 > n:
    # f' = f + 2^100 makes f'^2 > n hold while y^f' is computed with only the low 64 bits (= f)
    ks, n3 = None, None
    for _ in range(400):
        fs = sympy.randprime(1 << 37, 1 << 38)          # small prime: p_i = 1 + k_i fs gives ~64-bit factors
        for _ in range(20000):
            k1 = 2 * rng.randrange(1 << 24, 1 << 25)
            k2 = 2 * rng.randrange(1 << 24, 1 << 25)
            if sympy.isprime(1 + k1 * fs) and sympy.isprime(1 + k2 * fs):
                n3, y3 = forge(fs, (k1, k2), rng)
                if 1 << 127 <= n3 < 1 << 128:
                    ks = (k1, k2)
                    break
        if ks:
            break
    assert ks, "could not build the high-bits forgery"
    out["f has bits above FB (ignored by the exponent)"] = big_toml(n3, fs, y3, f_limbs=[fs + (1 << 100)])
    # composite n < f^2 (so f^2 > n holds) with an arbitrary y: ONLY y^f = 1 stops it
    while True:
        fr = sympy.randprime(int(2 ** 63.7), 1 << 64)
        nr = rng.randrange(1 << 127, min(1 << 128, fr * fr)) | 1
        if not sympy.isprime(nr):
            y0 = rng.randrange(3, nr)
            if gcd(y0 - 1, nr) == 1 and pow(y0, fr, nr) != 1:
                break
    out["random composite n < f^2, arbitrary y (y^f != 1)"] = big_toml(nr, fr, y0)
    # y = 1: y^f = 1 trivially, f^2 > n holds, but y - 1 = 0 has no inverse
    out["y = 1 with composite n < f^2 (no inverse of y - 1)"] = big_toml(nr, fr, 1, inv=0)
    return out


class StepTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="zkp_steps_")
        for d in KEEP:
            shutil.copytree(os.path.join(HERE, d), os.path.join(cls.tmp, d),
                            ignore=shutil.ignore_patterns("target", "*.toml.bak"))
        cls.native = Harness(cls.tmp, "step_native")
        cls.big = Harness(cls.tmp, "step_big")
        cls.trial = Harness(cls.tmp, "step_trial")
        cls.rng = random.Random(2026)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ------------- completeness
    def test_native_honest(self):
        rng = random.Random(1)
        for _ in range(6):
            f = sympy.randprime(1 << 20, 1 << 31)
            n = None
            while n is None:
                e = rng.randrange(2, (f * f - 1) // f)   # n = f*e + 1 < f^2
                if sympy.isprime(f * e + 1) and f * e + 1 < 1 << 64:
                    n = f * e + 1
            self.assertTrue(self.native.solvable(native_toml(n, f, honest_y(n, f))), f"honest n={n} f={f}")

    def test_big_honest(self):
        rng = random.Random(2)
        for _ in range(3):
            f = sympy.randprime(int(2 ** 63.7), 1 << 64)   # f > 2^63.5 so that a 128-bit n < f^2 exists
            n = None
            while n is None:
                e = rng.randrange((1 << 127) // f + 1, min((1 << 128) // f, f - 1))
                c = f * e + 1
                if (1 << 127) <= c < (1 << 128) and c < f * f and sympy.isprime(c):
                    n = c
            self.assertTrue(self.big.solvable(big_toml(n, f, honest_y(n, f))), f"honest n={n} f={f}")

    # ------------- soundness
    def test_native_attacks_rejected(self):
        for label, text in native_attacks(self.rng).items():
            self.assertFalse(self.native.solvable(text), f"native: accepted {label}")

    def test_big_attacks_rejected(self):
        for label, text in big_attacks(self.rng).items():
            self.assertFalse(self.big.solvable(text), f"big: accepted {label}")

    # ------------- base case: trial division
    def test_trial_division_matches_primality_on_a_sample(self):
        rng = random.Random(8)
        sample = rng.sample(range(256, 65536), 70) + [sympy.randprime(256, 65536) for _ in range(40)]
        for n in sample:
            self.assertEqual(self.trial.solvable(f'n = "{n}"\n'), sympy.isprime(n), f"n={n}")

    def test_trial_division_attacks_rejected(self):
        attacks = {
            "251^2 (smallest prime factor 251)": 251 * 251,
            "n = 1 (no divisor at all)": 1,
            "n = 255": 255,
            "257^2 = 66049 (>= 2^16)": 257 * 257,
            "65536": 65536,
            "n = 0": 0,
            "247 * 251": 247 * 251,
        }
        for label, n in attacks.items():
            self.assertFalse(self.trial.solvable(f'n = "{n}"\n'), f"trial division accepted {label}")
        for n in (257, 65521, 46349, 12289 + 40000):
            if sympy.isprime(n):
                self.assertTrue(self.trial.solvable(f'n = "{n}"\n'), f"prime {n} rejected")

    def test_big_modulus_must_have_exactly_128_bits(self):
        rng = random.Random(5)
        f = sympy.randprime(1 << 63, 1 << 64)           # f > 2^63 so that f^2 > any 126-bit n
        for _ in range(200000):
            e = rng.randrange((1 << 125) // f, (1 << 126) // f)
            n = f * e + 1
            if n.bit_length() == 126 and sympy.isprime(n):
                # valid Pocklington data (f^2 > n), but the circuit is instantiated for 128-bit moduli
                self.assertTrue(f * f > n)
                self.assertFalse(self.big.solvable(big_toml(n, f, honest_y(n, f))))
                return
        self.fail("no 126-bit example found")


def run_mutants():
    rng = random.Random(99)
    n_att, b_att = native_attacks(rng), big_attacks(rng)
    mutants = [
        # label, file, old, new, harness, attack-name that the mutant must accept
        ("native: f^2 > n dropped", "zkp_primality/src/native.nr", "    assert(f * f > n);\n", "", "native", "forged composite p1*p2 (f^2 <= n)"),
        ("native: y^f == 1 dropped", "zkp_primality/src/native.nr", "    assert(z == 1);\n", "", "native", "random composite, arbitrary y (y^f != 1)"),
        ("native: inverse of y-1 dropped", "zkp_primality/src/native.nr", "    assert((y_minus_1 * inv) % n == 1);\n", "", "native", "y = 1 (no inverse of y - 1)"),
        ("native: n >= 3 dropped", "zkp_primality/src/native.nr", "    assert(n >= 3);\n", "", "native", "n = 1"),
        ("big: f^2 > n dropped", "zkp_primality/src/pocklington.nr", "    assert(fu * fu > to_u512(n_limbs));\n", "", "big", "forged composite p1*p2 (f^2 <= n)"),
        ("big: y^f == 1 dropped", "zkp_primality/src/pocklington.nr", "    assert(z == one); // y^f = 1\n", "", "big", "random composite n < f^2, arbitrary y (y^f != 1)"),
        ("big: inverse of y-1 dropped", "zkp_primality/src/pocklington.nr", "    assert((y - one) * inv == one); // gcd(y - 1, n) = 1\n", "", "big", "y = 1 with composite n < f^2 (no inverse of y - 1)"),
        ("big: f < 2^FB (high bits) not enforced", "zkp_primality/src/pocklington.nr", "                assert(!limb_bits[i]);\n", "                // dropped\n", "big", "f has bits above FB (ignored by the exponent)"),
    ]
    t_att = {"251^2": 'n = "63001"\n', "257^2": 'n = "66049"\n', "n = 1": 'n = "1"\n'}
    mutants += [
        ("trial: prime 251 missing from the list", "zkp_primality/src/native.nr", "239, 241, 251,", "239, 241, 241,", "trial", "251^2"),
        ("trial: bound n < 2^16 dropped", "zkp_primality/src/native.nr", "    assert(n < 65536);\n", "", "trial", "257^2"),
        ("trial: n >= 256 dropped", "zkp_primality/src/native.nr", "    assert(n >= 256);\n", "", "trial", "n = 1"),
    ]
    attacks = {"native": n_att, "big": b_att, "trial": t_att}
    survivors = []
    # provably redundant (kept as defense in depth): with canonical integer comparisons, n = 1 and n = 2
    # are already rejected by the z == 1 and inverse checks, so `n >= 3` has no attack of its own.
    expected_redundant = {"native: n >= 3 dropped"}
    for label, path, old, new, which, attack in mutants:
        tmp = tempfile.mkdtemp(prefix="zkp_mut_")
        try:
            for d in KEEP:
                shutil.copytree(os.path.join(HERE, d), os.path.join(tmp, d), ignore=shutil.ignore_patterns("target"))
            f = os.path.join(tmp, path)
            s = open(f).read()
            assert old in s, label
            open(f, "w").write(s.replace(old, new))
            h = Harness(tmp, {"native": "step_native", "big": "step_big", "trial": "step_trial"}[which])
            accepted = h.solvable(attacks[which][attack])
            print(f"MUTANT {label!r}: " + (f"caught (attack '{attack}' accepted by mutant)" if accepted else ("redundant (expected)" if label in expected_redundant else "SURVIVED  <-- the attack is rejected even without this assertion")))
            if not accepted and label not in expected_redundant:
                survivors.append(label)
                print("   nargo said:", " | ".join(l.strip() for l in h.last_output.splitlines()[-6:] if l.strip())[:400])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print("survivors:", survivors if survivors else "none")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "mutants":
        run_mutants()
    else:
        unittest.main(verbosity=2)
