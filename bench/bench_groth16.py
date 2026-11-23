"""Benchmark the Groth16 pipeline stage by stage for one circuit.

Measures wall time and peak memory (macOS `/usr/bin/time -l`) of: compile, witness
generation, setup, prove, verify, plus the size of every artifact.  Output is one
JSON line per run so results can be diffed between toolchains.

Example (old vs new toolchain on the same circuit and ceremony file):
    python3 bench/bench_groth16.py --circuit rabin_miller --ptau build/pot16_final.ptau \
        --label old  --circom circom --snarkjs snarkjs
    python3 bench/bench_groth16.py --circuit rabin_miller --ptau hez16.ptau \
        --label new  --circom /path/to/circom-2.2.3 --snarkjs /path/to/snarkjs
    python3 bench/bench_groth16.py ... --prover rapidsnark --rapidsnark-dir /path/to/rapidsnark

The proof is only generated with a zkey that is NOT contributed to (no phase-2
randomness), so these numbers are for benchmarking, not for production keys.
"""
import argparse
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def timed(cmd, cwd=None, env=None):
    """Run cmd under /usr/bin/time -l.  Returns (seconds, peak_rss_MB, completed_process)."""
    t0 = time.perf_counter()
    r = subprocess.run(["/usr/bin/time", "-l"] + cmd, capture_output=True, text=True, cwd=cwd, env=env)
    dt = time.perf_counter() - t0
    m = re.search(r"(\d+)\s+maximum resident set size", r.stderr)
    rss = int(m.group(1)) / 2**20 if m else float("nan")   # macOS reports bytes
    # snarkjs prints "[ERROR] ..." but still exits 0, so scan the output too.
    out = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout + r.stderr)
    if r.returncode != 0 or "[ERROR]" in out:
        sys.exit(f"command failed: {' '.join(cmd)}\n{out[-1200:]}")
    return dt, rss, r


def size_mb(path):
    return os.path.getsize(path) / 2**20


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--circuit", required=True, help="name of circom/<name>.circom (inputs/<name>.json is used)")
    ap.add_argument("--ptau", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--circom", default="circom")
    ap.add_argument("--circom-flags", default="", help="e.g. --O2")
    ap.add_argument("--snarkjs", default="snarkjs")
    ap.add_argument("--prover", choices=("snarkjs", "rapidsnark"), default="snarkjs")
    ap.add_argument("--rapidsnark-dir", help="directory containing bin/prover and bin/verifier")
    ap.add_argument("--repeat", type=int, default=3, help="proving/verifying repetitions (median reported)")
    ap.add_argument("--workdir", help="reuse/keep this directory (default: temp dir, deleted)")
    ap.add_argument("--reuse", action="store_true", help="skip compile/witness/setup if artifacts exist in --workdir")
    ap.add_argument("--out", help="append the JSON result to this file")
    a = ap.parse_args()

    wd = a.workdir or tempfile.mkdtemp(prefix="zkp_bench_")
    os.makedirs(wd, exist_ok=True)
    name = a.circuit
    src = os.path.join(ROOT, "circom", f"{name}.circom")
    inp = os.path.join(ROOT, "inputs", f"{name}.json")
    r1cs, wasm = f"{wd}/{name}.r1cs", f"{wd}/{name}_js/{name}.wasm"
    wtns, zkey, vk = f"{wd}/witness.wtns", f"{wd}/{name}.zkey", f"{wd}/vk.json"
    proof, pub = f"{wd}/proof.json", f"{wd}/public.json"
    res = {"label": a.label, "circuit": name, "prover": a.prover}

    versions = {}
    versions["circom"] = subprocess.run([a.circom, "--version"], capture_output=True, text=True).stdout.strip()
    versions["snarkjs"] = (subprocess.run([a.snarkjs, "--version"], capture_output=True, text=True).stdout
                           .strip().splitlines() or ["?"])[0]
    res["versions"] = versions

    reuse = a.reuse and os.path.exists(zkey) and os.path.exists(wtns)
    if not reuse:
        dt, rss, r = timed([a.circom, src, "--r1cs", "--wasm", "--sym", "-o", wd] + a.circom_flags.split())
        res["compile_s"] = round(dt, 3)
        out = re.sub(r"\x1b\[[0-9;]*m", "", r.stdout + r.stderr)
        res["constraints"] = int(re.search(r"non-linear constraints:\s*(\d+)", out).group(1))
        res["linear_constraints"] = int(re.search(r"(?<!non-)linear constraints:\s*(\d+)", out).group(1))

        gen = f"{wd}/{name}_js/generate_witness.js"
        dt, rss, _ = timed(["node", gen, wasm, inp, wtns])
        res["witness_s"], res["witness_rss_mb"] = round(dt, 3), round(rss)

        dt, rss, _ = timed([a.snarkjs, "groth16", "setup", r1cs, a.ptau, zkey])
        if not os.path.exists(zkey) or os.path.getsize(zkey) == 0:
            sys.exit("setup produced no zkey")
        res["setup_s"], res["setup_rss_mb"] = round(dt, 2), round(rss)
        subprocess.run([a.snarkjs, "zkey", "export", "verificationkey", zkey, vk], capture_output=True, check=True)
    else:
        res["note"] = "reused compile/witness/setup artifacts"

    # ---- prove (median of repeats; first run is a warm-up and is discarded when repeat > 1)
    if a.prover == "snarkjs":
        prove_cmd = [a.snarkjs, "groth16", "prove", zkey, wtns, proof, pub]
        verify_cmd = [a.snarkjs, "groth16", "verify", vk, pub, proof]
    else:
        rb = os.path.join(a.rapidsnark_dir, "bin")
        prove_cmd = [os.path.join(rb, "prover"), zkey, wtns, proof, pub]
        verify_cmd = [os.path.join(rb, "verifier"), vk, pub, proof]

    def repeat(cmd):
        runs = [timed(cmd)[:2] for _ in range(a.repeat + (1 if a.repeat > 1 else 0))]
        if a.repeat > 1:
            runs = runs[1:]
        return round(statistics.median(t for t, _ in runs), 3), round(max(m for _, m in runs))

    res["prove_s"], res["prove_rss_mb"] = repeat(prove_cmd)
    res["verify_s"], res["verify_rss_mb"] = repeat(verify_cmd)
    # make sure the proof really verifies
    v = subprocess.run(verify_cmd, capture_output=True, text=True)
    res["verified"] = v.returncode == 0 and "Invalid" not in (v.stdout + v.stderr)

    res["size_mb"] = {"r1cs": round(size_mb(r1cs), 2), "wasm": round(size_mb(wasm), 2),
                      "zkey": round(size_mb(zkey), 2), "witness": round(size_mb(wtns), 2)}
    res["size_bytes"] = {"proof": os.path.getsize(proof), "public": os.path.getsize(pub),
                         "verification_key": os.path.getsize(vk)}

    line = json.dumps(res)
    print(line)
    if a.out:
        with open(a.out, "a") as f:
            f.write(line + "\n")
    if not a.workdir:
        shutil.rmtree(wd, ignore_errors=True)


if __name__ == "__main__":
    main()
