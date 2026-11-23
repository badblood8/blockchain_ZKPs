"""Write inputs/<circuit>.json for the Circom circuits, with the same validity rules the circuits enforce.

    python3 scripts/gen_inputs.py fermat 982451653 [--bases 25]
    python3 scripts/gen_inputs.py lehmann 982451653 [--bases 10]
    python3 scripts/gen_inputs.py rabin_miller 982451653 [--bases 10]
    python3 scripts/gen_inputs.py multiply 17 19
    python3 scripts/gen_inputs.py pratt 8675309            # delegates to pratt_certificate_generator.py

The circuits are instantiated for 32-bit n (lib/modarith.circom caps values at 125 bits), accept only
2 <= a <= n-2 as bases, need n >= 5, and (Lehmann / Rabin-Miller) odd n.  A composite n has no valid witness,
so this refuses to write one unless --force is given (useful to test that the circuit rejects it).
"""
import argparse
import json
import os
import sys

import sympy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_BASES = {"fermat": 25, "lehmann": 10, "rabin_miller": 10}
NBITS = 32


def first_bases(n, k):
    bases = [p for p in sympy.primerange(2, 1000) if 2 <= p <= n - 2][:k]
    if len(bases) < k:
        bases += [b for b in range(2, n - 1) if b not in bases][: k - len(bases)]
    return bases[:k]


def make(circuit, n, bases_count):
    if not 5 <= n < 1 << NBITS:
        raise SystemExit(f"n must satisfy 5 <= n < 2^{NBITS} for the shipped circuits (got {n})")
    if circuit in ("lehmann", "rabin_miller") and n % 2 == 0:
        raise SystemExit("n must be odd")
    bases = first_bases(n, bases_count)
    if len(bases) < bases_count:
        raise SystemExit(f"n={n} is too small for {bases_count} bases in [2, n-2]")
    return {"n": n, "a": bases}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("circuit", choices=["fermat", "lehmann", "rabin_miller", "multiply", "pratt"])
    ap.add_argument("values", type=int, nargs="+")
    ap.add_argument("--bases", type=int)
    ap.add_argument("--force", action="store_true", help="write a composite n anyway")
    ap.add_argument("--out", help="output path (default: inputs/<circuit>.json)")
    a = ap.parse_args()
    out = a.out or os.path.join(ROOT, "inputs", f"{a.circuit}.json")

    if a.circuit == "multiply":
        if len(a.values) != 2:
            raise SystemExit("multiply needs p and q")
        data = {"p": str(a.values[0]), "q": str(a.values[1])}
    elif a.circuit == "pratt":
        sys.path.insert(0, HERE)
        import pratt_certificate_generator as g
        data = g.build_certificate(a.values[0], 9, 4)
    else:
        n = a.values[0]
        if not sympy.isprime(n) and not a.force:
            raise SystemExit(f"{n} is not prime: the circuit has no valid witness for it (use --force to write it anyway)")
        data = make(a.circuit, n, a.bases or DEFAULT_BASES[a.circuit])
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
