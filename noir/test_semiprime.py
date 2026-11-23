"""Tests for the semiprime circuit: public N = p*q, private distinct 256-bit primes p, q with chains.

    NARGO=/path/to/nargo python3 test_semiprime.py            # behaviour
    NARGO=... python3 test_semiprime.py mutants               # mutation check of the circuit's assertions
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
sys.path.insert(0, os.path.join(HERE, "prime_chain"))
sys.path.insert(0, os.path.join(HERE, "semiprime"))
import gen_chain as g  # noqa: E402

KEEP = ("zkp_primality", "semiprime")


def toml(n_limbs, p, q, fields_p, fields_q):
    return (f"n = {g.lst(n_limbs)}\np = {g.lst(g.limbs(p, 3))}\nq = {g.lst(g.limbs(q, 3))}\n\n"
            + g.render_table("cp", fields_p) + "\n" + g.render_table("cq", fields_q))


class Env:
    def __init__(self, root=None, mutate=None):
        self.tmp = tempfile.mkdtemp(prefix="zkp_semi_")
        for d in KEEP:
            shutil.copytree(os.path.join(HERE, d), os.path.join(self.tmp, d),
                            ignore=shutil.ignore_patterns("target", "Prover.toml", "__pycache__"))
        if mutate:
            path, old, new = mutate
            f = os.path.join(self.tmp, path)
            s = open(f).read()
            assert old in s, mutate
            open(f, "w").write(s.replace(old, new))
        self.dir = os.path.join(self.tmp, "semiprime")
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


def fixtures():
    cp, cq = g.chain_for(21), g.chain_for(22)
    p, q = cp[-1], cq[-1]
    fp, fq = g.chain_fields(cp), g.chain_fields(cq)
    return cp, cq, p, q, fp, fq


def attacks():
    """label -> toml.  Every one must be REJECTED."""
    cp, cq, p, q, fp, fq = fixtures()
    n = p * q
    out = {}
    out["N + 2 (not p*q)"] = toml(g.limbs(n + 2, 5), p, q, fp, fq)
    out["N + 2^512 (same residue mod 2^512)"] = toml(g.limbs(n + (1 << 512), 5), p, q, fp, fq)
    # p = q: N = p^2 with the same (valid) chain twice
    out["p = q (N = p^2)"] = toml(g.limbs(p * p, 5), p, p, fp, fp)
    # swapped chains
    out["chains swapped between p and q"] = toml(g.limbs(n, 5), p, q, fq, fp)
    # q composite: N = p * q' with a best-effort chain (the real q's chain)
    rng = random.Random(3)
    while True:
        qc = rng.getrandbits(256) | (1 << 255) | 1
        if not sympy.isprime(qc):
            break
    out["q composite (chain of another prime)"] = toml(g.limbs(p * qc, 5), p, qc, fp, fq)
    out["p composite (chain of another prime)"] = toml(g.limbs(qc * q, 5), qc, q, fp, fq)
    # a 255-bit prime factor
    p255 = sympy.prevprime(1 << 255)
    out["255-bit factor"] = toml(g.limbs(p255 * q, 5), p255, q, fp, fq)
    # N of the right size but not a product of the claimed factors
    out["wrong N for the claimed p, q"] = toml(g.limbs(p * sympy.nextprime(q), 5), p, q, fp, fq)
    return out


class Semiprime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = Env()

    @classmethod
    def tearDownClass(cls):
        cls.env.close()

    def test_honest_accepted(self):
        for sp, sq in ((21, 22), (31, 32), (5, 77)):
            cp, cq = g.chain_for(sp), g.chain_for(sq)
            if cp[-1] == cq[-1]:
                continue
            p, q = cp[-1], cq[-1]
            self.assertEqual((p * q).bit_length() in (511, 512), True)
            self.assertTrue(self.env.solvable(toml(g.limbs(p * q, 5), p, q, g.chain_fields(cp), g.chain_fields(cq))),
                            f"honest ({sp},{sq}) rejected")

    def test_symmetric_in_p_and_q(self):
        cp, cq, p, q, fp, fq = fixtures()
        self.assertTrue(self.env.solvable(toml(g.limbs(p * q, 5), q, p, fq, fp)))

    def test_attacks_rejected(self):
        for label, text in attacks().items():
            self.assertFalse(self.env.solvable(text), f"accepted: {label}")


def run_mutants():
    att = attacks()
    sp = "semiprime/src/main.nr"
    mutants = [
        ("product equality dropped", sp, "    assert(to_u512(p) * to_u512(q) == U512::from_limbs(n));\n", "", "wrong N for the claimed p, q"),
        ("N < 2^512 bound dropped", sp, "    assert(n[4] < 4294967296);\n", "", "N + 2^512 (same residue mod 2^512)"),
        ("p != q dropped", sp, "    assert((p[0] != q[0]) | (p[1] != q[1]) | (p[2] != q[2]));\n", "", "p = q (N = p^2)"),
        ("primality of q dropped", sp, "    assert_prime_256(q, cq);\n", "", "q composite (chain of another prime)"),
        ("primality of p dropped", sp, "    assert_prime_256(p, cp);\n", "", "p composite (chain of another prime)"),
    ]
    survivors = []
    for label, path, old, new, attack in mutants:
        env = Env(mutate=(path, old, new))
        try:
            accepted = env.solvable(att[attack])
        finally:
            env.close()
        print(f"MUTANT {label!r}: " + (f"caught (attack '{attack}' accepted by mutant)" if accepted
                                        else "SURVIVED  <-- attack rejected even without this assertion"))
        if not accepted:
            survivors.append(label)
    print("survivors:", survivors if survivors else "none")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "mutants":
        run_mutants()
    else:
        unittest.main(verbosity=2)
