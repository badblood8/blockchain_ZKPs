pragma circom 2.0.6;

include "../lib/modarith.circom";

// Fermat primality test: n passes iff, for every base a[i] with 2 <= a[i] <= n-2,
//     a[i]^(n-1) == 1 (mod n).
// isPrime is the product of the k per-base indicator bits, so it is 1 only if
// EVERY base (including a[0]) passes.
// A pass is probabilistic evidence of primality only: Carmichael numbers pass
// for every base coprime to them.
template FermatPrimalityTest(k, nBits) {
    assert(k >= 1);
    signal input n;
    signal input a[k];
    signal output isPrime;

    component baseRange[k];
    component modExp[k];
    component isOne[k];
    signal acc[k + 1];          // acc[i] = AND of the first i per-base results
    acc[0] <== 1;

    for (var i = 0; i < k; i++) {
        baseRange[i] = AssertBaseInRange(nBits);
        baseRange[i].a <== a[i];
        baseRange[i].n <== n;

        modExp[i] = ModExp(nBits);
        modExp[i].base <== a[i];
        modExp[i].exp <== n - 1;
        modExp[i].mod <== n;

        isOne[i] = IsEqual();
        isOne[i].in[0] <== modExp[i].result;
        isOne[i].in[1] <== 1;

        acc[i + 1] <== acc[i] * isOne[i].out;
    }

    isPrime <== acc[k];
}

// Top-level circuit: the proof exists only if every base passes (isPrime == 1).
template FermatVerifier(k, nBits) {
    signal input n;
    signal input a[k];

    component test = FermatPrimalityTest(k, nBits);
    test.n <== n;
    test.a <== a;
    test.isPrime === 1;
}

component main {public [n, a]} = FermatVerifier(25, 32);
