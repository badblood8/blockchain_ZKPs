"""Tests for circom/fermat.circom and circom/lehmann.circom (the real circuits).

  * differential : circuit accepts  <=>  Python reference says "all bases pass"
  * regressions  : the audit bugs -- non-boolean equality, the skipped first base,
                   and vacuous bases 0 / 1 / n-1
  * soundness    : tamper with named internal wires, require the R1CS to reject

Run from the repo root:  python3 tests/test_primality.py
"""
import os
import random
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_lib import CircuitHarness, ROOT, read_wtns, write_tampered  # noqa: E402

FERMAT_K, LEHMANN_K, NBITS = 25, 10, 32


def bases_ok(n, bases):
    return n >= 5 and all(2 <= a <= n - 2 for a in bases)


def fermat_ref(n, bases):
    return bases_ok(n, bases) and all(pow(a, n - 1, n) == 1 for a in bases)


def lehmann_ref(n, bases):
    return (bases_ok(n, bases) and n % 2 == 1
            and all(pow(a, (n - 1) // 2, n) in (1, n - 1) for a in bases))


def is_prime(n):
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True


def pad(bases, k, fill):
    return (list(bases) + [fill] * k)[:k]


class PrimalityBase:
    """Shared tests; subclasses set NAME, K, ref."""
    NAME = K = None
    harness = None

    @classmethod
    def ref(cls, n, bases):
        raise NotImplementedError

    def accepts(self, n, bases):
        ok, w = self.harness.witness({"n": n, "a": bases})
        if ok:
            self.assertTrue(self.harness.check(w), "witness generated but R1CS unsatisfied")
        return ok

    def expect(self, n, bases, label=""):
        want = self.ref(n, bases)
        got = self.accepts(n, bases)
        self.assertEqual(got, want, f"{self.NAME} n={n} bases={bases} {label}: circuit={got} reference={want}")

    # --- known primes / composites with the standard base list
    def test_primes_accepted_composites_rejected(self):
        std = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97][:self.K]
        for n in (101, 997, 7919, 982451653, 4294967291):
            self.assertTrue(self.accepts(n, std), f"prime {n} rejected")
        for n in (100, 1001, 561, 1105, 982451654, 4294967295, 4, 9, 15, 25):
            self.assertFalse(self.accepts(n, std), f"composite {n} accepted")

    # --- differential testing against the Python reference
    def test_differential_random(self):
        rng = random.Random(2024)
        for _ in range(10):
            n = rng.randrange(5, 2**NBITS)
            if rng.random() < 0.5:                       # bias half the trials toward primes
                while not is_prime(n) and n < 2**NBITS - 1:
                    n += 1
            bases = [rng.randrange(2, n - 1) for _ in range(self.K)]
            self.expect(n, bases)

    # --- regression: the first base used to be silently skipped
    def test_every_base_position_is_checked(self):
        good, witness = self.pass_and_fail_base()
        n = self.PSEUDOPRIME
        for pos in (0, 1, self.K // 2, self.K - 1):
            bases = [good] * self.K
            bases[pos] = witness
            self.assertFalse(self.accepts(n, bases),
                             f"{self.NAME}: composite {n} accepted although base at position {pos} is a witness")
        self.assertTrue(self.accepts(n, [good] * self.K),
                        f"{self.NAME}: sanity -- pseudoprime {n} should pass when every base is a non-witness")

    # --- regression: vacuous bases must not count
    def test_vacuous_bases_rejected(self):
        p = 101
        std = pad([2, 3, 5, 7], self.K, 2)
        self.assertTrue(self.accepts(p, std))
        for label, bad in (("a=0", 0), ("a=1", 1), ("a=n-1", p - 1), ("a=n", p), ("a=n+5", p + 5)):
            for pos in (0, self.K - 1):
                bases = list(std)
                bases[pos] = bad
                self.assertFalse(self.accepts(p, bases), f"{self.NAME}: base {label} at position {pos} accepted")

    def test_tiny_and_even_n_rejected(self):
        for n in (0, 1, 2, 3, 4, 6, 8, 100, 2**32, 2**32 + 1):
            self.assertFalse(self.accepts(n, pad([2, 2], self.K, 2)), f"{self.NAME}: n={n} accepted")

    # --- soundness: tamper with named internal wires
    def test_tamper_internal_wires(self):
        n = 101
        bases = pad([2, 3, 5, 7, 11, 13, 17, 19, 23, 29], self.K, 2)
        ok, w = self.harness.witness({"n": n, "a": bases})
        self.assertTrue(ok)
        vals = read_wtns(w)[0]
        names = {}
        with open(os.path.join(self.harness.dir, self.NAME + ".sym")) as f:
            for line in f:
                label, var, comp, name = line.strip().split(",", 3)
                if int(var) >= 0:
                    names[name] = int(var)
        targets = [v for nm, v in names.items()
                   if re.search(r"\.(acc\[\d+\]|isOne\[\d+\]\.(out|inv)|isNMinusOne\[\d+\]\.(out|inv)|baseOk\[\d+\])$", nm)]
        self.assertGreater(len(targets), 10)
        rng = random.Random(5)
        survivors = []
        for wire in rng.sample(targets, 8):
            for delta in (1, -1):
                t = os.path.join(self.harness.dir, f"tamper_{wire}_{delta}.wtns")
                write_tampered(w, t, wire, vals[wire] + delta)
                if self.harness.check(t):
                    survivors.append((wire, delta))
        self.assertEqual(survivors, [], f"tampered wires still satisfy the constraints: {survivors}")


class FermatTests(PrimalityBase, unittest.TestCase):
    NAME, K = "fermat", FERMAT_K
    PSEUDOPRIME = 341          # 2^340 = 1 mod 341 (Fermat pseudoprime to base 2)
    ref = staticmethod(fermat_ref)

    def pass_and_fail_base(self):
        assert pow(2, 340, 341) == 1 and pow(3, 340, 341) != 1
        return 2, 3

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="zkp_fermat_")
        cls.harness = CircuitHarness(os.path.join(ROOT, "circom/fermat.circom"), cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)


class LehmannTests(PrimalityBase, unittest.TestCase):
    NAME, K = "lehmann", LEHMANN_K
    PSEUDOPRIME = 341          # 2^170 = 1 mod 341, but 3^170 = 67
    ref = staticmethod(lehmann_ref)

    def pass_and_fail_base(self):
        assert pow(2, 170, 341) == 1 and pow(3, 170, 341) not in (1, 340)
        return 2, 3

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="zkp_lehmann_")
        cls.harness = CircuitHarness(os.path.join(ROOT, "circom/lehmann.circom"), cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
