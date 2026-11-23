# Toolchain and proof-system comparison (2026-11-23)

Question: would newer tools give better proofs, time- and space-wise?
Short answer: **yes, but not where it is usually assumed.** Upgrading Circom/snarkjs alone changes
nothing measurable; a native prover (rapidsnark) gives ~12x faster proving and ~17x less memory
with the same circuits; and Noir/UltraHonk is the only option here that reaches 256-bit numbers.

All numbers: Apple M2 (8 cores), 8 GB RAM, macOS, one machine, one run of each configuration
(proving/verifying = median of 3-5 repeats after a warm-up). Raw data: `bench/results/`,
harness: `bench/bench_groth16.py`. Statement benchmarked everywhere: **Rabin-Miller, 10 public
bases, 32-bit n = 982451653** unless stated otherwise.

## 1. Same circuit, different tools (Circom R1CS, Groth16)

| | circom 2.1.9 + snarkjs 0.7.4 (baseline) | circom 2.2.3 `--O2` + snarkjs 0.7.6 | same keys, **rapidsnark 0.0.8** |
|---|---|---|---|
| R1CS constraints | 64,972 | 64,972 | 64,972 |
| witness generation (wasm) | 0.13 s | 0.13 s | (same) |
| per-circuit setup | 49 s | 47 s | (same zkey) |
| proving key (zkey) | 37 MB | 37 MB | 37 MB |
| **prove time** | 1.65-1.70 s | 1.65 s | **0.13 s** |
| **prove peak memory** | 1.2 GB | 1.2 GB | **68 MB** |
| verify time | 0.21-0.25 s (mostly node start-up) | 0.21 s | 8 ms |
| proof (JSON) | 806 B | 804 B | 704 B |

Lehmann (44,189 constraints) shows the same picture: prove 1.41 s -> 1.32 s (snarkjs old -> new) ->
0.11 s (rapidsnark), memory 1.0 GB -> 55 MB.

Findings:
* **circom 2.2.3 / snarkjs 0.7.6 are not faster.** An early reading of 2.9 s for the old stack was
  noise; a 5-repeat re-measurement gives 1.65-1.70 s old vs 1.65-1.68 s new. Compile is ~25-30% faster
  but compiling already takes < 2 s.
* **circom 2.2.x changed its default optimisation to `--O1`.** Without `--O2` the circuit gets 3,564
  extra linear constraints (64,982 + 3,564 = 68,546 total), which no longer fits a 2^16 ceremony file
  and makes everything larger. Always pass `--O2` (it then matches 2.1.9 exactly).
* **rapidsnark is a drop-in**: same `.zkey` and `.wtns`, Groth16 only. Its proofs verify with snarkjs.
* The Groth16 proof is three curve points: 128 bytes compressed. The 0.7-0.8 KB above is the JSON text.

## 2. Different proof system: Noir 1.0.0 + Barretenberg 6.0.0 (UltraHonk, zero-knowledge)

Same statement, same 10 bases, 32-bit n, a faithful port (`experiments/noir_rabin_miller_32`):

| | Circom + rapidsnark (Groth16) | Noir + bb (UltraHonk) |
|---|---|---|
| size of circuit | 64,972 constraints | **22,126 gates** (12,217 ACIR opcodes) |
| compile + witness | 0.5 s + 0.13 s | 0.24 s + 0.18 s |
| per-circuit setup / proving key | 47 s / 37 MB | **0.9 s (verification key only) / none** |
| prove time | 0.13 s | 0.15 s |
| prove peak memory | 68 MB | 81 MB |
| verify time | 8 ms | 10 ms |
| **proof size** | **~0.7-0.8 KB (JSON), 128 B binary** | **14.7 KB** |
| verification key | 4.8 KB (JSON) | 3.7 KB |
| trusted setup | **per circuit** (phase 2) + universal ceremony | **universal only** (12 MB SRS, fetched on demand) |

* Proving time and memory are a tie at this size. **Proof size is where Groth16 wins**: 14.7 KB vs the ~0.8 KB JSON
  (about 19x), or vs the 128-byte binary encoding (about 115x).
* Noir wins on setup: no per-circuit ceremony and no 37 MB proving key.
* The circuit shrinks 3x mainly because Noir has native range-checked `u64` arithmetic. That is a
  language advantage, not a backend one: my Circom library pays ~4k^2 constraints per modular
  exponentiation for bit-decomposition range checks. A smarter Circom design could narrow the gap.
* Default `bb prove` output is zero-knowledge (target `noir-recursive`, Poseidon2); the `-no-zk` targets
  are explicit opt-ins (verified: the no-ZK verifier rejects the default proof; 14,656 B vs 13,120 B).

## 3. The real difference: how big a number can be proven

The project goal is primality of large numbers (a "256-bit" N = p*q). My Circom library keeps every
value inside one BN254 field element, so it caps at **125 bits** (`lib/modarith.circom`).

10 bases, same test:

| | Circom (this repo's library) | Noir + noir-bignum (`RuntimeBigNum`, 3 x 120-bit limbs) |
|---|---|---|
| widest supported n | **125 bits** | **256 bits** (more limbs -> wider) |
| size at that width | 951,448 constraints (compile only; proving needs a 2^20 ceremony file, not run) | **750,671 gates** |
| prove time | not measured | **3.4 s** |
| prove peak memory | not measured | **1.3 GB** |
| proof size | n/a | 14.7 KB (unchanged) |
| verify time | n/a | 10 ms |

One base at 256 bits (`experiments/noir_rabin_miller_256`, default K = 1): 78,793 gates, prove 0.42 s,
270 MB. Cost grows ~linearly with the number of bases; the proof size does not grow.

The 256-bit circuit uses a different algorithm that would also help the Circom circuit: one
left-to-right square-and-multiply pass over the bits of n-1 gives every value a^(d*2^j) on the way,
so no explicit decomposition n-1 = d*2^r is needed, and the prover only *hints* which position hits
n-1 (one big-number equality per base instead of one per bit).

## 4. How much to trust the Noir experiment

* `experiments/noir_rabin_miller_32`: 9 Noir unit tests (primes incl. r = 30 and the largest 32-bit prime,
  Carmichael, strong pseudoprime 3215031751, vacuous bases).
* `experiments/noir_rabin_miller_256/test_noir.py`: 8 adversarial tests (random 256-bit primes, r >= 200,
  the `a^d = 1` branch, semiprimes and other composites with every hint combination, wrong/out-of-range
  hints, even / 255-bit / 257-bit moduli, wrong `redc_param`).
* `experiments/noir_rabin_miller_256/model_check.py`: the circuit's decision rule vs textbook Rabin-Miller
  on all 2,089,989 (n, a) pairs with n < 2^11: **0 false accepts, 0 false rejects**. Dropping `i <= r` gives
  8,044 false accepts, dropping the odd check gives 7,432 (so both are necessary).
* Mutation check on the circuit: deleting the final equality is caught by tests. The mutants for `i <= r`,
  `i >= 1`, `hits == 1` and "n is odd" were *not* caught by the 256-bit tests, because I cannot construct
  a 256-bit composite that exposes them. `model_check.py` shows `i <= r` and odd-n are necessary (small
  sizes); `i >= 1` (s_0 = -1 is impossible for odd n) and `hits == 1` are provably redundant and kept as
  defense in depth. **This is a weaker assurance than the exhaustive Circom mutation testing.**
* `redc_param` is an unvalidated witness by library design (it only steers unconstrained Barrett
  reduction); tests show a wrong value cannot produce a witness for a composite. The modulus must be a
  public input for `RuntimeBigNum` to be meaningful (it is).
* Barretenberg < 0.82.2 had a critical UltraHonk soundness bug (per `bbup`'s own warning). This used 6.0.0.

## 5. Caveats

* One machine, small circuits (<= 1M gates); scaling at 2^20+ constraints is not measured. Proof-system
  rankings change with circuit size (a Semaphore-Noir study found Circom/Groth16 faster at small sizes,
  a Base study found Noir 5-50x faster on large ones).
* Setup timings use an un-contributed zkey (benchmark only, not for production).
* On-chain verification cost (gas) is not evaluated; for EVM, Groth16's small proof matters more.
* The Hermez ceremony files used here come from a hash-verified community mirror because the official
  hosts return 403 now (see `docs/TOOLCHAIN.md`).

## 6. The project goal in Noir: N = p*q with provable primes (added after choosing Noir)

All of `noir/`, same machine, zero-knowledge UltraHonk proofs of 15 KB, verified in 10 ms:

| statement | method | gates | prove time / peak memory |
|---|---|---|---|
| public **512-bit N = p*q**, private distinct 256-bit primes | Pocklington chains for p and q | **70,982** | **0.41 s / 248 MB** |
| public 256-bit n is prime | Pocklington chain 16->32->64->128->256 | 38,147 | 0.24 s / 131 MB |
| public 64-bit n is prime | **real ECPP** chain 64->33->17->9 bits | 121,036 | 0.6 s / 350 MB |
| (earlier) 256-bit Rabin-Miller, 1 base | probabilistic | 78,793 | 0.42 s / 270 MB |
| (earlier) 256-bit Rabin-Miller, 10 bases | probabilistic | 750,671 | 3.4 s / 1.3 GB |

* **Deterministic Pocklington is ~2x cheaper than ONE Rabin-Miller base at 256 bits** (38,147 vs 78,793 gates)
  and has no error probability. A sound Rabin-Miller (hash-derived bases, ~40 for 80-bit security) would be about
  3.1 M gates per prime (extrapolated from the measured per-base cost, not measured).
* The Pocklington criterion needs only `f` prime, `f^2 > n`, and a residue `y` with `y^f = 1`, `gcd(y-1, n) = 1`.
  Dropping the `n-1 = f*e` link and the base halved the circuit (68,868 -> 38,147 gates). An exhaustive check
  (n < 1500, all primes f < 200) confirms it accepts no composite.
* **ECPP works for any prime but is expensive**: at 64 bits it already costs 3x the 256-bit Pocklington proof, and a
  chain at best halves the bit length per level. Its ECPP gate count at 256 bits was not measured.
* Trade-off: Pocklington requires the prover to have *generated* the primes with the chain structure (provable
  primes); ECPP can certify a prime issued by someone else.
* Evidence and gaps for each circuit: `noir/README.md` ("How much to trust each part").

## Reproduce

```bash
# Circom side (tools from docs/TOOLCHAIN.md)
python3 bench/bench_groth16.py --circuit rabin_miller --ptau <hermez 2^16> --label new \
    --circom <circom-2.2.3> --circom-flags=--O2 --snarkjs <snarkjs-0.7.6>
python3 bench/bench_groth16.py ... --prover rapidsnark --rapidsnark-dir <dir> --workdir <same dir> --reuse

# Noir side
cd experiments/noir_rabin_miller_32 && nargo test && nargo execute \
  && bb write_vk -b target/rabin_miller_32.json -o target/out \
  && bb prove -b target/rabin_miller_32.json -w target/rabin_miller_32.gz -k target/out/vk -o target/out \
  && bb verify -k target/out/vk -p target/out/proof -i target/out/public_inputs
```
