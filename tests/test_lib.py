"""Tests for lib/bits.circom and lib/modarith.circom.

Three kinds of check:
  1. Functional : witness output equals Python's pow() / modular product.
  2. Rejection  : inputs that violate a precondition make witness generation fail.
  3. Soundness  : take an honest witness, change ONE wire to a wrong value, and
                  require `snarkjs wtns check` to reject it.  If any wire were
                  still assigned with `<--` and never constrained, tampering with
                  it would go unnoticed and this test would fail.

Requires circom, node and snarkjs on PATH.  Run from the repo root:
    python3 tests/test_lib.py
"""
import json
import os
import random
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
K = 32  # bit width the harness circuits are compiled with
FIELD_P = 21888242871839275222246405745257275088548364400416034343698204183013485423617


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def read_wtns(path):
    """Parse a snarkjs .wtns file. Returns (list of ints, raw bytes, offset of section 2)."""
    with open(path, "rb") as f:
        data = f.read()
    assert data[:4] == b"wtns"
    n_sections = struct.unpack_from("<I", data, 8)[0]
    pos, sections = 12, {}
    for _ in range(n_sections):
        sid, size = struct.unpack_from("<IQ", data, pos)
        sections[sid] = (pos + 12, size)
        pos += 12 + size
    n8 = struct.unpack_from("<I", data, sections[1][0])[0]
    start, size = sections[2]
    vals = [int.from_bytes(data[start + i * n8: start + (i + 1) * n8], "little")
            for i in range(size // n8)]
    return vals, data, start, n8


def write_tampered(src, dst, wire, new_value):
    vals, data, start, n8 = read_wtns(src)
    buf = bytearray(data)
    buf[start + wire * n8: start + (wire + 1) * n8] = (new_value % FIELD_P).to_bytes(n8, "little")
    with open(dst, "wb") as f:
        f.write(bytes(buf))


class CircuitHarness:
    """Compile a circuit once; generate witnesses for many inputs."""

    def __init__(self, circom_file, workdir):
        self.name = os.path.splitext(os.path.basename(circom_file))[0]
        self.dir = workdir
        r = run(["circom", circom_file, "--r1cs", "--wasm", "--sym", "-o", workdir])
        if r.returncode != 0:
            raise RuntimeError(r.stdout + r.stderr)
        self.r1cs = os.path.join(workdir, self.name + ".r1cs")
        self.wasm = os.path.join(workdir, self.name + "_js", self.name + ".wasm")
        self.gen = os.path.join(workdir, self.name + "_js", "generate_witness.js")
        self.counter = 0

    def witness(self, inputs):
        """Return (ok, wtns_path)."""
        self.counter += 1
        inp = os.path.join(self.dir, f"in{self.counter}.json")
        out = os.path.join(self.dir, f"w{self.counter}.wtns")
        with open(inp, "w") as f:
            json.dump({k: str(v) if not isinstance(v, list) else [str(x) for x in v]
                       for k, v in inputs.items()}, f)
        r = run(["node", self.gen, self.wasm, inp, out])
        return (r.returncode == 0 and os.path.exists(out)), out

    def check(self, wtns):
        r = run(["snarkjs", "wtns", "check", self.r1cs, wtns])
        return r.returncode == 0


class LibTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="zkp_libtest_")
        cls.modexp = CircuitHarness(os.path.join(ROOT, "tests/lib/modexp_test.circom"), cls.tmp)
        cls.modmul = CircuitHarness(os.path.join(ROOT, "tests/lib/modmul_test.circom"), cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ---------- helpers
    def exp_result(self, base, exp, mod):
        ok, w = self.modexp.witness({"base": base, "exp": exp, "mod": mod})
        self.assertTrue(ok, f"witness generation failed for {(base, exp, mod)}")
        vals = read_wtns(w)[0]
        self.assertTrue(self.modexp.check(w), "honest witness does not satisfy the R1CS")
        return vals[1]

    # ---------- ModExp: functional
    def test_modexp_known_values(self):
        cases = [(2, 10, 1000), (3, 0, 7), (0, 5, 7), (1, 12345, 2), (5, 22, 23),
                 (2, 560, 561), (3, 560, 561), (7, 2**32 - 1, 2**32 - 1 - 4)]
        for b, e, m in cases:
            if b < m:
                self.assertEqual(self.exp_result(b, e, m), pow(b, e, m), (b, e, m))

    def test_modexp_edge_moduli(self):
        top = 2**32 - 1
        self.assertEqual(self.exp_result(top - 1, top, top), pow(top - 1, top, top))
        self.assertEqual(self.exp_result(1, 7, 2), 1)
        self.assertEqual(self.exp_result(0, 0, 2), 1)   # 0^0 convention = 1

    def test_modexp_random(self):
        rng = random.Random(1234)
        for _ in range(25):
            m = rng.randrange(2, 2**K)
            b = rng.randrange(0, m)
            e = rng.randrange(0, 2**K)
            self.assertEqual(self.exp_result(b, e, m), pow(b, e, m), (b, e, m))

    # ---------- ModExp: rejection of invalid inputs
    def test_modexp_rejects_invalid(self):
        bad = {
            "mod = 0": (3, 5, 0),
            "mod = 1": (0, 5, 1),
            "base >= mod": (7, 5, 7),
            "base > mod": (50, 5, 7),
            "mod >= 2^32": (3, 5, 2**32),
            "exp >= 2^32": (3, 2**32, 7),
        }
        for label, (b, e, m) in bad.items():
            ok, _ = self.modexp.witness({"base": b, "exp": e, "mod": m})
            self.assertFalse(ok, f"{label}: witness generation should have failed")

    # ---------- ModMul
    def test_modmul_random(self):
        rng = random.Random(99)
        for _ in range(25):
            n = rng.randrange(2, 2**K)
            a, b = rng.randrange(0, n), rng.randrange(0, n)
            ok, w = self.modmul.witness({"a": a, "b": b, "n": n})
            self.assertTrue(ok)
            self.assertEqual(read_wtns(w)[0][1], (a * b) % n)
            self.assertTrue(self.modmul.check(w))

    # ---------- Soundness: tamper with single wires
    def _tamper_all(self, harness, inputs, n_wires, label):
        ok, w = harness.witness(inputs)
        self.assertTrue(ok)
        vals = read_wtns(w)[0]
        self.assertTrue(harness.check(w))
        rng = random.Random(7)
        n_pub = len(inputs)           # witness layout: 1, outputs, public inputs, rest
        # always include the output wire; the rest are random internal wires
        wires = [1] + rng.sample(range(2 + n_pub, len(vals)), n_wires)
        survivors = []
        for i in wires:
            for delta in (1, -1):
                t = os.path.join(self.tmp, f"t_{label}_{i}_{delta}.wtns")
                write_tampered(w, t, i, vals[i] + delta)
                if harness.check(t):
                    survivors.append((i, delta))
        self.assertEqual(survivors, [],
                         f"{label}: tampered witness still satisfied constraints at wires {survivors} "
                         "(these wires are not fully constrained)")

    def test_modexp_soundness_tamper(self):
        self._tamper_all(self.modexp, {"base": 123456, "exp": 987654, "mod": 1000003}, 14, "modexp")

    def test_modmul_soundness_tamper(self):
        self._tamper_all(self.modmul, {"a": 123456, "b": 654321, "n": 1000003}, 8, "modmul")

    def test_modexp_cannot_claim_wrong_result(self):
        """The core attack on the old library: prove base^exp = X for a wrong X."""
        ok, w = self.modexp.witness({"base": 5, "exp": 22, "mod": 23})
        vals = read_wtns(w)[0]
        self.assertEqual(vals[1], 1)
        forged = os.path.join(self.tmp, "forged.wtns")
        for wrong in (0, 2, 22, 12345):
            write_tampered(w, forged, 1, wrong)
            self.assertFalse(self.modexp.check(forged), f"forged result {wrong} accepted")


if __name__ == "__main__":
    unittest.main(verbosity=2)
