# Zero-knowledge primality proofs in Noir

Circuits for the project goal: prove that **N = p·q with p, q large primes** without revealing p or q.
Built with Noir 1.0.0, Barretenberg 6.0.0 (UltraHonk, zero-knowledge) and noir-bignum 0.11.0
(see `../docs/TOOLCHAIN.md` for versions and install notes).

## What is here

| package | proves | size | prove / peak mem |
|---|---|---|---|
| `semiprime` | public 512-bit **N = p·q**, private distinct 256-bit primes p, q | 70,982 gates | 0.41 s / 248 MB |
| `prime_chain` | public 256-bit **n is prime** | 38,147 gates | 0.24 s / 131 MB |
| `ecpp_chain` | public 64-bit **n is prime**, by real ECPP | 121,036 gates | 0.6 s / 350 MB |
| `zkp_primality` | the library all of the above use | - | - |
| `step_native`, `step_big`, `step_trial`, `step_ecpp` | test harnesses: ONE step with all inputs free | - | - |

(Proof size 15 KB, verification 10 ms, verification key 3.7 KB for all of them; measured on an M2 / 8 GB.)

## The two primality methods

**Pocklington chain (deterministic, for primes you generate).** If `f` is prime, `f² > n`, and some `y` has
`y^f ≡ 1 (mod n)` with `gcd(y−1, n) = 1`, then `n` is prime: for any prime `p | n` the order of `y` mod `p` is
exactly `f`, so `p > f > √n`; this holds for every prime factor, so `n` has only one. A chain
16 → 32 → 64 → 128 → 256 bits (16-bit base case by trial division) certifies a 256-bit prime with **no error
probability**, because the prover builds each prime as `n = f·e + 1` from the previous one (Maurer's provable
primes, allowed by FIPS 186). The circuit needs neither `n−1 = f·e` nor a base: only `y` and the inverse of `y−1`.

**ECPP (Atkin–Goldwasser–Kilian, for any prime).** Works on a prime that was not built with structure, at a much
higher price: about 9 modular multiplications per scalar bit and a chain that at best halves the bit length per
level (`q > (n^¼+1)² > √n`). Certificates need point counting; the pure-Python generator here (baby-step
giant-step) reaches ~64 bits in minutes. 64-bit n costs 3x the gates of the 256-bit Pocklington proof.

## Why not Rabin-Miller for the semiprime proof?

With fixed public bases a malicious prover can pick a strong pseudoprime to those bases. A sound version needs
bases derived by hashing, and about 40 of them for 80-bit security: roughly 40 × 78,793 = 3.1 M gates *per prime*
(extrapolated from the one-base circuit measured in `../experiments/noir_rabin_miller_256`), against 38,147 for
a deterministic Pocklington proof. Rabin-Miller remains the right tool when the prime was NOT generated with a
provable construction and a probabilistic statement is acceptable.

## How much to trust each part

Every soundness-relevant assertion was **mutation-checked**: delete the assertion from a copy, run an attack that
satisfies everything else, and require the mutant to accept it while the real circuit rejects it.

| component | evidence |
|---|---|
| Pocklington criterion | exhaustive model: n < 1500, every prime f < 200: **0 composites accepted**, all honest primes accepted, and 573 composites accepted when `f² > n` is dropped (`prime_chain/model_check.py`) |
| native + bignum steps | 5 + 7 adversarial tests; mutants for `f² > n`, `y^f = 1`, inverse of `y−1`, and "f < 2^FB" (high bits) all caught by their own attack (composite `p₁·p₂` with `pᵢ = 1 + kᵢ·f`, random composites, `y = 1`, `f` with extra high bits) (`test_steps.py`) |
| trial-division base case | mutants for the prime list, the size bound and the lower bound caught (`test_steps.py`) |
| end-to-end Pocklington chain | honest chains, composites at every level, tampering of every witness, bad base case (`test_chain.py`) |
| semiprime composition | all five assertions caught (product, `N < 2^512`, `p ≠ q`, primality of p, of q) (`test_semiprime.py`) |
| ECPP step | model check of the rule (below) and mutants for the size bound, the fourth-root witness and the final `[q]R = O` check (`test_ecpp.py`) |

**Known gaps (be careful with these):**
* `n ≥ 3` in the native step is redundant given the other checks (documented, kept as defense in depth).
* ECPP: the on-curve and discriminant checks are **redundant for soundness** (the group-law formulas never use `b`,
  and the size bound already excludes singular curves; model check confirms). The per-step inverse checks and the
  top-bit assertions could not be attacked at circuit level, because the inverse hints are computed inside the
  circuit; their necessity rests on the argument, not on a failing mutant.
* The ECPP model check is exhaustive only for n ≤ 55 and sampled for 13 larger composites up to 221.
* `redc_param` (noir-bignum's Barrett constant) is an unvalidated witness by library design: it only steers
  witness generation. Tests showed a wrong value never helps a composite.
* Everything uses a 16-bit trial-division base case and fixed bit widths (16/32/64/128/256 for Pocklington; 64/33/17/9
  for ECPP). Other sizes need new instantiations (the step functions are generic).
* Numbers are bounded at 256 bits for the Pocklington chain and at 64 bits for ECPP (certificate generation).
  The ECPP gate cost at 256 bits was **not measured**; scaling from the measured bignum multiplication suggests
  roughly 10x the Pocklington proof.

## Running things

```bash
# tools: nargo 1.0.0, bb 6.0.0, python3 with sympy.  NARGO must point at the nargo binary.
export NARGO=/path/to/nargo

cd noir/semiprime && python3 gen_semiprime.py 11 12 > Prover.toml     # p, q from two seeded chains
nargo execute && bb write_vk -b target/semiprime.json -o target/out \
  && bb prove -b target/semiprime.json -w target/semiprime.gz -k target/out/vk -o target/out \
  && bb verify -k target/out/vk -p target/out/proof -i target/out/public_inputs

# tests (each compiles a scratch copy of the packages it needs)
python3 test_steps.py            # steps + trial division          python3 test_steps.py mutants
python3 test_chain.py            # 256-bit chain
python3 test_semiprime.py        # N = p*q                          python3 test_semiprime.py mutants
python3 test_ecpp.py             # ECPP                             python3 test_ecpp.py mutants
python3 prime_chain/model_check.py ; python3 ecpp_chain/model_check.py     # exhaustive small-size models
```

`ecpp_chain/gen_ecpp.py <seed>` caches certificate chains in `ecpp_chain/fixtures.json` (about 3.5 min each).
