pragma circom 2.0.6;

include "../lib/modarith.circom";
include "../lib/twoadic.circom";

// Rabin-Miller (strong probable prime) test.
//
// n is accepted iff n is odd, and for every base a[i] with 2 <= a[i] <= n-2:
//     writing n-1 = d * 2^r with d odd, r >= 1,
//     a^d == 1 (mod n)           or
//     a^(d*2^j) == n-1 (mod n)   for some 0 <= j < r.
//
// The decomposition (d, r) is computed inside the circuit and fully constrained
// (lib/twoadic.circom): d is odd, so (d, r) is unique and a prover cannot pick a
// different decomposition.  maxR = nBits - 1 is the largest r any nBits-bit n can
// have, so no valid n is lost.
// A pass is probabilistic evidence of primality: at most 1/4 of bases are strong
// liars for a composite n, so k bases leave error <= 4^-k for random bases.
template RabinMillerPrimalityTest(k, nBits) {
    assert(k >= 1 && nBits >= 3);
    var maxR = nBits - 1;

    signal input n;
    signal input a[k];
    signal output isPrime;

    // ---------- decompose n - 1 = d * 2^r  (d odd, 1 <= r <= maxR)
    // d and the one-hot selector of r are computed as witness hints, then fully
    // constrained by CheckTwoAdicDecomposition (see lib/twoadic.circom).
    var r0 = twoAdicValuation(n - 1);
    signal d;
    d <-- (n - 1) >> r0;

    signal sel[maxR + 1];                 // sel[j] = 1 iff r == j
    sel[0] <== 0;
    for (var j = 1; j <= maxR; j++) {
        sel[j] <-- (j == r0) ? 1 : 0;
    }

    component decomp = CheckTwoAdicDecomposition(nBits);
    decomp.n <== n;
    decomp.d <== d;
    decomp.sel <== sel;

    // ---------- per-base test
    component baseRange[k];
    component modExp[k];
    component sq[k][maxR - 1];
    component isNm1[k][maxR];
    component isOne[k];
    component hitZero[k];
    signal x[k][maxR];                    // x[i][j] = a[i]^(d * 2^j) mod n
    signal hitAcc[k][maxR + 1];           // sum over j < r of [x[i][j] == n-1]
    signal hit[k];
    signal passed[k];
    signal acc[k + 1];
    acc[0] <== 1;

    for (var i = 0; i < k; i++) {
        baseRange[i] = AssertBaseInRange(nBits);
        baseRange[i].a <== a[i];
        baseRange[i].n <== n;

        modExp[i] = ModExp(nBits);
        modExp[i].base <== a[i];
        modExp[i].exp <== d;
        modExp[i].mod <== n;
        x[i][0] <== modExp[i].result;

        for (var j = 0; j < maxR - 1; j++) {
            sq[i][j] = ModMul(nBits);
            sq[i][j].a <== x[i][j];
            sq[i][j].b <== x[i][j];
            sq[i][j].n <== n;
            x[i][j + 1] <== sq[i][j].r;
        }

        hitAcc[i][0] <== 0;
        for (var j = 0; j < maxR; j++) {
            isNm1[i][j] = IsEqual();
            isNm1[i][j].in[0] <== x[i][j];
            isNm1[i][j].in[1] <== n - 1;

            // round mask [j < r] = sel[j+1] + ... + sel[maxR]  (linear in sel)
            var mask = 0;
            for (var t = j + 1; t <= maxR; t++) {
                mask += sel[t];
            }
            hitAcc[i][j + 1] <== hitAcc[i][j] + mask * isNm1[i][j].out;
        }

        hitZero[i] = IsZero();
        hitZero[i].in <== hitAcc[i][maxR];
        hit[i] <== 1 - hitZero[i].out;

        isOne[i] = IsEqual();
        isOne[i].in[0] <== x[i][0];
        isOne[i].in[1] <== 1;

        passed[i] <== isOne[i].out + hit[i] - isOne[i].out * hit[i];
        acc[i + 1] <== acc[i] * passed[i];
    }

    isPrime <== acc[k];
}

// Top-level circuit: the proof exists only if every base passes (isPrime == 1).
// Public inputs: n and the bases.  d and r are derived (and constrained) inside.
template RabinMillerVerifier(k, nBits) {
    signal input n;
    signal input a[k];

    component test = RabinMillerPrimalityTest(k, nBits);
    test.n <== n;
    test.a <== a;
    test.isPrime === 1;
}

// 10 bases, 32-bit n (the range supported by this build; the library caps at 125 bits).
component main {public [n, a]} = RabinMillerVerifier(10, 32);
