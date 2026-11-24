# Toolchain notes (verified 2026-11-23)

Versions used for `bench/RESULTS.md`. Nothing here is installed globally: every tool was
unpacked into an isolated directory so the old and new stacks could be run side by side.

| Tool | Version | Source | Check |
|---|---|---|---|
| circom | 2.2.3 (was 2.1.9) | `cargo install --git https://github.com/iden3/circom --tag v2.2.3 --locked circom` (builds with Rust 1.80) | `circom --version` |
| snarkjs | 0.7.6 (was 0.7.4) | `npm install --prefix <dir> snarkjs@0.7.6` | `snarkjs --version` |
| rapidsnark | 0.0.8 | GitHub release `rapidsnark-macOS-arm64-v0.0.8.zip` | sha256 matches the release digest |
| nargo (Noir) | 1.0.0 | GitHub release `noir-aarch64-apple-darwin.tar.gz` | sha256 matches the release digest |
| bb (Barretenberg) | **6.0.0** (paired with nargo 1.0.0) | `aztec-packages` release `v6.0.0`, `barretenberg-arm64-darwin.tar.gz` | sha256 matches the release digest |
| noir-bignum | v0.11.0 | `git` dependency in `Nargo.toml` | - |

Verify a downloaded release asset against GitHub's published digest (works for every asset above):

```bash
check() { repo=$1 tag=$2 asset=$3 file=$4
  want=$(gh release view "$tag" -R "$repo" --json assets --jq ".assets[] | select(.name==\"$asset\") | .digest" | sed 's/sha256://')
  got=$(shasum -a 256 "$file" | awk '{print $1}')
  [ -n "$want" ] && [ "$want" = "$got" ] && echo "MATCH $asset" || echo "MISMATCH $asset" ; }
```

## Things that will bite you

1. **circom 2.2.x defaults to `--O1`, 2.1.x effectively used full simplification.** With the new default,
   Rabin-Miller gets 3,564 extra linear constraints and 3.6k extra wires (68,546 total, no longer fits
   a 2^16 ceremony). Always compile with `--O2`; then the counts match 2.1.9 exactly.
2. **snarkjs prints `[ERROR] ...` but exits with status 0** (e.g. "circuit too big for this power of tau
   ceremony"), leaving a 0-byte output file. Scripts must scan the output or check the file size
   (`bench/bench_groth16.py` does).
3. **The official Perpetual Powers of Tau download hosts are dead.** Both
   `storage.googleapis.com/zkevm/ptau/...` and `hermez.s3-eu-west-1.amazonaws.com/...` answered
   `AccessDenied` on 2026-11-23 (third-party repos report the same since ~Sep 2026). The snarkjs README
   still publishes the BLAKE2b-512 hash of every file, and **a file whose hash matches is the genuine
   54-contributor ceremony output regardless of who served it**:

   ```python
   import hashlib; h = hashlib.blake2b(digest_size=64)   # then h.update(chunks of the file)
   ```

   | file | BLAKE2b-512 (from the snarkjs README) |
   |---|---|
   | `powersOfTau28_hez_final_16.ptau` | `6a6277a2f74e1073601b4f9fed6e1e55226917efb0f0db8a07d98ab01df1ccf43eb0e8c3159432acd4960e2f29fe84a4198501fa54c8dad9e43297453efec125` |
   | `powersOfTau28_hez_final_17.ptau` | `6247a3433948b35fbfae414fa5a9355bfb45f56efa7ab4929e669264a0258976741dfbe3288bfb49828e5df02c2e633df38d2245e30162ae7e3bcca5b8b49345` |
   | `powersOfTau28_hez_final_18.ptau` | `7e6a9c2e5f05179ddfc923f38f917c9e6831d16922a902b0b4758b8e79c2ab8a81bb5f29952e16ee6c5067ed044d7857b5de120a90704c1d3b637fd94b95b13e` |

   The 2^16 file was fetched from the community mirror `eleostechorg/pikd-ptau-mirror` (release `v1`) and its hash
   matched. **No verified source for 2^17 / 2^18 was found**, which blocks a full-size Pratt (198,828
   constraints) or Fermat (110,399) Groth16 setup. Generating your own `powersoftau` ceremony
   (what the makefiles do today) is single-party and takes ~22 min at 2^16, roughly 4x per extra bit.
4. **`noirup` / `bbup` installers append to your shell profile.** Download the release tarballs
   directly instead. `bb` must match `nargo`: the map is
   `AztecProtocol/aztec-packages/.../barretenberg/bbup/bb-versions.json` (`"1.0.0": "6.0.0"`).
   `bb` versions below 0.82.2 had a critical UltraHonk soundness bug.
5. **`bb` fetches its SRS (~12 MB) from a remote server on first use** into `~/.bb-crs`.
6. **Noir 1.0 syntax changes**: no `dep::` prefix in imports, no `u1` type (`to_le_bits` returns `[bool; N]`).
   noir-bignum v0.11: constructor is `RuntimeBigNum::from_array`, not `from_limbs` as its README says.
7. `bb prove` default target is `noir-recursive` (Poseidon2, zero-knowledge). Do not pass `*-no-zk` targets.
