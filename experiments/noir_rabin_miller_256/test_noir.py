"""Adversarial tests for rabin_miller_256 (Noir + noir-bignum).

Each case writes a Prover.toml (n, bases, redc_param, hints), runs `nargo execute`
in a scratch copy of the project, and checks that the witness is solvable exactly
when the statement is true and the prover is honest.  A rejected case means NO valid
witness exists, i.e. no proof can be produced.

    NARGO=/path/to/nargo python3 test_noir.py
"""
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
LIMB = 120
MASK = (1 << LIMB) - 1
K = 1


def limbs(x, count=3):
    return [(x >> (LIMB * i)) & MASK for i in range(count)]


def honest_hint(n, a):
    e = n - 1
    r = (e & -e).bit_length() - 1
    d = e >> r
    if pow(a, d, n) == 1:
        return 1, True
    for j in range(r):
        if pow(a, d << j, n) == n - 1:
            return r - j, False
    return 1, False


def toml(n, a, idx=None, use_one=None, redc=None):
    if idx is None or use_one is None:
        h = honest_hint(n, a) if n > 3 and n % 2 else (1, False)
        idx = h[0] if idx is None else idx
        use_one = h[1] if use_one is None else use_one
    if redc is None:
        redc = (1 << (2 * 256 + 6)) // n
    q = lambda v: f'"0x{v:x}"'
    return "\n".join([
        "n = [" + ", ".join(q(v) for v in limbs(n)) + "]",
        f'a = ["{a}"]',
        "redc_param = [" + ", ".join(q(v) for v in limbs(redc)) + "]",
        f'idx = ["{idx}"]',
        "use_one = [" + ("true" if use_one else "false") + "]",
    ]) + "\n"


def rand_prime_256(rng, two_adic=None):
    """256-bit prime (top bit set); optionally with n-1 = k * 2^two_adic exactly 2-adic valuation >= two_adic."""
    while True:
        if two_adic:
            k = rng.getrandbits(256 - two_adic) | (1 << (255 - two_adic))
            n = (k << two_adic) + 1
        else:
            n = rng.getrandbits(256) | (1 << 255) | 1
        if n.bit_length() == 256 and sympy.isprime(n):
            return n


class Rm256(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="zkp_noir256_")
        cls.proj = os.path.join(cls.tmp, "proj")
        shutil.copytree(HERE, cls.proj, ignore=shutil.ignore_patterns("target", "__pycache__", "Prover.toml"))
        r = subprocess.run([NARGO, "compile"], cwd=cls.proj, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.rng = random.Random(256)
        cls.n = rand_prime_256(cls.rng)                  # random prime, small r
        cls.n_big_r = rand_prime_256(cls.rng, 200)       # prime with r >= 200
        cls.count = 0

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def solvable(self, text):
        Rm256.count += 1
        name = f"case{Rm256.count}"
        with open(os.path.join(self.proj, name + ".toml"), "w") as f:
            f.write(text)
        r = subprocess.run([NARGO, "execute", "--prover-name", name], cwd=self.proj,
                           capture_output=True, text=True)
        return r.returncode == 0

    # ---------------- completeness
    def test_honest_primes_accepted(self):
        for n in (self.n, self.n_big_r, 57896044618658097711785492504343953926634992332820282019728792003957552474657):
            self.assertEqual(n.bit_length(), 256)
            for a in (2, 3, 5, 65537, 2**63 + 25):
                self.assertTrue(self.solvable(toml(n, a)), f"prime {n:x} base {a} rejected")

    def test_large_two_adic_valuation(self):
        n = self.n_big_r
        r = ((n - 1) & -(n - 1)).bit_length() - 1
        self.assertGreaterEqual(r, 200)
        a = 2
        idx, use_one = honest_hint(n, a)
        self.assertFalse(use_one)
        self.assertTrue(1 <= idx <= r)
        self.assertTrue(self.solvable(toml(n, a)))

    def test_x0_equals_one_branch(self):
        """A 64-bit base inside the subgroup of odd order d (a^d == 1): probability 2^-r per base."""
        n = rand_prime_256(self.rng, 4)
        e = n - 1
        r = (e & -e).bit_length() - 1
        d = e >> r
        a = next(a for a in (self.rng.getrandbits(63) + 2 for _ in range(10000)) if pow(a, d, n) == 1)
        self.assertEqual(honest_hint(n, a), (1, True))
        self.assertTrue(self.solvable(toml(n, a)))
        # flipping the hint to the other branch must fail: s_i == n-1 never holds when s_r == 1
        self.assertFalse(self.solvable(toml(n, a, use_one=False)))

    # ---------------- soundness: composites
    def test_composites_rejected(self):
        rng = random.Random(7)
        cases = []
        # semiprime of two ~128-bit primes with the top bit of n set
        while True:
            p, q = sympy.randprime(2**127, 2**128), sympy.randprime(2**127, 2**128)
            if (p * q).bit_length() == 256 and p * q > 2 ** 255:
                cases.append(p * q)
                break
        cases.append(self.n * 3 if (self.n * 3).bit_length() == 256 else self.n_big_r + 2)  # n*3 or near-prime odd
        cases.append(2 ** 255 + 1)                         # divisible by 3
        cases.append(2 ** 256 - 1)                          # 2^256 - 1
        cases.append(rng.getrandbits(256) | (1 << 255) | 1)
        for n in cases:
            if sympy.isprime(n) or n % 2 == 0 or n.bit_length() != 256:
                continue
            for a in (2, 3, 5, 7):
                for hint in (honest_hint(n, a), (1, False), (1, True), (2, False), (5, False)):
                    self.assertFalse(self.solvable(toml(n, a, idx=hint[0], use_one=hint[1])),
                                     f"composite {n:x} accepted (a={a}, hint={hint})")

    # ---------------- soundness: malformed statements
    def test_bad_moduli_rejected(self):
        for label, n in {
            "even": self.n + 1,
            "255 bits (top bit clear)": rand_prime_256(random.Random(1)) >> 1 | 1,
            "n = 2^256 + 1 (257 bits)": 2 ** 256 + 1,
            "n = 1": 1,
        }.items():
            self.assertFalse(self.solvable(toml(n, 2, idx=1, use_one=False)), f"{label}: accepted")

    def test_bad_bases_rejected(self):
        for a in (0, 1):
            self.assertFalse(self.solvable(toml(self.n, a, idx=1, use_one=False)), f"base {a} accepted")

    # ---------------- soundness: dishonest hints on a TRUE statement
    def test_wrong_hints_rejected(self):
        n, a = self.n, 2
        idx, use_one = honest_hint(n, a)
        r = ((n - 1) & -(n - 1)).bit_length() - 1
        self.assertFalse(use_one)
        self.assertTrue(self.solvable(toml(n, a, idx=idx, use_one=use_one)))
        wrong = {
            "idx = 0": (0, False),
            "idx = idx - 1": (idx - 1, False),
            "idx = idx + 1": (idx + 1, False),
            "idx = r + 1 (beyond r)": (r + 1, False),
            "idx = 255": (255, False),
            "idx = 256 (out of range)": (256, False),
            "use_one with a^d != 1": (idx, True),
        }
        for label, (i, u) in wrong.items():
            if (i, u) == (idx, use_one):
                continue
            self.assertFalse(self.solvable(toml(n, a, idx=i, use_one=u)), f"{label}: accepted")

    # ---------------- soundness: unvalidated redc_param
    def test_wrong_redc_param_cannot_help(self):
        """redc_param is an unvalidated witness (noir-bignum: it only steers unconstrained Barrett
        reduction).  The property that matters for soundness: a wrong value must not let a prover
        get a witness for a FALSE statement.  (For a true statement a slightly wrong constant may
        still solve, since Barrett reduction is tolerant; that is harmless.)"""
        rng = random.Random(11)
        composites = []
        while len(composites) < 3:
            p, q = sympy.randprime(2**127, 2**128), sympy.randprime(2**127, 2**128)
            if (p * q).bit_length() == 256:
                composites.append(p * q)
        for comp in composites:
            for delta in (0, 1, -1, 99999, 1 << 100, -(1 << 100)):
                redc = (1 << 518) // comp + delta
                if redc < 0:
                    continue
                for a in (2, 3):
                    self.assertFalse(self.solvable(toml(comp, a, redc=redc)),
                                     f"composite accepted with redc delta {delta}")
        # a true statement with a wild redc_param either solves (harmless) or fails; never crashes the check
        n = self.n
        for redc in (0, 1, (1 << 518) // n + 12345):
            self.solvable(toml(n, 2, redc=redc))

if __name__ == "__main__":
    unittest.main(verbosity=2)
