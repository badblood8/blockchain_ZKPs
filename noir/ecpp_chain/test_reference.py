"""Fast tests of the ECPP Python reference (no Noir needed): verifier rule, generator and cached certificates.

    python3 test_reference.py
"""
import json
import os
import random
import sys
import unittest

import sympy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ecpp_py as E  # noqa: E402
import gen_ecpp as G  # noqa: E402


class Reference(unittest.TestCase):
    def test_cached_certificates_verify(self):
        cache = json.load(open(G.FIXTURES))
        self.assertTrue(cache)
        for seed, ch in cache.items():
            self.assertTrue(G.verify_python(ch), f"seed {seed}")
            self.assertEqual([L["n"].bit_length() for L in ch["levels"]][0], 64)

    def test_small_chain_generation(self):
        rng = random.Random(1)
        for _ in range(3):
            n = sympy.randprime(1 << 19, 1 << 20)
            res = E.next_level(n, rng, qbits=11, kbits=9)
            self.assertIsNotNone(res)
            a, b, P, k, q, r = res
            self.assertTrue(sympy.isprime(q))
            self.assertTrue(E.verify_level(n, a, b, P, k, q, r))

    def test_tampering_is_rejected(self):
        rng = random.Random(2)
        n = sympy.randprime(1 << 19, 1 << 20)
        a, b, P, k, q, r = E.next_level(n, rng, qbits=11, kbits=9)
        self.assertFalse(E.verify_level(n + 2, a, b, P, k, q, r))
        self.assertFalse(E.verify_level(n, a, b, P, k + 1, q, r))
        self.assertFalse(E.verify_level(n, a, b, (P[0], (P[1] + 1) % n), k, q, r))
        self.assertFalse(E.verify_level(n, a, b, P, k, q + 2, r))

    def test_size_bound_forgery(self):
        # composite n = 281 * 269 passes everything except q >= (r+2)^2
        n, a, b, P, k, q, r = 75589, 37659, 14846, (6127, 25990), 128, 281, 16
        self.assertFalse(E.verify_level(n, a, b, P, k, q, r))
        self.assertTrue(E.verify_level(n, a, b, P, k, q, r, {"bound": False}))

    def test_bsgs_matches_brute_force(self):
        rng = random.Random(3)
        for _ in range(5):
            n = sympy.randprime(1 << 12, 1 << 14)
            a, b, P = E.random_curve_point(n, rng)
            lo, hi = n + 1 - 2 * int(n ** 0.5) - 3, n + 1 + 2 * int(n ** 0.5) + 3
            m = E.bsgs_order(P, a, n, lo, hi)
            if m is None:
                continue
            # brute force: smallest j with [j]P = O
            cur, j = P, 1
            while True:
                nxt = E.add(cur, P, a, n)
                j += 1
                if nxt is None:
                    break
                cur = nxt
            self.assertEqual(m % j, 0, "the BSGS multiple must be a multiple of the point order")

    def test_fourth_root_witness(self):
        for n in (5, 81, 82, 1000, 2 ** 32, 2 ** 64 - 1):
            r = E.fourth_root_witness(n)
            self.assertGreater((r + 1) ** 4, n)
            self.assertTrue(r == 0 or r ** 4 <= n)


if __name__ == "__main__":
    unittest.main(verbosity=2)
