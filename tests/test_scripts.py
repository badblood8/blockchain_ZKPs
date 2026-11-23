"""Tests that need only python3 + sympy: reference primality scripts, the input generator and scripts/zk.py.

    python3 tests/test_scripts.py
"""
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

import sympy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import fermat  # noqa: E402
import gen_inputs  # noqa: E402
import lehmann  # noqa: E402
import pratt_certificate_generator as pcg  # noqa: E402
import rabin_miller  # noqa: E402
import zk  # noqa: E402

CARMICHAEL = [561, 1105, 1729, 2465, 2821, 6601, 8911]


class ReferenceTests(unittest.TestCase):
    def test_edge_inputs_are_not_prime(self):
        for fn in (fermat.fermat_primality_test, lehmann.lehmann_primality_test,
                   rabin_miller.rabin_miller_primality_test):
            for n in (-7, -1, 0, 1):
                self.assertFalse(fn(n), f"{fn.__name__}({n})")

    def test_primes_accepted_everywhere(self):
        for p in (2, 3, 5, 7, 101, 997, 7919, 982451653):
            for fn in (fermat.fermat_primality_test, lehmann.lehmann_primality_test,
                       rabin_miller.rabin_miller_primality_test):
                self.assertTrue(fn(p), f"{fn.__name__}({p})")

    def test_rabin_miller_rejects_carmichael_numbers(self):
        for n in CARMICHAEL:
            self.assertFalse(rabin_miller.rabin_miller_primality_test(n, 20), n)

    def test_random_composites(self):
        for n in (4, 9, 15, 100, 1001, 1000001, 982451654):
            self.assertFalse(rabin_miller.rabin_miller_primality_test(n), n)


class PrattGeneratorTests(unittest.TestCase):
    def test_certificates_verify(self):
        for p in (3, 5, 1933, 65521, 8675309, 4294967291):
            cert = pcg.build_certificate(p, 20, 12)
            self.assertTrue(pcg.verify_certificate(cert)[0], p)


class InputGeneratorTests(unittest.TestCase):
    def test_bases_in_range_and_sized(self):
        for n, k in ((5, 2), (101, 25), (982451653, 10)):
            d = gen_inputs.make("fermat", n, k)
            self.assertEqual(len(d["a"]), k)
            self.assertTrue(all(2 <= a <= n - 2 for a in d["a"]))

    def test_validation(self):
        with self.assertRaises(SystemExit):
            gen_inputs.make("lehmann", 100, 5)          # even n
        with self.assertRaises(SystemExit):
            gen_inputs.make("fermat", 3, 1)             # n < 5
        with self.assertRaises(SystemExit):
            gen_inputs.make("fermat", 1 << 33, 5)       # wider than the 32-bit circuits
        with self.assertRaises(SystemExit):
            gen_inputs.make("fermat", 7, 25)            # not enough distinct bases

    def test_cli_refuses_composites_unless_forced(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "x.json")
            run = lambda *a: subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "gen_inputs.py"), *a],
                                            capture_output=True, text=True)
            r = run("rabin_miller", "100001", "--out", out)
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse(os.path.exists(out))
            r = run("rabin_miller", "100001", "--force", "--out", out)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.load(open(out))["n"], 100001)
            r = run("multiply", "17", "19", "--out", out)
            self.assertEqual(json.load(open(out)), {"p": "17", "q": "19"})

    def test_shipped_inputs_are_valid_statements(self):
        for name in ("fermat", "lehmann", "rabin_miller"):
            d = json.load(open(os.path.join(ROOT, "inputs", f"{name}.json")))
            self.assertTrue(sympy.isprime(d["n"]), name)
            self.assertTrue(all(2 <= a <= d["n"] - 2 for a in d["a"]), name)
        self.assertTrue(pcg.verify_certificate(json.load(open(os.path.join(ROOT, "inputs", "pratt.json"))))[0])


class CeremonyHelperTests(unittest.TestCase):
    def test_pot_level_matches_snarkjs_rule(self):
        # snarkjs: cirPower = floor(log2(constraints + public + outputs)) + 1
        self.assertEqual(zk.pot_level_from_counts(64972, 11, 0), 16)    # Rabin-Miller (fits 2^16)
        self.assertEqual(zk.pot_level_from_counts(68546, 11, 0), 17)    # same circuit compiled with --O1 (did not fit)
        self.assertEqual(zk.pot_level_from_counts(110399, 26, 0), 17)   # Fermat
        self.assertEqual(zk.pot_level_from_counts(198828, 1, 0), 18)    # Pratt
        self.assertEqual(zk.pot_level_from_counts(1, 0, 1), 2)          # multiply
        # boundary (snarkjs cli.cjs: log2 is the floor, so power = bit_length of the sum)
        self.assertEqual(zk.pot_level_from_counts(65534, 1, 0), 16)     # sum 65535 = 2^16 - 1
        self.assertEqual(zk.pot_level_from_counts(65535, 1, 0), 17)     # sum 65536 = 2^16
        self.assertEqual(zk.pot_level_from_counts(65536, 0, 0), 17)

    def test_pot_level_parses_snarkjs_output(self):
        text = ("[INFO]  snarkJS: Curve: bn-128\n[INFO]  snarkJS: # of Wires: 63981\n"
                "[INFO]  snarkJS: # of Constraints: 64972\n[INFO]  snarkJS: # of Private Inputs: 0\n"
                "[INFO]  snarkJS: # of Public Inputs: 11\n[INFO]  snarkJS: # of Labels: 75586\n"
                "[INFO]  snarkJS: # of Outputs: 0\n")
        self.assertEqual(zk.pot_level(text), 16)

    def test_published_hash_table_is_well_formed(self):
        for power, h in zk.HEZ_BLAKE2B.items():
            self.assertEqual(len(h), 128, power)
            int(h, 16)

    def test_ceremony_file_is_hash_checked(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, zk.ptau_name(16))
            with open(path, "wb") as f:
                f.write(b"this is not the ceremony file")
            ok, why = zk.verify_ptau(path, 16)
            self.assertFalse(ok)
            self.assertIsNone(zk.find_ptau(16, d), "a file with the wrong hash must be ignored")
            # a file whose hash equals the published one is accepted (simulate by patching the table)
            good = hashlib.blake2b(b"this is not the ceremony file", digest_size=64).hexdigest()
            saved = zk.HEZ_BLAKE2B[16]
            zk.HEZ_BLAKE2B[16] = good
            try:
                with redirect_stderr(io.StringIO()):
                    self.assertEqual(zk.find_ptau(16, d), path)
                self.assertEqual(zk.find_ptau(15, d), path, "a larger ceremony file serves a smaller circuit")
                self.assertIsNone(zk.find_ptau(17, d), "a smaller ceremony file must not serve a bigger circuit")
            finally:
                zk.HEZ_BLAKE2B[16] = saved

    def test_unknown_power_cannot_be_verified(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, zk.ptau_name(12))
            open(path, "wb").write(b"x")
            self.assertFalse(zk.verify_ptau(path, 12)[0])

    def test_timed_records_metrics_and_propagates_failure(self):
        with tempfile.TemporaryDirectory() as d:
            m = os.path.join(d, "m.json")
            with redirect_stdout(io.StringIO()):
                zk.timed(m, "step", [sys.executable, "-c", "pass"])
            data = json.load(open(m))
            self.assertIn("step", data)
            self.assertGreaterEqual(data["step"]["ms"], 0)
            with self.assertRaises(SystemExit) as cm, redirect_stdout(io.StringIO()):
                zk.timed(m, "bad", [sys.executable, "-c", "raise SystemExit(3)"])
            self.assertEqual(cm.exception.code, 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
