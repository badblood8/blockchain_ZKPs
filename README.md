# Zero-knowledge proofs of primality, and of N = p·q

Circuits that prove, without revealing the witness, that a number is prime, culminating in a proof that a
public 512-bit **N = p·q** is the product of two distinct 256-bit primes **p** and **q** that stay private
(the "cryptographic banking" use case: prove an RSA modulus is well formed without disclosing its factors).

Two implementations of the same ideas:

| | language / proof system | numbers | role |
|---|---|---|---|
| `circom/` | Circom, Groth16 (tiny 0.8 KB proofs, per-circuit trusted setup) | up to 125 bits, instantiated at **32 bits** | the tested reference of the classic tests |
| `noir/` | Noir + Barretenberg UltraHonk (14.7 KB proofs, universal setup) | **256 bits** (512-bit N), ECPP at 64 bits | the practical route to N = p·q |

Everything was rewritten and adversarially tested in 2026; the first (2024) circuits did not constrain their
arithmetic and could have "proved" a composite prime (see the report and `TODO.md` for what was wrong).

## Results at a glance

Apple M2 (8 cores), one run of each configuration; all Noir proofs are zero-knowledge, 15 KB, verified in 10 ms.

| Statement | Method | Gates / constraints | Prove | Peak memory |
|---|---|---|---|---|
| public 512-bit **N = p·q**, private distinct 256-bit primes | Pocklington chains (Noir) | 70,982 | **0.41 s** | 248 MB |
| public 256-bit n is prime | Pocklington chain (Noir) | 38,147 | 0.24 s | 131 MB |
| public 64-bit n is prime | real ECPP (Noir) | 121,036 | 0.6 s | 350 MB |
| 32-bit n, Rabin-Miller with 10 bases | Circom + rapidsnark | 42,561 | 0.12 s | 57 MB |
| same | Circom + snarkjs | 42,561 | 1.5 - 2 s | 0.7 - 0.9 GB |

Details, the other circuits and the caveats: [`bench/RESULTS.md`](bench/RESULTS.md). Reference documents:
[`main.tex`](main.tex) / [`zkp_final_report.pdf`](zkp_final_report.pdf) (the report), [`noir/README.md`](noir/README.md)
(what each Noir package proves and how much to trust it), [`docs/TOOLCHAIN.md`](docs/TOOLCHAIN.md) (versions and pitfalls),
[`TODO.md`](TODO.md) (audit and status of every item).

## Primality methods

| Method | Idea | Deterministic? | Where | Notes |
|---|---|---|---|---|
| Fermat | $a^{n-1} \equiv 1 \pmod n$ for several bases | no (Carmichael numbers pass) | `circom/fermat.circom` | bases must satisfy $2 \le a \le n-2$ |
| Lehmann | $a^{(n-1)/2} \equiv \pm 1 \pmod n$ | no | `circom/lehmann.circom` | n odd |
| Rabin-Miller | strong probable prime: $n-1 = d\,2^r$ | no (error $\le 4^{-k}$ for random bases) | `circom/rabin_miller.circom`, `experiments/noir_rabin_miller_*` | with fixed public bases an adversary can choose a pseudoprime |
| Pratt | Lucas: a primitive root per prime and a full factorisation of $p-1$, recursively | yes | `circom/pratt.circom`, `scripts/pratt_certificate_generator.py` | needs $p-1$ to factor |
| **Pocklington chain** | $f$ prime, $f^2>n$, $y^f \equiv 1$, $\gcd(y-1,n)=1 \Rightarrow n$ prime | **yes** | `noir/prime_chain`, `noir/semiprime` | prover builds the primes as $n = fe+1$ (provable primes) |
| ECPP | elliptic curve of order $kq$ with $q>(n^{1/4}+1)^2$ | yes | `noir/ecpp_chain` | works for any prime; ~9 mulmods per scalar bit; certificates up to ~64 bits here |

## Requirements

* Circom side: `circom` 2.2.x (**always compile with `--O2`**, the Makefile does), `snarkjs` 0.7.6, `node`, `python3` with `sympy`
  (`pip install -r requirements.txt`; `npm install` pins snarkjs). Optional: [rapidsnark](https://github.com/iden3/rapidsnark) for ~12× faster proving.
* Noir side: `nargo` 1.0.0 and `bb` 6.0.0 (these two must be paired; see `docs/TOOLCHAIN.md`).
* `make doctor` shows what is installed.

## Circom: build, prove, verify

```bash
make list                                   # multiply fermat lehmann rabin_miller pratt
make CIRCUIT=rabin_miller all               # compile, witness, setup, prove, verify, metrics
make CIRCUIT=pratt PROVER=rapidsnark RAPIDSNARK_DIR=/path/to/rapidsnark proof verify
make CIRCUIT=rabin_miller clean
```

* Each circuit builds in `build/<circuit>/`; times and peak memory land in `build/<circuit>/metrics.json`.
* **Ceremony file.** `make setup` needs a hash-verified Hermez "powers of tau" file in `ptau/` (power computed from the
  circuit) and reuses it. `python3 scripts/zk.py fetch-ptau 16` downloads and verifies one (the official hosts are dead; see
  `docs/TOOLCHAIN.md`). No verified source was found for 2^17 / 2^18, which Fermat (110,399 constraints) and Pratt
  (198,828) need; `ALLOW_LOCAL_PTAU=1` generates an **insecure single-party** ceremony for development only.
* Other inputs: `python3 scripts/gen_inputs.py rabin_miller 982451653` (also `fermat`, `lehmann`, `multiply`, `pratt`).
  The shipped circuits take 32-bit n, require n ≥ 5 and bases in [2, n−2]; a composite has **no valid witness**.

## Noir: prove N = p·q

```bash
export NARGO=/path/to/nargo
cd noir/semiprime
python3 gen_semiprime.py 11 12 > Prover.toml          # builds p and q with their primality chains
nargo execute
bb write_vk -b target/semiprime.json -o target/out
bb prove    -b target/semiprime.json -w target/semiprime.gz -k target/out/vk -o target/out
bb verify   -k target/out/vk -p target/out/proof -i target/out/public_inputs
```

The only public input is N. See `noir/README.md` for the other circuits and for the evidence behind each one.

## Tests

```bash
make test           # python3 + sympy only (4 s): reference scripts, input generator, ceremony helper, Pratt generator, models
make test-circom    # needs circom + snarkjs + node: library, Fermat/Lehmann/Rabin-Miller, Pratt   (several minutes)
NARGO=/path/to/nargo make test-noir    # Pocklington, N = p·q, ECPP                            (a few minutes)
```

The circuit tests compare against Python references, tamper with witness wires, and are **mutation-checked**: each
soundness-critical constraint is deleted from a copy and an attack that satisfies everything else must then be accepted.

## Limitations (please read)

* **Not audited.** No formal review; the evidence is the test suites above. Per-component evidence and known gaps are in
  `noir/README.md` ("How much to trust each part").
* Circom circuits are limited to 125-bit values by design (one BN254 field element) and instantiated at 32 bits.
  Rabin-Miller / Fermat / Lehmann give probabilistic statements only.
* The Pocklington proof requires the prover to have *generated* the primes with the chain structure.
* ECPP certificates can only be generated up to about 64 bits here (pure-Python point counting); the 256-bit ECPP gate count was not measured.
* Groth16 setups made with `ALLOW_LOCAL_PTAU=1` or with the benchmark scripts are not secure; the `.zkey` files from `make` get a
  fresh random contribution but their security rests on the ceremony file used.
* `experiments/` and `bench/` are measurements and prototypes, not production code.

## Layout

```
circom/        circuits (multiply, fermat, lehmann, rabin_miller, pratt)      lib/      sound Circom library
inputs/        sample inputs                                                  scripts/  reference tests, generators, zk.py
noir/          Noir packages: zkp_primality (library), prime_chain, semiprime, ecpp_chain, step_* test harnesses
experiments/   Noir Rabin-Miller prototypes (32 and 256 bit)                  bench/    benchmark harness and results
tests/         Circom test suites (+ test_scripts.py)                         docs/     toolchain notes
Makefile       build pipeline and test entry points                           main.tex  the report
```

## Contributions and citation

Contributions for optimisation and further testing are welcome. Circom and snarkjs are core components of the Circom
side; Noir, Barretenberg and noir-bignum of the Noir side (see the respective documentation).
