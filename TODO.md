# Unfinished work checklist

Audit date: 2026-11-23, branch `fix/complete-unfinished-work`.
Method: compiled all 6 circuits with circom 2.1.9, generated witnesses from `inputs/*.json`,
read the `isPrime` output wire, ran the Python tests, rebuilt `main.tex`, and checked the report's
worked examples numerically.

Baseline: all circuits compile and produce witnesses. Only `multiply`, `fermat` (n=101) and `lehmann`
(n=101) return a sensible output. `rabin_miller`, `pratt` and `ecpp` return garbage field elements
on their own sample inputs.

## A. Circuits that give wrong answers
- [x] **1. Shared `ModularExponentiation` is unsound.** DONE.
  - New `lib/bits.circom` and `lib/modarith.circom` (`Num2Bits`, `AssertLessThan`, `ModMul`, `ModExp`) replace the 5 copy-pasted versions.
  - Every wire is constrained: `a*b = q*n + r` with `q < 2^k`, `r < n`. Verified by `tests/test_lib.py`, which tampers with random witness wires and requires the R1CS to reject each one.
  - Mutation check: the same tamper test run against the OLD modexp accepted a forged result (it let you "prove" 5^22 mod 23 = 0).
  - **Limit:** a single-field-element design caps values at **125 bits** (`k <= 125`), not 256. Wider moduli need multi-limb bignum arithmetic. The circuits are now instantiated at 32 bits (primes up to 4294967291). Supporting 64 or 125 bits is only a parameter change, but constraint counts grow as about 4k² per exponentiation.
  - **Cost:** circuits are far bigger now (Fermat 6,448 → 108,773 constraints; Lehmann 2,598 → 43,528), which is the price of actually constraining the arithmetic. Makefile `POT_LEVEL`s were raised to fit; item 10 should compute them.
- [x] **2. `isPrime` is never constrained to 1.** DONE.
  - Every circuit now has a top-level wrapper (`FermatVerifier`, `LehmannVerifier`, `RabinMillerVerifier`, `PrattVerifier`, `ECPPMain`) that asserts `isPrime === 1`. A composite input now has no valid witness. Checked on primes and composites (101, 997, 982451653, 4294967291 pass; 100, 1001, 561, 982451654, 4294967295 rejected).
  - The `*PrimalityTest` / `*CertificateVerifier` templates still output `isPrime`, so they stay composable (item 7).
  - **Side effect:** Rabin-Miller, Pratt and ECPP now refuse their own sample inputs (previously they silently output garbage). That is correct and exposes items 4 to 6.
  - Still unconstrained (`<--`) and left for the items that rewrite them: Rabin-Miller `conditionSignals`, `isNMinusOne`; Pratt `nonZeroFactor`, `factorChecks`; ECPP `y2`, `x3PlusAxPlusB`, `nonZeroFactor`.
- [x] **3. Fermat / Lehmann equality checks are not boolean.** DONE.
  - Added `IsZero` / `IsEqual` to `lib/bits.circom` (genuinely 0/1; forging the opposite answer is rejected, see `test_iszero_isequal`).
  - Fermat and Lehmann now use them, and combine per-base results as `acc[i+1] = acc[i] * result[i]` from `acc[0] = 1`.
  - **Also fixed the skipped first base** found during items 1-2: `a[0]` was never tested. `tests/test_primality.py` puts the only witness at position 0, 1, middle and last and requires rejection at each.
  - **Bases must satisfy 2 <= a <= n-2** (`AssertBaseInRange`). Previously a base of 0, 1 or n-1 passed vacuously. Consequence: n = 2 and 3 can't be proven (no valid base exists), and n >= 5 is required. Document this in the README (item 12).
  - Tests (`tests/test_primality.py`, 12 tests, runs the real circuits): differential random testing against a Python reference, known primes/composites up to 4294967291, even and tiny n, vacuous bases, and tampering with named internal wires.
  - Mutation check: against the previous commit's circuits, all 4 regression tests fail, so they have teeth.
  - Constraint counts: Fermat 110,399, Lehmann 44,189.
  - Open point: these tests need a Fermat/Lehmann run per case (~1 s each), so the suite takes about a minute. Item 11 should wire it into one `make test`.
- [x] **4. Rabin-Miller circuit and input are both wrong.** DONE.
  - **Input fixed by design:** `d` and `r` are no longer inputs. The circuit derives them as hints and constrains them (`lib/twoadic.circom`, `CheckTwoAdicDecomposition`): one-hot selector for r, `n-1 = d * 2^r`, `d` odd, so (d, r) is unique and an even n has no witness. `inputs/rabin_miller.json` is now just `n` and the bases (it used to describe n=561 while claiming n=491).
  - **Rewritten without the exp-2 chain:** squarings use `ModMul` directly, with the round mask `[j < r]` as a linear function of the selector. 217,464 -> 64,972 constraints, with 10 bases instead of 5.
  - **Extra bug found:** the old loop started at `j = 1`, so `a^d == n-1` (j = 0, the most common way a prime passes) never counted as a pass. Fixed and covered by `test_x0_equal_n_minus_1_counts`.
  - Removed the `maxRounds` parameter (it is now derived: `nBits - 1`, the largest r any n can have). `main` is `(10 bases, 32 bits)`, so the old comment/code mismatch is gone.
  - **Tests** (`tests/test_primality.py::RabinMillerTests`, 11 tests + 2 decomposition tests in `tests/test_lib.py`): differential vs Python reference, primes with r = 1, 2, 3, 8, 16, 30, Carmichael numbers, strong pseudoprime 3215031751 (passes bases 2,3,5,7 but not 11), vacuous bases, tampering with `d` and the selector, and every *alternative* self-consistent decomposition (even `d`, wrong `r`, two selectors set, ...).
  - **Mutation checks:** (A) ignoring `x_0 == n-1` fails 4 tests; (B) removing the "d is odd" check is caught by `test_decomposition_rejects_alternatives` (`d=2, r=15` accepted). The "tamper d by +-1" test alone would NOT have caught (B): a coherent alternative pair silently downgrades the test to Lehmann.
  - **End to end:** real Groth16 proof for n = 982451653: 64,972 constraints, proving 2.0 s, verified OK, 806-byte proof (run with the existing 2^16 ceremony file; `makefile_rabin_miller` POT_LEVEL set to 17 to be safe).
  - Note for the report (item 13): bases {2,3,5,7,11} are *deterministic* for all n < 2,152,302,898,747, so for the 32-bit circuit those five bases turn Rabin-Miller into a proof of primality, not just evidence.
- [x] **5. Pratt design is mathematically wrong.** DONE.
  - **Rewritten** as `lib/pratt.circom` (`PrattEntry`, `PrattVerifier`); `circom/pratt.circom` is just the 32-bit instance (9 entries, 4 odd factors).
  - Per-prime base `g_i` (a primitive root), exact factorization `p-1 = 2^s * q_0*...*q_{F-1}` (one-hot s, product chain), every non-padding `q` must equal some entry's prime (induction on value: q < p, so no cycle check is needed), `g^((p-1)/2) != 1` with `h^2 = 1`, and `g^((p-1)/q) != 1` for each distinct q (the dedup flag is derived, so a check can't be skipped). `mainPrime === certPrimes[0]`.
  - Padding is the valid entry (3, g=2, no factors), which removes the old `% 0`.
  - Only `mainPrime` is public; the certificate is private witness (right shape for composing with N = p*q in item 7).
  - The old sample certificate was incomplete: 3, 7 and 17 were used as factors but had no entries. Real certificate for 8675309 needs 9 entries.
  - `scripts/pratt_certificate_generator.py` rewritten (library + CLI + Python reference verifier; no longer runs on import or hardcodes the prime). This covers part of items 8/9.
  - **Tests** (`tests/test_pratt.py`, 16 tests): valid certificates for many primes, every composite-with-best-certificate tried against EVERY base (none certifies), 12 targeted forgeries (each first checked to be invalid in Python), 45-case mutation fuzzing (circuit == Python reference on every one), wire tampering, and the real 32-bit circuit.
  - **Mutation checks:** deleting any of 6 soundness constraints is caught (membership, exact factorization, g^((p-1)/q) != 1, mainPrime tie, h != 1, g^(p-1) == 1). One survivor, the partial-product range check: it is only needed when 31 + nBits*F >= 253 (F >= 7 at 32 bits), so it is unreachable at tested sizes. Kept as defense-in-depth (about 165 constraints per entry).
  - **Size:** 198,828 constraints (needs 2^18 ptau; the full-size end-to-end proof is deferred to item 10, which should build one shared ptau). Small instance (16-bit, 7x5, 50,092 constraints) proven end to end: proving 1.7 s, verifies, 805-byte proof, public signals = just the prime, and the proof is rejected against a different prime.
- [ ] **6. ECPP circuit is not ECPP.**
  - No elliptic-curve point arithmetic, no check that `m*P = O`, no check on `q*P` for the large factor q.
  - `isOrderValid = 1 - x^order^2` is inverted (it is 0 when the result is 1).
  - `inputs/ecpp.json` is 5 unrelated curves against one prime (10177), with no recursion down to a small prime.
  - Output is garbage on its own input.
- [ ] **7. `multiply` does not reach the project goal (N = p·q, p and q prime).**
  - There is no primality check on p or q, and no `p, q > 1` range check (so 1·N passes).
  - N is an output but p and q are private: nothing composes with the primality circuits.
  - Inputs are quoted strings.
  - Need a combined circuit.

## B. Missing / empty files
- [ ] **8. `scripts/ecpp.py` and `scripts/pratt.py` are empty (0 bytes).**
  - Need an ECPP certificate generator that emits `inputs/ecpp.json`.
  - Need to fold the standalone generator into `pratt.py`, or delete the stub.
- [ ] **9. Input generation and tests.**
  - Only Pratt has a generator. Fermat / Lehmann / Rabin-Miller / ECPP inputs are hand-written.
  - The Pratt generator has no tests, hardcodes 8675309, and runs on import.
  - The `fermat.py` test class sits above the function it tests.
  - `n <= 0` is mishandled in Fermat and Lehmann.
  - No negative tests: no composite input has ever been run through a circuit.

## C. Build / tooling
- [ ] **10. Makefiles.**
  - Six near-identical copies (they differ only in name and POT level).
  - All share one `build/` dir, so `witness.wtns`, `proof.json` and the zkeys collide between circuits.
  - Powers of tau is regenerated on every run (slow).
  - The entropy string is hardcoded.
  - `clean` leaves ptau files behind.
  - Commit messages say "verification time" was added, but `verify` has no timing.
  - POT levels were set by hand.
- [ ] **11. No dependency or test entry points.** No `requirements.txt` (sympy), no `package.json`, no circomlib decision, no single `make test`, no CI.

## D. Docs and report
- [ ] **12. README.**
  - `\text` was mangled into a tab character (`	ext{mod}`).
  - Usage only covers Pratt and ECPP.
  - Prerequisites are missing (circom 2.1.x, snarkjs, node, sympy).
  - Claims scripts exist for ECPP certificates (empty files).
  - No results table.
- [ ] **13. `main.tex` has wrong worked examples** (verified numerically).
  - Fermat: it claims 3^560 ≡ 1 (mod 561). It is 375, so base 3 rejects 561.
  - Lehmann: it claims 3^170 ≡ 340 (mod 341). It is 67, so 341 is rejected.
  - Pratt: it claims 2^11 ≢ 1 (mod 23). It is 1, so base 2 is invalid for 23 (use 5).
  - ECPP: the n=11 example conflates the curve order with n-1, and the report's "p = 23, 29" tests do not match `ecpp.json` (10177).
  - The report has no results section at all (constraints, proving time, proof size, verification time), though that was the point of the last commits.
- [ ] **14. `zkp_final_report.pdf` is stale.** Rebuild from `main.tex` after item 13, and ignore LaTeX aux files in `.gitignore`.
- [ ] **15. Repo hygiene.** Commits use two git identities. Minor, and optional to fix (`.mailmap`).

## Suggested order
Foundation first, because 3 to 7 all depend on it: **1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12 → 13 → 14**.
