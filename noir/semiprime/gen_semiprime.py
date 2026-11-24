"""Prover.toml for the semiprime circuit: N = p * q with p, q distinct 256-bit provable primes.

    python3 gen_semiprime.py [seed_p] [seed_q] > Prover.toml
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prime_chain"))
import gen_chain as g  # noqa: E402


def semiprime_toml(chain_p, chain_q):
    p, q = chain_p[-1], chain_q[-1]
    assert p != q
    n = p * q
    head = (f"n = {g.lst(g.limbs(n, 5))}\n"
            f"p = {g.lst(g.limbs(p, 3))}\n"
            f"q = {g.lst(g.limbs(q, 3))}\n\n")
    return head + g.render_table("cp", g.chain_fields(chain_p)) + "\n" + g.render_table("cq", g.chain_fields(chain_q))


if __name__ == "__main__":
    sp = int(sys.argv[1]) if len(sys.argv) > 1 else 11
    sq = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    cp, cq = g.chain_for(sp), g.chain_for(sq)
    sys.stderr.write(f"p = {cp[-1]}\nq = {cq[-1]}\nN = {cp[-1] * cq[-1]}  ({(cp[-1] * cq[-1]).bit_length()} bits)\n")
    print(semiprime_toml(cp, cq), end="")
