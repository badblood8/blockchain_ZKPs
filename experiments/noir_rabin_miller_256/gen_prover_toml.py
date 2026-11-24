"""Write Prover.toml for rabin_miller_256 from n and the bases (computes the hints).

    python3 gen_prover_toml.py <n> <K> [--bases 2,3,5,...] [--bad-redc] > Prover.toml
The hints (idx, use_one) are what an honest prover computes; for composite n no valid
hints exist, so the best-effort values are written and the circuit must reject.
"""
import argparse
import sys

LIMB = 120
MASK = (1 << LIMB) - 1


def limbs(x, count=3):
    return [(x >> (LIMB * i)) & MASK for i in range(count)]


def hints(n, a):
    e = n - 1
    r = (e & -e).bit_length() - 1
    d = e >> r
    x0 = pow(a, d, n)
    if x0 == 1:
        return 1, True
    for j in range(r):
        if pow(a, d << j, n) == n - 1:
            return r - j, False
    return 1, False  # no valid hint: composite (or a is a strong witness)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("n", type=int)
    ap.add_argument("k", type=int)
    ap.add_argument("--bases", default="2,3,5,7,11,13,17,19,23,29,31,37")
    ap.add_argument("--bad-redc", action="store_true", help="write a wrong redc_param")
    a = ap.parse_args()
    bases = [int(b) for b in a.bases.split(",")][: a.k]
    assert len(bases) == a.k, "not enough bases"
    redc = (1 << (2 * 256 + 6)) // a.n
    if a.bad_redc:
        redc += 12345
    hx = [hints(a.n, b) for b in bases]
    q = lambda v: f'"0x{v:x}"'
    print("n = [" + ", ".join(q(v) for v in limbs(a.n)) + "]")
    print("a = [" + ", ".join(f'"{b}"' for b in bases) + "]")
    print("redc_param = [" + ", ".join(q(v) for v in limbs(redc)) + "]")
    print("idx = [" + ", ".join(f'"{i}"' for i, _ in hx) + "]")
    print("use_one = [" + ", ".join("true" if u else "false" for _, u in hx) + "]")


if __name__ == "__main__":
    main()
