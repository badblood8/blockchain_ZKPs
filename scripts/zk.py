"""Helper for the Makefile: ceremony-file handling, timing and tool checks.

    zk.py pot-level <circuit.r1cs>            power of tau needed by snarkjs for this circuit
    zk.py ptau <power> [--dir ptau]           path of a VERIFIED ceremony file with >= that power
    zk.py fetch-ptau <power> [--dir ptau]     download it from a known mirror and verify it
    zk.py timed <metrics.json> <label> -- cmd ...    run cmd, record wall time and peak memory
    zk.py doctor                              report which tools are installed (and their versions)

Why the ceremony file is verified: the official Perpetual Powers of Tau download hosts stopped answering
(see docs/TOOLCHAIN.md).  The snarkjs README publishes a BLAKE2b-512 hash for every file, and a file whose hash
matches is the genuine multi-party ceremony output no matter where it came from.
"""
import argparse
import hashlib
import json
import math
import os
import re
import resource
import shutil
import subprocess
import sys
import time
import urllib.request

# BLAKE2b-512 of powersOfTau28_hez_final_<power>.ptau, from the snarkjs README.
HEZ_BLAKE2B = {
    15: "982372c867d229c236091f767e703253249a9b432c1710b4f326306bfa2428a17b06240359606cfe4d580b10a5a1f63fbed499527069c18ae17060472969ae6e",
    16: "6a6277a2f74e1073601b4f9fed6e1e55226917efb0f0db8a07d98ab01df1ccf43eb0e8c3159432acd4960e2f29fe84a4198501fa54c8dad9e43297453efec125",
    17: "6247a3433948b35fbfae414fa5a9355bfb45f56efa7ab4929e669264a0258976741dfbe3288bfb49828e5df02c2e633df38d2245e30162ae7e3bcca5b8b49345",
    18: "7e6a9c2e5f05179ddfc923f38f917c9e6831d16922a902b0b4758b8e79c2ab8a81bb5f29952e16ee6c5067ed044d7857b5de120a90704c1d3b637fd94b95b13e",
    19: "bca9d8b04242f175189872c42ceaa21e2951e0f0f272a0cc54fc37193ff6648600eaf1c555c70cdedfaf9fb74927de7aa1d33dc1e2a7f1a50619484989da0887",
    20: "89a66eb5590a1c94e3f1ee0e72acf49b1669e050bb5f93c73b066b564dca4e0c7556a52b323178269d64af325d8fdddb33da3a27c34409b821de82aa2bf1a27b",
    21: "9aef0573cef4ded9c4a75f148709056bf989f80dad96876aadeb6f1c6d062391f07a394a9e756d16f7eb233198d5b69407cca44594c763ab4a5b67ae73254678",
}
# Places that have served the files.  The first two answered 403 on 2026-11-23; the third is a community mirror
# that only carries 2^16.  Whatever is downloaded is checked against HEZ_BLAKE2B, so the host is not trusted.
MIRRORS = [
    "https://storage.googleapis.com/zkevm/ptau/powersOfTau28_hez_final_{power}.ptau",
    "https://hermez.s3-eu-west-1.amazonaws.com/powersOfTau28_hez_final_{power}.ptau",
    "https://github.com/eleostechorg/pikd-ptau-mirror/releases/download/v1/powersOfTau28_hez_final_{power}.ptau",
]
MAX_POWER = 28


def ptau_name(power):
    return f"powersOfTau28_hez_final_{power}.ptau"


def pot_level_from_counts(constraints, public_inputs, outputs):
    """snarkjs: cirPower = floor(log2(constraints + public + outputs)) + 1, i.e. the bit length."""
    return max(1, (constraints + public_inputs + outputs).bit_length())


def pot_level(r1cs_info_text):
    def grab(label):
        m = re.search(rf"# of {label}:\s*(\d+)", r1cs_info_text)
        if not m:
            raise SystemExit(f"could not find '# of {label}' in the r1cs info")
        return int(m.group(1))

    return pot_level_from_counts(grab("Constraints"), grab("Public Inputs"), grab("Outputs"))


def blake2b_file(path):
    h = hashlib.blake2b(digest_size=64)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_ptau(path, power):
    want = HEZ_BLAKE2B.get(power)
    if want is None:
        return False, f"no published hash for power {power} in this repo (known: {sorted(HEZ_BLAKE2B)})"
    got = blake2b_file(path)
    return got == want, ("ok" if got == want else f"BLAKE2b mismatch for {path}")


def find_ptau(power, directory):
    """A verified ceremony file with at least the requested power, or None."""
    for p in range(power, MAX_POWER + 1):
        path = os.path.join(directory, ptau_name(p))
        if os.path.exists(path):
            marker = path + ".verified"
            if os.path.exists(marker) and os.path.getmtime(marker) >= os.path.getmtime(path):
                return path
            ok, why = verify_ptau(path, p)
            if ok:
                open(marker, "w").write("blake2b-512 verified against the snarkjs README\n")
                return path
            print(f"warning: ignoring {path}: {why}", file=sys.stderr)
    return None


def fetch_ptau(power, directory):
    os.makedirs(directory, exist_ok=True)
    if power not in HEZ_BLAKE2B:
        raise SystemExit(f"cannot fetch power {power}: only {sorted(HEZ_BLAKE2B)} have a published hash here")
    dest = os.path.join(directory, ptau_name(power))
    for url in MIRRORS:
        url = url.format(power=power)
        tmp = dest + ".part"
        try:
            print(f"trying {url}", file=sys.stderr)
            with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
                shutil.copyfileobj(r, f)
        except Exception as e:  # noqa: BLE001 - any network failure just means "try the next mirror"
            print(f"  failed: {e}", file=sys.stderr)
            continue
        ok, why = verify_ptau(tmp, power)
        if ok:
            os.replace(tmp, dest)
            open(dest + ".verified", "w").write("blake2b-512 verified against the snarkjs README\n")
            print(f"downloaded and verified {dest}", file=sys.stderr)
            return dest
        os.remove(tmp)
        print(f"  discarded: {why}", file=sys.stderr)
    raise SystemExit(f"no mirror served a verified file for power {power}. Copy a hash-verified "
                     f"{ptau_name(power)} into {directory}/ by hand, or use ALLOW_LOCAL_PTAU=1 for an INSECURE "
                     f"single-party development ceremony.")


def timed(metrics_path, label, cmd):
    """Run cmd, print and record wall time (ms) and peak resident memory (MB) of the child."""
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    t0 = time.perf_counter()
    r = subprocess.run(cmd)
    ms = int((time.perf_counter() - t0) * 1000)
    rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    # ru_maxrss is bytes on macOS and kilobytes on Linux; it is a running maximum over all children of this process
    mb = round(rss / (2 ** 20 if sys.platform == "darwin" else 2 ** 10))
    print(f"{label}: {ms} ms, peak memory {mb} MB")
    data = {}
    if os.path.exists(metrics_path):
        data = json.load(open(metrics_path))
    data[label] = {"ms": ms, "peak_mb": mb}
    json.dump(data, open(metrics_path, "w"), indent=1)
    if r.returncode != 0:
        raise SystemExit(r.returncode)


TOOLS = {
    "circom": (["circom", "--version"], "circom 2.2.x (always pass --O2)"),
    "snarkjs": (["snarkjs", "--version"], "snarkjs 0.7.6"),
    "node": (["node", "--version"], "node"),
    "python3": ([sys.executable, "--version"], "python 3 with sympy"),
    "nargo": (["nargo", "--version"], "nargo 1.0.0 (needed for noir/)"),
    "bb": (["bb", "--version"], "bb 6.0.0, paired with nargo 1.0.0"),
}


def doctor():
    for name, (cmd, want) in TOOLS.items():
        exe = shutil.which(cmd[0]) or (cmd[0] if os.path.isabs(cmd[0]) else None)
        if not exe:
            print(f"  MISSING  {name:8} expected: {want}")
            continue
        out = subprocess.run(cmd, capture_output=True, text=True)
        version = (out.stdout or out.stderr).strip().splitlines()[0] if (out.stdout or out.stderr).strip() else "?"
        print(f"  ok       {name:8} {version}   (expected: {want})")
    try:
        import sympy  # noqa: F401
        print(f"  ok       sympy    {sympy.__version__}")
    except ImportError:
        print("  MISSING  sympy    pip install -r requirements.txt")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pot-level"); p.add_argument("r1cs_info", help="file with the output of `snarkjs r1cs info`")
    p = sub.add_parser("ptau"); p.add_argument("power", type=int); p.add_argument("--dir", default="ptau")
    p = sub.add_parser("fetch-ptau"); p.add_argument("power", type=int); p.add_argument("--dir", default="ptau")
    p = sub.add_parser("timed"); p.add_argument("metrics"); p.add_argument("label"); p.add_argument("command", nargs=argparse.REMAINDER)
    sub.add_parser("doctor")
    a = ap.parse_args()

    if a.cmd == "pot-level":
        print(pot_level(re.sub(r"\x1b\[[0-9;]*m", "", open(a.r1cs_info).read())))
    elif a.cmd == "ptau":
        path = find_ptau(a.power, a.dir)
        if not path:
            raise SystemExit(f"no verified {ptau_name(a.power)} (or larger) in {a.dir}/")
        print(path)
    elif a.cmd == "fetch-ptau":
        print(find_ptau(a.power, a.dir) or fetch_ptau(a.power, a.dir))
    elif a.cmd == "timed":
        cmd = a.command[1:] if a.command and a.command[0] == "--" else a.command
        timed(a.metrics, a.label, cmd)
    elif a.cmd == "doctor":
        doctor()


if __name__ == "__main__":
    main()
