"""Tests for lib/pratt.circom, circom/pratt.circom and scripts/pratt_certificate_generator.py.

  * valid certificates for many primes are accepted
  * composites / forged certificates are rejected
  * fuzzing: mutate valid certificates and require circuit == Python reference verifier
  * soundness: tamper with named internal wires, the R1CS must reject
  * the real 32-bit circuit accepts inputs/pratt.json and rejects tampered copies

Run from the repo root:  python3 tests/test_pratt.py
"""
import copy
import json
import os
import random
import re
import shutil
import sys
import tempfile
import unittest

import sympy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))
from test_lib import CircuitHarness, ROOT, read_wtns, write_tampered  # noqa: E402
import pratt_certificate_generator as gen  # noqa: E402

SMALL_BITS, SMALL_M, SMALL_F = 16, 7, 5


def small_cert(p):
    return gen.build_certificate(p, SMALL_M, SMALL_F)


def idx(cert, p):
    """Index of the entry whose prime is p (entries are in discovery order, not sorted)."""
    return cert["certPrimes"].index(p)


def blank(cert, i, f):
    """Replace entry i by the padding entry (3, 2, no factors)."""
    cert["certPrimes"][i], cert["certBases"][i], cert["certFactors"][i] = 3, 2, [1] * f


class GeneratorTests(unittest.TestCase):
    def test_generated_certificates_verify_in_python(self):
        for p in (3, 5, 7, 13, 1933, 65521, 8675309, 982451653, 4294967291):
            cert = gen.build_certificate(p, 20, 12)
            ok, why = gen.verify_certificate(cert)
            self.assertTrue(ok, f"{p}: {why}")

    def test_primitive_roots_are_primitive(self):
        for p in (3, 5, 23, 1933, 2168827, 8675309):
            g = gen.primitive_root(p)
            self.assertEqual(sympy.n_order(g, p), p - 1)

    def test_rejects_composites_and_overflow(self):
        for n in (1, 2, 4, 15, 561):
            with self.assertRaises(ValueError):
                gen.build_certificate(n, 9, 4)
        with self.assertRaises(ValueError):
            gen.build_certificate(8675309, 3, 4)       # too few entries
        with self.assertRaises(ValueError):
            gen.build_certificate(8675309, 9, 1)       # too few factor slots

    def test_python_verifier_rejects_bad_certificates(self):
        good = gen.build_certificate(1933, 7, 5)
        self.assertTrue(gen.verify_certificate(good)[0])
        bad = copy.deepcopy(good); bad["certBases"][0] += 1
        self.assertFalse(gen.verify_certificate(bad)[0])
        bad = copy.deepcopy(good); blank(bad, idx(bad, 23), 5)   # drop the entry for 23
        self.assertFalse(gen.verify_certificate(bad)[0])
        bad = copy.deepcopy(good); bad["mainPrime"] = 1931
        self.assertFalse(gen.verify_certificate(bad)[0])


class PrattCircuitBase:
    harness = None

    def accepts(self, cert):
        ok, w = self.harness.witness(cert)
        if ok:
            self.assertTrue(self.harness.check(w), "witness generated but R1CS unsatisfied")
        return ok


class SmallPrattTests(PrattCircuitBase, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="zkp_pratt_")
        cls.harness = CircuitHarness(os.path.join(ROOT, "tests/lib/pratt_small.circom"), cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ---------- completeness
    def test_valid_certificates_accepted(self):
        primes = [3, 5, 7, 11, 13, 17, 23, 97, 257, 1933, 12289, 40961, 65521, 65519]
        for p in primes:
            self.assertTrue(self.accepts(small_cert(p)), f"valid certificate for {p} rejected")

    def test_random_primes_accepted(self):
        rng = random.Random(11)
        done = 0
        while done < 8:
            p = sympy.randprime(3, 2 ** SMALL_BITS)
            try:
                cert = small_cert(p)
            except ValueError:                      # does not fit this instance's capacity
                continue
            self.assertTrue(self.accepts(cert), f"valid certificate for {p} rejected")
            done += 1

    # ---------- soundness: composites cannot be certified
    def test_composites_have_no_certificate(self):
        """For composite n, build the most plausible certificate (true factorization of n-1,
        real entries for each factor) and try EVERY base: none may pass in Python, and the
        circuit must agree on a sample."""
        rng = random.Random(1)
        for n in (9, 15, 21, 91, 341, 561, 1105, 1729, 2047, 6601, 65535, 65521 * 1):
            if sympy.isprime(n):
                continue
            facs = []
            for q, e in sorted(sympy.factorint(n - 1).items()):
                if q != 2:
                    facs += [q] * e
            s = sympy.multiplicity(2, n - 1)
            if s < 1 or len(facs) > SMALL_F:
                continue
            try:
                fac_cert = [gen.build_certificate(q, SMALL_M, SMALL_F) for q in set(facs)]
            except ValueError:
                continue
            entries = [n] + sorted({q for fc in fac_cert for q in fc["certPrimes"] if q != 3} | {3} if facs else set())
            entries = (entries + [3] * SMALL_M)[:SMALL_M]
            if any(f not in entries for f in facs):
                continue
            passed_python = []
            sample = rng.sample(range(2, n), min(6, n - 2))
            for g in range(2, n):
                cert = {"mainPrime": n,
                        "certPrimes": entries,
                        "certBases": [g] + [gen.primitive_root(e) if e > 2 else 2 for e in entries[1:]],
                        "certFactors": [facs + [1] * (SMALL_F - len(facs))] +
                                       [gen.odd_prime_factors(e) + [1] * (SMALL_F - len(gen.odd_prime_factors(e)))
                                        for e in entries[1:]]}
                if gen.verify_certificate(cert, SMALL_BITS)[0]:
                    passed_python.append(g)
                if g in sample:
                    self.assertFalse(self.accepts(cert), f"composite {n} accepted with base {g}")
            self.assertEqual(passed_python, [], f"python reference certified composite {n}")

    def test_specific_forgeries_rejected(self):
        good = small_cert(1933)                      # entries 1933,23,11,7,5,3,pad
        self.assertTrue(self.accepts(good))
        cases = {}
        i23 = idx(good, 23)
        c = copy.deepcopy(good); c["certBases"][0] = 4                 # a square is never a primitive root
        cases["non-primitive-root base for 1933"] = c
        c = copy.deepcopy(good); c["certBases"][i23] = 2               # 2 has order 11 mod 23
        cases["base 2 for 23 (order 11, not 22)"] = c
        c = copy.deepcopy(good); blank(c, i23, SMALL_F)
        cases["entry for factor 23 removed"] = c
        c = copy.deepcopy(good); c["certFactors"][0] = [3, 7, 1, 1, 1]  # omits the factor 23
        cases["factor list omits a prime factor"] = c
        c = copy.deepcopy(good); c["certFactors"][0] = [3, 7, 23, 23, 1]
        cases["extra factor, product too large"] = c
        c = copy.deepcopy(good); c["mainPrime"] = 1931
        cases["mainPrime != certPrimes[0]"] = c
        c = copy.deepcopy(good); c["certPrimes"][0] = 1935; c["mainPrime"] = 1935
        cases["composite 1935 in place of 1933"] = c
        c = copy.deepcopy(good); c["certBases"][0] = 0
        cases["base 0"] = c
        c = copy.deepcopy(good); c["certBases"][0] = 1
        cases["base 1"] = c
        c = copy.deepcopy(good); c["certBases"][0] = 1933
        cases["base == p"] = c
        c = copy.deepcopy(good); c["certFactors"][0] = [1, 1, 1, 1, 1]
        cases["no factors at all"] = c
        for label, cert in cases.items():
            # guard against a "forgery" that is secretly valid (a mistake in the test itself)
            self.assertFalse(gen.verify_certificate(cert, SMALL_BITS)[0], f"test bug, not a forgery: {label}")
            self.assertFalse(self.accepts(cert), f"forgery accepted: {label}")

    def test_out_of_range_and_degenerate_primes_rejected(self):
        for p in (0, 1, 2, 4, 65537, 2 ** 16, 2 ** 20 + 7):
            cert = small_cert(3)
            cert["mainPrime"] = p
            cert["certPrimes"][0] = p
            self.assertFalse(self.accepts(cert), f"mainPrime {p} accepted")

    def test_duplicate_factors_both_orders(self):
        """65521 - 1 = 2^4 * 3^2 * 5 * 7 * 13: repeated 3 is listed twice."""
        cert = small_cert(65521)
        self.assertEqual(cert["certFactors"][0], [3, 3, 5, 7, 13])
        self.assertTrue(self.accepts(cert))
        shuffled = copy.deepcopy(cert); shuffled["certFactors"][0] = [3, 5, 3, 7, 13]
        self.assertTrue(gen.verify_certificate(shuffled)[0])
        self.assertTrue(self.accepts(shuffled), "non-adjacent duplicate is merely redundant, must be accepted")

    def test_cannot_skip_a_lucas_check_by_faking_duplicates(self):
        """If the bad prime is listed AFTER an equal value, the 2nd copy is skipped -- but the first is
        checked, so a base that fails for q still fails."""
        cert = small_cert(23)                        # 22 = 2 * 11; 2 is not a primitive root mod 23
        cert["certBases"][0] = 2
        self.assertFalse(self.accepts(cert))

    # ---------- fuzzing: circuit must agree with the Python reference
    def test_fuzz_mutations_match_reference(self):
        rng = random.Random(2024)
        bases = [small_cert(p) for p in (1933, 65521, 12289, 257)]
        disagreements = []
        for _ in range(45):
            cert = copy.deepcopy(rng.choice(bases))
            for _ in range(rng.choice((1, 1, 2))):
                i = rng.randrange(SMALL_M)
                kind = rng.choice(("base", "prime", "factor", "factor", "swap", "main"))
                if kind == "base":
                    cert["certBases"][i] = rng.randrange(0, cert["certPrimes"][i] + 3)
                elif kind == "prime":
                    cert["certPrimes"][i] = max(0, cert["certPrimes"][i] + rng.randrange(-3, 4))
                    if i == 0:
                        cert["mainPrime"] = cert["certPrimes"][0]
                elif kind == "factor":
                    pool = [1, 1, 2, 3, 5, 7, 11, 13, 23] + cert["certPrimes"] + [rng.randrange(0, 70000)]
                    cert["certFactors"][i][rng.randrange(SMALL_F)] = rng.choice(pool)
                elif kind == "swap":
                    j = rng.randrange(SMALL_M)
                    for key in ("certPrimes", "certBases", "certFactors"):
                        cert[key][i], cert[key][j] = cert[key][j], cert[key][i]
                    cert["mainPrime"] = cert["certPrimes"][0]
                else:
                    cert["mainPrime"] = max(0, cert["mainPrime"] + rng.randrange(-2, 3))
            want = gen.verify_certificate(cert, SMALL_BITS)[0]
            got = self.accepts(cert)
            if want != got:
                disagreements.append((want, got, cert))
        self.assertEqual(disagreements, [], f"circuit and reference verifier disagree: {disagreements[:2]}")

    # ---------- soundness: tamper with internal wires
    def test_tamper_internal_wires(self):
        cert = small_cert(1933)
        ok, w = self.harness.witness(cert)
        self.assertTrue(ok)
        vals = read_wtns(w)[0]
        names = {}
        with open(os.path.join(self.harness.dir, "pratt_small.sym")) as f:
            for line in f:
                label, var, comp, name = line.strip().split(",", 3)
                if int(var) >= 0:
                    names[name] = int(var)
        pat = r"\.(entry\[\d+\]\.(exp2|sel\[\d+\]|prod\[\d+\]|exps\[\d+\]|needsCheck\[\d+\]|memberSum\[\d+\]|pow2s))$"
        targets = sorted(v for nm, v in names.items() if re.search(pat, nm))
        self.assertGreater(len(targets), 50)
        rng = random.Random(9)
        survivors = []
        for wire in rng.sample(targets, 14):
            for delta in (1, -1):
                t = os.path.join(self.harness.dir, f"tp_{wire}_{delta}.wtns")
                write_tampered(w, t, wire, vals[wire] + delta)
                if self.harness.check(t):
                    survivors.append((wire, delta))
        self.assertEqual(survivors, [], f"tampered wires still satisfy the constraints: {survivors}")


class RealPrattCircuitTests(PrattCircuitBase, unittest.TestCase):
    """The shipped 32-bit circuit (9 entries, 4 factors) and inputs/pratt.json."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="zkp_pratt32_")
        cls.harness = CircuitHarness(os.path.join(ROOT, "circom/pratt.circom"), cls.tmp)
        with open(os.path.join(ROOT, "inputs/pratt.json")) as f:
            cls.sample = json.load(f)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_shipped_input_matches_generator_and_verifies(self):
        self.assertEqual(self.sample, gen.build_certificate(8675309, 9, 4))
        self.assertTrue(gen.verify_certificate(self.sample)[0])
        self.assertTrue(self.accepts(self.sample))

    def test_other_32bit_primes(self):
        for p in (65537, 982451653, 2147483647, 3221225473):
            try:
                cert = gen.build_certificate(p, 9, 4)
            except ValueError:
                continue
            self.assertTrue(self.accepts(cert), f"certificate for {p} rejected")

    def test_tampered_sample_rejected(self):
        s = self.sample
        cases = {}
        i1933 = idx(s, 1933)
        i2168827 = idx(s, 2168827)
        c = copy.deepcopy(s); c["certBases"][0] = 4          # a square is never a primitive root
        cases["wrong base"] = c
        c = copy.deepcopy(s); c["mainPrime"] = 8675311; c["certPrimes"][0] = 8675311
        cases["different (composite) mainPrime"] = c
        c = copy.deepcopy(s); blank(c, i1933, 4)
        cases["missing entry for factor 1933"] = c
        c = copy.deepcopy(s); c["certFactors"][i2168827][3] = 1
        cases["omit factor 1933 of 2168826"] = c
        c = copy.deepcopy(s); c["mainPrime"] = 2168827
        cases["mainPrime != certPrimes[0]"] = c
        for label, cert in cases.items():
            self.assertFalse(gen.verify_certificate(cert)[0], f"test bug, not a forgery: {label}")
            self.assertFalse(self.accepts(cert), f"accepted: {label}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
