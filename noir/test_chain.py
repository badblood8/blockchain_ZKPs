"""End-to-end tests for prime_chain (public 256-bit n proven prime by a private Pocklington chain).

    NARGO=/path/to/nargo python3 test_chain.py
"""
import os
import random
import re
import shutil
import subprocess
import tempfile
import unittest

import sympy

HERE = os.path.dirname(os.path.abspath(__file__))
NARGO = os.environ.get("NARGO", "nargo")
import sys
sys.path.insert(0, os.path.join(HERE, "prime_chain"))
import gen_chain as g  # noqa: E402

KEEP = ("zkp_primality", "prime_chain")


def parse(toml):
    return dict(re.findall(r'^(\w+) = (.*)$', toml, re.M))


def render(d):
    return "\n".join(f"{k} = {v}" for k, v in d.items()) + "\n"


class Chain(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="zkp_chain_")
        for d in KEEP:
            shutil.copytree(os.path.join(HERE, d), os.path.join(cls.tmp, d),
                            ignore=shutil.ignore_patterns("target", "Prover.toml", "__pycache__"))
        cls.dir = os.path.join(cls.tmp, "prime_chain")
        r = subprocess.run([NARGO, "compile"], cwd=cls.dir, capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        cls.count = 0
        cls.chains = [g.chain_for(s) for s in (1, 2, 3)]

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def solvable(self, text):
        Chain.count += 1
        name = f"case{Chain.count}"
        with open(os.path.join(self.dir, name + ".toml"), "w") as f:
            f.write(text)
        r = subprocess.run([NARGO, "execute", "--prover-name", name], cwd=self.dir, capture_output=True, text=True)
        return r.returncode == 0

    # ---------- completeness
    def test_honest_chains_accepted(self):
        for chain in self.chains:
            self.assertEqual([c.bit_length() for c in chain], [16, 32, 64, 128, 256])
            self.assertTrue(self.solvable(g.prover_toml(chain)), f"honest chain for {chain[-1]} rejected")

    # ---------- soundness: composites
    def test_composite_public_n_rejected(self):
        rng = random.Random(1)
        base = parse(g.prover_toml(self.chains[0]))
        for _ in range(4):
            while True:
                n = rng.getrandbits(256) | (1 << 255) | 1
                if not sympy.isprime(n):
                    break
            d = dict(base)
            d["n"] = g.lst(g.limbs(n, 3))
            d["redc256"] = g.lst(g.redc(n, 256, 3))
            self.assertFalse(self.solvable(render(d)), "composite n accepted with the honest lower levels")
        # n+2 / n-2 of a real prime, and 2*prime
        n256 = self.chains[0][-1]
        for n in (n256 + 2, n256 - 2, n256 + 4):
            if not sympy.isprime(n):
                d = dict(base)
                d["n"] = g.lst(g.limbs(n, 3))
                d["redc256"] = g.lst(g.redc(n, 256, 3))
                self.assertFalse(self.solvable(render(d)), f"composite {n} accepted")

    def test_composite_at_each_lower_level_rejected(self):
        """Swap level i for a composite of the same size, keeping the rest of the data."""
        rng = random.Random(2)
        chain = list(self.chains[1])
        for level in (1, 2, 3):                       # n32, n64, n128 (n16 is covered by the trial-division tests)
            bits = [16, 32, 64, 128, 256][level]
            while True:
                comp = rng.getrandbits(bits) | (1 << (bits - 1)) | 1
                if not sympy.isprime(comp):
                    break
            bad = list(chain)
            bad[level] = comp
            # best-effort witnesses: y = honest-looking element, inverse when it exists
            toml = parse(g.prover_toml(chain))
            names = {1: "n32", 2: "n64", 3: "n128"}
            if level == 3:
                toml["n128"] = g.lst(g.limbs(comp, 2))
                toml["redc128"] = g.lst(g.redc(comp, 128, 2))
            else:
                toml[names[level]] = f'"{comp}"'
            self.assertFalse(self.solvable(render(toml)), f"composite at level {level} accepted")

    def test_tampered_witnesses_rejected(self):
        base = parse(g.prover_toml(self.chains[2]))
        for key in ("y256", "inv256", "y128", "inv128", "y64", "inv64", "y32", "inv32"):
            d = dict(base)
            v = d[key]
            if v.startswith("["):
                items = re.findall(r'"(0x[0-9a-f]+)"', v)
                items[0] = hex(int(items[0], 16) ^ 1)
                d[key] = "[" + ", ".join(f'"{i}"' for i in items) + "]"
            else:
                d[key] = f'"{int(v.strip(chr(34))) ^ 1}"'
            self.assertFalse(self.solvable(render(d)), f"tampered {key} accepted")

    def test_wrong_size_or_even_rejected(self):
        base = parse(g.prover_toml(self.chains[0]))
        n256 = self.chains[0][-1]
        cases = {
            "even n": n256 + 1,
            "255-bit number": n256 >> 1 | 1,
            "n = 1": 1,
        }
        for label, n in cases.items():
            d = dict(base)
            d["n"] = g.lst(g.limbs(n, 3))
            self.assertFalse(self.solvable(render(d)), f"{label} accepted")

    def test_bad_base_case_rejected(self):
        base = parse(g.prover_toml(self.chains[0]))
        for n16 in (63001, 255, 1, 256 * 3):          # 251^2, 255, 1, composite
            d = dict(base)
            d["n16"] = f'"{n16}"'
            self.assertFalse(self.solvable(render(d)), f"n16={n16} accepted")


if __name__ == "__main__":
    unittest.main(verbosity=2)
